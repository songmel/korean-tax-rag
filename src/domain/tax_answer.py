"""
RAG + LLM 최종 출력 모델 — L5 Output Validator의 입력이자 API 응답 형태
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class TaxVerdict(str, Enum):
    EXEMPT = "비과세"              # 소득세법 §89 — 1세대 1주택 등
    REDUCED = "감면"               # 조특법 감면 규정 (8년 자경 등)
    HEAVY_TAX = "중과"             # 다주택자 중과세율 (+20%p/+30%p)
    GENERAL = "일반과세"           # 기본세율 6~45%
    SHORT_TERM = "단기세율"        # 보유 1년 미만 70%, 1~2년 60%
    PARTIALLY_EXEMPT = "고가주택"  # 12억 초과분만 과세
    NEEDS_VERIFICATION = "사실관계부족"  # 필수 사실관계 미확인


@dataclass
class Citation:
    chunk_id: str
    article: str        # 예: "소득세법 시행령 제154조 제1항"
    excerpt: str        # 관련 조문 발췌
    law_version: str    # 적용 법령 버전 (시행일 기준)


@dataclass
class TaxAnswer:
    answer: str                          # LLM 생성 답변
    verdict: str                         # TaxVerdict 값 또는 레거시 문자열
    confidence: float                    # 0.0 ~ 1.0

    citations: List[Citation] = field(default_factory=list)
    chunk_ids: List[str] = field(default_factory=list)  # 검색된 청크 ID 전체
    missing_facts: List[str] = field(default_factory=list)  # 추가 확인 필요 항목
    warnings: List[str] = field(default_factory=list)

    def with_update(self, **kwargs) -> "TaxAnswer":
        """불변 업데이트 헬퍼"""
        import dataclasses
        return dataclasses.replace(self, **kwargs)
