"""
Red Team / Blue Team 논쟁 엔진.

흐름:
  Blue 판단 → Red 반박 → Blue 방어(추가 검색) → 결과 저장
  결과는 data/debates/ JSONL에 누적되고
  blue_wins → golden set, red_wins → 오류 패턴으로 분류된다.

트리거 조건 (pipeline.py에서 호출):
  - confidence < 0.80
  - danger_flags >= 2개
  - verdict == "사실관계부족"
  또는 batch 모드 (모든 케이스 재검토)
"""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import anthropic
from dotenv import load_dotenv

from src.agents.prompts import (
    BLUE_DEFENSE_SYSTEM,
    BLUE_DEFENSE_TEMPLATE,
    RED_TEAM_CHALLENGE_TEMPLATE,
    RED_TEAM_SYSTEM,
)
from src.domain.pipeline import PipelineResult
from src.domain.tax_answer import TaxAnswer

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

DEBATE_DIR = Path("data/debates")
RED_WINS_DIR = Path("data/red_wins")
BLUE_WINS_DIR = Path("data/blue_wins")
GOLDEN_FILE = Path("data/golden/qa_pairs.json")


# ── 데이터 구조 ───────────────────────────────────────────────────────────────

@dataclass
class RedChallenge:
    has_challenge: bool
    challenge_type: str          # "유령인용" | "요건오판" | ... | "이의없음"
    challenge_text: str
    challenged_citations: List[str] = field(default_factory=list)
    missing_articles: List[str] = field(default_factory=list)
    red_confidence: float = 0.0


@dataclass
class BlueDefense:
    defense_result: str          # "defended" | "conceded" | "partial"
    revised_verdict: str
    defense_text: str
    new_citations: List[str] = field(default_factory=list)
    blue_confidence: float = 0.0


@dataclass
class DebateRecord:
    debate_id: str
    trace_id: str
    timestamp: str
    fact_json: dict
    blue_answer: dict            # 원본 Blue 판단
    red_challenge: dict          # Red 반박
    blue_defense: dict           # Blue 방어
    outcome: str                 # "blue_won" | "red_won" | "no_contest" | "draw"
    new_chunks_found: List[str] = field(default_factory=list)
    promoted_to_golden: bool = False


# ── LLM 호출 헬퍼 ─────────────────────────────────────────────────────────────

def _call_claude_sync(system: str, user: str, max_tokens: int = 1024) -> dict:
    """동기 Claude 호출 → JSON 파싱. 파싱 실패 시 raw 반환."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    raw = msg.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"_parse_error": raw}


# ── Red Team: 반박 ────────────────────────────────────────────────────────────

async def _red_challenge(
    fact_json: dict,
    blue_answer: TaxAnswer,
    retrieved_chunk_ids: List[str],
) -> RedChallenge:
    """Red Team이 Blue 판단을 검토하고 오류를 반박한다."""

    citations_str = "\n".join(
        f"- {c.article}" if hasattr(c, "article") else f"- {c}"
        for c in blue_answer.citations
    ) or "(없음)"

    fact_summary = json.dumps(fact_json, ensure_ascii=False, indent=2)

    prompt = RED_TEAM_CHALLENGE_TEMPLATE.format(
        fact_summary=fact_summary,
        verdict=blue_answer.verdict,
        answer=blue_answer.answer[:800],
        citations=citations_str,
        confidence=blue_answer.confidence,
        chunk_ids=", ".join(retrieved_chunk_ids[:10]),
    )

    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(
        None, lambda: _call_claude_sync(RED_TEAM_SYSTEM, prompt)
    )

    if "_parse_error" in data:
        return RedChallenge(
            has_challenge=False,
            challenge_type="이의없음",
            challenge_text=data["_parse_error"],
        )

    return RedChallenge(
        has_challenge=data.get("has_challenge", False),
        challenge_type=data.get("challenge_type", "이의없음"),
        challenge_text=data.get("challenge_text", ""),
        challenged_citations=data.get("challenged_citations", []),
        missing_articles=data.get("missing_articles", []),
        red_confidence=float(data.get("red_confidence", 0.0)),
    )


# ── Blue Team: 방어 (추가 검색 포함) ─────────────────────────────────────────

async def _blue_defend(
    blue_answer: TaxAnswer,
    red_challenge: RedChallenge,
    fact_json: dict,
) -> tuple[BlueDefense, List[str]]:
    """
    Blue Team이 Red 반박에 응답한다.
    missing_articles를 재검색해 추가 컨텍스트를 확보한 뒤 방어한다.
    반환: (BlueDefense, 새로 찾은 chunk_id 목록)
    """
    additional_context = ""
    new_chunk_ids: List[str] = []

    # 누락 조문 추가 검색
    if red_challenge.missing_articles:
        try:
            from src.rag import retrieve_tax_law
            for article_hint in red_challenge.missing_articles[:3]:
                chunks = retrieve_tax_law(article_hint, top_k=10, rerank_top_n=3)
                for c in chunks:
                    additional_context += (
                        f"\n[추가] {c.law_name} 제{c.article_number}조 {c.article_title}\n"
                        f"{c.full_text[:400]}\n"
                    )
                    new_chunk_ids.append(c.id)
        except Exception:
            additional_context = "(추가 검색 실패)"

    if not additional_context:
        additional_context = "(추가 검색 결과 없음)"

    prompt = BLUE_DEFENSE_TEMPLATE.format(
        verdict=blue_answer.verdict,
        answer=blue_answer.answer[:600],
        challenge_text=red_challenge.challenge_text,
        additional_context=additional_context[:1500],
    )

    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(
        None, lambda: _call_claude_sync(BLUE_DEFENSE_SYSTEM, prompt, max_tokens=1500)
    )

    if "_parse_error" in data:
        defense = BlueDefense(
            defense_result="defended",
            revised_verdict=blue_answer.verdict,
            defense_text=data["_parse_error"],
        )
    else:
        defense = BlueDefense(
            defense_result=data.get("defense_result", "defended"),
            revised_verdict=data.get("revised_verdict", blue_answer.verdict),
            defense_text=data.get("defense_text", ""),
            new_citations=data.get("new_citations", []),
            blue_confidence=float(data.get("blue_confidence", 0.0)),
        )

    return defense, new_chunk_ids


# ── 결과 판정 ─────────────────────────────────────────────────────────────────

def _judge_outcome(red: RedChallenge, blue: BlueDefense) -> str:
    """논쟁 결과 판정."""
    if not red.has_challenge:
        return "no_contest"          # Red가 이의 없음
    if blue.defense_result == "conceded":
        return "red_won"             # Blue가 오류 인정
    if blue.defense_result == "defended" and blue.blue_confidence >= 0.75:
        return "blue_won"            # Blue가 방어 성공
    return "draw"                    # 판정 불가


# ── 저장 ──────────────────────────────────────────────────────────────────────

def _ensure_dirs():
    for d in (DEBATE_DIR, RED_WINS_DIR, BLUE_WINS_DIR, GOLDEN_FILE.parent):
        d.mkdir(parents=True, exist_ok=True)


def _save_debate(record: DebateRecord) -> None:
    _ensure_dirs()
    path = DEBATE_DIR / f"{record.debate_id}.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump({
            "debate_id": record.debate_id,
            "trace_id": record.trace_id,
            "timestamp": record.timestamp,
            "outcome": record.outcome,
            "fact_json": record.fact_json,
            "blue_answer": record.blue_answer,
            "red_challenge": record.red_challenge,
            "blue_defense": record.blue_defense,
            "new_chunks_found": record.new_chunks_found,
            "promoted_to_golden": record.promoted_to_golden,
        }, f, ensure_ascii=False, indent=2)


def _save_to_outcome_dir(record: DebateRecord) -> None:
    """결과에 따라 red_wins / blue_wins 에 심링크 대신 복사 저장."""
    _ensure_dirs()
    if record.outcome == "red_won":
        target_dir = RED_WINS_DIR
    elif record.outcome in ("blue_won", "no_contest"):
        target_dir = BLUE_WINS_DIR
    else:
        return  # draw는 별도 분류 보류

    path = target_dir / f"{record.debate_id}.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump({
            "debate_id": record.debate_id,
            "outcome": record.outcome,
            "fact_json": record.fact_json,
            "final_verdict": record.blue_defense.get("revised_verdict", ""),
            "defense_text": record.blue_defense.get("defense_text", ""),
            "challenge_type": record.red_challenge.get("challenge_type", ""),
        }, f, ensure_ascii=False, indent=2)


def _promote_to_golden(record: DebateRecord) -> None:
    """
    blue_won / no_contest 케이스를 골든셋에 추가.
    data/golden/qa_pairs.json 에 append.
    """
    _ensure_dirs()
    existing: list = []
    if GOLDEN_FILE.exists():
        with GOLDEN_FILE.open(encoding="utf-8") as f:
            try:
                existing = json.load(f)
            except json.JSONDecodeError:
                existing = []

    defense = record.blue_defense
    entry = {
        "id": record.debate_id,
        "source": "debate",
        "fact_json": record.fact_json,
        "verdict": defense.get("revised_verdict", ""),
        "answer": defense.get("defense_text", record.blue_answer.get("answer", "")),
        "citations": defense.get("new_citations", []) or record.blue_answer.get("citations", []),
        "timestamp": record.timestamp,
    }
    existing.append(entry)

    with GOLDEN_FILE.open("w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)


# ── 메인 진입점 ───────────────────────────────────────────────────────────────

async def run_red_blue_debate(
    fact_json: dict,
    pipeline_result: PipelineResult,
    trace_id: str = "",
    auto_promote: bool = True,
) -> DebateRecord:
    """
    Red-Blue 논쟁 1회 실행.

    auto_promote=True 이면 blue_won/no_contest 케이스를 골든셋에 자동 추가.
    세무사 검토 없이 자동화하려면 True, 검토 후 수동 승격은 False.
    """
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY 미설정 — 논쟁 실행 불가")

    debate_id = str(uuid.uuid4())[:8]
    timestamp = datetime.utcnow().isoformat()
    trace_id = trace_id or debate_id

    blue_answer = pipeline_result.answer
    retrieved_ids = [c.metadata.chunk_id for c in pipeline_result.retrieved_chunks]

    # ── Round 1: Red 반박 ─────────────────────────────────────────────────
    red = await _red_challenge(fact_json, blue_answer, retrieved_ids)

    # ── Round 2: Blue 방어 ────────────────────────────────────────────────
    blue_defense, new_chunks = await _blue_defend(blue_answer, red, fact_json)

    # ── 판정 ──────────────────────────────────────────────────────────────
    outcome = _judge_outcome(red, blue_defense)

    record = DebateRecord(
        debate_id=debate_id,
        trace_id=trace_id,
        timestamp=timestamp,
        fact_json=fact_json,
        blue_answer={
            "verdict": blue_answer.verdict,
            "answer": blue_answer.answer,
            "confidence": blue_answer.confidence,
            "citations": [
                c.article if hasattr(c, "article") else str(c)
                for c in blue_answer.citations
            ],
            "chunk_ids": blue_answer.chunk_ids,
            "missing_facts": blue_answer.missing_facts,
            "warnings": blue_answer.warnings,
        },
        red_challenge={
            "has_challenge": red.has_challenge,
            "challenge_type": red.challenge_type,
            "challenge_text": red.challenge_text,
            "challenged_citations": red.challenged_citations,
            "missing_articles": red.missing_articles,
            "red_confidence": red.red_confidence,
        },
        blue_defense={
            "defense_result": blue_defense.defense_result,
            "revised_verdict": blue_defense.revised_verdict,
            "defense_text": blue_defense.defense_text,
            "new_citations": blue_defense.new_citations,
            "blue_confidence": blue_defense.blue_confidence,
        },
        outcome=outcome,
        new_chunks_found=new_chunks,
    )

    # ── 저장 ──────────────────────────────────────────────────────────────
    _save_debate(record)
    _save_to_outcome_dir(record)

    if auto_promote and outcome in ("blue_won", "no_contest"):
        _promote_to_golden(record)
        record.promoted_to_golden = True

    return record


# ── 트리거 조건 판단 ──────────────────────────────────────────────────────────

def should_debate(pipeline_result: PipelineResult) -> bool:
    """
    파이프라인 결과를 보고 논쟁을 시작할지 결정한다.
    비용 절감을 위해 의심스러운 케이스만 대상으로 한다.
    """
    ans = pipeline_result.answer
    fc = pipeline_result.fact_check

    if pipeline_result.blocked_at_l2:
        return False  # 사실관계 부족 — 논쟁 의미 없음

    return (
        ans.confidence < 0.80
        or len(fc.danger_flags) >= 2
        or ans.verdict in ("사실관계부족", "needs_verification")
        or len(ans.warnings) >= 2
    )


# ── 통계 ─────────────────────────────────────────────────────────────────────

def debate_summary() -> dict:
    """누적 논쟁 통계."""
    _ensure_dirs()
    debates = list(DEBATE_DIR.glob("*.json"))
    outcomes = {"blue_won": 0, "red_won": 0, "no_contest": 0, "draw": 0}
    error_types: dict[str, int] = {}

    for path in debates:
        with path.open(encoding="utf-8") as f:
            d = json.load(f)
        outcomes[d.get("outcome", "draw")] = outcomes.get(d.get("outcome", "draw"), 0) + 1
        ct = d.get("red_challenge", {}).get("challenge_type", "")
        if ct and ct != "이의없음":
            error_types[ct] = error_types.get(ct, 0) + 1

    return {
        "total_debates": len(debates),
        "outcomes": outcomes,
        "top_error_types": sorted(error_types.items(), key=lambda x: -x[1])[:5],
        "golden_set_size": len(json.load(GOLDEN_FILE.open(encoding="utf-8")))
        if GOLDEN_FILE.exists() else 0,
    }
