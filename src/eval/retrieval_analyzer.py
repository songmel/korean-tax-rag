"""
검색 품질 분석기 + DANGER_KEYWORD_MAP 자동 개선 제안

오프라인 피드백 루프 (RLVR):
  eval 결과 + gold_chunk_ids → danger_flag별 recall 집계
  → 약한 flag 감지 → 누락 조문에서 키워드 후보 자동 추출
  → DANGER_KEYWORD_MAP 업데이트 제안 생성

Reward 신호:
  - citation_precision : L5 phantom 검사 — human 없이 자동 측정
  - recall@k           : gold_chunk_ids 기반 — 리뷰어 1회 지정 후 자동 반복
  - verdict_match      : expected_verdict 일치 여부
"""
from __future__ import annotations

import json
import re
import time
from collections import defaultdict
from pathlib import Path
from typing import Optional

from src.domain.query_enrichment import DANGER_KEYWORD_MAP, detect_flags_from_text
from src.eval.feedback import compute_retrieval_metrics

REPORT_DIR = Path("data/eval_results")
KEYWORD_PATCH_PATH = Path("data/eval_results/keyword_map_patch.json")

# 누락 조문 텍스트에서 추출할 법령 패턴
_ARTICLE_RE = re.compile(r"제\d+조(?:의\d+)?")
_LAW_RE = re.compile(r"(?:소득세법|조세특례제한법)(?:\s*시행령|\s*시행규칙)?")
_DOMAIN_TERMS = [
    "이월과세", "장기보유특별공제", "1세대1주택", "고가주택", "일시적2주택",
    "상속주택", "상생임대", "분양권", "조합원입주권", "비거주자", "동거봉양",
    "관리처분", "원취득가액", "거주요건", "보유기간", "중과세율", "합가",
    "피상속인", "배우자", "직계존비속", "증여", "수용", "협의취득",
]


# ── 내부 유틸 ──────────────────────────────────────────────────────────────────

def _extract_legal_keywords(text: str) -> list[str]:
    """법령 텍스트에서 조문번호·법령명·도메인 용어를 추출한다."""
    found: list[str] = []
    found += _ARTICLE_RE.findall(text)
    found += _LAW_RE.findall(text)
    found += [t for t in _DOMAIN_TERMS if t in text]
    return list(dict.fromkeys(found))  # 순서 유지 중복 제거


def _fetch_chunk_texts(chunk_ids: list[str]) -> dict[str, str]:
    """Pinecone에서 chunk_id → full_text 맵 반환. 실패 시 빈 dict."""
    if not chunk_ids:
        return {}
    try:
        from src.infra.pinecone_client import get_pinecone_index, PINECONE_NAMESPACE
        index = get_pinecone_index()
        res = index.fetch(ids=chunk_ids, namespace=PINECONE_NAMESPACE)
        vectors = (
            res.get("vectors", {}) if isinstance(res, dict)
            else getattr(res, "vectors", {})
        )
        result = {}
        for cid, vec in vectors.items():
            meta = (
                vec.get("metadata", {}) if isinstance(vec, dict)
                else getattr(vec, "metadata", {})
            )
            result[cid] = (meta or {}).get("full_text", "")
        return result
    except Exception:
        return {}


def _auto_flags(case: dict) -> list[str]:
    """
    golden case에 danger_flags 필드가 없으면 질문 텍스트에서 자동 탐지한다.
    """
    flags = case.get("danger_flags")
    if flags is not None:
        return flags
    question = case.get("question", "") + " " + case.get("description", "")
    return detect_flags_from_text(question)


# ── 분석 함수 ──────────────────────────────────────────────────────────────────

def analyze_flag_recall(
    golden_cases: list[dict],
    eval_results: list[dict],
) -> dict[str, dict]:
    """
    danger_flag별 recall@k, verdict_match, citation_precision을 집계한다.

    Returns:
        {flag: {avg_recall, avg_verdict_match, avg_citation_precision, count, cases}}
    """
    stats: dict[str, dict] = defaultdict(lambda: {
        "recall_sum": 0.0,
        "verdict_sum": 0.0,
        "cit_sum": 0.0,
        "count": 0,
        "cases": [],
    })

    result_by_id = {r["case_id"]: r for r in eval_results}

    for case in golden_cases:
        case_id = case.get("id", "")
        flags = _auto_flags(case)
        result = result_by_id.get(case_id)
        if not result or not flags:
            continue

        recall = result.get("retrieval_metrics", {}).get("recall_at_k") or 0.0
        verdict = float(result.get("verdict_match") or 0)
        cit = result.get("citation_precision", 1.0)

        for flag in flags:
            s = stats[flag]
            s["recall_sum"] += recall
            s["verdict_sum"] += verdict
            s["cit_sum"] += cit
            s["count"] += 1
            s["cases"].append(case_id)

    out: dict[str, dict] = {}
    for flag, s in stats.items():
        n = s["count"]
        out[flag] = {
            "avg_recall": round(s["recall_sum"] / n, 4) if n else 0.0,
            "avg_verdict_match": round(s["verdict_sum"] / n, 4) if n else 0.0,
            "avg_citation_precision": round(s["cit_sum"] / n, 4) if n else 0.0,
            "count": n,
            "cases": s["cases"],
        }
    return out


def discover_missing_keywords(
    golden_cases: list[dict],
    eval_results: list[dict],
    recall_threshold: float = 0.6,
) -> dict[str, list[str]]:
    """
    recall이 낮은 flag의 누락 조문 텍스트에서 키워드 후보를 추출한다.

    gold_chunk_ids가 비어있는 케이스는 건너뛴다.
    Returns:
        {flag: [keyword_candidate, ...]}
    """
    flag_recall = analyze_flag_recall(golden_cases, eval_results)
    result_by_id = {r["case_id"]: r for r in eval_results}

    # recall 낮은 flag에 대해 누락 chunk 수집
    flag_missing: dict[str, set[str]] = defaultdict(set)
    for case in golden_cases:
        case_id = case.get("id", "")
        flags = _auto_flags(case)
        gold_ids = set(case.get("gold_chunk_ids") or [])
        if not gold_ids:
            continue
        result = result_by_id.get(case_id)
        if not result:
            continue

        retrieved = set(result.get("retrieved_chunk_ids") or [])
        missing = gold_ids - retrieved

        for flag in flags:
            if flag_recall.get(flag, {}).get("avg_recall", 1.0) < recall_threshold:
                flag_missing[flag].update(missing)

    if not flag_missing:
        return {}

    # Pinecone에서 누락 chunk 텍스트 fetch
    all_missing = set().union(*flag_missing.values())
    chunk_texts = _fetch_chunk_texts(list(all_missing))

    # flag별 키워드 후보 추출 (현재 map에 없는 것만)
    suggestions: dict[str, list[str]] = {}
    for flag, missing_ids in flag_missing.items():
        kws: list[str] = []
        for cid in missing_ids:
            text = chunk_texts.get(cid, "")
            if text:
                kws.extend(_extract_legal_keywords(text))

        current_kw = DANGER_KEYWORD_MAP.get(flag, "")
        new_kws = [k for k in dict.fromkeys(kws) if k not in current_kw]
        if new_kws:
            suggestions[flag] = new_kws

    return suggestions


def suggest_map_updates(
    golden_cases: list[dict],
    eval_results: list[dict],
    recall_threshold: float = 0.6,
) -> dict[str, dict]:
    """
    DANGER_KEYWORD_MAP 업데이트 제안을 생성한다.

    Returns:
        {flag: {current, suggested_additions, avg_recall, avg_verdict_match, case_count}}
    """
    flag_stats = analyze_flag_recall(golden_cases, eval_results)
    kw_suggestions = discover_missing_keywords(golden_cases, eval_results, recall_threshold)

    updates: dict[str, dict] = {}
    for flag, stats in flag_stats.items():
        # recall 또는 verdict_match가 threshold 미달인 flag만 제안
        if stats["avg_recall"] < recall_threshold or stats["avg_verdict_match"] < recall_threshold:
            updates[flag] = {
                "current_keyword": DANGER_KEYWORD_MAP.get(flag, "(없음)"),
                "suggested_additions": kw_suggestions.get(flag, []),
                "avg_recall": stats["avg_recall"],
                "avg_verdict_match": stats["avg_verdict_match"],
                "avg_citation_precision": stats["avg_citation_precision"],
                "case_count": stats["count"],
                "note": (
                    "gold_chunk_ids 미입력 — 리뷰어가 정답 chunk를 지정하면 키워드 후보 자동 추출"
                    if not kw_suggestions.get(flag)
                    else ""
                ),
            }
    return updates


# ── 자동 적용 ──────────────────────────────────────────────────────────────────

def auto_apply_map_updates(
    golden_cases: list[dict],
    eval_results: list[dict],
    recall_threshold: float = 0.6,
    dry_run: bool = False,
) -> dict[str, str]:
    """
    recall이 낮은 flag의 키워드 보강을 DANGER_KEYWORD_MAP에 자동 적용한다.

    검색(retrieval) 레이어만 변경 — verdict 판단 로직은 건드리지 않음.
    Red Team(eval 루프)이 실수를 잡아주므로 검색 레이어 자동 적용 허용.
    적용 내역은 keyword_map_patch.json에 저장해 감사 추적 가능.

    Args:
        dry_run: True이면 적용하지 않고 변경 예정 내용만 반환

    Returns:
        {flag: new_full_keyword_string} — 실제 적용(또는 예정)된 변경 내역
    """
    from src.domain.query_enrichment import DANGER_KEYWORD_MAP

    updates = suggest_map_updates(golden_cases, eval_results, recall_threshold)
    applied: dict[str, str] = {}

    for flag, info in updates.items():
        additions = info.get("suggested_additions", [])
        if not additions:
            continue
        current = DANGER_KEYWORD_MAP.get(flag, "")
        new_kw = (current + " " + " ".join(additions)).strip() if current else " ".join(additions)

        if not dry_run:
            DANGER_KEYWORD_MAP[flag] = new_kw

        applied[flag] = new_kw

    if not dry_run and applied:
        # 패치 파일에 누적 저장 — 재시작 후 query_enrichment._load_keyword_patch()에서 재적용
        KEYWORD_PATCH_PATH.parent.mkdir(parents=True, exist_ok=True)
        existing: dict[str, str] = {}
        if KEYWORD_PATCH_PATH.exists():
            try:
                existing = json.loads(KEYWORD_PATCH_PATH.read_text(encoding="utf-8"))
            except Exception:
                pass
        existing.update(applied)
        KEYWORD_PATCH_PATH.write_text(
            json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"[auto_apply] {len(applied)}개 flag 키워드 업데이트 → {KEYWORD_PATCH_PATH}")

    return applied


# ── 메인 진입점 ────────────────────────────────────────────────────────────────

def run_analysis(
    golden_cases: list[dict],
    eval_results: list[dict],
    recall_threshold: float = 0.6,
    save_report: bool = True,
) -> dict:
    """
    전체 분석 실행:
      1. danger_flag별 recall / verdict_match / citation_precision 집계
      2. 약한 flag 키워드 보강 제안
      3. 리포트 저장

    golden_cases에 danger_flags 필드가 없으면 질문 텍스트에서 자동 탐지.
    gold_chunk_ids가 없으면 recall 분석은 건너뛰고 verdict/citation만 집계.
    """
    flag_stats = analyze_flag_recall(golden_cases, eval_results)
    updates = suggest_map_updates(golden_cases, eval_results, recall_threshold)

    has_gold = any(case.get("gold_chunk_ids") for case in golden_cases)

    # ── 출력 ──────────────────────────────────────────────────────────────────

    print("\n" + "=" * 60)
    print("  danger_flag별 검색 품질 분석")
    print("=" * 60)

    if not flag_stats:
        print("  (분석 대상 없음 — golden_cases에 danger_flags 또는 질문 텍스트 필요)")
    else:
        if not has_gold:
            print("  ⚠ gold_chunk_ids 미입력 — recall@k는 N/A, verdict/citation만 집계됨")
            print("    리뷰어가 gold_chunk_ids를 채우면 recall + 키워드 발견이 활성화됩니다.\n")

        header = f"  {'flag':<40} {'recall':>7} {'verdict':>8} {'cit_prec':>9} {'n':>4}"
        print(header)
        print("  " + "-" * 72)
        for flag, s in sorted(flag_stats.items(), key=lambda x: x[1]["avg_recall"]):
            recall_str = f"{s['avg_recall']:.2f}" if has_gold else "  N/A"
            warn = " ←" if (
                (has_gold and s["avg_recall"] < recall_threshold)
                or s["avg_verdict_match"] < recall_threshold
            ) else ""
            print(
                f"  {flag:<40} {recall_str:>7} "
                f"{s['avg_verdict_match']:>8.2f} "
                f"{s['avg_citation_precision']:>9.2f} "
                f"{s['count']:>4}{warn}"
            )

    print("\n" + "=" * 60)
    print("  DANGER_KEYWORD_MAP 업데이트 제안")
    print("=" * 60)

    if not updates:
        print("  (threshold 미달 flag 없음 — 모두 양호)")
    else:
        for flag, info in updates.items():
            print(f"\n  [{flag}]  recall={info['avg_recall']}  verdict={info['avg_verdict_match']}")
            print(f"    현재 키워드: {info['current_keyword']}")
            additions = info["suggested_additions"]
            if additions:
                print(f"    추가 후보:   {' | '.join(additions)}")
            elif info.get("note"):
                print(f"    {info['note']}")

    report = {
        "recall_threshold": recall_threshold,
        "has_gold_chunks": has_gold,
        "flag_stats": {
            k: {kk: vv for kk, vv in v.items() if kk != "cases"}
            for k, v in flag_stats.items()
        },
        "keyword_update_suggestions": {
            k: {kk: vv for kk, vv in v.items() if kk != "note"}
            for k, v in updates.items()
        },
    }

    if save_report:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        path = REPORT_DIR / f"retrieval_analysis_{ts}.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n  리포트 저장: {path}")

    return report
