"""
법령 데이터 수집 스크립트
www.law.go.kr DRF API → data/raw/ (XML) + data/processed/ (JSON chunks)

버전 관리 전략:
- 각 법령의 개정 이력을 모두 수집 (최근 YEARS_BACK년)
- 각 버전(MST)에 effective_date + expiration_date 부여
- chunk ID = {version_mst}_{조문키} → 버전별 고유성 보장
"""
import json
import ssl
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path

import requests
import urllib3
from requests.adapters import HTTPAdapter

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

OC = "jctax"
BASE_URL = "https://www.law.go.kr/DRF"
RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")
YEARS_BACK = 10  # 최근 N년치 개정 버전 수집


def _make_session() -> requests.Session:
    """law.go.kr SSL 호환성 우선 세션 — 재시도 3회 포함"""
    session = requests.Session()
    adapter = HTTPAdapter(max_retries=urllib3.Retry(total=3, backoff_factor=2))
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.verify = False  # law.go.kr TLS 핸드셰이크 호환성
    session.headers.update({"User-Agent": "Mozilla/5.0 (tax-rag collector)"})
    return session


_SESSION = _make_session()

TARGET_LAWS = [
    {"name": "소득세법",                    "mst": "285523", "category": "법률"},
    {"name": "소득세법 시행령",              "mst": "285631", "category": "대통령령"},
    {"name": "소득세법 시행규칙",            "mst": "284987", "category": "부령"},
    {"name": "조세특례제한법",              "mst": "285525", "category": "법률"},
    {"name": "조세특례제한법 시행령",        "mst": "283625", "category": "대통령령"},
    {"name": "조세특례제한법 시행규칙",      "mst": "284611", "category": "부령"},
]


# ── 버전 이력 조회 ────────────────────────────────────────────────────────────

def fetch_law_version_list(law_name: str) -> list[dict]:
    """
    법령명으로 개정 이력 상의 모든 버전 조회.
    반환: [{"mst", "effective_date", "promulgation_date", "expiration_date"}, ...]
    시행일 오름차순 정렬, 만료일 자동 계산.
    """
    url = f"{BASE_URL}/lawSearch.do"
    params = {
        "OC": OC,
        "target": "law",
        "query": law_name,
        "display": 100,
        "type": "XML",
    }
    resp = _SESSION.get(url, params=params, timeout=30)
    resp.raise_for_status()
    resp.encoding = "utf-8"

    try:
        root = ET.fromstring(resp.text.encode("utf-8"))
    except ET.ParseError:
        print(f"  ⚠ {law_name} 이력 XML 파싱 실패, 현행 버전만 사용")
        return []

    cutoff = (datetime.now() - timedelta(days=YEARS_BACK * 365)).strftime("%Y%m%d")

    versions = []
    for law_elem in root.findall(".//법령"):
        name_elem = law_elem.find("법령명한글")
        if name_elem is None or name_elem.text is None:
            continue
        if name_elem.text.strip() != law_name:
            continue

        mst_elem = law_elem.find("법령일련번호")
        eff_elem = law_elem.find("시행일자")
        prom_elem = law_elem.find("공포일자")

        if mst_elem is None or mst_elem.text is None:
            continue

        eff_date = eff_elem.text.strip() if eff_elem is not None and eff_elem.text else ""
        if eff_date and eff_date < cutoff:
            continue

        versions.append({
            "mst": mst_elem.text.strip(),
            "effective_date": eff_date,
            "promulgation_date": prom_elem.text.strip() if prom_elem is not None and prom_elem.text else "",
            "expiration_date": "",
        })

    if not versions:
        return []

    # 시행일 오름차순 정렬
    versions.sort(key=lambda x: x["effective_date"])

    # 만료일 = 다음 버전 시행일 전날
    for i, v in enumerate(versions[:-1]):
        next_eff = versions[i + 1]["effective_date"]
        if next_eff:
            exp_dt = datetime.strptime(next_eff, "%Y%m%d") - timedelta(days=1)
            v["expiration_date"] = exp_dt.strftime("%Y%m%d")

    # 마지막(현행) 버전은 만료일 없음
    return versions


# ── XML 수집 ──────────────────────────────────────────────────────────────────

def fetch_law_xml(mst: str) -> str:
    url = f"{BASE_URL}/lawService.do"
    params = {"OC": OC, "target": "law", "MST": mst, "type": "XML"}
    resp = _SESSION.get(url, params=params, timeout=30)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    return resp.text


# ── XML 파싱 → 청크 ───────────────────────────────────────────────────────────

def parse_xml_to_chunks(xml_text: str, law_info: dict, version: dict) -> list[dict]:
    """
    version: {"mst", "effective_date", "promulgation_date", "expiration_date"}
    chunk ID = {version_mst}_{조문키}
    """
    root = ET.fromstring(xml_text.encode("utf-8"))
    chunks = []

    law_name_elem = root.find(".//법령명한글")
    law_name = law_name_elem.text.strip() if law_name_elem is not None else law_info["name"]

    for 조문단위 in root.findall(".//조문단위"):
        조문키 = 조문단위.get("조문키", "")
        조문번호_elem = 조문단위.find("조문번호")
        조문여부_elem = 조문단위.find("조문여부")
        조문제목_elem = 조문단위.find("조문제목")
        시행일자_elem = 조문단위.find("조문시행일자")
        내용_elem = 조문단위.find("조문내용")

        조문번호 = 조문번호_elem.text.strip() if 조문번호_elem is not None and 조문번호_elem.text else ""
        조문여부 = 조문여부_elem.text.strip() if 조문여부_elem is not None and 조문여부_elem.text else ""
        조문제목 = 조문제목_elem.text.strip() if 조문제목_elem is not None and 조문제목_elem.text else ""
        시행일자 = 시행일자_elem.text.strip() if 시행일자_elem is not None and 시행일자_elem.text else version["effective_date"]
        내용 = 내용_elem.text.strip() if 내용_elem is not None and 내용_elem.text else ""

        항_list = []
        for 항 in 조문단위.findall(".//항"):
            항번호_elem = 항.find("항번호")
            항내용_elem = 항.find("항내용")
            호_list = []
            for 호 in 항.findall(".//호"):
                호번호_elem = 호.find("호번호")
                호내용_elem = 호.find("호내용")
                호_list.append({
                    "호번호": 호번호_elem.text.strip() if 호번호_elem is not None and 호번호_elem.text else "",
                    "호내용": 호내용_elem.text.strip() if 호내용_elem is not None and 호내용_elem.text else "",
                })
            항_list.append({
                "항번호": 항번호_elem.text.strip() if 항번호_elem is not None and 항번호_elem.text else "",
                "항내용": 항내용_elem.text.strip() if 항내용_elem is not None and 항내용_elem.text else "",
                "호": 호_list,
            })

        if not 내용 and not 항_list:
            continue

        full_text_parts = []
        if 내용:
            full_text_parts.append(내용)
        for 항 in 항_list:
            if 항["항내용"]:
                full_text_parts.append(f"  {항['항내용']}")
            for 호 in 항["호"]:
                if 호["호내용"]:
                    full_text_parts.append(f"    {호['호내용']}")

        chunk = {
            "id": f"{version['mst']}_{조문키}",
            "law_name": law_name,
            "law_mst": law_info["mst"],          # 법령 고유 ID (버전 무관)
            "version_mst": version["mst"],        # 이 버전의 MST
            "law_category": law_info["category"],
            "article_number": 조문번호,
            "article_type": 조문여부,
            "article_title": 조문제목,
            "effective_date": 시행일자,
            "expiration_date": version["expiration_date"],  # 빈 문자열 = 현행
            "promulgation_date": version["promulgation_date"],
            "content": 내용,
            "clauses": 항_list,
            "full_text": "\n".join(full_text_parts),
            "metadata": {
                "law_name": law_name,
                "article": 조문번호,
                "article_number": 조문번호,
                "article_title": 조문제목,
                "effective_date": 시행일자,
                "expiration_date": version["expiration_date"],
                "category": law_info["category"],
                "version_mst": version["mst"],
                "source": "law.go.kr",
            },
        }
        chunks.append(chunk)

    return chunks


# ── 메인 수집 ─────────────────────────────────────────────────────────────────

def collect_all():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    all_chunks = []

    for law in TARGET_LAWS:
        print(f"\n[{law['name']}] 개정 이력 조회 중...")

        # 버전 목록 조회
        versions = fetch_law_version_list(law["name"])

        if not versions:
            # 이력 조회 실패 시 현행 버전 단독 수집
            # effective_date=0, expiration_date=99991231 → Pinecone 날짜 필터에서 항상 통과
            print(f"  → 이력 없음, 현행 버전만 수집 (MST={law['mst']})")
            versions = [{
                "mst": law["mst"],
                "effective_date": "0",
                "promulgation_date": "",
                "expiration_date": "99991231",
            }]
        else:
            # 현행 MST가 목록에 없으면 추가
            existing_msts = {v["mst"] for v in versions}
            if law["mst"] not in existing_msts:
                versions.append({
                    "mst": law["mst"],
                    "effective_date": "",
                    "promulgation_date": "",
                    "expiration_date": "",
                })
            print(f"  → {len(versions)}개 버전 발견")

        law_chunks = []
        for v in versions:
            raw_path = RAW_DIR / f"{law['name'].replace(' ', '_')}_{v['mst']}.xml"

            if raw_path.exists():
                xml_text = raw_path.read_text(encoding="utf-8")
                print(f"  → 캐시 사용: {v['mst']} (시행일: {v['effective_date'] or '불명'})")
            else:
                try:
                    xml_text = fetch_law_xml(v["mst"])
                    raw_path.write_text(xml_text, encoding="utf-8")
                    print(f"  → XML 저장: {v['mst']} (시행일: {v['effective_date'] or '불명'}, {len(xml_text):,} bytes)")
                    time.sleep(0.5)
                except Exception as e:
                    print(f"  ⚠ {v['mst']} 수집 실패: {e}")
                    continue

            chunks = parse_xml_to_chunks(xml_text, law, v)
            print(f"     청크: {len(chunks)}개 | 만료일: {v['expiration_date'] or '현행'}")
            law_chunks.extend(chunks)

        # 법령별 통합 JSON
        processed_path = PROCESSED_DIR / f"{law['name'].replace(' ', '_')}_{law['mst']}.json"
        processed_path.write_text(
            json.dumps(law_chunks, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        all_chunks.extend(law_chunks)

    # 전체 통합 JSON
    all_path = PROCESSED_DIR / "all_chunks.json"
    all_path.write_text(
        json.dumps(all_chunks, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n[완료] 총 {len(all_chunks)}개 청크 → {all_path}")
    return all_chunks


if __name__ == "__main__":
    collect_all()
