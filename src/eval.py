"""
골든 데이터셋 평가 러너
data/golden/qa_pairs.json → 배치 실행 → 지표 출력
변경 사항(청킹·검색·프롬프트·모델) 배포 전 전체 실행 필수.
"""
import json
import time
from pathlib import Path
from typing import Optional

from src.feedback import compute_citation_precision, compute_retrieval_metrics
from src.rag import answer_with_citations, retrieve_tax_law

GOLDEN_PATH = Path("data/golden/qa_pairs.json")
RESULTS_DIR = Path("data/eval_results")


def _load_golden() -> list[dict]:
    if not GOLDEN_PATH.exists():
        raise FileNotFoundError(f"골든 데이터셋 없음: {GOLDEN_PATH}")
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


def run_eval(
    top_k: int = 20,
    rerank_top_n: int = 5,
    save_results: bool = True,
) -> dict:
    """
    골든 데이터셋 전체를 실행하고 지표를 반환한다.
    - retrieval: Recall@k, Precision@k, MRR
    - citation precision: 인용 chunk가 검색 결과에 있는지
    - answer coverage: 예상 verdict와 일치 여부 (키워드 매칭 기반 — 리뷰어 보완 필요)
    """
    cases = _load_golden()
    print(f"골든 케이스 {len(cases)}개 평가 시작")

    results = []
    retrieval_metrics_all = []
    citation_precision_all = []

    for i, case in enumerate(cases, 1):
        question = case["question"]
        gold_chunks = case.get("gold_chunk_ids", [])
        as_of_date = case.get("as_of_date")
        expected_verdict = case.get("expected_verdict")  # "exempt" | "taxable" | "uncertain"

        t0 = time.time()
        chunks = retrieve_tax_law(question, top_k=top_k, rerank_top_n=rerank_top_n, as_of_date=as_of_date)
        answer = answer_with_citations(question, as_of_date=as_of_date)
        latency_ms = int((time.time() - t0) * 1000)

        retrieved_ids = [c.id for c in chunks]
        ret_metrics = compute_retrieval_metrics(retrieved_ids, gold_chunks, k=rerank_top_n)
        cit_prec = compute_citation_precision(answer.chunk_ids, retrieved_ids)

        # 간단한 verdict 일치 확인 (키워드 기반)
        verdict_match = None
        if expected_verdict:
            answer_lower = answer.answer.lower()
            if expected_verdict == "exempt":
                verdict_match = "비과세" in answer.answer
            elif expected_verdict == "taxable":
                verdict_match = any(k in answer.answer for k in ["과세", "납부"])
            elif expected_verdict == "uncertain":
                verdict_match = (
                    len(answer.missing_facts) > 0
                    or answer.confidence < 0.5
                )

        case_result = {
            "case_id": case.get("id", f"case_{i:03d}"),
            "question": question,
            "as_of_date": as_of_date,
            "expected_verdict": expected_verdict,
            "verdict_match": verdict_match,
            "retrieval_metrics": ret_metrics,
            "citation_precision": cit_prec,
            "confidence": answer.confidence,
            "missing_facts_count": len(answer.missing_facts),
            "latency_ms": latency_ms,
        }
        results.append(case_result)
        retrieval_metrics_all.append(ret_metrics)
        citation_precision_all.append(cit_prec)

        status = "✓" if verdict_match else ("✗" if verdict_match is False else "?")
        print(
            f"  [{i:03d}] {status} "
            f"recall@{rerank_top_n}={ret_metrics.get('recall_at_k', 'N/A')!s:.4} "
            f"cit_prec={cit_prec:.2f} "
            f"conf={answer.confidence:.2f} "
            f"({latency_ms}ms)"
        )

    # 집계
    def avg(lst):
        vals = [v for v in lst if v is not None]
        return sum(vals) / len(vals) if vals else None

    summary = {
        "total": len(results),
        "verdict_match_rate": avg([r["verdict_match"] for r in results if r["verdict_match"] is not None]),
        "avg_recall_at_k": avg([r["retrieval_metrics"].get("recall_at_k") for r in results]),
        "avg_mrr": avg([r["retrieval_metrics"].get("mrr") for r in results]),
        "avg_citation_precision": avg(citation_precision_all),
        "avg_confidence": avg([r["confidence"] for r in results]),
        "avg_latency_ms": avg([r["latency_ms"] for r in results]),
    }

    print("\n=== 평가 결과 ===")
    for k, v in summary.items():
        print(f"  {k}: {v}")

    if save_results:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        out_path = RESULTS_DIR / f"eval_{ts}.json"
        out_path.write_text(
            json.dumps({"summary": summary, "cases": results}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\n결과 저장: {out_path}")

    return summary


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    run_eval()
