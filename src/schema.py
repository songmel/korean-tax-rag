"""
양도소득세 RAG 엔진 입출력 스키마
업스트림 플랫폼이 이 스키마로 구조화된 사실관계를 전달한다.
"""
from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, field_validator, model_validator


# ── 날짜 묶음 ─────────────────────────────────────────────────────────────────

class DateBundle(BaseModel):
    transfer_date: str                      # 양도일 YYYYMMDD (필수)
    acquisition_date: str                   # 취득일 YYYYMMDD (필수)
    contract_date: Optional[str] = None     # 계약일 — 부칙 경과조치 기준
    balance_payment_date: Optional[str] = None  # 잔금일 — 실질 양도일 판단


# ── 거주 이력 ─────────────────────────────────────────────────────────────────

class ResidencePeriod(BaseModel):
    start_date: str    # YYYYMMDD
    end_date: str      # YYYYMMDD, 거주 중이면 transfer_date 와 동일


# ── 세대원 ────────────────────────────────────────────────────────────────────

class HouseholdMember(BaseModel):
    relation: Literal["spouse", "child", "parent", "sibling", "other"]
    age: Optional[int] = None
    has_income: Optional[bool] = None      # 30세 미만 자녀 독립세대 판정용


# ── 상속 상세 ─────────────────────────────────────────────────────────────────

class InheritanceDetail(BaseModel):
    death_date: str                         # 상속개시일 (피상속인 사망일)
    donor_acquisition_date: Optional[str] = None   # 피상속인 원취득일
    is_same_household_before_death: bool = False   # 사망 전 동일세대 여부
    is_joint_inheritance: bool = False      # 공동상속 여부
    inheritance_share_pct: Optional[float] = None  # 지분율 (공동상속 시)
    is_largest_share: Optional[bool] = None        # 최대 지분 보유 여부
    selling_inherited_house: bool = True    # True: 상속주택 양도 / False: 일반주택 양도


# ── 증여 상세 ─────────────────────────────────────────────────────────────────

class GiftDetail(BaseModel):
    gift_date: str                          # 증여일 YYYYMMDD
    is_gift_from_spouse_or_lineal: bool     # 배우자·직계존비속 여부 → 이월과세 트리거
    donor_acquisition_date: Optional[str] = None   # 증여자 원취득일
    donor_acquisition_price: Optional[int] = None  # 증여자 원취득가액 (이월과세 시 필요)


# ── 혼인 합가 ─────────────────────────────────────────────────────────────────

class MarriageMergeDetail(BaseModel):
    marriage_date: str                      # 혼인일
    # 혼인 전 각자 보유 주택 취득일 (소령 §155⑤ — 5년 이내 먼저 양도 비과세)
    my_house_acquisition_date: str
    spouse_house_acquisition_date: str


# ── 동거봉양 합가 ─────────────────────────────────────────────────────────────

class CohabitationCareDetail(BaseModel):
    cohabitation_start_date: str            # 합가일 (소령 §155④ — 10년 이내 비과세)
    parent_age: Optional[int] = None        # 60세 이상
    parent_has_severe_illness: bool = False # 중증질환으로 60세 미만 예외 적용 시


# ── 재건축 / 재개발 ───────────────────────────────────────────────────────────

class ReconstructionDetail(BaseModel):
    is_original_member: bool                # 원조합원 vs 승계조합원
    management_disposal_date: str           # 관리처분계획인가일 ← 보유기간 기산점
    original_house_acquisition_date: str    # 종전 주택 취득일
    original_house_area_sqm: Optional[float] = None
    completion_date: Optional[str] = None   # 완공일
    move_in_date: Optional[str] = None      # 입주일
    paid_liquidation: int = 0               # 추가 납부 청산금
    received_liquidation: int = 0           # 수령 청산금


# ── 일시적 2주택 ──────────────────────────────────────────────────────────────

class TempTwoHouseDetail(BaseModel):
    new_house_acquisition_date: str         # 신규주택 취득일
    new_house_is_adjustment_area: bool      # 신규주택 조정대상지역 여부
    # 3년 이내 종전주택 양도 기한은 자동 계산


# ── 장기임대주택 ──────────────────────────────────────────────────────────────

class LongTermRentalDetail(BaseModel):
    local_gov_registration_date: str        # 지자체 임대사업자 등록일
    rental_type: Literal["short_4yr", "long_8yr"]
    actual_rental_start: str
    actual_rental_end: Optional[str] = None
    rent_increase_cap_complied: bool        # 임대료 5% 상한 준수
    mandatory_period_fulfilled: bool        # 의무임대기간 충족
    public_price_at_acquisition: Optional[int] = None   # 공시가격 (6억/3억 이하 요건)
    exclusive_area_sqm: Optional[float] = None          # 전용면적 85㎡ 이하
    is_apartment: bool = False
    registered_before_2020_0818: bool = True  # 정책 변경 전 등록 여부
    auto_cancelled: bool = False
    auto_cancel_date: Optional[str] = None


# ── 상생임대 ──────────────────────────────────────────────────────────────────

class SangsaengRentalDetail(BaseModel):
    contract_date: str                      # 상생임대차계약 체결일
                                            # 반드시 2021.12.20~2024.12.31
    contract_period_months: int             # 실제 임대기간 (2년 이상)
    previous_monthly_rent: int              # 직전 계약 월세
    new_monthly_rent: int                   # 상생임대 월세
    # 인상률은 자동 계산: (new - prev) / prev ≤ 0.05

    @property
    def increase_rate(self) -> float:
        if self.previous_monthly_rent == 0:
            return 0.0
        return (self.new_monthly_rent - self.previous_monthly_rent) / self.previous_monthly_rent

    @property
    def qualifies(self) -> bool:
        return (
            self.increase_rate <= 0.05
            and self.contract_period_months >= 24
            and "20211220" <= self.contract_date.replace("-", "") <= "20241231"
        )


# ── 거주요건 면제 특례 ─────────────────────────────────────────────────────────

class ResidenceExemption(BaseModel):
    reason: Literal[
        "sangsaeng_rental",   # 상생임대 — 소령 §155의3
        "overseas_dispatch",  # 해외 파견 근무
        "emigration",         # 해외이주법 적용
        "compulsory_acq",     # 공익사업 수용
        "school_work",        # 취학·근무 1년 이상 거주 후 부득이
    ]
    evidence_date: Optional[str] = None     # 수용일, 출국일 등 근거 날짜


# ── 수용 ──────────────────────────────────────────────────────────────────────

class CompulsoryAcquisitionDetail(BaseModel):
    acquisition_type: Literal["compulsory", "negotiated", "voluntary"]
    compensation_type: Literal["cash", "bond", "land"]


# ═══════════════════════════════════════════════════════════════════════════════
# 메인 입력 스키마
# ═══════════════════════════════════════════════════════════════════════════════

class TaxCase(BaseModel):
    """
    양도소득세 판단 요청 — 업스트림 플랫폼이 이 형식으로 전달.
    필수 필드: dates, property_type, acquisition_reason, household.
    나머지는 해당하는 케이스에만 채운다.
    """

    # ── 날짜 (항상 필수) ──────────────────────────────────────────────────────
    dates: DateBundle

    # ── 주택 ──────────────────────────────────────────────────────────────────
    property_type: Literal[
        "apartment",            # 아파트
        "house",                # 단독주택
        "villa",                # 빌라·다세대
        "dagagu",               # 다가구 (전체를 1주택으로)
        "gyeomyong",            # 겸용주택 (주거+상가)
        "subscription_right",   # 분양권
        "association_right",    # 조합원입주권
        "officetel_residential",# 주거용 오피스텔 (주택 수 포함)
        "rural",                # 농어촌주택
    ]

    # 겸용주택 면적 비율 (gyeomyong 일 때 필수)
    residential_area_sqm: Optional[float] = None
    commercial_area_sqm: Optional[float] = None

    # ── 가액 (고가주택 판단 필수) ─────────────────────────────────────────────
    transfer_price: Optional[int] = None      # 양도가액 (원)
    acquisition_price: Optional[int] = None   # 취득가액 (원)
    standard_price: Optional[int] = None      # 기준시가 (공시가격)

    # ── 주택 수 ───────────────────────────────────────────────────────────────
    # 업스트림이 산정 전 원시값을 보내면 fact_checker가 산입/제외 판단
    property_count_raw: int                   # 실제 보유 중인 주택+권리 총수
    property_count_for_tax: Optional[int] = None  # 세법상 주택 수 (업스트림 계산값)

    # ── 조정대상지역 (시점 분리) ──────────────────────────────────────────────
    is_adjustment_area_at_acquisition: Optional[bool] = None  # 취득일 기준
    is_adjustment_area_at_transfer: Optional[bool] = None     # 양도일 기준

    # ── 거주 이력 ─────────────────────────────────────────────────────────────
    residence_periods: list[ResidencePeriod] = []
    # 비어있으면 = 미거주

    # ── 세대 ──────────────────────────────────────────────────────────────────
    has_spouse: bool
    household_members: list[HouseholdMember] = []
    is_resident: bool = True                  # 거주자 여부 (비거주자 비과세 불가)

    # ── 취득 경위 ─────────────────────────────────────────────────────────────
    acquisition_reason: Literal[
        "purchase",             # 매매
        "inheritance",          # 상속
        "gift",                 # 증여
        "marriage_merge",       # 혼인 합가
        "newbuild",             # 신축
        "reconstruction",       # 재건축·재개발
    ]

    # ── 특수 상황 플래그 ──────────────────────────────────────────────────────
    # fact_checker가 이 플래그로 required 상세 모델 존재 여부 검증
    special_situations: list[Literal[
        "temp_two_house",       # 일시적 2주택
        "long_term_rental",     # 장기임대주택 보유 (소령 §155⑳, 조특법 §97의3)
        "sangsaeng_rental",     # 상생임대 (소령 §155의3)
        "cohabitation_care",    # 동거봉양 합가 (소령 §155④)
        "compulsory_acq",       # 공익사업 수용
        "overseas_work",        # 해외 파견 근무
    ]] = []

    # ── 특수 케이스 상세 (해당 시만 채움) ────────────────────────────────────
    inheritance_detail: Optional[InheritanceDetail] = None
    gift_detail: Optional[GiftDetail] = None
    marriage_detail: Optional[MarriageMergeDetail] = None
    cohabitation_detail: Optional[CohabitationCareDetail] = None
    reconstruction_detail: Optional[ReconstructionDetail] = None
    temp_two_house: Optional[TempTwoHouseDetail] = None
    long_term_rentals: list[LongTermRentalDetail] = []
    sangsaeng_rental: Optional[SangsaengRentalDetail] = None
    residence_exemption: Optional[ResidenceExemption] = None
    compulsory_detail: Optional[CompulsoryAcquisitionDetail] = None

    # ── 이력 플래그 ───────────────────────────────────────────────────────────
    used_geoju_special_before: bool = False   # 거주주택 비과세 특례 평생 1회 소진 여부
    is_unregistered_transfer: bool = False    # 미등기 양도 (70% 중과)

    # ── 보완 텍스트 ───────────────────────────────────────────────────────────
    additional_context: str = ""

    # ── Cross-field 검증 ──────────────────────────────────────────────────────

    @model_validator(mode="after")
    def check_required_details(self) -> TaxCase:
        errors = []

        if self.acquisition_reason == "inheritance" and not self.inheritance_detail:
            errors.append("acquisition_reason=inheritance → inheritance_detail 필수")

        if self.acquisition_reason == "gift" and not self.gift_detail:
            errors.append("acquisition_reason=gift → gift_detail 필수")

        if self.acquisition_reason == "marriage_merge" and not self.marriage_detail:
            errors.append("acquisition_reason=marriage_merge → marriage_detail 필수")

        if self.acquisition_reason == "reconstruction" and not self.reconstruction_detail:
            errors.append("acquisition_reason=reconstruction → reconstruction_detail 필수")

        if "temp_two_house" in self.special_situations and not self.temp_two_house:
            errors.append("special_situations에 temp_two_house → temp_two_house 상세 필수")

        if "sangsaeng_rental" in self.special_situations and not self.sangsaeng_rental:
            errors.append("special_situations에 sangsaeng_rental → sangsaeng_rental 상세 필수")

        if self.property_type == "gyeomyong":
            if self.residential_area_sqm is None or self.commercial_area_sqm is None:
                errors.append("property_type=gyeomyong → residential_area_sqm, commercial_area_sqm 필수")

        if errors:
            raise ValueError("\n".join(errors))

        return self


# ═══════════════════════════════════════════════════════════════════════════════
# 출력 스키마
# ═══════════════════════════════════════════════════════════════════════════════

class TaxDecision(BaseModel):
    verdict: Literal[
        "exempt",               # 비과세
        "taxable",              # 과세
        "partially_exempt",     # 고가주택 — 12억 이하 비과세, 초과 과세
        "needs_verification",   # 사실관계 불충분 — 판단 불가
        "manual_review",        # 복잡성 높음 — 전문가 검토 필요
    ]
    answer: str                 # 상세 판단 (법령 근거 포함)
    citations: list[str]        # ["소득세법 제89조 제1항 제3호", ...]
    chunk_ids: list[str]        # 검색된 조문 ID (감사용)
    confidence: float           # 0.0 ~ 1.0
    missing_facts: list[str]    # 판단에 필요한 추가 정보
    warnings: list[str]         # 주의사항
    as_of_date: str             # 적용된 법령 기준일 YYYYMMDD
    trace_id: str               # 요청 추적 ID
    knowledge_snapshot: dict    # 사용된 버전 정보
    # {
    #   "corpus_version": "2026-05-17",
    #   "prompt_version": "v1",
    #   "model": "claude-sonnet-4-6",
    # }
