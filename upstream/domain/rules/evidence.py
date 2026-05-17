"""
[L2 Verification] Evidence Hierarchy (증거 위계) 시스템

데이터 신뢰도를 계층화하여 관리합니다.
- Tier 1: API/PDF 연동 (100점) - 변조 불가
- Tier 2: 확인서 서명 (70점) - 면책 동의 후 진행
- Tier 3: 단순 사용자 주장 (0점) - 계산 불가

Risk Score가 임계값 미달 시 세무사 이관됩니다.
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


# ============================================================
# 신뢰도 계층 정의
# ============================================================

class EvidenceTier(str, Enum):
    """증거 신뢰도 계층"""
    TIER_1 = "TIER_1"  # API/PDF - Immutable Fact (100점)
    TIER_2 = "TIER_2"  # 확인서 서명 - Confirmed Fact (70점)
    TIER_3 = "TIER_3"  # 단순 주장 - User Claim (0점, 계산 불가)


class EvidenceSource(str, Enum):
    """증거 출처 유형"""
    # Tier 1 Sources
    GOV24_API = "GOV24_API"           # 정부24 등본 API
    REGISTRY_API = "REGISTRY_API"     # 등기소 API
    PDF_OCR = "PDF_OCR"               # 업로드된 PDF OCR
    CONTRACT_OCR = "CONTRACT_OCR"     # 매매계약서 OCR
    
    # Tier 2 Sources
    ACKNOWLEDGEMENT = "ACKNOWLEDGEMENT"  # 전자 확인서 서명
    
    # Tier 3 Sources
    USER_INPUT = "USER_INPUT"         # 단순 사용자 입력
    VERBAL_CLAIM = "VERBAL_CLAIM"     # 구두 주장


# 출처별 점수 매핑
EVIDENCE_SCORES: Dict[EvidenceSource, int] = {
    # Tier 1 - 100점
    EvidenceSource.GOV24_API: 100,
    EvidenceSource.REGISTRY_API: 100,
    EvidenceSource.PDF_OCR: 95,
    EvidenceSource.CONTRACT_OCR: 90,
    
    # Tier 2 - 70점
    EvidenceSource.ACKNOWLEDGEMENT: 70,
    
    # Tier 3 - 0점
    EvidenceSource.USER_INPUT: 0,
    EvidenceSource.VERBAL_CLAIM: 0,
}


# 임계값 설정
RISK_THRESHOLD_AUTO = 80     # 이 이상이면 AI 자동 처리
RISK_THRESHOLD_MANUAL = 50   # 이 이상이면 확인서 받고 진행
# 50점 미만: 세무사 이관 필수


# ============================================================
# 데이터 모델
# ============================================================

class EvidenceItem(BaseModel):
    """개별 증거 항목"""
    field_key: str = Field(description="사실관계 필드 키 (예: residence_years)")
    value: Any = Field(description="값")
    source: EvidenceSource = Field(description="증거 출처")
    score: int = Field(description="신뢰도 점수 (0-100)")
    tier: EvidenceTier = Field(description="신뢰도 계층")
    
    # 메타데이터
    collected_at: datetime = Field(default_factory=datetime.now)
    document_id: Optional[str] = Field(default=None, description="연결된 문서 ID")
    
    # 확인서 관련
    acknowledgement_signed: bool = Field(default=False, description="확인서 서명 여부")
    acknowledgement_text: Optional[str] = Field(default=None, description="확인서 내용")


class FactLedgerWithEvidence(BaseModel):
    """증거 기반 사실관계 원장"""
    user_id: str
    items: Dict[str, EvidenceItem] = Field(default_factory=dict)
    
    # 통계
    total_score: float = Field(default=0.0)
    min_score: int = Field(default=0)
    tier_1_count: int = Field(default=0)
    tier_2_count: int = Field(default=0)
    tier_3_count: int = Field(default=0)
    
    # 상태
    is_calculable: bool = Field(default=False, description="계산 가능 여부")
    requires_acknowledgement: bool = Field(default=False, description="확인서 필요 여부")
    requires_escalation: bool = Field(default=False, description="세무사 이관 필요 여부")
    escalation_reason: Optional[str] = Field(default=None)
    
    def add_evidence(self, item: EvidenceItem) -> None:
        """증거 항목 추가 및 점수 재계산"""
        self.items[item.field_key] = item
        self._recalculate_scores()
    
    def _recalculate_scores(self) -> None:
        """전체 점수 및 상태 재계산"""
        if not self.items:
            self.total_score = 0
            self.is_calculable = False
            return
        
        scores = [item.score for item in self.items.values()]
        self.total_score = sum(scores) / len(scores)
        self.min_score = min(scores)
        
        # 계층별 카운트
        self.tier_1_count = sum(1 for item in self.items.values() if item.tier == EvidenceTier.TIER_1)
        self.tier_2_count = sum(1 for item in self.items.values() if item.tier == EvidenceTier.TIER_2)
        self.tier_3_count = sum(1 for item in self.items.values() if item.tier == EvidenceTier.TIER_3)
        
        # 상태 결정
        if self.tier_3_count > 0:
            # Tier 3 항목이 하나라도 있으면
            unsigned_tier3 = [
                item for item in self.items.values() 
                if item.tier == EvidenceTier.TIER_3 and not item.acknowledgement_signed
            ]
            
            if unsigned_tier3:
                self.is_calculable = False
                self.requires_acknowledgement = True
                self.requires_escalation = False
            else:
                # 확인서 서명 완료 -> 계산 가능
                self.is_calculable = True
                self.requires_acknowledgement = False
        else:
            self.is_calculable = True
            self.requires_acknowledgement = False
        
        # Risk Score 기반 이관 판단
        if self.total_score < RISK_THRESHOLD_MANUAL:
            self.requires_escalation = True
            self.escalation_reason = f"신뢰도 점수 미달 ({self.total_score:.0f}점 < {RISK_THRESHOLD_MANUAL}점)"
            self.is_calculable = False


class Acknowledgement(BaseModel):
    """전자 확인서 (면책 동의)"""
    id: str
    user_id: str
    
    # 확인 내용
    field_key: str = Field(description="확인 대상 필드")
    claimed_value: Any = Field(description="사용자 주장 값")
    
    # 서명
    signed_at: Optional[datetime] = Field(default=None)
    signature_text: str = Field(default="")
    ip_address: Optional[str] = Field(default=None)
    
    # 면책 조항
    disclaimer: str = Field(
        default=(
            "본인은 위 정보가 사실과 다를 경우 발생하는 세무상 불이익에 대해 "
            "본인이 책임을 부담함을 확인합니다."
        )
    )
    
    @property
    def is_valid(self) -> bool:
        return self.signed_at is not None and len(self.signature_text) > 0


# ============================================================
# 헬퍼 함수
# ============================================================

def create_evidence_item(
    field_key: str,
    value: Any,
    source: EvidenceSource,
    document_id: Optional[str] = None
) -> EvidenceItem:
    """EvidenceItem 생성 헬퍼"""
    score = EVIDENCE_SCORES.get(source, 0)
    
    if score >= 90:
        tier = EvidenceTier.TIER_1
    elif score >= 50:
        tier = EvidenceTier.TIER_2
    else:
        tier = EvidenceTier.TIER_3
    
    return EvidenceItem(
        field_key=field_key,
        value=value,
        source=source,
        score=score,
        tier=tier,
        document_id=document_id
    )


def upgrade_to_tier2(item: EvidenceItem, acknowledgement: Acknowledgement) -> EvidenceItem:
    """Tier 3 항목을 확인서 서명 후 Tier 2로 승격"""
    if item.tier != EvidenceTier.TIER_3:
        return item  # 이미 Tier 1 또는 2면 변경 없음
    
    if not acknowledgement.is_valid:
        return item  # 유효하지 않은 확인서
    
    # 승격
    item.tier = EvidenceTier.TIER_2
    item.score = EVIDENCE_SCORES[EvidenceSource.ACKNOWLEDGEMENT]
    item.acknowledgement_signed = True
    item.acknowledgement_text = acknowledgement.disclaimer
    
    return item


def get_risk_assessment(ledger: FactLedgerWithEvidence) -> Dict[str, Any]:
    """Risk 평가 결과 반환"""
    if ledger.total_score >= RISK_THRESHOLD_AUTO:
        action = "AUTO_PROCESS"
        message = "모든 데이터가 검증되었습니다. 자동 계산이 가능합니다."
    elif ledger.total_score >= RISK_THRESHOLD_MANUAL:
        action = "REQUIRE_ACKNOWLEDGEMENT"
        message = "일부 데이터에 대한 확인서 서명이 필요합니다."
    else:
        action = "ESCALATE_TO_HUMAN"
        message = "이 건은 세무사의 최종 검토가 필요합니다. 상담을 예약하시겠습니까?"
    
    return {
        "score": ledger.total_score,
        "action": action,
        "message": message,
        "tier_breakdown": {
            "tier_1": ledger.tier_1_count,
            "tier_2": ledger.tier_2_count,
            "tier_3": ledger.tier_3_count
        },
        "requires_acknowledgement": ledger.requires_acknowledgement,
        "requires_escalation": ledger.requires_escalation
    }
