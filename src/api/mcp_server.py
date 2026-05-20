"""
MCP 서버 — tax-rag
FastMCP 기반: stdio(Claude Desktop) + SSE(HTTP 클라이언트) 양쪽 지원
"""
import os
import json
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from src.rag import TaxAnswer, answer_with_citations, retrieve_tax_law
from src.domain.query_enrichment import enrich_raw_query_text

load_dotenv()

mcp = FastMCP(
    name="tax-rag",
    instructions=(
        "한국 양도소득세 비과세·감면·중과 여부를 판단하는 법령 RAG 서버입니다. "
        "모든 답변은 law.go.kr 법령 조문 검색 결과에만 근거합니다."
    ),
)


# ── Tool 1: 법령 벡터 검색 ────────────────────────────────────────────────────

@mcp.tool()
def search_tax_law(
    query: str,
    top_k: int = 20,
    rerank_top_n: int = 5,
    as_of_date: str = "",
) -> str:
    """
    한국 양도소득세 관련 법령 조문을 벡터 검색 + BGE reranking으로 검색합니다.

    Args:
        query: 검색할 법령 키워드 또는 질문
        top_k: 벡터 검색 후보 수 (기본 20)
        rerank_top_n: BGE reranking 후 반환할 조문 수 (기본 5)
        as_of_date: 기준일자 YYYYMMDD (예: "20220101"). 비워두면 전체 버전 검색.
    """
    enriched_query = enrich_raw_query_text(query)
    chunks = retrieve_tax_law(
        enriched_query, top_k=top_k, rerank_top_n=rerank_top_n,
        as_of_date=as_of_date or None,
    )
    if not chunks:
        return "관련 법령 조문을 찾을 수 없습니다."

    lines = []
    for i, chunk in enumerate(chunks, 1):
        lines.append(
            f"[{i}] {chunk.law_name} 제{chunk.article_number}조 {chunk.article_title}\n"
            f"    chunk_id: {chunk.id} | rerank_score: {chunk.score:.4f}\n"
            f"    {chunk.full_text[:500]}"
        )
    return "\n\n".join(lines)


# ── Tool 2: 특정 조문 직접 조회 ───────────────────────────────────────────────

@mcp.tool()
def retrieve_article(law_name: str, article_number: str) -> str:
    """
    특정 법령의 조문 번호로 직접 조회합니다.

    Args:
        law_name: 법령명 (예: "소득세법", "소득세법 시행령")
        article_number: 조문 번호 (예: "89", "154")
    """
    query = f"{law_name} 제{article_number}조"
    chunks = retrieve_tax_law(query, top_k=20, rerank_top_n=10)

    matched = [
        c for c in chunks
        if c.law_name == law_name and c.article_number == article_number
    ]

    if not matched:
        return f"{law_name} 제{article_number}조를 찾을 수 없습니다."

    lines = []
    for chunk in matched:
        lines.append(
            f"{chunk.law_name} 제{chunk.article_number}조 {chunk.article_title}\n"
            f"chunk_id: {chunk.id}\n\n"
            f"{chunk.full_text}"
        )
    return "\n\n---\n\n".join(lines)


# ── Tool 3: 비과세 요건 분석 (RAG + LLM) ─────────────────────────────────────

@mcp.tool()
def analyze_exemption(question: str, as_of_date: str = "") -> str:
    """
    양도소득세 비과세·감면·중과 여부를 RAG 검색 후 Claude로 분석합니다.
    검색된 법령 조문에만 근거하며, 불확실한 사실관계는 추가 확인 항목으로 표시합니다.

    Args:
        question: 사실관계가 포함된 질문
                  (예: "2019년 취득, 2024년 양도, 보유 5년, 거주 3년, 1세대 1주택")
        as_of_date: 기준일자 YYYYMMDD (예: "20220101"). 취득일 또는 양도일 기준.
    """
    answer: TaxAnswer = answer_with_citations(question, as_of_date=as_of_date or None)

    result = {
        "answer": answer.answer,
        "citations": answer.citations,
        "chunk_ids": answer.chunk_ids,
        "confidence": answer.confidence,
        "missing_facts": answer.missing_facts,
        "warnings": answer.warnings,
    }
    return json.dumps(result, ensure_ascii=False, indent=2)


# ── Tool 4: 인용 조문 검증 ────────────────────────────────────────────────────

@mcp.tool()
def verify_citations(question: str, chunk_ids: list[str]) -> str:
    """
    인용된 chunk_id가 실제 검색 결과에 존재하는지 검증합니다.
    존재하지 않는 chunk_id를 인용하는 것은 허용되지 않습니다.

    Args:
        question: 원래 질문 (재검색에 사용)
        chunk_ids: 검증할 chunk_id 목록
    """
    chunks = retrieve_tax_law(question, top_k=20, rerank_top_n=10)
    retrieved_ids = {c.id for c in chunks}

    verified = [cid for cid in chunk_ids if cid in retrieved_ids]
    unverified = [cid for cid in chunk_ids if cid not in retrieved_ids]

    result = {
        "verified_chunk_ids": verified,
        "unverified_chunk_ids": unverified,
        "warning": (
            f"{len(unverified)}개 chunk_id가 검색 결과에 없습니다. 인용 금지."
            if unverified else "모든 chunk_id 검증 완료"
        ),
    }
    return json.dumps(result, ensure_ascii=False, indent=2)


# ── 실행 ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    # 인자 없으면 stdio (Claude Desktop), --sse 이면 HTTP SSE
    if "--sse" in sys.argv:
        port = int(os.getenv("MCP_PORT", "8001"))
        mcp.run(transport="sse", host="0.0.0.0", port=port)
    else:
        mcp.run(transport="stdio")
