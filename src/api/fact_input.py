"""
채팅 모드용 JSON 사실관계 입력 스키마 및 RAGQueryInput 변환 팩토리.

외부에서 이 형식으로 사실관계를 전달하면 내부 파이프라인(L1-L5)이 동작한다.
"""
from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, model_validator

from src.domain.query_input import RAGQueryInput


# ── 특례 상세 (중첩 JSON) ────────────────────────────────────────────────────

class TempTwoHouseInput(BaseModel):
    """일시적 2주택 특례 상세"""
    new_acquisition_date: str       # 신규주택 취득일 YYYYMMDD
    old_house_must_sell_by: str     # 종전주택 양도 기한 YYYYMMDD
    new_is_adjustment_area: bool = False


class InheritanceInput(BaseModel):
    """상속 상세"""
    death_date: str                         # 상속개시일 YYYYMMDD
    same_household_at_death: bool = False
    inherited_as_only_house: bool = False
    selling_inherited_house: bool = True    # True: 상속주택 양도, False: 일반주택 양도
    donor_acquisition_date: Optional[str] = None


class GiftInput(BaseModel):
    """증여 상세 (이월과세 트리거 여부 포함)"""
    is_gift_from_spouse_or_lineal: bool     # 배우자·직계존비속 여부
    donor_acquisition_date: Optional[str] = None
    donor_acquisition_price: Optional[int] = None


class MarriageMergeInput(BaseModel):
    """혼인합가 상세"""
    marriage_date: str
    spouse_house_count_before_marriage: int = 1
    own_house_count_before_marriage: int = 1


class SangsaengRentalInput(BaseModel):
    """상생임대 상세 (소령 §155의3)"""
    contract_date: str              # 상생임대차계약 체결일 YYYYMMDD
    contract_period_months: int     # 실제 임대기간 (월 수, 24 이상)
    previous_monthly_rent: int      # 직전 계약 월세
    new_monthly_rent: int           # 상생임대 계약 월세
    has_prior_contract: bool = True


class LongTermRentalInput(BaseModel):
    """장기임대 감면 상세"""
    registration_date: str          # 임대사업자 등록일 YYYYMMDD
    mandatory_period_years: int = 8
    mandatory_period_fulfilled: bool = False
    rent_increase_limit_complied: bool = False


class SpecialCasesInput(BaseModel):
    """시나리오별 특례 상세 — 해당하는 항목만 채운다"""
    temp_two_house: Optional[TempTwoHouseInput] = None
    inheritance: Optional[InheritanceInput] = None
    gift: Optional[GiftInput] = None
    marriage_merge: Optional[MarriageMergeInput] = None
    sangsaeng_rental: Optional[SangsaengRentalInput] = None
    long_term_rental: Optional[LongTermRentalInput] = None
    residence_exemption_reason: Optional[str] = None  # "해외이주" | "취학" | "수용" 등


# ── 메인 입력 스키마 ─────────────────────────────────────────────────────────

class FactInput(BaseModel):
    """
    채팅 API가 수신하는 JSON 사실관계.

    필수 필드만으로도 기본 판단이 가능하며,
    special_cases를 채울수록 정밀한 판단이 가능하다.

    예시:
    {
        "transfer_date": "20240601",
        "acquisition_date": "20200301",
        "property_type": "아파트",
        "acquisition_reason": "매매",
        "household_house_count": 1,
        "transfer_price": 1100000000,
        "residence_years": 2.5,
        "is_adjustment_area_at_transfer": true
    }
    """
    # ── 필수 ──────────────────────────────────────────────────────────────────
    transfer_date: str          # 양도일 YYYYMMDD
    acquisition_date: str       # 취득일 YYYYMMDD
    property_type: Literal[
        "아파트", "단독주택", "연립다세대", "다가구", "겸용주택",
        "분양권", "입주권", "주거용오피스텔", "업무용오피스텔",
        "농어촌주택", "토지", "상가",
    ]
    acquisition_reason: Literal[
        "매매", "분양", "상속", "증여", "부담부증여", "이혼재산분할",
        "경매", "재건축", "재개발", "수용", "혼인합가",
    ]
    household_house_count: int  # 양도 시점 세대 보유 주택 수

    # ── 선택: 과세 계산에 필요 ────────────────────────────────────────────────
    transfer_price: Optional[int] = None        # 양도가액 (원) — 고가주택 판단 필수
    acquisition_price: Optional[int] = None     # 취득가액 (원)
    holding_years: Optional[float] = None       # 보유기간 (년) — 없으면 날짜로 계산
    residence_years: Optional[float] = None     # 거주기간 (년)
    is_adjustment_area_at_acquisition: bool = False  # 취득 시 조정대상지역
    is_adjustment_area_at_transfer: bool = False     # 양도 시 조정대상지역
    joint_ownership: bool = False               # 공동명의 여부
    is_non_resident: bool = False               # 비거주자 여부
    residential_area_ratio: Optional[float] = None   # 겸용주택 주거면적 비율 (0~1)

    # ── 특례 상세 ─────────────────────────────────────────────────────────────
    special_cases: Optional[SpecialCasesInput] = None

    @model_validator(mode="after")
    def _validate_dates(self) -> "FactInput":
        for field_name in ("transfer_date", "acquisition_date"):
            val = getattr(self, field_name)
            if len(val) != 8 or not val.isdigit():
                raise ValueError(f"{field_name}은 YYYYMMDD 형식이어야 합니다: {val!r}")
        if self.transfer_date < self.acquisition_date:
            raise ValueError("양도일이 취득일보다 이전일 수 없습니다.")
        return self


def fact_input_to_rag_query(fact: FactInput) -> RAGQueryInput:
    """
    FactInput → RAGQueryInput 변환.
    기존 from_fact_ledger(fact_ledger, owner_profile, user_property) 시그니처를 재사용한다.
    """
    sc = fact.special_cases or SpecialCasesInput()

    # user_property dict — from_fact_ledger가 기대하는 컬럼명 사용
    user_property: dict = {
        "transfer_date": _yyyymmdd_to_iso(fact.transfer_date),
        "acquisition_date": _yyyymmdd_to_iso(fact.acquisition_date),
        "asset_kind": fact.property_type,
        "acquisition_cause": fact.acquisition_reason,
        "sale_price_total": fact.transfer_price,
        "acquisition_price": fact.acquisition_price,
        "adjustment_area_at_acquisition": fact.is_adjustment_area_at_acquisition,
        "adjustment_area_at_transfer": fact.is_adjustment_area_at_transfer,
        "joint_ownership_yn": fact.joint_ownership,
        "overseas_residence_yn": fact.is_non_resident,
    }
    if sc.long_term_rental:
        lr = sc.long_term_rental
        user_property.update({
            "long_term_rental_yn": True,
            "rental_registration_date": _yyyymmdd_to_iso(lr.registration_date),
            "mandatory_rental_years": lr.mandatory_period_years,
            "mandatory_period_fulfilled": lr.mandatory_period_fulfilled,
            "rent_increase_limit_complied": lr.rent_increase_limit_complied,
        })
    if sc.inheritance:
        inh = sc.inheritance
        user_property["death_date"] = _yyyymmdd_to_iso(inh.death_date)
        if inh.donor_acquisition_date:
            user_property["donor_acquisition_date"] = _yyyymmdd_to_iso(inh.donor_acquisition_date)

    # fact_ledger dict — 특례 플래그
    fact_ledger: dict = {
        "household_house_count": fact.household_house_count,
        "holding_years": fact.holding_years,
        "residence_years": fact.residence_years,
    }
    if sc.temp_two_house:
        tt = sc.temp_two_house
        fact_ledger.update({
            "is_temporary_two_house": True,
            "temp_new_acquisition_date": _yyyymmdd_to_iso(tt.new_acquisition_date),
            "temp_old_must_sell_by": _yyyymmdd_to_iso(tt.old_house_must_sell_by),
            "temp_new_is_adjustment_area": tt.new_is_adjustment_area,
        })
    if sc.inheritance:
        inh = sc.inheritance
        fact_ledger.update({
            "deceased_same_household": inh.same_household_at_death,
            "inherited_as_only_house": inh.inherited_as_only_house,
            "selling_inherited_house": inh.selling_inherited_house,
        })
    if sc.gift:
        g = sc.gift
        fact_ledger["is_gift_from_spouse_or_lineal"] = g.is_gift_from_spouse_or_lineal
        if g.donor_acquisition_date:
            fact_ledger["donor_acquisition_date"] = _yyyymmdd_to_iso(g.donor_acquisition_date)
        if g.donor_acquisition_price is not None:
            fact_ledger["donor_acquisition_price"] = g.donor_acquisition_price
    if sc.marriage_merge:
        mm = sc.marriage_merge
        fact_ledger.update({
            "marriage_date": _yyyymmdd_to_iso(mm.marriage_date),
            "spouse_house_count_before_marriage": mm.spouse_house_count_before_marriage,
            "own_house_count_before_marriage": mm.own_house_count_before_marriage,
        })
    if sc.sangsaeng_rental:
        sr = sc.sangsaeng_rental
        fact_ledger.update({
            "sangsaeng_rental_yn": True,
            "sangsaeng_contract_date": _yyyymmdd_to_iso(sr.contract_date),
            "sangsaeng_period_months": sr.contract_period_months,
            "sangsaeng_prev_rent": sr.previous_monthly_rent,
            "sangsaeng_new_rent": sr.new_monthly_rent,
            "sangsaeng_has_prior_contract": sr.has_prior_contract,
        })
    if sc.residence_exemption_reason:
        fact_ledger["residence_exemption_reason"] = sc.residence_exemption_reason
    if fact.residential_area_ratio is not None:
        fact_ledger["residential_area_ratio"] = fact.residential_area_ratio

    # owner_profile — 세대원 구성 (현재는 주택 수만 전달)
    owner_profile: dict = {
        "household_house_count": fact.household_house_count,
    }

    return RAGQueryInput.from_fact_ledger(fact_ledger, owner_profile, user_property)


def _yyyymmdd_to_iso(d: str) -> str:
    """YYYYMMDD → YYYY-MM-DD"""
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}"
