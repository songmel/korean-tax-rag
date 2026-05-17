"""
BGE Cross-Encoder Reranker — 최종 조문 선택 직전 호출.
"""
from __future__ import annotations

import os
from typing import Optional

from dotenv import load_dotenv
from sentence_transformers import CrossEncoder

load_dotenv()

BGE_RERANKER_MODEL = os.getenv("BGE_RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")

_reranker: Optional[CrossEncoder] = None


def get_reranker() -> CrossEncoder:
    """BGE reranker 싱글톤."""
    global _reranker
    if _reranker is None:
        print(f"BGE Reranker 로드 중: {BGE_RERANKER_MODEL}")
        _reranker = CrossEncoder(BGE_RERANKER_MODEL)
        print("Reranker 준비 완료")
    return _reranker


def rerank(
    query: str,
    candidates: list[dict],
    top_n: int = 5,
) -> list[tuple[float, dict]]:
    """
    BGE Cross-Encoder로 (query, candidate.full_text) 점수 계산 후 상위 N개 반환.
    candidates: Pinecone matches (id, metadata) — metadata.full_text 사용.
    """
    if not candidates:
        return []
    reranker = get_reranker()
    pairs = [(query, c["metadata"].get("full_text", "")) for c in candidates]
    scores = reranker.predict(pairs)
    ranked = sorted(
        zip(scores, candidates),
        key=lambda x: x[0],
        reverse=True,
    )[:top_n]
    return list(ranked)
