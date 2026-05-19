"""
업스트림 llm_fn 계약 구현 — RetrievedChunk + missing_hints → TaxAnswer.

anthropic SDK 는 sync 이므로 asyncio executor 로 래핑한다.
프롬프트는 src/agents/prompts.py 에 버전 관리 (RAG_SYSTEM_PROMPT 재사용).
"""
from __future__ import annotations

import asyncio
import json
import os
from typing import List, Optional

import anthropic
from dotenv import load_dotenv

from src.agents.prompts import RAG_SYSTEM_PROMPT
from src.domain.retriever import RetrievedChunk
from src.domain.tax_answer import Citation, TaxAnswer

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")


def _build_user_prompt(
    enriched_query: str,
    chunks: List[RetrievedChunk],
    missing_hints: List[str],
    few_shot_block: str = "",
) -> str:
    """검색 결과 + 누락 힌트 → Claude user prompt."""
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        m = chunk.metadata
        marker = " [부칙]" if chunk.included_as_linked_buchik else ""
        context_parts.append(
            f"[{i}]{marker} {m.law_name} 제{m.article_number}조\n"
            f"(chunk_id: {m.chunk_id}, score: {chunk.score:.4f})\n"
            f"{chunk.content}"
        )
    context = "\n\n".join(context_parts)

    hints_text = ""
    if missing_hints:
        hints_text = "\n\n[추가 확인 필요 항목 — 이 정보가 없어 판단에 불확실성이 있습니다]\n"
        hints_text += "\n".join(f"- {h}" for h in missing_hints)

    few_shot_section = f"\n{few_shot_block}\n" if few_shot_block else ""

    return f"""다음 법령 조문을 근거로 판단하십시오.

[검색된 법령 조문]
{context}
{hints_text}{few_shot_section}
[질문]
{enriched_query}

반드시 아래 JSON 형식으로 답변하십시오:
{{
  "answer": "상세 판단 (법령 근거 포함)",
  "verdict": "비과세" | "과세" | "조건부비과세" | "needs_verification",
  "confidence": 0.0 ~ 1.0,
  "citations": [
    {{"chunk_id": "...", "article": "소득세법 시행령 제154조 제1항", "excerpt": "관련 조문 발췌", "law_version": "시행일"}}
  ],
  "missing_facts": ["추가 확인 필요 항목"],
  "warnings": ["주의사항"]
}}"""


async def llm_fn(
    enriched_query: str,
    chunks: List[RetrievedChunk],
    missing_hints: List[str],
    fact_json: Optional[dict] = None,
) -> TaxAnswer:
    """
    업스트림 시그니처 — 검색된 청크와 누락 힌트로 TaxAnswer 생성.
    ANTHROPIC_API_KEY 미설정 시 needs_verification 으로 안전 반환.
    """
    if not ANTHROPIC_API_KEY:
        return TaxAnswer(
            answer="[ANTHROPIC_API_KEY 미설정]",
            verdict="needs_verification",
            confidence=0.0,
            chunk_ids=[c.metadata.chunk_id for c in chunks],
            warnings=["LLM 미설정"],
        )

    # 골든셋 few-shot 주입 (5건 이상 쌓인 경우에만)
    few_shot_block = ""
    if fact_json:
        try:
            from src.eval.golden_injector import build_few_shot_block
            few_shot_block = build_few_shot_block(fact_json)
        except Exception:
            pass

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    user_prompt = _build_user_prompt(enriched_query, chunks, missing_hints, few_shot_block)

    loop = asyncio.get_event_loop()
    message = await loop.run_in_executor(
        None,
        lambda: client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=2048,
            system=RAG_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        ),
    )

    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return TaxAnswer(
            answer=raw,
            verdict="needs_verification",
            confidence=0.3,
            chunk_ids=[c.metadata.chunk_id for c in chunks],
            warnings=["JSON 파싱 실패 — 원문 반환"],
        )

    citations = [
        Citation(
            chunk_id=c.get("chunk_id", ""),
            article=c.get("article", ""),
            excerpt=c.get("excerpt", ""),
            law_version=c.get("law_version", ""),
        )
        for c in data.get("citations", [])
    ]

    return TaxAnswer(
        answer=data.get("answer", ""),
        verdict=data.get("verdict", "needs_verification"),
        confidence=float(data.get("confidence", 0.0)),
        citations=citations,
        chunk_ids=[c.metadata.chunk_id for c in chunks],
        missing_facts=data.get("missing_facts", []),
        warnings=data.get("warnings", []),
    )
