"""
[Domain Layer] Models
순수 비즈니스 로직 및 데이터 교환을 위한 Pydantic 모델 정의.
**경고:** 이 파일에는 SQLAlchemy(DB) 관련 코드가 포함되면 안 됩니다.
"""
from pydantic import BaseModel, Field
from datetime import date
from typing import Optional, List, Dict, Any

# Fact 모델 (세무 계산의 핵심 입력값)
class Fact(BaseModel):
    """사실관계 데이터 모델 (Pydantic)"""
    house_count: int = Field(ge=1, le=10, description="보유 주택 수")
    acquisition_date: date = Field(description="취득일")
    sale_date: date = Field(description="양도일")
    acquisition_price: int = Field(ge=0, description="취득가액")
    sale_price: int = Field(ge=0, description="양도가액")
    residence_years: float = Field(ge=0, description="거주 기간(년)")
    is_adjusted_area: bool = Field(default=False, description="조정대상지역 여부")
    new_house_acquisition_date: Optional[date] = Field(default=None, description="신규주택 취득일")
    
    @property
    def holding_period_years(self) -> float:
        """보유 기간 계산"""
        delta = self.sale_date - self.acquisition_date
        return delta.days / 365.0
    
    @property
    def profit(self) -> int:
        """양도차익 계산 (양도가액 - 취득가액)"""
        return self.sale_price - self.acquisition_price

    class Config:
        extra = "allow"  # 런타임에 계산된 속성(holding_years 등) 주입 허용

# 시나리오 모델 (순수 데이터)
class Scenario(BaseModel):
    """시나리오 정의"""
    id: str
    name: str
    description: str
    tax_type: str = Field(description="exempt, general, heavy 등")
    
    # 로직 조건
    # 예: "scenarios/SCENARIO_001.json"의 구조와 일치해야 함
    
class CalculationRequest(BaseModel):
    """계산 요청 DTO"""
    scenario_id: str
    facts: Fact

class TaxResult(BaseModel):
    """계산 결과 DTO"""
    payment_amount: int
    deductions: Dict[str, int] # 상세 공제 내역
    rate_applied: float # 적용 세율
    calculation_log: List[str] # 상세 계산 과정 (Audit용)
