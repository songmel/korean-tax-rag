"""
Streamlit 채팅 UI
입력 수집 + 결과 표시만 담당. 법령 판단 로직 없음.
"""
import asyncio
import json
import random
import sys
import os

# streamlit run src/ui.py 실행 시 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

from src.api.sample_cases import CATEGORY_LABELS, SAMPLE_CASES

# ── 사실관계 한국어 표시 ───────────────────────────────────────────────────────

_FIELD_LABELS = {
    "transfer_date": "양도일",
    "acquisition_date": "취득일",
    "property_type": "부동산 종류",
    "acquisition_reason": "취득 원인",
    "household_house_count": "보유 주택 수",
    "transfer_price": "양도가액",
    "acquisition_price": "취득가액",
    "residence_years": "거주기간(년)",
    "holding_years": "보유기간(년)",
    "is_adjustment_area_at_transfer": "양도시 조정대상지역",
    "is_adjustment_area_at_acquisition": "취득시 조정대상지역",
    "is_gift_from_spouse_or_lineal": "배우자/직계존비속 증여",
    "special_cases": "특례 사항",
}


def _fmt_value(v) -> str:
    if isinstance(v, bool):
        return "예" if v else "아니오"
    if isinstance(v, int):
        return f"{v:,}"
    if isinstance(v, float):
        formatted = f"{v:,.3f}".rstrip("0").rstrip(".")
        return formatted
    if isinstance(v, str) and len(v) == 8 and v.isdigit():
        return f"{v[:4]}-{v[4:6]}-{v[6:]}"
    if isinstance(v, dict):
        return ", ".join(f"{k}: {_fmt_value(vv)}" for k, vv in v.items())
    return str(v)


def _render_fact_korean(fact: dict) -> None:
    for k, v in fact.items():
        label = _FIELD_LABELS.get(k, k)
        col1, col2 = st.columns([4, 5])
        col1.caption(label)
        col2.caption(f"**{_fmt_value(v)}**")

st.set_page_config(page_title="양도소득세 RAG", page_icon="⚖️", layout="wide")

# ── 세션 상태 초기화 ──────────────────────────────────────────────────────────

if "fact_json_str" not in st.session_state:
    st.session_state.fact_json_str = ""
if "current_case_label" not in st.session_state:
    st.session_state.current_case_label = ""

# ── 사이드바 ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("양도소득세 RAG")
    st.caption("법령 조문 기반 — 법률 자문이 아닌 정보 제공 목적입니다.")

    st.divider()
    st.subheader("케이스 생성기")

    # ── 케이스 선택 ──────────────────────────────────────────────────────────
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("🎲 랜덤 케이스", use_container_width=True):
            case = random.choice(SAMPLE_CASES)
            st.session_state.fact_json_str = json.dumps(
                case["fact_json"], ensure_ascii=False, indent=2
            )
            st.session_state.current_case_label = (
                f"{CATEGORY_LABELS.get(case['category'], case['category'])}  \n{case['label']}"
            )
            st.rerun()
    with col_btn2:
        if st.button("🗑️ 초기화", use_container_width=True):
            st.session_state.fact_json_str = ""
            st.session_state.current_case_label = ""
            st.rerun()

    if st.session_state.current_case_label:
        st.info(st.session_state.current_case_label, icon="✅")

    fact_json_str = st.session_state.fact_json_str

    if st.button("⚡ 분석 시작", type="primary", use_container_width=True):
        st.session_state.run_analysis = True
        st.rerun()

    if st.button("💬 대화 초기화", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    st.divider()
    enable_debate = st.toggle(
        "🔴 Red Team 검증",
        value=False,
        help="confidence < 0.8 또는 복합 특례 케이스에 자동으로 Red-Blue 논쟁을 실행합니다. 응답 시간이 늘어납니다.",
    )

    with st.expander("RAG 파라미터"):
        top_k = st.slider("top_k", 5, 50, 20)
        rerank_top_n = st.slider("rerank_top_n", 1, 10, 5)

    with st.expander("논쟁 통계"):
        if st.button("통계 새로고침"):
            from src.eval.debate import debate_summary
            from src.eval.golden_injector import golden_summary
            ds = debate_summary()
            gs = golden_summary()
            st.json({**ds, "golden": gs})

    with st.expander("RAG 검색 디버그"):
        debug_query = st.text_input("검색 쿼리")
        if st.button("검색") and debug_query:
            from src.rag import retrieve_tax_law
            with st.spinner("검색 중..."):
                chunks = retrieve_tax_law(debug_query, top_k=top_k, rerank_top_n=rerank_top_n)
            st.write(f"{len(chunks)}개 조문")
            for i, c in enumerate(chunks, 1):
                with st.expander(f"[{i}] {c.law_name} 제{c.article_number}조 {c.score:.3f}"):
                    st.text(c.full_text)
                    st.caption(f"chunk_id: {c.id}")


# ── 세션 상태 초기화 (추가 항목) ─────────────────────────────────────────────

if "messages" not in st.session_state:
    st.session_state.messages = []
if "run_analysis" not in st.session_state:
    st.session_state.run_analysis = False

# ── 채팅 메시지 표시 ──────────────────────────────────────────────────────────

st.markdown("## 양도소득세 판단 채팅")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "user" and msg.get("fact_json"):
            if msg.get("case_label"):
                st.markdown(f"**{msg['case_label']}**")
            _render_fact_korean(msg["fact_json"])
        else:
            st.markdown(msg["content"])
        if "extra" in msg:
            extra = msg["extra"]
            _verdict = extra.get("verdict", "")
            _conf = extra.get("confidence", 0.0)
            _citations = extra.get("citations", [])
            _missing = extra.get("missing_facts", [])
            _warnings = extra.get("warnings", [])
            _chunks = extra.get("chunk_ids", [])

            c1, c2 = st.columns(2)
            with c1:
                verdict_color = {
                    "비과세": "green", "감면": "blue", "중과": "red",
                    "일반과세": "orange", "단기세율": "red",
                    "고가주택": "orange", "사실관계부족": "gray",
                }.get(_verdict, "gray")
                st.markdown(f"**판단: :{verdict_color}[{_verdict}]**")
            with c2:
                st.metric("신뢰도", f"{_conf:.0%}")

            if _citations:
                with st.expander("근거 법령"):
                    for c in _citations:
                        st.markdown(f"- {c}")
            if _missing:
                with st.expander("추가 확인 필요"):
                    for m in _missing:
                        st.warning(m, icon="⚠️")
            if _warnings:
                with st.expander("유의사항"):
                    for w in _warnings:
                        st.info(w)
            if _chunks:
                with st.expander("검색된 조문 ID"):
                    st.write(_chunks)


# ── 분석 실행 함수 ────────────────────────────────────────────────────────────

def _render_pipeline_result(result: dict) -> None:
    """파이프라인 결과를 채팅 말풍선 안에 렌더링."""
    verdict = result["verdict"]
    answer_text = result["answer"]
    st.markdown(answer_text)

    verdict_color = {
        "비과세": "green", "감면": "blue", "중과": "red",
        "일반과세": "orange", "단기세율": "red",
        "고가주택": "orange", "사실관계부족": "gray",
    }.get(verdict, "gray")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**판단: :{verdict_color}[{verdict}]**")
    with c2:
        st.metric("신뢰도", f"{result['confidence']:.0%}")

    if result.get("citations"):
        with st.expander("근거 법령"):
            for c in result["citations"]:
                st.markdown(f"- {c}")
    if result.get("missing_facts"):
        with st.expander("추가 확인 필요"):
            for m in result["missing_facts"]:
                st.warning(m, icon="⚠️")
    if result.get("warnings"):
        with st.expander("유의사항"):
            for w in result["warnings"]:
                st.info(w)
    if result.get("chunk_ids"):
        with st.expander("검색된 조문 ID"):
            st.write(result["chunk_ids"])
    if result.get("debate_record"):
        dr = result["debate_record"]
        outcome_label = {
            "blue_won": "🔵 Blue 방어 성공",
            "red_won": "🔴 Red 지적 수용 — 판단 수정됨",
            "no_contest": "✅ Red 이의 없음",
            "draw": "⚖️ 논쟁 무승부",
        }.get(dr.get("outcome", ""), "논쟁 실행됨")
        with st.expander(f"Red Team 검증 결과: {outcome_label}"):
            st.write(dr)


def _run_analysis(user_text: str, parsed_fact: dict | None) -> None:
    """분석 실행 후 채팅 히스토리에 추가."""
    case_label = st.session_state.current_case_label if parsed_fact else None
    msg_entry: dict = {"role": "user", "content": user_text}
    if parsed_fact:
        msg_entry["fact_json"] = parsed_fact
        msg_entry["case_label"] = case_label
    st.session_state.messages.append(msg_entry)
    with st.chat_message("user"):
        if parsed_fact:
            if case_label:
                st.markdown(f"**{case_label}**")
            _render_fact_korean(parsed_fact)
        else:
            st.markdown(user_text)

    with st.chat_message("assistant"):
        with st.spinner("법령 검색 및 판단 중..."):
            from src.api.chat_api import chat_turn
            result = asyncio.run(chat_turn(
                fact_json=parsed_fact,
                question=user_text if not parsed_fact else None,
                enable_debate=enable_debate,
            ))
            _render_pipeline_result(result)
            extra = {k: result[k] for k in ("verdict", "confidence", "citations", "missing_facts", "warnings", "chunk_ids")}
            st.session_state.messages.append({
                "role": "assistant",
                "content": result["answer"],
                "extra": extra,
            })


# ── 사이드바 분석 버튼 트리거 ────────────────────────────────────────────────

if st.session_state.run_analysis:
    st.session_state.run_analysis = False
    parsed_fact = None
    if fact_json_str.strip():
        try:
            parsed_fact = json.loads(fact_json_str)
        except json.JSONDecodeError:
            parsed_fact = None
    if parsed_fact:
        label = st.session_state.current_case_label or "사실관계 분석"
        _run_analysis(label, parsed_fact)
    else:
        st.warning("먼저 케이스를 생성해주세요.")


# ── 채팅 입력 ─────────────────────────────────────────────────────────────────

user_input = st.chat_input("추가 질문을 입력하거나, 케이스 선택 후 '⚡ 분석 시작'을 클릭하세요.")

if user_input:
    parsed_fact = None
    if fact_json_str.strip():
        try:
            parsed_fact = json.loads(fact_json_str)
        except json.JSONDecodeError:
            parsed_fact = None
    _run_analysis(user_input, parsed_fact)
