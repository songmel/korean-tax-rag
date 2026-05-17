from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class IntentType(str, Enum):
    ANSWER = "answer"
    QUESTION = "question"
    SWITCH_OWNER = "switch_owner"
    SWITCH_PROPERTY = "switch_property"
    ADD_OWNER = "add_owner"
    ADD_PROPERTY = "add_property"
    ABORT = "abort"
    BACK = "back"
    CONFIRM = "confirm"
    DENY = "deny"
    AMBIGUOUS = "ambiguous"


class ConflictScope(str, Enum):
    FACT_LEDGER = "fact_ledger"
    OWNER_PROFILE = "owner_profile"
    USER_PROPERTY = "user_property"
    RELATION = "relation"
    INTENT = "intent"


class ConflictResolution(str, Enum):
    PENDING = "pending"
    USER_CONFIRMED = "user_confirmed"
    SYSTEM_CONFIRMED = "system_confirmed"
    BOTH_KEPT = "both_kept"
    ESCALATED = "escalated"


class ActiveSubflow(BaseModel):
    type: str
    step: str
    owner_id: Optional[str] = None
    property_id: Optional[str] = None
    started_at: datetime


class FactConflict(BaseModel):
    scope: ConflictScope
    field: str
    user_input: str
    system_value: Optional[str] = None
    source: Optional[str] = None
    detected_at: datetime
    resolution: ConflictResolution = ConflictResolution.PENDING


class IntentRecord(BaseModel):
    turn: int
    intent: IntentType
    confidence: float = Field(ge=0.0, le=1.0)
    detected_entities: List[str] = Field(default_factory=list)
    ambiguous: bool = False


class FactLedgerSlim(BaseModel):
    """이번 상담 세션의 작업 노트.

    영속 데이터(취득가액, 양도가액, household_members 등)는 OwnerProfile/UserProperty에 저장.
    여기엔 세션 동안만 유효한 포커스/진행상태/충돌/의도 로그만 담는다.
    """

    active_subflow: Optional[ActiveSubflow] = None
    selected_owner_ids: List[str] = Field(default_factory=list)
    selected_property_ids: List[str] = Field(default_factory=list)
    focus_owner_id: Optional[str] = None

    fact_conflicts: List[FactConflict] = Field(default_factory=list)
    intent_history: List[IntentRecord] = Field(default_factory=list)

    contract_upload_slots: List[str] = Field(default_factory=list)
    pending_ui_signal: Optional[str] = None

    pending_doc_uploads: List[str] = Field(default_factory=list)
    last_user_message: Optional[str] = None


_PERSISTENT_FACT_KEYS = frozenset({
    "asset_kind",
    "house_location_address",
    "acquisition_cause",
    "acquisition_date",
    "acquisition_price",
    "transfer_date",
    "sale_date",
    "sale_price_total",
    "sale_price_building",
    "sale_price_land",
    "balance_payment_date",
    "use_approval_date",
    "joint_ownership_yn",
    "joint_owner_info",
    "rental_business_yn",
    "long_term_rental_yn",
    "remodeling_yn",
    "necessary_expenses",
    "installment_sale_yn",
    "mutual_rental_yn",
    "official_price",
    "official_price_date",
    "real_trade_price",
    "is_adjustment_area",
    "holding_period_years",
    "residence_period_years",
    "household_members",
    "household_member_count",
    "registrant_address",
    "address_history",
    "family_relations",
    "household_house_count",
    "owner_name",
    "phone",
    "relationship",
    "household_head_name",
    "household_head_relation",
    "has_bunyang",
    "bunyang_info",
    "overseas_residence_yn",
    "auth_status",
})


def is_persistent_fact_key(key: str) -> bool:
    return key in _PERSISTENT_FACT_KEYS


def slim_from_dict(legacy_dict: Dict[str, Any]) -> FactLedgerSlim:
    payload: Dict[str, Any] = {}
    if "_active_subflow" in legacy_dict and legacy_dict["_active_subflow"]:
        payload["active_subflow"] = legacy_dict["_active_subflow"]
    payload["selected_owner_ids"] = legacy_dict.get("_selected_owner_ids", []) or []
    payload["selected_property_ids"] = (
        legacy_dict.get("_selected_property_ids", [])
        or legacy_dict.get("selected_property_ids", [])
        or []
    )
    payload["focus_owner_id"] = legacy_dict.get("_focus_owner_id")
    payload["fact_conflicts"] = legacy_dict.get("_fact_conflicts", []) or []
    payload["intent_history"] = legacy_dict.get("_intent_history", []) or []
    payload["contract_upload_slots"] = (
        legacy_dict.get("_contract_upload_slots", []) or []
    )
    payload["pending_ui_signal"] = legacy_dict.get("_pending_ui_signal")
    payload["pending_doc_uploads"] = legacy_dict.get("_pending_doc_uploads", []) or []
    payload["last_user_message"] = legacy_dict.get("_last_user_message")
    return FactLedgerSlim(**payload)


def slim_to_legacy_dict(slim: FactLedgerSlim) -> Dict[str, Any]:
    return {
        "_active_subflow": slim.active_subflow.model_dump() if slim.active_subflow else None,
        "_selected_owner_ids": list(slim.selected_owner_ids),
        "_selected_property_ids": list(slim.selected_property_ids),
        "_focus_owner_id": slim.focus_owner_id,
        "_fact_conflicts": [c.model_dump() for c in slim.fact_conflicts],
        "_intent_history": [i.model_dump() for i in slim.intent_history],
        "_contract_upload_slots": list(slim.contract_upload_slots),
        "_pending_ui_signal": slim.pending_ui_signal,
        "_pending_doc_uploads": list(slim.pending_doc_uploads),
        "_last_user_message": slim.last_user_message,
    }
