"""
RAG + LLM 최종 출력 모델 — L5 Output Validator의 입력이자 API 응답 형태
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Citation:
    chunk_id: str
    article: str        # 예: "소득세법 시행령 제154조 제1항"
    excerpt: str        # 관련 조문 발췌
    law_version: str    # 적용 법령 버전 (시행일 기준)


@dataclass
class TaxAnswer:
    answer: str                          # LLM 생성 답변
    verdict: str                         # "비과세" | "과세" | "조건부비과세" | "needs_verification"
    confidence: float                    # 0.0 ~ 1.0

    citations: List[Citation] = field(default_factory=list)
    chunk_ids: List[str] = field(default_factory=list)  # 검색된 청크 ID 전체
    missing_facts: List[str] = field(default_factory=list)  # 추가 확인 필요 항목
    warnings: List[str] = field(default_factory=list)

    def with_update(self, **kwargs) -> "TaxAnswer":
        """불변 업데이트 헬퍼"""
        import dataclasses
        return dataclasses.replace(self, **kwargs)
