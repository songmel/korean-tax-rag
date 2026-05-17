"""
[L1 Core Logic] Modular Logic Block System (Refactored)

- Dict 의존성 제거 -> Pydantic Fact 객체 사용
- 불필요한 validate_input 제거 (모델이 보장함)
- Type Hinting 강화
- Block Result Chaining via Dynamic Fact Injection
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import date, datetime

from app.domain.models import Fact

@dataclass
class BlockResult:
    """블록 실행 결과"""
    success: bool
    # 계산된 중간값이나 결과값
    value: Dict[str, Any] = field(default_factory=dict) 
    message: str = ""
    block_id: str = ""
    execution_time_ms: float = 0.0


class LogicBlock(ABC):
    """모든 로직 블록의 베이스 클래스 (Type-Safe)"""
    
    block_id: str = "UNKNOWN"
    block_name: str = "Unknown Block"
    
    @abstractmethod
    def execute(self, fact: Fact) -> BlockResult:
        """
        [변경점] Dict[str, Any] -> Fact
        이제 IDE가 fact.acquisition_date 자동완성을 지원합니다.
        """
        pass


# ============================================================
# Concrete Blocks
# ============================================================

class PeriodCalculatorBlock(LogicBlock):
    block_id = "BLK_PERIOD"
    block_name = "기간 계산 블록"
    
    def __init__(self, include_start_day: bool = True):
        self.include_start_day = include_start_day
    
    def execute(self, fact: Fact) -> BlockResult:
        if fact.sale_date < fact.acquisition_date:
            return BlockResult(
                success=False, 
                message=f"시간 역행: 취득({fact.acquisition_date}) > 양도({fact.sale_date})",
                block_id=self.block_id
            )
        
        days = (fact.sale_date - fact.acquisition_date).days
        if self.include_start_day:
            days += 1
            
        years = days / 365.0
        
        return BlockResult(
            success=True,
            value={
                "holding_days": days,
                "holding_years": round(years, 2),
                "holding_years_int": int(years)
            },
            message=f"보유기간: {days}일 ({years:.2f}년)",
            block_id=self.block_id
        )


class AdjustedAreaBlock(LogicBlock):
    block_id = "BLK_AREA"
    block_name = "조정지역 판정 블록"
    
    def execute(self, fact: Fact) -> BlockResult:
        return BlockResult(
            success=True,
            value={"is_adjusted_area": fact.is_adjusted_area},
            message=f"조정지역: {fact.is_adjusted_area}",
            block_id=self.block_id
        )


class HouseCountBlock(LogicBlock):
    block_id = "BLK_COUNT"
    block_name = "주택 수 판정 블록"
    
    def execute(self, fact: Fact) -> BlockResult:
        # Fact에 동적으로 주입된 속성들 확인 (없으면 기본값)
        has_pre_sale = getattr(fact, "has_pre_sale_rights", False)
        has_occupancy = getattr(fact, "has_occupancy_rights", False)
        
        total_count = fact.house_count
        if has_pre_sale: total_count += 1
        if has_occupancy: total_count += 1
        
        return BlockResult(
            success=True,
            value={
                "total_house_count": total_count,
                "is_single_house": total_count == 1,
                "is_multi_house": total_count >= 2
            },
            message=f"주택 수: {total_count}채",
            block_id=self.block_id
        )


class ResidenceRequirementBlock(LogicBlock):
    block_id = "BLK_RESIDENCE"
    block_name = "거주 요건 판정 블록"
    
    def __init__(self, required_years: float = 2.0):
        self.required_years = required_years
    
    def execute(self, fact: Fact) -> BlockResult:
        # 동적 주입된 is_adjusted_area가 있으면 우선 사용
        is_adjusted = getattr(fact, "is_adjusted_area", fact.is_adjusted_area)
        
        meets = True
        if is_adjusted:
            meets = fact.residence_years >= self.required_years
            
        return BlockResult(
            success=True,
            value={
                "meets_residence_requirement": meets,
                "required_residence_years": self.required_years if is_adjusted else 0
            },
            message=f"거주요건: {'충족' if meets else '미충족'}",
            block_id=self.block_id
        )


class HighValueHouseBlock(LogicBlock):
    block_id = "BLK_HIGH_VALUE"
    block_name = "고가주택 안분 블록"
    THRESHOLD = 1_200_000_000

    def execute(self, fact: Fact) -> BlockResult:
        total_profit = fact.profit
        
        if fact.sale_price <= self.THRESHOLD:
            return BlockResult(
                success=True,
                value={
                    "is_high_value": False,
                    "taxable_ratio": 0.0,
                    "taxable_profit": 0,
                    "exempt_profit": total_profit
                },
                message="고가주택 아님 (12억 이하)",
                block_id=self.block_id
            )
            
        taxable_ratio = (fact.sale_price - self.THRESHOLD) / fact.sale_price
        taxable_profit = int(total_profit * taxable_ratio)
        exempt_profit = total_profit - taxable_profit
        
        return BlockResult(
            success=True,
            value={
                "is_high_value": True,
                "taxable_ratio": round(taxable_ratio, 4),
                "taxable_profit": taxable_profit,
                "exempt_profit": exempt_profit
            },
            message=f"고가주택 과세대상: {taxable_profit:,}원 ({taxable_ratio*100:.1f}%)",
            block_id=self.block_id
        )


class LongTermDeductionBlock(LogicBlock):
    block_id = "BLK_DEDUCTION"
    block_name = "장기보유특별공제 블록"
    MIN_HOLDING_YEARS = 3
    
    def execute(self, fact: Fact) -> BlockResult:
        # 동적 주입된 holding_years 사용 (없으면 계산 프로퍼티)
        holding_years = getattr(fact, "holding_years", fact.holding_period_years)
        
        if holding_years < self.MIN_HOLDING_YEARS:
            return BlockResult(
                success=True,
                value={"deduction_rate": 0.0},
                message="장특공제 미적용 (3년 미만)",
                block_id=self.block_id
            )
            
        is_single_house = getattr(fact, "is_single_house", True)
        
        if is_single_house:
            h_rate = min(int(holding_years) * 0.04, 0.40)
            r_rate = min(int(fact.residence_years) * 0.04, 0.40)
            rate = min(h_rate + r_rate, 0.80)
            msg = f"장특공제 {int(rate*100)}% (1세대 1주택)"
        else:
            rate = min(int(holding_years) * 0.02, 0.30)
            msg = f"장특공제 {int(rate*100)}% (일반)"
            
        return BlockResult(
            success=True,
            value={"deduction_rate": rate},
            message=msg,
            block_id=self.block_id
        )


class TaxRateBlock(LogicBlock):
    block_id = "BLK_RATE"
    block_name = "세율 적용 블록"
    
    BASIC_RATES = [
        {"limit": 14_000_000, "rate": 0.06, "deduction": 0},
        {"limit": 50_000_000, "rate": 0.15, "deduction": 1_260_000},
        {"limit": 88_000_000, "rate": 0.24, "deduction": 5_760_000},
        {"limit": 150_000_000, "rate": 0.35, "deduction": 15_440_000},
        {"limit": 300_000_000, "rate": 0.38, "deduction": 19_940_000},
        {"limit": 500_000_000, "rate": 0.40, "deduction": 25_940_000},
        {"limit": 1_000_000_000, "rate": 0.42, "deduction": 35_940_000},
        {"limit": None, "rate": 0.45, "deduction": 65_940_000},
    ]

    def execute(self, fact: Fact) -> BlockResult:
        # 이전 블록에서 주입된 tax_base 확인
        tax_base = getattr(fact, "tax_base", 0)
        holding_years = getattr(fact, "holding_years", fact.holding_period_years)
        
        if holding_years < 1:
            rate_type = "SHORT_TERM_1Y"
            rate = 0.70
            deduction = 0
        elif holding_years < 2:
            rate_type = "SHORT_TERM_2Y"
            rate = 0.60
            deduction = 0
        else:
            rate_type = "BASIC"
            bracket = self._get_bracket(tax_base)
            rate = bracket["rate"]
            deduction = bracket["deduction"]
            
        return BlockResult(
            success=True,
            value={
                "rate_type": rate_type,
                "rate": rate,
                "progressive_deduction": deduction
            },
            message=f"세율 {int(rate*100)}% ({rate_type})",
            block_id=self.block_id
        )

    def _get_bracket(self, tax_base: int) -> dict:
        for bracket in self.BASIC_RATES:
            if bracket["limit"] is None or tax_base <= bracket["limit"]:
                return bracket
        return self.BASIC_RATES[-1]


# ============================================================
# Scenario Builder
# ============================================================

class ScenarioBuilder:
    def __init__(self, scenario_id: str = "CUSTOM"):
        self.scenario_id = scenario_id
        self.blocks: List[LogicBlock] = []
    
    def add_block(self, block: LogicBlock) -> "ScenarioBuilder":
        self.blocks.append(block)
        return self
    
    def execute(self, fact: Fact) -> Dict[str, Any]:
        """
        블록체인 실행
        각 블록의 결과(Result.value)를 Fact 객체에 동적 주입(Injection)하여
        다음 블록이 참조할 수 있도록 함.
        """
        results_log = []
        accumulated_values = {}
        
        start_time_total = datetime.now()
        
        # Fact 객체가 오염되지 않도록 원본 보존하고 싶다면 copy() 사용해야 함
        # 여기서는 Chaining을 위해 런타임 주입을 허용했으므로 그대로 사용
        
        try:
            for block in self.blocks:
                start = datetime.now()
                
                # [핵심] Fact 객체 전달
                result = block.execute(fact)
                
                result.execution_time_ms = (datetime.now() - start).total_seconds() * 1000
                
                # 결과 로깅
                results_log.append({
                    "block_id": result.block_id,
                    "success": result.success,
                    "message": result.message,
                    "value": result.value,
                    "execution_time_ms": result.execution_time_ms
                })
                
                if not result.success:
                    return {
                        "success": False,
                        "scenario_id": self.scenario_id,
                        "error": result.message,
                        "block_results": results_log
                    }
                
                # [핵심] Dynamic Context Injection
                # 블록의 출력값을 Fact 객체에 주입하여 다음 블록이 사용할 수 있게 함
                if result.value:
                    accumulated_values.update(result.value)
                    for k, v in result.value.items():
                        setattr(fact, k, v)
                        
        except Exception as e:
            return {
                "success": False, 
                "scenario_id": self.scenario_id,
                "error": f"System Error: {str(e)}",
                "block_results": results_log
            }

        total_time = (datetime.now() - start_time_total).total_seconds() * 1000
        
        # 최종 결과 반환
        return {
            "success": True,
            "scenario_id": self.scenario_id,
            "final_fact": {**fact.dict(), **accumulated_values}, # 원본+계산값
            "block_results": results_log,
            "execution_time_ms": total_time
        }


# ============================================================
# Registry
# ============================================================

BLOCK_REGISTRY = {
    "BLK_PERIOD": PeriodCalculatorBlock,
    "BLK_AREA": AdjustedAreaBlock,
    "BLK_COUNT": HouseCountBlock,
    "BLK_RESIDENCE": ResidenceRequirementBlock,
    "BLK_RATE": TaxRateBlock,
    "BLK_DEDUCTION": LongTermDeductionBlock,
    "BLK_HIGH_VALUE": HighValueHouseBlock,
}

def get_block(block_id: str) -> Optional[LogicBlock]:
    block_class = BLOCK_REGISTRY.get(block_id)
    return block_class() if block_class else None

def create_scenario_from_block_ids(scenario_id: str, block_ids: List[str]) -> ScenarioBuilder:
    builder = ScenarioBuilder(scenario_id)
    for block_id in block_ids:
        block = get_block(block_id)
        if block:
            builder.add_block(block)
    return builder
