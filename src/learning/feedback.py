"""
피드백 수집 + 검색 품질 지표 기록
trace_id 단위로 JSONL에 append — 온라인 학습 없음, eval 기반 오프라인 개선 전용
"""
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

FEEDBACK_DIR = Path("data/feedback")
FEEDBACK_FILE = FEEDBACK_DIR / "feedback.jsonl"


def _ensure_dir():
    FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)


# ── 추론 추적 로그 ─────────────────────────────────────────────────────────────

def log_trace(
    trace_id: str,
    question: str,
    facts: dict,
    retrieved_chunk_ids: list[str],
    rerank_scores: list[float],
    cited_chunk_ids: list[str],
    answer: str,
    confidence: float,
    missing_facts: list[str],
    warnings: list[str],
    as_of_date: Optional[str],
    prompt_version: str,
    model_version: str,
    latency_ms: int,
) -> None:
    """
    매 추론마다 전체 추적 정보를 기록한다.
    retrieval 품질과 LLM 품질을 독립적으로 측정할 수 있도록 분리해 저장.
    """
    _ensure_dir()
    record = {
        "trace_id": trace_id,
        "timestamp": datetime.utcnow().isoformat(),
        "type": "trace",
        "question": question,
        "facts": facts,
        "as_of_date": as_of_date,
        "retrieved_chunk_ids": retrieved_chunk_ids,
        "rerank_scores": rerank_scores,
        "cited_chunk_ids": cited_chunk_ids,
        "answer": answer,
        "confidence": confidence,
        "missing_facts": missing_facts,
        "warnings": warnings,
        "prompt_version": prompt_version,
        "model_version": model_version,
        "latency_ms": latency_ms,
        # 업데이트 시 채워지는 필드
        "reviewer_verdict": None,   # "correct" | "incorrect" | "partial"
        "reviewer_note": None,
        "gold_chunk_ids": None,     # 리뷰어가 지정한 정답 chunk
    }
    with FEEDBACK_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ── 리뷰어 피드백 기록 ─────────────────────────────────────────────────────────

def log_reviewer_feedback(
    trace_id: str,
    verdict: str,           # "correct" | "incorrect" | "partial"
    note: str = "",
    gold_chunk_ids: Optional[list[str]] = None,
) -> None:
    """
    리뷰어가 사후에 판단을 수정하거나 정답 chunk를 지정하는 경우 사용.
    기존 trace와 동일한 trace_id로 별도 레코드 append — 이후 eval에서 join.
    """
    _ensure_dir()
    assert verdict in ("correct", "incorrect", "partial"), f"invalid verdict: {verdict}"
    record = {
        "trace_id": trace_id,
        "timestamp": datetime.utcnow().isoformat(),
        "type": "reviewer_feedback",
        "verdict": verdict,
        "note": note,
        "gold_chunk_ids": gold_chunk_ids or [],
    }
    with FEEDBACK_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ── 검색 품질 지표 계산 ────────────────────────────────────────────────────────

def compute_retrieval_metrics(
    retrieved_ids: list[str],
    gold_ids: list[str],
    k: int = 5,
) -> dict:
    """
    Recall@k, Precision@k, MRR 계산.
    gold_ids: 해당 케이스에서 반드시 포함되어야 할 chunk_id 목록 (리뷰어 지정).
    """
    if not gold_ids:
        return {"recall_at_k": None, "precision_at_k": None, "mrr": None}

    top_k = retrieved_ids[:k]
    gold_set = set(gold_ids)

    hits = [1 if rid in gold_set else 0 for rid in top_k]
    recall = sum(hits) / len(gold_set)
    precision = sum(hits) / k

    mrr = 0.0
    for rank, rid in enumerate(retrieved_ids, 1):
        if rid in gold_set:
            mrr = 1.0 / rank
            break

    return {"recall_at_k": recall, "precision_at_k": precision, "mrr": mrr}


def compute_citation_precision(cited_ids: list[str], retrieved_ids: list[str]) -> float:
    """인용된 chunk_id 중 실제 검색 결과에 있는 비율 — 허위 인용 탐지"""
    if not cited_ids:
        return 1.0
    retrieved_set = set(retrieved_ids)
    return sum(1 for cid in cited_ids if cid in retrieved_set) / len(cited_ids)


# ── 피드백 통계 ────────────────────────────────────────────────────────────────

def load_feedback() -> list[dict]:
    if not FEEDBACK_FILE.exists():
        return []
    records = []
    with FEEDBACK_FILE.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def feedback_summary() -> dict:
    """빠른 품질 현황 확인용"""
    records = load_feedback()
    traces = [r for r in records if r["type"] == "trace"]
    reviews = [r for r in records if r["type"] == "reviewer_feedback"]

    reviewed = {r["trace_id"]: r for r in reviews}
    verdicts = [v["verdict"] for v in reviewed.values()]

    return {
        "total_traces": len(traces),
        "reviewed": len(reviewed),
        "correct": verdicts.count("correct"),
        "partial": verdicts.count("partial"),
        "incorrect": verdicts.count("incorrect"),
        "avg_confidence": (
            sum(t["confidence"] for t in traces) / len(traces) if traces else None
        ),
    }


def generate_trace_id() -> str:
    return str(uuid.uuid4())[:8]
