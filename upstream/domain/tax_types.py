"""
[Domain Layer] Tax Type Definitions
세금 유형 열거형. 양도세 → 증여세 → 상속세 확장을 위한 기반 구조.
"""
import enum


class TaxType(str, enum.Enum):
    """세금 유형"""
    TRANSFER = "transfer"       # 양도소득세
    GIFT = "gift"               # 증여세 (2차 확장)
    INHERITANCE = "inheritance"  # 상속세 (3차 확장)
