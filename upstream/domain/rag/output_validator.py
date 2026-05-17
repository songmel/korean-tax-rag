"""
L5 — Output Validator

LLM 출력이 나온 후 실행. 두 종류의 오류를 방어:

- 조용한 오류: 이월과세 무시하고 "비과세" → L2가 잡아야 하지만 통과된 경우 최후 방어
- 자신감 있는 오류: 고가주택 확인 없이 "100% 비과세" → 신뢰도 강제 하향

원칙: confidence가 높아도 missing_facts가 있으면 하향.
     인용 chunk가 검색 결과에 없으면(phantom citation) 신뢰도 0.3 이하.
"""

from __future__ import annotations

from typing import Set

from .tax_answer import TaxAnswer

# 신뢰도 상한 — missing_facts 있을 때
CONFIDENCE_CAP_WITH_MISSING = 0.75

# phantom citation 발견 시 신뢰도 강제 상한
CONFIDENCE_CAP_PHANTOM_CITATION = 0.3

# "비과세" verdict인데 고가주택 미확인 시 신뢰도 상한
CONFIDENCE_CAP_UNCHECKED_HIGH_VALUE = 0.6


def validate_output(answer: TaxAnswer, retrieved_chunk_ids: Set[str]) -> TaxAnswer:
    """
    TaxAnswer를 검증하고 필요 시 confidence를 하향 조정.

    Args:
        answer: LLM이 생성한 TaxAnswer
        retrieved_chunk_ids: Stage 1+2 검색에서 실제로 반환된 chunk ID 집합

    Returns:
        warnings 추가 및 confidence 조정된 TaxAnswer
    """
    warnings = list(answer.warnings)
    confidence = answer.confidence

    # ── 1. Phantom Citation 검사 ─────────────────────────────────────────
    # LLM이 인용한 chunk가 실제 검색 결과에 없으면 hallucination 의심
    cited_ids = {c.chunk_id for c in answer.citations}
    phantom = cited_ids - retrieved_chunk_ids
    if phantom:
        warnings.append(
            f"⚠ 인용 {len(phantom)}개 청크가 검색 결과에 없음 — "
            f"환각 인용 가능성: {', '.join(sorted(phantom))}"
        )
        confidence = min(confidence, CONFIDENCE_CAP_PHANTOM_CITATION)

    # ── 2. Missing Facts → 신뢰도 상한 ──────────────────────────────────
    if answer.missing_facts and confidence > CONFIDENCE_CAP_WITH_MISSING:
        warnings.append(
            f"추가 확인 필요 항목 {len(answer.missing_facts)}건 — "
            f"신뢰도 {confidence:.0%} → {CONFIDENCE_CAP_WITH_MISSING:.0%}로 조정"
        )
        confidence = CONFIDENCE_CAP_WITH_MISSING

    # ── 3. 비과세 verdict + 고가주택 미확인 ─────────────────────────────
    # "비과세"라고 했는데 양도가액을 확인하지 않은 경우
    # 12억 초과이면 초과분은 과세 → 완전 비과세가 아님
    is_exemption_verdict = answer.verdict in ("비과세", "조건부비과세")
    high_value_unchecked = any(
        "양도가액" in f or "고가주택" in f
        for f in answer.missing_facts
    )
    if is_exemption_verdict and high_value_unchecked:
        warnings.append(
            "⚠ 양도가액 미확인 — 고가주택(12억 초과) 해당 시 초과분 과세됨. "
            "비과세 판단은 양도가액 확인 후 재검토 필요"
        )
        confidence = min(confidence, CONFIDENCE_CAP_UNCHECKED_HIGH_VALUE)

    # ── 4. 이월과세 경고 통과 여부 ──────────────────────────────────────
    # L2에서 이월과세 크리티컬 항목이 빠졌는데 여기까지 왔다면
    # (can_proceed=True인데 이월과세 관련 missing_facts가 있는 경우)
    iota_missing = any("이월과세" in f or "원취득일" in f or "원취득가액" in f for f in answer.missing_facts)
    if iota_missing and is_exemption_verdict:
        warnings.append(
            "⚠ 이월과세 적용 여부 미확인 — 배우자/직계 증여 후 기간 내 양도 시 "
            "취득가액이 증여자 원가로 바뀌어 세액이 크게 달라질 수 있음"
        )
        confidence = min(confidence, 0.5)

    # ── 5. 최종 반환 ─────────────────────────────────────────────────────
    if confidence != answer.confidence or warnings != answer.warnings:
        return answer.with_update(confidence=confidence, warnings=warnings)
    return answer
