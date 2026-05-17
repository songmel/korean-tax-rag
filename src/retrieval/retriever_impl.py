"""
PineconeTaxLawRetriever — TaxLawRetriever ABC 의 Pinecone 구현.

Pinecone 메타데이터 ↔ LawChunkMetadata 매핑을 담당한다.
현재 미수집 필드(linked_buchik_ids, entity_scopes 등)는 합리적 기본값 사용.
"""
from __future__ import annotations

import os
from datetime import date
from typing import List, Optional

from dotenv import load_dotenv

from src.domain.chunk_metadata import (
    AmendmentType,
    AppendixType,
    ApplicabilityRuleType,
    ApplicabilitySpec,
    LawChunkMetadata,
    LawId,
    LawLevel,
)
from src.domain.query_input import RAGQueryInput
from src.domain.retriever import RetrievedChunk, TaxLawRetriever
from src.infra.embedder import embed_query
from src.infra.pinecone_client import get_pinecone_index, query_pinecone
from src.infra.reranker import rerank

load_dotenv()

PINECONE_NAMESPACE = os.getenv("PINECONE_NAMESPACE", "tax-law")
TOP_K = int(os.getenv("RETRIEVER_TOP_K", "20"))
RERANK_TOP_N = int(os.getenv("RETRIEVER_RERANK_TOP_N", "5"))

# 법령명 → LawId 매핑
_LAW_NAME_TO_ID = {
    "소득세법": LawId.INCOME_TAX_ACT,
    "소득세법 시행령": LawId.INCOME_TAX_DECREE,
    "소득세법 시행규칙": LawId.INCOME_TAX_RULE,
    "조세특례제한법": LawId.SPECIAL_TAX_ACT,
    "조세특례제한법 시행령": LawId.SPECIAL_TAX_DECREE,
    "조세특례제한법 시행규칙": LawId.SPECIAL_TAX_RULE,
}

_LAW_CATEGORY_TO_LEVEL = {
    "법률": LawLevel.ACT,
    "대통령령": LawLevel.ENFORCEMENT_DECREE,
    "부령": LawLevel.ENFORCEMENT_RULE,
    "시행규칙": LawLevel.ENFORCEMENT_RULE,
}


def _int_to_date(val: int) -> date:
    """YYYYMMDD 정수 → date. 형식 오류면 2000-01-01 안전 fallback."""
    s = str(int(val))
    if len(s) != 8:
        return date(2000, 1, 1)
    try:
        return date(int(s[:4]), int(s[4:6]), int(s[6:8]))
    except ValueError:
        return date(2000, 1, 1)


def _pinecone_meta_to_chunk_metadata(match_id: str, meta: dict) -> LawChunkMetadata:
    """Pinecone match.metadata → LawChunkMetadata 로 변환."""
    eff_int = int(float(meta.get("effective_date", 0) or 0))
    exp_int = int(float(meta.get("expiration_date", 99991231) or 99991231))
    law_name = meta.get("law_name", "")
    return LawChunkMetadata(
        chunk_id=match_id,
        law_id=_LAW_NAME_TO_ID.get(law_name, LawId.INCOME_TAX_ACT),
        law_name=law_name,
        law_level=_LAW_CATEGORY_TO_LEVEL.get(meta.get("law_category", ""), LawLevel.ACT),
        article_number=meta.get("article_number", ""),
        paragraph=None,
        item=None,
        lsi_seq=str(meta.get("version_mst", "")),
        promulgation_date=_int_to_date(eff_int) if eff_int else date(2000, 1, 1),
        effective_from=_int_to_date(eff_int) if eff_int else date(2000, 1, 1),
        effective_to=None if exp_int == 99991231 else _int_to_date(exp_int),
        amendment_type=AmendmentType.PARTIAL,
        article_lineage_root=meta.get("article_number", ""),
        appendix_type=AppendixType.MAIN_BODY,
        applicability=ApplicabilitySpec(rule_type=ApplicabilityRuleType.NONE),
        tax_types=["transfer"],
    )


class PineconeTaxLawRetriever(TaxLawRetriever):
    """Pinecone + BGE Reranker 기반 TaxLawRetriever 구현."""

    def __init__(
        self,
        top_k: int = TOP_K,
        rerank_top_n: int = RERANK_TOP_N,
        namespace: str = PINECONE_NAMESPACE,
    ):
        self.top_k = top_k
        self.rerank_top_n = rerank_top_n
        self.namespace = namespace

    def retrieve(self, query: RAGQueryInput) -> List[RetrievedChunk]:
        query_text = query.fact_vector.to_text()
        vector = embed_query(query_text)

        # query.top_k 우선, 없으면 인스턴스 기본값
        top_k = getattr(query, "top_k", None) or self.top_k

        # Stage 1 — Symbolic Filter: 양도일 기준 날짜 범위 (Pinecone 숫자 필터)
        # DateBundle.transfer_date는 required — None 불가
        as_of_int = int(query.date_bundle.transfer_date.strftime("%Y%m%d"))
        pinecone_filter = {
            "$and": [
                {"effective_date": {"$lte": as_of_int}},
                {"expiration_date": {"$gte": as_of_int}},
            ]
        }

        matches = query_pinecone(
            vector=vector,
            top_k=top_k,
            namespace=self.namespace,
            filter_dict=pinecone_filter,
        )

        # 날짜 필터 결과 없으면 필터 없이 재검색 (법령 버전 이력 미수집 상태 대응)
        if not matches:
            matches = query_pinecone(
                vector=vector,
                top_k=top_k,
                namespace=self.namespace,
            )

        if not matches:
            return []

        # Stage 1 보강 — entity_scope 후필터 (Pinecone entity_scopes 메타데이터 기반)
        # EntityScope.value = "주택"/"분양권" 등 — embed.py의 _tag_chunk()와 동일한 값 사용
        scope_val = query.entity_scope.value
        if scope_val:
            filtered = [
                m for m in matches
                if not m.get("metadata", {}).get("entity_scopes")  # 태그 없으면 통과
                or scope_val in m["metadata"]["entity_scopes"]
            ]
            matches = filtered if filtered else matches  # 필터 결과 비면 전체 유지

        # Stage 2 — Vector Rerank
        ranked = rerank(query_text, matches, self.rerank_top_n)

        results: List[RetrievedChunk] = []
        for score, match in ranked:
            meta = match["metadata"]
            chunk_meta = _pinecone_meta_to_chunk_metadata(match["id"], meta)
            results.append(
                RetrievedChunk(
                    metadata=chunk_meta,
                    content=meta.get("full_text", ""),
                    score=float(score),
                )
            )
        return results

    def _get_chunk_by_id(self, chunk_id: str) -> Optional[LawChunkMetadata]:
        index = get_pinecone_index()
        res = index.fetch(ids=[chunk_id], namespace=self.namespace)
        vectors = res.get("vectors", {}) if isinstance(res, dict) else getattr(res, "vectors", {})
        if chunk_id not in vectors:
            return None
        vec = vectors[chunk_id]
        meta = vec.get("metadata", {}) if isinstance(vec, dict) else getattr(vec, "metadata", {})
        return _pinecone_meta_to_chunk_metadata(chunk_id, meta or {})

    def _get_content(self, chunk_id: str) -> str:
        index = get_pinecone_index()
        res = index.fetch(ids=[chunk_id], namespace=self.namespace)
        vectors = res.get("vectors", {}) if isinstance(res, dict) else getattr(res, "vectors", {})
        if chunk_id not in vectors:
            return ""
        vec = vectors[chunk_id]
        meta = vec.get("metadata", {}) if isinstance(vec, dict) else getattr(vec, "metadata", {})
        return (meta or {}).get("full_text", "")
