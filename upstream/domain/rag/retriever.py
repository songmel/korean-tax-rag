"""
2단계 법령 검색 전략 인터페이스

Stage 1 (Symbolic Filter): date_bundle + entity_scope + tax_type
  → 전체 청크에서 법적으로 적용 가능한 후보 집합 추출
  → 빠르고 결정론적. 이 단계에서 잘못된 버전 제거.

Stage 2 (Vector Rerank): fact_vector 임베딩 유사도
  → 후보 내에서만 검색 — 전체 인덱스 대상 아님
  → BM25(법령 용어) + embedding 하이브리드 권장

구현체는 infrastructure 레이어에서 주입 (VectorDB 종류에 무관).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Protocol

from .chunk_metadata import LawChunkMetadata
from .query_input import DateBundle, RAGQueryInput


@dataclass
class RetrievedChunk:
    metadata: LawChunkMetadata
    content: str
    score: float

    # Stage 1에서 부칙 청크가 자동 포함된 경우 표시
    included_as_linked_buchik: bool = False


class SymbolicFilter(Protocol):
    """
    Stage 1: 날짜/스코프 기반 후보 집합 추출.

    구현 시 고려사항:
    - applicability.anchors 별로 date_bundle에서 날짜를 꺼내 effective 범위 체크
    - 부칙 청크는 parent_main_chunk_id로 연결된 본칙이 통과하면 자동 포함
    - entity_scope, tax_type으로 1차 필터링
    """
    def filter(
        self,
        query: RAGQueryInput,
        all_chunks: List[LawChunkMetadata],
    ) -> List[LawChunkMetadata]: ...


class VectorRanker(Protocol):
    """
    Stage 2: 후보 내 벡터 유사도 순위.

    구현 시 고려사항:
    - fact_vector.to_text()를 쿼리 텍스트로 사용
    - BM25(법령 용어 정확 매칭) + embedding 하이브리드 권장
    - 본칙과 부칙 청크를 같은 풀에서 함께 순위 부여
    """
    def rank(
        self,
        query: RAGQueryInput,
        candidates: List[LawChunkMetadata],
    ) -> List[RetrievedChunk]: ...


class TaxLawRetriever(ABC):
    """
    조합 진입점. 구현체는 infrastructure/rag/ 에서 주입.

    사용:
        retriever = PineconeRetriever(...)   # 또는 ChromaRetriever 등
        chunks = retriever.retrieve(query)
    """

    @abstractmethod
    def retrieve(self, query: RAGQueryInput) -> List[RetrievedChunk]:
        """Stage 1 → Stage 2 순서로 실행"""
        ...

    def retrieve_with_buchik(self, query: RAGQueryInput) -> List[RetrievedChunk]:
        """
        본칙 검색 후 linked_buchik_ids 자동 추가.
        경과조치/적용례가 있는 개정에서 부칙 누락 방지.
        """
        results = self.retrieve(query)
        if not query.include_buchik:
            return results

        seen_ids = {r.metadata.chunk_id for r in results}
        extra: List[RetrievedChunk] = []

        for chunk in results:
            for buchik_id in chunk.metadata.linked_buchik_ids:
                if buchik_id not in seen_ids:
                    buchik_chunk = self._get_chunk_by_id(buchik_id)
                    if buchik_chunk:
                        extra.append(RetrievedChunk(
                            metadata=buchik_chunk,
                            content=self._get_content(buchik_id),
                            score=chunk.score,  # 본칙 score 상속
                            included_as_linked_buchik=True,
                        ))
                        seen_ids.add(buchik_id)

        return results + extra

    @abstractmethod
    def _get_chunk_by_id(self, chunk_id: str) -> LawChunkMetadata | None: ...

    @abstractmethod
    def _get_content(self, chunk_id: str) -> str: ...


# ── 헬퍼: Symbolic Filter 기본 구현 (in-memory, 테스트용) ──

class DefaultSymbolicFilter:
    """
    프로덕션에서는 DB 인덱스로 대체.
    여기서는 로직 참조용으로만 사용.
    """

    def filter(
        self,
        query: RAGQueryInput,
        all_chunks: List[LawChunkMetadata],
    ) -> List[LawChunkMetadata]:
        results = []
        for chunk in all_chunks:
            if not chunk.matches_entity_scope(query.entity_scope):
                continue
            if not chunk.matches_tax_type(query.tax_type):
                continue
            if not self._check_applicability(chunk, query.date_bundle):
                continue
            results.append(chunk)
        return results

    def _check_applicability(
        self,
        chunk: LawChunkMetadata,
        date_bundle: DateBundle,
    ) -> bool:
        """
        applicability.anchors에 명시된 날짜들 중 하나라도
        effective_from ~ effective_to 범위에 들어오면 통과.

        경과조치(GYEONGGWAJOCHIUI): condition_text는 LLM이 판단하므로
        여기선 범위 체크만. 최종 적용 여부는 LLM 단계에서 재확인.
        """
        applicable_dates = chunk.get_applicable_dates(date_bundle)
        if not applicable_dates:
            # anchor 날짜를 특정할 수 없으면 transfer_date fallback
            fallback = date_bundle.transfer_date
            return chunk.is_effective_at(fallback)

        # 명시된 anchor 날짜 중 하나라도 범위 내면 후보로 포함
        return any(chunk.is_effective_at(d) for d in applicable_dates)
