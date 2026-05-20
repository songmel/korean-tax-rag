"""
행정 고시 수집 모듈

수집 범위 확장 로드맵:
  ① 세법   : law.go.kr           → src/ingestion/collect.py  (기구현)
  ② 행정   : 국토부/MOEF 고시    → 이 모듈 (조정대상지역, 투기과열지구, 공시지가 기준)
  ③ 금융   : 금융위/금감원 고시  → 이 모듈 (DSR, LTV, 특례보금자리론 한도)

관계부처 합동 발표 패턴:
  부동산 대책 = 기획재정부 + 국토교통부 + 금융위원회 동시 발표
  → ① 세제(collect.py) + ② 행정(이 모듈) + ③ 금융(이 모듈)을 함께 수집해야
    "비과세 요건 + 현재 조정대상지역 여부 + DSR 규제" 통합 상담이 가능함

API 연동 현황:
  ② 조정대상지역: 국토교통부 공공데이터포털 API (TODO: MOEF_API_KEY 발급)
  ② 투기과열지구: 동일 API
  ③ 금융규제:     금융위원회 OpenAPI (TODO: FSC_API_KEY 발급)

환경변수:
  MOEF_API_KEY=   # 국토교통부 공공데이터포털 API 키
  FSC_API_KEY=    # 금융위원회 OpenAPI 키
  ADMIN_NOTICES_DIR=data/admin_notices  # 수집 결과 저장 경로
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import date
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

MOEF_API_KEY = os.getenv("MOEF_API_KEY", "")
FSC_API_KEY = os.getenv("FSC_API_KEY", "")
NOTICES_DIR = Path(os.getenv("ADMIN_NOTICES_DIR", "data/admin_notices"))


# ── 데이터 모델 ────────────────────────────────────────────────────────────────


@dataclass
class AdjustmentAreaRecord:
    """
    조정대상지역 / 투기과열지구 단건 레코드.

    세법 적용 기준:
      - 취득일 기준 조정대상지역 여부 → 2년 거주요건 발생 (소령 §154①)
      - 양도일 기준 조정대상지역 여부 → 다주택 중과세율 적용 (소법 §104①)
      두 날짜를 별도로 조회해야 함.
    """
    region: str                         # 지역명 ("서울특별시 강남구" 등)
    area_type: str                      # "조정대상지역" | "투기과열지구" | "투기지역"
    designated_at: date                 # 지정일
    released_at: Optional[date]         # 해제일 (None = 현재 유효)
    announcement_no: str                # 고시 번호 ("국토교통부고시 제2021-1588호" 등)
    source_url: Optional[str] = None    # 원문 URL

    @property
    def is_active(self) -> bool:
        return self.released_at is None

    def is_designated_as_of(self, target_date: date) -> bool:
        """target_date 시점에 이 지역이 지정 상태였는지 확인."""
        return (
            self.designated_at <= target_date
            and (self.released_at is None or self.released_at > target_date)
        )


@dataclass
class FinancialRegulationRecord:
    """
    금융 규제 단건 레코드 (DSR/LTV/보금자리론 등).

    확장 목표:
      - DSR 40% 전 금융권 적용 (2022.07~)
      - LTV 지역별/주택수별 차등
      - 특례보금자리론 한도 및 적용 기간
      - 정책모기지 금리
    """
    regulation_type: str        # "DSR" | "LTV" | "보금자리론" | "정책금리"
    target: str                 # 적용 대상 ("전 금융권", "강남3구", ...)
    value: str                  # 규제값 ("40%", "50%", ...)
    effective_from: date
    effective_to: Optional[date]
    announcement_no: str
    source_url: Optional[str] = None


@dataclass
class AdminNoticesDB:
    """
    수집된 행정 고시 전체 보관소.
    JSON 파일로 직렬화해 Pinecone과 별도로 관리.
    """
    adjustment_areas: list[AdjustmentAreaRecord] = field(default_factory=list)
    financial_regulations: list[FinancialRegulationRecord] = field(default_factory=list)
    last_updated: Optional[str] = None


# ── 조정대상지역 조회 헬퍼 ─────────────────────────────────────────────────────


def resolve_adjustment_area(region: str, target_date: date, db: AdminNoticesDB) -> bool:
    """
    region이 target_date 시점에 조정대상지역이었는지 조회.
    DB가 비어있으면 False 반환 (수집 미완료 상태).

    사용처:
      - L1 RAGQueryInput 생성 시 adjustment_area_at_acquisition / _at_transfer 계산
      - fact_input.py FlatFactInput → RAGQueryInput 변환 시
    """
    for rec in db.adjustment_areas:
        if rec.area_type == "조정대상지역" and rec.region in region:
            if rec.is_designated_as_of(target_date):
                return True
    return False


def load_db() -> AdminNoticesDB:
    """저장된 DB 로드. 파일 없으면 빈 DB 반환."""
    path = NOTICES_DIR / "admin_notices_db.json"
    if not path.exists():
        return AdminNoticesDB()
    raw = json.loads(path.read_text(encoding="utf-8"))

    areas = [
        AdjustmentAreaRecord(
            region=r["region"],
            area_type=r["area_type"],
            designated_at=date.fromisoformat(r["designated_at"]),
            released_at=date.fromisoformat(r["released_at"]) if r.get("released_at") else None,
            announcement_no=r["announcement_no"],
            source_url=r.get("source_url"),
        )
        for r in raw.get("adjustment_areas", [])
    ]
    fins = [
        FinancialRegulationRecord(
            regulation_type=r["regulation_type"],
            target=r["target"],
            value=r["value"],
            effective_from=date.fromisoformat(r["effective_from"]),
            effective_to=date.fromisoformat(r["effective_to"]) if r.get("effective_to") else None,
            announcement_no=r["announcement_no"],
            source_url=r.get("source_url"),
        )
        for r in raw.get("financial_regulations", [])
    ]
    return AdminNoticesDB(
        adjustment_areas=areas,
        financial_regulations=fins,
        last_updated=raw.get("last_updated"),
    )


def save_db(db: AdminNoticesDB) -> None:
    NOTICES_DIR.mkdir(parents=True, exist_ok=True)
    path = NOTICES_DIR / "admin_notices_db.json"

    def _serial(obj):
        if isinstance(obj, date):
            return obj.isoformat()
        return obj

    raw = {
        "adjustment_areas": [
            {k: _serial(v) for k, v in asdict(r).items()}
            for r in db.adjustment_areas
        ],
        "financial_regulations": [
            {k: _serial(v) for k, v in asdict(r).items()}
            for r in db.financial_regulations
        ],
        "last_updated": db.last_updated,
    }
    path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")


# ── 수집 스텁 ──────────────────────────────────────────────────────────────────


async def collect_adjustment_areas() -> list[AdjustmentAreaRecord]:
    """
    국토교통부 공공데이터포털 API에서 조정대상지역 현황 수집.

    API: data.go.kr > 국토교통부_투기과열지구·조정대상지역 고시 현황
    환경변수: MOEF_API_KEY

    TODO:
      1. data.go.kr에서 API 키 발급 (MOEF_API_KEY)
      2. 엔드포인트 확인 후 아래 구현 채우기
      3. 응답 파싱: region, designated_at, released_at, announcement_no 추출
    """
    if not MOEF_API_KEY:
        raise EnvironmentError(
            "MOEF_API_KEY 미설정 — data.go.kr에서 국토교통부 API 키 발급 후 .env에 추가"
        )
    # TODO: implement
    # async with httpx.AsyncClient() as client:
    #     resp = await client.get(
    #         "https://api.data.go.kr/openapi/tn_pubr_public_aptrnk_ctprvn_api",
    #         params={"serviceKey": MOEF_API_KEY, "type": "json"},
    #     )
    raise NotImplementedError("국토교통부 API 구현 예정")


async def collect_financial_regulations() -> list[FinancialRegulationRecord]:
    """
    금융위원회 DSR/LTV 규제 현황 수집.

    대상 규제:
      - DSR 40% (2022.07~ 전 금융권, 총대출 1억 초과)
      - LTV: 무주택/1주택/다주택 × 조정/비조정 조합으로 6단계
      - 특례보금자리론: 한도, 금리, 적용 기간

    TODO:
      1. 금융위 OpenAPI (fsc.go.kr) 또는 보도자료 크롤링
      2. FSC_API_KEY 발급 후 .env에 추가
    """
    if not FSC_API_KEY:
        raise EnvironmentError(
            "FSC_API_KEY 미설정 — fsc.go.kr에서 금융위원회 API 키 발급 후 .env에 추가"
        )
    raise NotImplementedError("금융위원회 API 구현 예정")


async def run_collect_all() -> AdminNoticesDB:
    """
    전체 행정/금융 고시 수집 실행.

    세법 수집(collect.py)과 함께 주기적으로 실행:
      python -m src.ingestion.collect        # 세법
      python -m src.ingestion.admin_notices  # 행정·금융
    """
    import time
    db = load_db()

    try:
        areas = await collect_adjustment_areas()
        db.adjustment_areas = areas
        print(f"조정대상지역 {len(areas)}건 수집 완료")
    except NotImplementedError as e:
        print(f"[SKIP] 조정대상지역: {e}")

    try:
        fins = await collect_financial_regulations()
        db.financial_regulations = fins
        print(f"금융규제 {len(fins)}건 수집 완료")
    except NotImplementedError as e:
        print(f"[SKIP] 금융규제: {e}")

    db.last_updated = time.strftime("%Y-%m-%dT%H:%M:%SZ")
    save_db(db)
    return db


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_collect_all())
