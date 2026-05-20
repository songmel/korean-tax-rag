"""
RAG 파이프라인 진입점 — L1~L5 통합

사용법:
    result = await run_rag_pipeline(
        query=RAGQueryInput.from_fact_ledger(...),
        retriever=retriever,
        llm_fn=call_llm,
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, List, Optional, Set

from .fact_checker import FactCheckResult, check_facts
from .output_validator import validate_output
from .query_enrichment import build_rag_query
from .query_input import RAGQueryInput
from .retriever import RetrievedChunk, TaxLawRetriever
from .tax_answer import TaxAnswer, Citation


@dataclass
class PipelineResult:
    answer: TaxAnswer
    fact_check: FactCheckResult
    enriched_query: str
    retrieved_chunks: List[RetrievedChunk] = field(default_factory=list)
    blocked_at_l2: bool = False
    debate_record: Optional[dict] = None   # 논쟁이 실행된 경우 결과 요약


async def run_rag_pipeline(
    query: RAGQueryInput,
    retriever: TaxLawRetriever,
    llm_fn: Callable[[str, List[RetrievedChunk], List[str]], Awaitable[TaxAnswer]],
    fact_json: Optional[dict] = None,
    enable_debate: bool = False,
    debate_auto_promote: bool = True,
) -> PipelineResult:
    """
    L1: schema validation — RAGQueryInput 생성 시 이미 처리됨
    L2: fact completeness check
    L3: query enrichment
    L4: RAG + LLM
    L5: output validation
    """

    # ── L2: Fact Completeness ────────────────────────────────────────────
    fact_check = check_facts(query)

    if not fact_check.can_proceed:
        blocked_answer = TaxAnswer(
            answer="판단에 필요한 사실관계가 불충분합니다. 아래 항목을 추가로 확인해 주세요.",
            verdict="needs_verification",
            confidence=0.0,
            missing_facts=fact_check.missing_fact_texts(),
            warnings=[
                f"크리티컬 정보 {len(fact_check.critical_missing)}건 누락으로 추론 중단"
            ],
        )
        return PipelineResult(
            answer=blocked_answer,
            fact_check=fact_check,
            enriched_query="",
            blocked_at_l2=True,
        )

    # ── L3: Query Enrichment ─────────────────────────────────────────────
    enriched_query = build_rag_query(query, fact_check.danger_flags)

    # ── L4: RAG + LLM ────────────────────────────────────────────────────
    chunks = retriever.retrieve_with_buchik(query)
    retrieved_ids: Set[str] = {c.metadata.chunk_id for c in chunks}

    # missing_facts를 LLM 프롬프트에 전달 → "이 정보가 없어서 불확실합니다" 안내
    llm_missing_hints = fact_check.missing_fact_texts()

    raw_answer = await llm_fn(enriched_query, chunks, llm_missing_hints)

    # chunk_ids 동기화 — LLM이 누락시켰을 수 있으므로 검색 결과로 보완
    if not raw_answer.chunk_ids:
        raw_answer = raw_answer.with_update(chunk_ids=list(retrieved_ids))

    # missing_facts 병합
    combined_missing = list(set(raw_answer.missing_facts + llm_missing_hints))
    raw_answer = raw_answer.with_update(missing_facts=combined_missing)

    # ── L5: Output Validation ────────────────────────────────────────────
    validated = validate_output(raw_answer, retrieved_ids, danger_flags=fact_check.danger_flags)

    result = PipelineResult(
        answer=validated,
        fact_check=fact_check,
        enriched_query=enriched_query,
        retrieved_chunks=chunks,
    )

    # ── 선택적 Red-Blue 논쟁 ─────────────────────────────────────────────
    if enable_debate and fact_json:
        try:
            from src.eval.debate import run_red_blue_debate, should_debate
            if should_debate(result):
                debate = await run_red_blue_debate(
                    fact_json=fact_json,
                    pipeline_result=result,
                    auto_promote=debate_auto_promote,
                )
                result.debate_record = {
                    "debate_id": debate.debate_id,
                    "outcome": debate.outcome,
                    "challenge_type": debate.red_challenge.get("challenge_type"),
                    "revised_verdict": debate.blue_defense.get("revised_verdict"),
                    "promoted_to_golden": debate.promoted_to_golden,
                }
                # Red가 이겼으면 파이프라인 최종 verdict 업데이트
                if debate.outcome == "red_won":
                    revised = debate.blue_defense.get("revised_verdict", validated.verdict)
                    result.answer = validated.with_update(
                        verdict=revised,
                        warnings=validated.warnings + [
                            f"[Red Team 수정] {debate.red_challenge.get('challenge_type')}: "
                            f"{debate.blue_defense.get('defense_text', '')[:100]}"
                        ],
                    )
        except Exception as e:
            # 논쟁 실패가 주 파이프라인을 막으면 안 됨
            result.debate_record = {"error": str(e)}

    return result
