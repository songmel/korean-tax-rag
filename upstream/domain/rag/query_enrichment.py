"""
L3 — Query Enrichment

danger_flags → 도메인 키워드 주입.
벡터 검색은 "입력 텍스트와 유사한 조문"을 찾으므로,
키워드가 없으면 해당 조문이 검색 결과에서 누락됨.

예: "이월과세" 키워드 없이 "배우자 증여 주택 양도" 검색
    → §97의2 대신 일반 양도세 조문만 검색됨 → 틀린 취득가액 적용
"""

from __future__ import annotations

from typing import Dict, List

from .query_input import RAGQueryInput


# danger_flag → 삽입할 도메인 키워드 + 조문 번호
# 키워드가 쿼리에 있어야 벡터 검색이 해당 조문 청크를 찾아옴
DANGER_KEYWORD_MAP: Dict[str, str] = {
    "이월과세": "배우자 직계존비속 증여 이월과세 소득세법 제97조의2 원취득가액",
    "이월과세_5년이내": "증여 후 5년 이내 양도 이월과세 소득세법 제97조의2",
    "이월과세_10년이내": "증여 후 10년 이내 양도 이월과세 소득세법 제97조의2 2023년 개정",
    "고가주택_미확인": "고가주택 12억 초과 장기보유특별공제 표2 소득세법 제95조",
    "고가주택": "고가주택 12억 장기보유특별공제 표2 소득세법 제95조 시행령 제156조의2",
    "상속주택": "상속주택 소득세법 시행령 제155조 피상속인 보유기간 합산",
    "상속주택_자체양도": "상속주택 자체양도 피상속인 보유기간 합산 소령 제155조 제3항",
    "일시적2주택": "일시적 2주택 종전주택 3년 이내 양도 소득세법 시행령 제155조 제1항",
    "조합원입주권": "조합원입주권 관리처분계획인가 보유기간 소득세법 시행령 제156조의2",
    "분양권": "분양권 소득세법 제88조 주택 수 산입",
    "분양권_2021전_주택수미산입": "2020년 이전 취득 분양권 주택 수 미산입 소득세법 부칙",
    "분양권_2021후_주택수산입": "2021년 이후 취득 분양권 주택 수 산입 소득세법 제88조 제7항",
    "분양권_기준불명": "분양권 취득일 2021년 기준 주택 수 산입 여부 소득세법 제88조",
    "상생임대": "상생임대주택 거주요건 면제 소득세법 시행령 제155조의3",
    "공동명의": "공동명의 지분 양도 비율 소득세법 제88조 제1항",
    "비거주자": "비거주자 1세대 1주택 비과세 배제 소득세법 제121조",
    "비거주자_해외이주2년이내양도가능": "해외이주 2년 이내 양도 비과세 소득세법 시행령 제154조 제1항 제2호",
    "재건축재개발원조합원": "원조합원 재건축 보유기간 관리처분 소득세법 시행령 제156조의2",
    "재건축재개발승계조합원": "승계조합원 입주권 취득일 보유기간 소득세법 시행령 제156조의2",
    "동거봉양합가": "동거봉양 합가 10년 이내 비과세 소득세법 시행령 제155조 제4항",
    "수용_compulsory_거주요건면제": "강제수용 거주요건 면제 소득세법 시행령 제154조 제1항 단서",
    "수용_negotiated_거주요건면제": "협의취득 거주요건 면제 소득세법 시행령 제154조 제1항 단서",
}


def enrich_query(base_query: str, danger_flags: List[str]) -> str:
    """
    RAG 검색 쿼리에 danger_flags에 대응하는 도메인 키워드를 주입.

    Args:
        base_query: fact_vector.to_text() 등 기본 쿼리 텍스트
        danger_flags: FactCheckResult.danger_flags

    Returns:
        키워드가 주입된 강화 쿼리 텍스트
    """
    injected: List[str] = []
    seen: set[str] = set()

    for flag in danger_flags:
        kw = DANGER_KEYWORD_MAP.get(flag)
        if kw and kw not in seen:
            injected.append(kw)
            seen.add(kw)

    if not injected:
        return base_query

    enriched = base_query + "\n[검색 보강] " + " | ".join(injected)
    return enriched


def build_rag_query(query_input: RAGQueryInput, danger_flags: List[str]) -> str:
    """
    RAGQueryInput → 최종 RAG 검색 텍스트.
    fact_vector.to_text()를 base로 danger_flags 키워드를 추가.
    """
    base = query_input.fact_vector.to_text()
    return enrich_query(base, danger_flags)
