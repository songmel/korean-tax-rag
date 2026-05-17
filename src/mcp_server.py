"""
FastAPI + MCP 서버
MCP tools: search_tax_law, retrieve_article, analyze_exemption, verify_citations
"""
import os
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel

from src.rag import LawChunk, TaxAnswer, answer_with_citations, retrieve_tax_law

load_dotenv()

app = FastAPI(title="Tax RAG MCP Server", version="1.0.0")


# ── 요청/응답 스키마 ───────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str
    top_k: int = 20
    rerank_top_n: int = 5


class ArticleRequest(BaseModel):
    law_name: str
    article_number: str


class ExemptionRequest(BaseModel):
    question: str


class VerifyRequest(BaseModel):
    question: str
    citations: list[str]
    chunk_ids: list[str]


# ── MCP Tool 엔드포인트 ────────────────────────────────────────────────────────

@app.post("/tools/search_tax_law")
async def search_tax_law(req: SearchRequest) -> dict:
    """법령 벡터 검색 + BGE reranking"""
    chunks = retrieve_tax_law(req.query, top_k=req.top_k, rerank_top_n=req.rerank_top_n)
    return {
        "chunks": [c.model_dump() for c in chunks],
        "count": len(chunks),
    }


@app.post("/tools/retrieve_article")
async def retrieve_article(req: ArticleRequest) -> dict:
    """특정 법령 + 조문번호로 직접 조회 (메타데이터 필터링)"""
    query = f"{req.law_name} 제{req.article_number}조"
    chunks = retrieve_tax_law(query, top_k=20, rerank_top_n=10)

    # 해당 조문만 필터
    matched = [
        c for c in chunks
        if c.law_name == req.law_name and c.article_number == req.article_number
    ]
    return {
        "chunks": [c.model_dump() for c in matched],
        "count": len(matched),
    }


@app.post("/tools/analyze_exemption")
async def analyze_exemption(req: ExemptionRequest) -> dict:
    """비과세 요건 전체 분석 (RAG → LLM 추론)"""
    answer: TaxAnswer = answer_with_citations(req.question)
    return answer.model_dump()


@app.post("/tools/verify_citations")
async def verify_citations(req: VerifyRequest) -> dict:
    """인용된 조문이 실제 검색 결과에 존재하는지 검증"""
    chunks = retrieve_tax_law(req.question, top_k=20, rerank_top_n=10)
    retrieved_ids = {c.id for c in chunks}

    verified = []
    unverified = []
    for cid in req.chunk_ids:
        if cid in retrieved_ids:
            verified.append(cid)
        else:
            unverified.append(cid)

    return {
        "verified_chunk_ids": verified,
        "unverified_chunk_ids": unverified,
        "citations": req.citations,
        "warning": (
            f"{len(unverified)}개 chunk_id가 검색 결과에 없습니다. 인용 금지."
            if unverified else ""
        ),
    }


# ── 헬스 체크 ──────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok"}


# ── MCP manifest (Claude Desktop / MCP 클라이언트용) ──────────────────────────

@app.get("/.well-known/mcp.json")
async def mcp_manifest():
    base = os.getenv("MCP_BASE_URL", "http://localhost:8001")
    return {
        "name": "tax-rag",
        "description": "한국 양도소득세 법령 검색 및 비과세 판단 MCP 서버",
        "tools": [
            {
                "name": "search_tax_law",
                "description": "법령 벡터 검색 + BGE reranking",
                "endpoint": f"{base}/tools/search_tax_law",
                "method": "POST",
            },
            {
                "name": "retrieve_article",
                "description": "특정 조문 직접 조회",
                "endpoint": f"{base}/tools/retrieve_article",
                "method": "POST",
            },
            {
                "name": "analyze_exemption",
                "description": "비과세 요건 분석 (RAG + LLM)",
                "endpoint": f"{base}/tools/analyze_exemption",
                "method": "POST",
            },
            {
                "name": "verify_citations",
                "description": "인용 조문 검증",
                "endpoint": f"{base}/tools/verify_citations",
                "method": "POST",
            },
        ],
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("MCP_PORT", "8001"))
    uvicorn.run("src.mcp_server:app", host="0.0.0.0", port=port, reload=True)
