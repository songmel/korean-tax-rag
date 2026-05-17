"""
Streamlit 디버그 UI
입력 수집 + 결과 표시만 담당. 법령 판단 로직 없음.
"""
import streamlit as st

st.set_page_config(page_title="양도소득세 RAG", page_icon="⚖️", layout="wide")
st.title("양도소득세 비과세 판단 시스템")
st.caption("법령 조문 기반 RAG — 본 답변은 법률 자문이 아닌 정보 제공 목적입니다.")

# ── 사이드바: 모드 선택 ────────────────────────────────────────────────────────

mode = st.sidebar.radio(
    "실행 모드",
    ["RAG 단독 (빠름)", "CrewAI 2-Agent (정밀)"],
)

with st.sidebar.expander("RAG 파라미터"):
    top_k = st.slider("top_k (벡터 검색 후보)", 5, 50, 20)
    rerank_top_n = st.slider("rerank_top_n (최종 선택)", 1, 10, 5)

# ── 메인: 사실관계 입력폼 ───────────────────────────────────────────────────────

with st.form("fact_form"):
    st.subheader("사실관계 입력")
    col1, col2 = st.columns(2)
    with col1:
        acquisition_date = st.text_input("취득일", placeholder="예: 2020-03-15")
        transfer_date = st.text_input("양도일", placeholder="예: 2024-08-01")
        holding_years = st.text_input("보유기간", placeholder="예: 4년 5개월")
        residence_years = st.text_input("거주기간", placeholder="예: 2년")
    with col2:
        household_members = st.text_input("세대원 구성", placeholder="예: 배우자, 자녀 1명")
        house_count = st.selectbox("양도 당시 보유 주택 수", ["1주택", "2주택", "3주택 이상"])
        is_adjustment_area = st.selectbox("조정대상지역 여부", ["해당 없음", "해당"])
        special_case = st.multiselect(
            "특수 상황",
            ["일시적 2주택", "상속", "증여", "혼인", "동거봉양", "농어촌주택", "장기임대주택"],
        )

    free_text = st.text_area(
        "추가 사항 / 자유 질문",
        placeholder="예: 2년 이상 보유한 1세대 1주택인데 비과세가 되나요?",
        height=100,
    )
    submitted = st.form_submit_button("판단 요청", type="primary")

# ── 실행 ───────────────────────────────────────────────────────────────────────

if submitted:
    # 사실관계를 자연어 질문으로 조합
    facts = []
    if acquisition_date:
        facts.append(f"취득일: {acquisition_date}")
    if transfer_date:
        facts.append(f"양도일: {transfer_date}")
    if holding_years:
        facts.append(f"보유기간: {holding_years}")
    if residence_years:
        facts.append(f"거주기간: {residence_years}")
    if household_members:
        facts.append(f"세대원: {household_members}")
    facts.append(f"보유 주택 수: {house_count}")
    if is_adjustment_area != "해당 없음":
        facts.append("조정대상지역 해당")
    if special_case:
        facts.append(f"특수 상황: {', '.join(special_case)}")

    fact_str = " / ".join(facts)
    question = f"{fact_str}\n{free_text}".strip() if free_text else fact_str

    if not question:
        st.warning("사실관계를 입력해주세요.")
        st.stop()

    # 취득일을 기준일자로 자동 사용
    as_of_date = acquisition_date.replace("-", "") if acquisition_date else None

    with st.spinner("법령 검색 및 판단 중..."):
        if mode == "RAG 단독 (빠름)":
            from src.rag import answer_with_citations
            answer = answer_with_citations(question, as_of_date=as_of_date)

            st.success("판단 완료")
            st.subheader("요약 판단")
            st.write(answer.answer)

            col_a, col_b = st.columns(2)
            with col_a:
                st.metric("신뢰도", f"{answer.confidence:.0%}")
            with col_b:
                st.metric("인용 조문 수", len(answer.citations))

            if answer.citations:
                st.subheader("근거 법령")
                for c in answer.citations:
                    st.markdown(f"- {c}")

            if answer.missing_facts:
                st.subheader("추가 확인 필요")
                for f in answer.missing_facts:
                    st.warning(f)

            if answer.warnings:
                st.subheader("유의사항")
                for w in answer.warnings:
                    st.info(w)

            with st.expander("검색된 chunk_id 목록"):
                st.json(answer.chunk_ids)

        else:
            from src.agents.crew import run_tax_crew
            result = run_tax_crew(question)

            st.success("CrewAI 판단 완료")
            st.subheader("최종 답변")
            st.markdown(result)

# ── 디버그: RAG 검색 단독 실행 ─────────────────────────────────────────────────

with st.expander("RAG 검색 디버그"):
    debug_query = st.text_input("검색 쿼리 직접 입력")
    if st.button("검색") and debug_query:
        from src.rag import retrieve_tax_law
        with st.spinner("검색 중..."):
            chunks = retrieve_tax_law(debug_query, top_k=top_k, rerank_top_n=rerank_top_n)
        st.write(f"결과: {len(chunks)}개")
        for i, chunk in enumerate(chunks, 1):
            with st.expander(f"[{i}] {chunk.law_name} 제{chunk.article_number}조 — score: {chunk.score:.4f}"):
                st.text(chunk.full_text)
                st.caption(f"chunk_id: {chunk.id} | 시행일: {chunk.effective_date}")
