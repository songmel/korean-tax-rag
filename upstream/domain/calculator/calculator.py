"""
[L1 Core Engine] 세금 계산기 (Data-Driven Refactoring)

이제 하드코딩된 파이프라인 대신, DB(Scenario Object)에 저장된
'logic_config["pipeline"]'을 읽어서 동적으로 블록을 조립합니다.
"""

import json
import os
from typing import Dict, Any, Optional

from app.domain.models import Fact, Scenario
from app.domain.rules.blocks import (
    ScenarioBuilder,
    BLOCK_REGISTRY,
    LogicBlock 
)

class TaxCalculator:
    def __init__(self, rules_path: str = None):
        from app.infrastructure.config import settings
        self.rules_path = rules_path or os.path.join(settings.BASE_DIR, "data", "rules", "2025_tax_rules.json")
        # 규칙 로드 (예: 기본공제액 등 파라미터)
        full_path = self.rules_path
        
        self.rules = {}
        if os.path.exists(full_path):
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    self.rules = json.load(f).get("2025", {})
            except:
                pass
        
        # Default Fallback
        if not self.rules:
            self.rules = {"capital_gains": {"basic_deduction": 2_500_000}}

    def calculate(self, fact: Fact, scenario: Scenario) -> dict:
        """
        Data-Driven Main Entry Point
        """
        # 1. 블록 빌더 초기화
        builder = ScenarioBuilder(scenario.id)
        
        # 2. 파이프라인 로드 (DB -> Object)
        # scenario.logic_config는 DB의 JSON 컬럼
        config = scenario.logic_config or {}
        
        # Pydantic 호환성 처리
        if hasattr(config, "model_dump"): 
             config = config.model_dump()
        elif hasattr(config, "dict"): 
             config = config.dict()
             
        pipeline_codes = config.get("pipeline", [])
        
        # [Fallback] DB에 파이프라인 설정이 없는 경우 기본값 (안전장치)
        if not pipeline_codes:
            print(f"⚠️ [Calculator] 시나리오 {scenario.id}에 파이프라인 설정 없음. 기본값 적용.")
            # 가장 기본적인 계산 절차 (보유기간 -> 주택수 -> 조정지역 -> 거주요건 -> 세율)
            pipeline_codes = ["BLK_PERIOD", "BLK_COUNT", "BLK_AREA", "BLK_RESIDENCE", "BLK_RATE"]

        # 3. 동적 블록 조립 (Dynamic Assembly)
        for block_code in pipeline_codes:
            block_cls = BLOCK_REGISTRY.get(block_code)
            if block_cls:
                # 블록 인스턴스화
                builder.add_block(block_cls())
            else:
                print(f"⚠️ [Calculator] 알 수 없는 블록 코드: {block_code}")
                
        # 4. 실행 (Fact 객체 전달)
        # Builder가 내부적으로 block.execute(fact)를 순차 실행
        execution_result = builder.execute(fact)
        
        # 5. 결과 반환
        final_context = execution_result['final_fact']
        
        if not execution_result['success']:
            return {
                "status": "error",
                "message": execution_result.get('error', 'Unknown Error'),
                "tax_amount": 0,
                "breakdown": {}
            }
        
        # 계산된 세액 등 추출 (Fact 객체의 속성으로 접근하거나 dict 변환)
        # Fact 객체이므로 getattr 사용하거나 .dict()
        tax_amt = getattr(final_context, "tax_amount", 0)
        
        # Fact가 Pydantic 모델인 경우
        if hasattr(final_context, "dict"):
            result_dict = final_context.dict()
        else:
            result_dict = final_context # 이미 dict라면
            
        return {
            "status": "success",
            "tax_amount": result_dict.get("tax_amount", 0),
            "taxable_income": result_dict.get("taxable_income", 0),
            "description": f"{scenario.title} 적용 완료",
            "breakdown": {
                "profit": result_dict.get("profit", 0), # 양도차익
                "tax_base": result_dict.get("tax_base", 0), # 과세표준
                "tax_rate": result_dict.get("tax_rate", 0), # 세율
                "block_results": execution_result.get("block_results", [])
            }
        }
