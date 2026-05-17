"""
RAG 쿼리 입력 스키마 — 업스트림(상위 플랫폼)에서 전달되는 구조화된 사실관계.

STUB: 업스트림 query_input.py 교체 예정.
chunk_metadata.py / retriever.py 가 참조하는 최소 인터페이스만 정의한다.
실제 구조는 업스트림 팀이 확정 후 이 파일을 통째로 교체한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Dict, List, Optional


class EntityScope(str, Enum):
    """양도 대상 객체 분류 — chunk_metadata.entity_scopes 와 매칭."""
    HOUSE = "주택"
    SUBSCRIPTION_RIGHT = "분양권"
    ASSOCIATION_RIGHT = "조합원입주권"
    LAND = "토지"
    COMMERCIAL = "상가"
    OFFICETEL = "오피스텔"


class TaxType(str, Enum):
    """세목 분류 — chunk_metadata.tax_types 와 매칭."""
    TRANSFER = "transfer"          # 양도소득세
    COMPREHENSIVE = "comprehensive" # 종합소득세
    GIFT = "gift"                   # 증여세
    INHERITANCE = "inheritance"     # 상속세


@dataclass
class DateBundle:
    """
    질의에 등장하는 모든 시점을 묶어 전달.
    chunk applicability anchor와 매칭해 시행일/폐지일 범위 체크에 사용.
    """
    transfer_date: Optional[date] = None       # 양도일
    acquisition_date: Optional[date] = None    # 취득일
    contract_date: Optional[date] = None       # 계약일
    balance_payment_date: Optional[date] = None  # 잔금일
    extra: Dict[str, Optional[date]] = field(default_factory=dict)

    def get_anchor(self, key: str) -> Optional[date]:
        """앵커 키로 날짜 조회 — chunk applicability.anchors 와 동일 키 사용."""
        if key == "transfer_date":
            return self.transfer_date
        if key == "acquisition_date":
            return self.acquisition_date
        if key == "contract_date":
            return self.contract_date
        if key == "balance_payment_date":
            return self.balance_payment_date
        return self.extra.get(key)


@dataclass
class FactVector:
    """
    구조화된 사실관계 → 임베딩 검색용 텍스트로 변환 가능한 컨테이너.

    STUB: 업스트림이 확정한 구조로 교체 예정.
    현재는 to_text() 만 retriever_impl 에서 사용.
    """
    raw_query: str = ""
    facts: Dict[str, object] = field(default_factory=dict)

    def to_text(self) -> str:
        """임베딩 인코딩용 평탄화된 쿼리 텍스트."""
        if not self.facts:
            return self.raw_query
        parts = [self.raw_query] if self.raw_query else []
        for k, v in self.facts.items():
            parts.append(f"{k}: {v}")
        return " / ".join(p for p in parts if p)


@dataclass
class RAGQueryInput:
    """
    Retriever 입력 — 업스트림이 fact_checker 통과 후 전달하는 구조화 질의.

    STUB: 업스트림 query_input.py 교체 예정.
    PineconeTaxLawRetriever 가 참조하는 필드만 정의한다.
    """
    entity_scope: EntityScope
    tax_type: TaxType
    date_bundle: DateBundle
    fact_vector: FactVector
    include_buchik: bool = True
