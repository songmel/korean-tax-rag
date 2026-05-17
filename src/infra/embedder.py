"""
임베딩 클라이언트 — Upstage Solar (기본) / OpenAI (fallback).
싱글톤 클라이언트로 모듈 수명 동안 재사용.
"""
from __future__ import annotations

import os
from typing import Optional, Tuple

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

UPSTAGE_API_KEY = os.getenv("UPSTAGE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

_embed_client: Optional[OpenAI] = None
_embed_model: Optional[str] = None


def _get_embed_client() -> Tuple[OpenAI, str]:
    """임베딩 클라이언트와 모델명 반환 — Upstage 우선, 없으면 OpenAI."""
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


def embed_query(query: str) -> list[float]:
    """쿼리 텍스트를 임베딩 벡터로 변환 (2000자 제한)."""
    client, model = _get_embed_client()
    resp = client.embeddings.create(model=model, input=[query[:2000]])
    return resp.data[0].embedding
