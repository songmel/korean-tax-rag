"""
하위호환 shim — 기존 src.rag import 경로 유지용.

신규 코드는 src/infra/* + src/core/* + src/domain/* 사용 권장.
- 임베딩: src.infra.embedder.embed_query
- Pinecone: src.infra.pinecone_client.{get_pinecone_index, query_pinecone}
- Reranker: src.infra.reranker.{get_reranker, rerank}
- 도메인 모델: src.domain.tax_answer.TaxAnswer (업스트림 계약)

이 파일은 기존 mcp_server / agents.tools / ui / tests / eval 이
참조하는 LawChunk / TaxAnswer (legacy Pydantic) / retrieve_tax_law /
answer_with_citations 를 유지한다.
"""
from __future__ import annotations

import json
import os
import time as _time
from typing import Optional

import anthropic
from dotenv import load_dotenv
from pydantic import BaseModel

# 인프라 모듈 위임 — 모듈 이름은 patch target 호환 위해 그대로 노출
from src.infra import embedder as _embedder
from src.infra import pinecone_client as _pinecone_client
from src.infra import reranker as _reranker_mod
from src.agents.prompts import RAG_SYSTEM_PROMPT, RAG_USER_TEMPLATE

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
PINECONE_NAMESPACE = os.getenv("PINECONE_NAMESPACE", "tax-law")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-4-7")


# ── 레거시 Pydantic 모델 (tests / mcp_server / ui 호환) ───────────────────────

class LawChunk(BaseModel):
    id: str
    law_name: str
    article_number: str
    article_title: str
    effective_date: str
    expiration_date: str = ""
    full_text: str
    score: float


class TaxAnswer(BaseModel):
    answer: str
    citations: list[str]
    chunk_ids: list[str]
    confidence: float
    missing_facts: list[str]
    warnings: list[str]


# ── 레거시 함수 wrapper — 테스트 patch target 유지 ───────────────────────────
# 테스트가 `src.rag._embed_query`, `src.rag._get_pinecone_index`,
# `src.rag._get_reranker` 를 patch 한다. shim 도 같은 이름을 노출해야 한다.

def _embed_query(query: str) -> list[float]:
    return _embedder.embed_query(query)


def _get_pinecone_index():
    return _pinecone_client.get_pinecone_index()


def _get_reranker():
    return _reranker_mod.get_reranker()


# ── 핵심 함수 ─────────────────────────────────────────────────────────────────

def retrieve_tax_law(
    query: str,
    top_k: int = 20,
    rerank_top_n: int = 5,
    as_of_date: Optional[str] = None,
) -> list[LawChunk]:
    """
    법령 벡터 검색 + BGE reranking → 상위 rerank_top_n 개 반환.
    as_of_date: "YYYYMMDD" 문자열. 지정 시 해당 시점 유효 조문만 검색.
    """
    # 1. 쿼리 임베딩
    query_vec = _embed_query(query)

    # 2. Pinecone 날짜 필터
    pinecone_filter = None
    if as_of_date:
        as_of_int = int(as_of_date)
        pinecone_filter = {
            "$and": [
                {"effective_date": {"$lte": as_of_int}},
                {"expiration_date": {"$gte": as_of_int}},
            ]
        }

    # 3. Pinecone 벡터 검색 (테스트 호환: index.query 를 직접 호출)
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

    # 날짜 필터로 결과가 없으면 버전 이력 미수집 상태 — 필터 없이 재검색
    if not matches and pinecone_filter:
        fallback_kwargs = {k: v for k, v in query_kwargs.items() if k != "filter"}
        result = index.query(**fallback_kwargs)
        matches = result.get("matches", [])

    if not matches:
        return []

    # 4. BGE Reranker (테스트 호환: predict 직접 호출)
    reranker = _get_reranker()
    pairs = [(query, m["metadata"].get("full_text", "")) for m in matches]
    rerank_scores = reranker.predict(pairs)

    ranked = sorted(
        zip(rerank_scores, matches),
        key=lambda x: x[0],
        reverse=True,
    )[:rerank_top_n]

    def _date_str(val) -> str:
        """정수/float → YYYYMMDD 문자열. 0 또는 99991231은 '' (현행) 처리."""
        if val is None or val == "":
            return ""
        v = int(float(val))
        return "" if v == 0 or v == 99991231 else str(v)

    chunks: list[LawChunk] = []
    for score, match in ranked:
        meta = match["metadata"]
        chunks.append(
            LawChunk(
                id=match["id"],
                law_name=meta.get("law_name", ""),
                article_number=meta.get("article_number", ""),
                article_title=meta.get("article_title", ""),
                effective_date=_date_str(meta.get("effective_date")),
                expiration_date=_date_str(meta.get("expiration_date")),
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
    """검색 → reranking → LLM 추론 → TaxAnswer. enable_trace=True 면 trace 기록."""
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

    # ANTHROPIC_API_KEY 없으면 LLM 스킵
    if not ANTHROPIC_API_KEY:
        return TaxAnswer(
            answer="[ANTHROPIC_API_KEY 미설정 — 검색 결과만 반환]\n\n"
            + "\n\n".join(
                f"[{c.law_name} 제{c.article_number}조] {c.full_text[:300]}" for c in chunks
            ),
            citations=[
                f"{c.law_name} 제{c.article_number}조 {c.article_title}".strip()
                for c in chunks
            ],
            chunk_ids=[c.id for c in chunks],
            confidence=0.0,
            missing_facts=[],
            warnings=["LLM 추론 미수행 — ANTHROPIC_API_KEY 필요"],
        )

    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        context_parts.append(
            f"[{i}] {chunk.law_name} 제{chunk.article_number}조 {chunk.article_title}\n"
            f"(chunk_id: {chunk.id}, rerank_score: {chunk.score:.4f})\n"
            f"{chunk.full_text}"
        )
    context = "\n\n".join(context_parts)

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
            from src.eval.feedback import generate_trace_id, log_trace
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


# ── CLI 진입점 (rag.py 단독 실행) ─────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    sys.stdout.reconfigure(encoding="utf-8")
    query = "1세대 1주택 비과세 요건이 무엇인가요?"
    print(f"=== 검색 쿼리: {query} ===\n")

    chunks = retrieve_tax_law(query, top_k=20, rerank_top_n=5)
    print(f"검색 결과 (reranking 후 상위 {len(chunks)}개):")
    for i, c in enumerate(chunks, 1):
        print(f"[{i}] {c.law_name} 제{c.article_number}조 {c.article_title}")
        print(f"     chunk_id: {c.id} | rerank_score: {c.score:.4f}")
        print(f"     {c.full_text[:120]}...")
