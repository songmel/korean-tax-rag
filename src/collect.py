"""
법령 데이터 수집 스크립트
www.law.go.kr DRF API → data/raw/ (XML) + data/processed/ (JSON chunks)
"""
import os
import json
import time
import requests
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime

OC = "jctax"
BASE_URL = "https://www.law.go.kr/DRF"
RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")

# 수집 대상 법령
TARGET_LAWS = [
    {"name": "소득세법",         "mst": "285523", "category": "법률"},
    {"name": "소득세법 시행령",   "mst": "285631", "category": "대통령령"},
    {"name": "소득세법 시행규칙", "mst": "284987", "category": "부령"},
    {"name": "조세특례제한법",    "mst": "285525", "category": "법률"},
    {"name": "조세특례제한법 시행령", "mst": "283625", "category": "대통령령"},
    {"name": "조세특례제한법 시행규칙", "mst": "284611", "category": "부령"},
]


def fetch_law_xml(mst: str) -> str:
    url = f"{BASE_URL}/lawService.do"
    params = {"OC": OC, "target": "law", "MST": mst, "type": "XML"}
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    return resp.text


def parse_xml_to_chunks(xml_text: str, law_info: dict) -> list[dict]:
    root = ET.fromstring(xml_text.encode("utf-8"))
    chunks = []

    # 법령 기본 정보
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
        시행일자 = 시행일자_elem.text.strip() if 시행일자_elem is not None and 시행일자_elem.text else ""
        내용 = 내용_elem.text.strip() if 내용_elem is not None and 내용_elem.text else ""

        # 항/호/목 수집
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

        # 전체 텍스트 조합 (RAG 검색용)
        full_text_parts = []
        if 조문제목:
            full_text_parts.append(f"제{조문번호}조({조문제목})")
        if 내용:
            full_text_parts.append(내용)
        for 항 in 항_list:
            if 항["항내용"]:
                full_text_parts.append(f"  ① {항['항내용']}" if 항["항번호"] == "1" else f"  {항['항번호']} {항['항내용']}")
            for 호 in 항["호"]:
                if 호["호내용"]:
                    full_text_parts.append(f"    {호['호번호']}. {호['호내용']}")

        chunk = {
            "id": f"{law_info['mst']}_{조문키}",
            "law_name": law_name,
            "law_mst": law_info["mst"],
            "law_category": law_info["category"],
            "article_number": 조문번호,
            "article_type": 조문여부,
            "article_title": 조문제목,
            "effective_date": 시행일자,
            "content": 내용,
            "clauses": 항_list,
            "full_text": "\n".join(full_text_parts),
            "metadata": {
                "law_name": law_name,
                "article": 조문번호,
                "effective_date": 시행일자,
                "category": law_info["category"],
                "source": "law.go.kr",
            }
        }
        chunks.append(chunk)

    return chunks


def collect_all():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    all_chunks = []

    for law in TARGET_LAWS:
        print(f"\n[{law['name']}] 수집 중... (MST={law['mst']})")

        # 1. XML 저장
        raw_path = RAW_DIR / f"{law['name'].replace(' ', '_')}_{law['mst']}.xml"
        if raw_path.exists():
            print(f"  → 캐시 사용: {raw_path}")
            xml_text = raw_path.read_text(encoding="utf-8")
        else:
            xml_text = fetch_law_xml(law["mst"])
            raw_path.write_text(xml_text, encoding="utf-8")
            print(f"  → XML 저장: {raw_path} ({len(xml_text):,} bytes)")
            time.sleep(1)  # API 부하 방지

        # 2. 파싱 → 청크
        chunks = parse_xml_to_chunks(xml_text, law)
        print(f"  → 청크 생성: {len(chunks)}개")

        # 3. 법령별 JSON 저장
        processed_path = PROCESSED_DIR / f"{law['name'].replace(' ', '_')}_{law['mst']}.json"
        processed_path.write_text(
            json.dumps(chunks, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        all_chunks.extend(chunks)

    # 4. 전체 통합 JSON 저장
    all_path = PROCESSED_DIR / "all_chunks.json"
    all_path.write_text(
        json.dumps(all_chunks, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(f"\n[완료] 총 {len(all_chunks)}개 청크 -> {all_path}")
    return all_chunks


if __name__ == "__main__":
    collect_all()
