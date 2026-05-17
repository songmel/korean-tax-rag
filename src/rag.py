"""
RAG 검색 모듈
Pinecone 벡터 검색 + BGE Reranker → Claude 법령 추론
"""
import os
import json
from typing import Optional

import anthropic
from dotenv import load_dotenv
from openai import OpenAI
from pinecone import Pinecone
from pydantic import BaseModel
from sentence_transformers import CrossEncoder

load_dotenv()

from src.agents.prompts import RAG_SYSTEM_PROMPT, RAG_USER_TEMPLATE

# ── 환경변수 ──────────────────────────────────────────────────
UPSTAGE_API_KEY = os.getenv("UPSTAGE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "tax-rag")
PINECONE_NAMESPACE = os.getenv("PINECONE_NAMESPACE", "tax-law")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-4-7")
BGE_RERANKER_MODEL = os.getenv("BGE_RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")

# ── Pydantic 모델 ─────────────────────────────────────────────

class LawChunk(BaseModel):
    id: str
    law_name: str
    article_number: str
    article_title: str
    effective_date: str
    expiration_date: str = ""  # 빈 문자열 = 현행
    full_text: str
    score: float


class TaxAnswer(BaseModel):
    answer: str
    citations: list[str]
    chunk_ids: list[str]
    confidence: float
    missing_facts: list[str]
    warnings: list[str]


# ── 싱글톤 클라이언트 (재사용) ─────────────────────────────────
_embed_client: Optional[OpenAI] = None
_embed_model: Optional[str] = None
_pinecone_index = None
_reranker: Optional[CrossEncoder] = None


def _get_embed_client() -> tuple[OpenAI, str]:
    global _embed_client, _embed_model
    if _embed_client is None:
        if UPSTAGE_API_KEY:
            _embed_client = OpenAI(
                api_key=UPSTAGE_API_KEY,
                base_url="https://api.upstage.ai/v1",
            )
            _embed_model = "solar-embedding-1-large-query"
        elif OPENAI_API_KEY:
            _embed_client = OpenAI(api_key=OPENAI_API_KEY)
            _embed_model = "text-embedding-3-large"
        else:
            raise RuntimeError("UPSTAGE_API_KEY 또는 OPENAI_API_KEY가 필요합니다")
    return _embed_client, _embed_model


def _get_pinecone_index():
    global _pinecone_index
    if _pinecone_index is None:
        if not PINECONE_API_KEY:
            raise RuntimeError("PINECONE_API_KEY가 필요합니다")
        pc = Pinecone(api_key=PINECONE_API_KEY)
        _pinecone_index = pc.Index(PINECONE_INDEX_NAME)
    return _pinecone_index


def _get_reranker() -> CrossEncoder:
    global _reranker
    if _reranker is None:
        print(f"BGE Reranker 로드 중: {BGE_RERANKER_MODEL}")
        _reranker = CrossEncoder(BGE_RERANKER_MODEL)
        print("Reranker 준비 완료")
    return _reranker


# ── 핵심 함수 ─────────────────────────────────────────────────

def _embed_query(query: str) -> list[float]:
    client, model = _get_embed_client()
    resp = client.embeddings.create(model=model, input=[query[:2000]])
    return resp.data[0].embedding


def retrieve_tax_law(
    query: str,
    top_k: int = 20,
    rerank_top_n: int = 5,
    as_of_date: Optional[str] = None,
) -> list[LawChunk]:
    """
    법령 벡터 검색 + BGE reranking → 상위 rerank_top_n개 반환.
    as_of_date: "YYYYMMDD" 형식. 지정 시 해당 시점에 유효한 조문만 검색.
                None이면 현행 + 모든 버전 검색.
    """
    # 1. 쿼리 임베딩
    query_vec = _embed_query(query)

    # 2. Pinecone 날짜 필터 구성
    pinecone_filter = None
    if as_of_date:
        # 시행일 <= as_of_date AND (만료일 없음(현행) OR 만료일 >= as_of_date)
        pinecone_filter = {
            "$and": [
                {"effective_date": {"$lte": as_of_date}},
                {"$or": [
                    {"expiration_date": {"$eq": ""}},
                    {"expiration_date": {"$gte": as_of_date}},
                ]},
            ]
        }

    # 3. Pinecone 벡터 검색
    index = _get_pinecone_index()
    query_kwargs = dict(
        vector=query_vec,
        top_k=top_k,
        namespace=PINECONE_NAMESPACE,
        include_metadata=True,
    )
    if pinecone_filter:
        query_kwargs["filter"] = pinecone_filter
    result = index.query(**query_kwargs)
    matches = result.get("matches", [])
    if not matches:
        return []

    # 3. BGE Reranker
    reranker = _get_reranker()
    pairs = [(query, m["metadata"].get("full_text", "")) for m in matches]
    rerank_scores = reranker.predict(pairs)

    # 점수 기준 정렬 후 상위 N개 선택
    ranked = sorted(
        zip(rerank_scores, matches),
        key=lambda x: x[0],
        reverse=True,
    )[:rerank_top_n]

    chunks = []
    for score, match in ranked:
        meta = match["metadata"]
        chunks.append(
            LawChunk(
                id=match["id"],
                law_name=meta.get("law_name", ""),
                article_number=meta.get("article_number", ""),
                article_title=meta.get("article_title", ""),
                effective_date=meta.get("effective_date", ""),
                expiration_date=meta.get("expiration_date", ""),
                full_text=meta.get("full_text", ""),
                score=float(score),
            )
        )
    return chunks


def answer_with_citations(
    question: str,
    as_of_date: Optional[str] = None,
    facts: Optional[dict] = None,
    enable_trace: bool = True,
) -> TaxAnswer:
    """검색 → reranking → LLM 추론 → TaxAnswer 반환. enable_trace=True 시 feedback.py에 추적 기록."""
    import time as _time
    t0 = _time.time()
    chunks = retrieve_tax_law(question, as_of_date=as_of_date)

    if not chunks:
        return TaxAnswer(
            answer="관련 법령을 찾을 수 없습니다.",
            citations=[],
            chunk_ids=[],
            confidence=0.0,
            missing_facts=[],
            warnings=["검색 결과 없음"],
        )

    # ANTHROPIC_API_KEY 없으면 LLM 스킵, 검색 결과만 반환
    if not ANTHROPIC_API_KEY:
        return TaxAnswer(
            answer="[ANTHROPIC_API_KEY 미설정 — 검색 결과만 반환]\n\n"
            + "\n\n".join(f"[{c.law_name} 제{c.article_number}조] {c.full_text[:300]}" for c in chunks),
            citations=[f"{c.law_name} 제{c.article_number}조 {c.article_title}".strip() for c in chunks],
            chunk_ids=[c.id for c in chunks],
            confidence=0.0,
            missing_facts=[],
            warnings=["LLM 추론 미수행 — ANTHROPIC_API_KEY 필요"],
        )

    # 컨텍스트 조합
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        context_parts.append(
            f"[{i}] {chunk.law_name} 제{chunk.article_number}조 {chunk.article_title}\n"
            f"(chunk_id: {chunk.id}, rerank_score: {chunk.score:.4f})\n"
            f"{chunk.full_text}"
        )
    context = "\n\n".join(context_parts)

    # Claude 호출
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2048,
        system=RAG_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": RAG_USER_TEMPLATE.format(context=context, question=question),
            }
        ],
    )

    raw = message.content[0].text.strip()

    # JSON 파싱 (코드블록 제거)
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = {
            "answer": raw,
            "citations": [f"{c.law_name} 제{c.article_number}조" for c in chunks],
            "chunk_ids": [c.id for c in chunks],
            "confidence": 0.5,
            "missing_facts": [],
            "warnings": ["JSON 파싱 실패 — 원문 반환"],
        }

    tax_answer = TaxAnswer(
        answer=data.get("answer", ""),
        citations=data.get("citations", []),
        chunk_ids=data.get("chunk_ids", []),
        confidence=float(data.get("confidence", 0.0)),
        missing_facts=data.get("missing_facts", []),
        warnings=data.get("warnings", []),
    )

    if enable_trace:
        try:
            from src.feedback import generate_trace_id, log_trace
            latency_ms = int((_time.time() - t0) * 1000)
            log_trace(
                trace_id=generate_trace_id(),
                question=question,
                facts=facts or {},
                retrieved_chunk_ids=[c.id for c in chunks],
                rerank_scores=[c.score for c in chunks],
                cited_chunk_ids=tax_answer.chunk_ids,
                answer=tax_answer.answer,
                confidence=tax_answer.confidence,
                missing_facts=tax_answer.missing_facts,
                warnings=tax_answer.warnings,
                as_of_date=as_of_date,
                prompt_version="v1",
                model_version=CLAUDE_MODEL,
                latency_ms=latency_ms,
            )
        except Exception:
            pass  # 추적 실패가 답변 반환을 막으면 안 됨

    return tax_answer


# ── 테스트 ────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    query = "1세대 1주택 비과세 요건이 무엇인가요?"
    print(f"=== 검색 쿼리: {query} ===\n")

    print("1단계: 벡터 검색 + BGE Reranking...")
    chunks = retrieve_tax_law(query, top_k=20, rerank_top_n=5)

    print(f"\n검색 결과 (reranking 후 상위 {len(chunks)}개):")
    print("-" * 60)
    for i, chunk in enumerate(chunks, 1):
        print(f"[{i}] {chunk.law_name} 제{chunk.article_number}조 {chunk.article_title}")
        print(f"     chunk_id: {chunk.id} | rerank_score: {chunk.score:.4f}")
        print(f"     {chunk.full_text[:120]}...")
        print()

    print("\n2단계: LLM 추론...")
    answer = answer_with_citations(query)

    print("\n=== 최종 답변 ===")
    print(f"[요약 판단]\n{answer.answer}\n")
    print(f"[근거 법령]")
    for c in answer.citations:
        print(f"  - {c}")
    print(f"\n[신뢰도] {answer.confidence:.2f}")
    if answer.missing_facts:
        print(f"\n[추가 확인 필요]")
        for f in answer.missing_facts:
            print(f"  - {f}")
    if answer.warnings:
        print(f"\n[유의사항]")
        for w in answer.warnings:
            print(f"  - {w}")
