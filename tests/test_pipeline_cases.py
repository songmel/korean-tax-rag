"""
업스트림 샘플 데이터 3케이스 — L2/L3 파이프라인 검증 (외부 서비스 불필요)

테스트 목적:
- RAGQueryInput.from_fact_ledger()가 올바르게 동작하는지 확인
- L2 fact_checker가 크리티컬 누락/정상 케이스를 정확히 분류하는지 확인
- L3 query_enrichment가 danger_flags에 맞는 키워드를 주입하는지 확인

E2E 테스트(Pinecone+Claude)는 pytest -m integration으로 별도 실행.
"""
from datetime import date
import pytest

from src.domain.query_input import RAGQueryInput
from src.domain.fact_checker import check_facts
from src.domain.query_enrichment import build_rag_query


# ── 샘플 데이터 ────────────────────────────────────────────────────────────────

CASE1_OWNER = {"household_house_count": 1, "overseas_residence_yn": False}
CASE1_PROP = {
    "asset_kind": "아파트",
    "acquisition_cause": "매매",
    "acquisition_date": "2018-03-15",
    "transfer_date": "2025-06-20",
    "acquisition_price": 500_000_000,
    "sale_price_total": 900_000_000,
    "adjustment_area_at_acquisition": True,
    "adjustment_area_at_transfer": False,
    "holding_period_years": 7.3,
    "residence_period_years": 3.5,
    "joint_ownership_yn": False,
}
CASE1_LEDGER = {"is_temporary_two_house": False}


CASE2_OWNER = {"household_house_count": 1, "overseas_residence_yn": False}
CASE2_PROP = {
    "asset_kind": "아파트",
    "acquisition_cause": "증여",
    "acquisition_date": "2022-05-10",
    "transfer_date": "2025-09-15",
    "acquisition_price": 600_000_000,
    "sale_price_total": 800_000_000,
    "adjustment_area_at_acquisition": True,
    "adjustment_area_at_transfer": False,
    "holding_period_years": 3.35,
    "residence_period_years": 2.1,
    "joint_ownership_yn": False,
    "gift_date": "2022-05-10",
}
CASE2_LEDGER = {
    "is_gift_from_spouse_or_lineal": True,
    "original_donor_acquisition_date": "2015-08-20",
    "original_donor_acquisition_price": 350_000_000,
}


CASE3_OWNER = {"household_house_count": 2, "overseas_residence_yn": False}
CASE3_PROP = {
    "asset_kind": "아파트",
    "acquisition_cause": "매매",
    "acquisition_date": "2016-11-01",
    "transfer_date": "2025-08-30",
    "acquisition_price": 700_000_000,
    "sale_price_total": 1_500_000_000,
    "adjustment_area_at_acquisition": True,
    "adjustment_area_at_transfer": False,
    "holding_period_years": 8.8,
    "residence_period_years": 4.0,
    "joint_ownership_yn": False,
}
CASE3_LEDGER = {
    "is_temporary_two_house": True,
    "temp_new_acquisition_date": "2024-09-01",
    "temp_old_must_sell_by": "2027-09-01",
    "temp_new_is_adjustment_area": False,
}


# ── 헬퍼 ───────────────────────────────────────────────────────────────────────

def build_query(ledger, owner, prop) -> RAGQueryInput:
    return RAGQueryInput.from_fact_ledger(ledger, owner, prop)


# ── 케이스 1: 1세대1주택 단순 매매 ────────────────────────────────────────────

class TestCase1:
    def setup_method(self):
        self.query = build_query(CASE1_LEDGER, CASE1_OWNER, CASE1_PROP)

    def test_from_fact_ledger_succeeds(self):
        assert self.query.date_bundle.transfer_date == date(2025, 6, 20)
        assert self.query.date_bundle.acquisition_date == date(2018, 3, 15)

    def test_entity_scope_is_house(self):
        from src.domain.query_input import EntityScope
        assert self.query.entity_scope == EntityScope.HOUSE

    def test_l2_can_proceed(self):
        result = check_facts(self.query)
        # 양도가액 제공됨(9억) → 고가주택 아님 → 크리티컬 누락 없음
        assert result.can_proceed is True
        assert len(result.critical_missing) == 0

    def test_l2_no_danger_flags(self):
        result = check_facts(self.query)
        # 단순 매매 1주택 — 이월과세/상속/입주권 없음
        dangerous = {"이월과세", "상속주택", "조합원입주권"}
        assert not dangerous & set(result.danger_flags)

    def test_l3_enriched_query_contains_base_info(self):
        result = check_facts(self.query)
        enriched = build_rag_query(self.query, result.danger_flags)
        assert "아파트" in enriched
        assert "매매" in enriched

    def test_fact_vector_to_text_includes_adjustment_area(self):
        text = self.query.fact_vector.to_text()
        assert "조정대상지역_취득시: 해당" in text
        assert "조정대상지역_양도시: 비해당" in text

    def test_fact_vector_high_value_false(self):
        # 9억 < 12억 → 고가주택 아님
        assert self.query.fact_vector.is_high_value_house is False


# ── 케이스 2: 이월과세 (배우자 증여 후 5년 이내 양도) ─────────────────────────

class TestCase2:
    def setup_method(self):
        self.query = build_query(CASE2_LEDGER, CASE2_OWNER, CASE2_PROP)

    def test_rollover_taxation_populated(self):
        rt = self.query.fact_vector.special_cases.rollover_taxation
        assert rt is not None
        assert rt.is_gift_from_spouse_or_lineal is True
        assert rt.gift_date == date(2022, 5, 10)
        assert rt.original_donor_acquisition_price == 350_000_000

    def test_iota_period_is_5_years(self):
        # 2022년 증여 → 2023년 이전 → 5년 적용
        rt = self.query.fact_vector.special_cases.rollover_taxation
        assert rt.iota_period_years == 5

    def test_l2_can_proceed_when_all_info_present(self):
        # 원취득일/원취득가액 모두 제공 → L2 차단 없음
        # (차단은 원취득 정보 누락 시에만 발생)
        result = check_facts(self.query)
        assert result.can_proceed is True

    def test_l2_danger_flag_iota(self):
        result = check_facts(self.query)
        # 3.35년 < 5년 이내 → danger flag 생성
        assert "이월과세_5년이내" in result.danger_flags

    def test_l3_injects_iota_keyword(self):
        result = check_facts(self.query)
        enriched = build_rag_query(self.query, result.danger_flags)
        assert "소득세법 제97조의2" in enriched
        assert "이월과세" in enriched

    def test_fact_vector_to_text_includes_iota_article(self):
        text = self.query.fact_vector.to_text()
        assert "소득세법제97조의2" in text
        assert "이월과세" in text

    def test_l2_blocks_when_donor_info_missing(self):
        """원취득 정보 없는 경우 → 이것이 실제 L2 차단 케이스.

        ledger에 is_gift_from_spouse_or_lineal=True만 있고 original_donor 정보가
        없으면 from_fact_ledger()가 rollover_taxation을 완전히 구성하지 못함.
        fact_checker 규칙 #2: rt is None → 'is_gift_from_spouse_or_lineal' 재확인 요청.
        """
        ledger_no_donor = {
            "is_gift_from_spouse_or_lineal": True,
            # original_donor 정보 없음 → rollover_taxation 미구성
        }
        q = build_query(ledger_no_donor, CASE2_OWNER, CASE2_PROP)
        result = check_facts(q)
        assert result.can_proceed is False
        # rt가 None 또는 미구성 → 'is_gift_from_spouse_or_lineal' 필드 재확인 요청
        fields = [m.field_name for m in result.critical_missing]
        assert any(
            "is_gift_from_spouse_or_lineal" in f or "original_donor" in f
            for f in fields
        )


# ── 케이스 3: 일시적 2주택 + 고가주택 ────────────────────────────────────────

class TestCase3:
    def setup_method(self):
        self.query = build_query(CASE3_LEDGER, CASE3_OWNER, CASE3_PROP)

    def test_temp_two_house_flag_set(self):
        sc = self.query.fact_vector.special_cases
        assert sc.is_temporary_two_house is True
        assert sc.temp_two_house is not None
        assert sc.temp_two_house.new_acquisition_date == date(2024, 9, 1)

    def test_high_value_house(self):
        # 15억 > 12억 → 고가주택
        assert self.query.fact_vector.is_high_value_house is True

    def test_l2_can_proceed(self):
        result = check_facts(self.query)
        assert result.can_proceed is True

    def test_l2_danger_flags_temp_two_house_and_high_value(self):
        result = check_facts(self.query)
        assert "일시적2주택" in result.danger_flags
        # 고가주택 미확인 flag: transfer_price 제공됐으므로 없어야 함
        assert "고가주택_미확인" not in result.danger_flags

    def test_l3_injects_temp_two_house_keyword(self):
        result = check_facts(self.query)
        enriched = build_rag_query(self.query, result.danger_flags)
        assert "소득세법 시행령 제155조 제1항" in enriched

    def test_fact_vector_to_text_includes_temp_two_house_flag(self):
        text = self.query.fact_vector.to_text()
        assert "일시적2주택" in text

    def test_household_count_2(self):
        assert self.query.fact_vector.household_house_count == 2
