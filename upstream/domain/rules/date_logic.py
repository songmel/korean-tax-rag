"""
[L1 Pure Function] 양도시기 판정 로직
날짜 계산만 담당하는 순수 함수
"""
from datetime import date
from typing import Optional


def calculate_transfer_date(
    c_date: date, 
    r_date: date, 
    a_date: Optional[date] = None
) -> dict:
    """
    [L1 Pure Function] 양도시기 판정 로직
    
    Args:
        c_date: 계약서상 잔금일 (Contract balance date)
        r_date: 등기접수일 (Registry receipt date)
        a_date: 실제 잔금일 (Actual balance date, optional)
    
    Returns:
        dict: {
            "date": date,      # 확정된 양도일
            "source": str      # 판정 근거 ("contract" | "registry" | "actual_payment")
        }
    
    Logic:
        1. 실제 잔금일(a_date)이 있으면 우선 사용
        2. 없으면 계약서 잔금일(c_date) 사용
        3. 위 날짜와 등기일(r_date) 중 빠른 날짜 선택
    """
    # 1. 비교할 잔금일 결정
    target_balance_date = a_date if a_date else c_date
    source = "actual_payment" if a_date else "contract"
    
    # 2. 등기일과 비교하여 빠른 날짜 선택
    if r_date < target_balance_date:
        return {
            "date": r_date, 
            "source": "registry"
        }
    
    return {
        "date": target_balance_date, 
        "source": source
    }
