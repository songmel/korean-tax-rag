"""
청킹 품질 테스트 — 조/항/호/목 구조 보존 검증
"""
import json
from pathlib import Path

import pytest

CHUNKS_PATH = Path("data/processed/all_chunks.json")
SAMPLE_LAW = Path("data/processed/소득세법_285523.json")


@pytest.fixture(scope="module")
def all_chunks():
    if not CHUNKS_PATH.exists():
        pytest.skip("data/processed/all_chunks.json 없음 — collect.py 먼저 실행")
    return json.loads(CHUNKS_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def income_tax_chunks():
    if not SAMPLE_LAW.exists():
        pytest.skip("소득세법 청크 파일 없음")
    return json.loads(SAMPLE_LAW.read_text(encoding="utf-8"))


def test_total_chunk_count(all_chunks):
    """6개 법령 → 최소 500개 청크 이상"""
    assert len(all_chunks) >= 500, f"청크 수 너무 적음: {len(all_chunks)}"


def test_required_fields(all_chunks):
    """모든 청크에 필수 필드 존재"""
    required = {"id", "law_name", "article_number", "effective_date", "full_text", "metadata"}
    for chunk in all_chunks:
        missing = required - set(chunk.keys())
        assert not missing, f"필수 필드 누락: {missing} (id={chunk.get('id')})"


def test_chunk_id_format(all_chunks):
    """id = {mst}_{조문키} 형식"""
    for chunk in all_chunks:
        assert "_" in chunk["id"], f"id 형식 오류: {chunk['id']}"
        parts = chunk["id"].split("_")
        assert len(parts) >= 2, f"id 파트 부족: {chunk['id']}"


def test_law_names_covered(all_chunks):
    """6개 법령이 모두 포함"""
    expected = {
        "소득세법", "소득세법 시행령", "소득세법 시행규칙",
        "조세특례제한법", "조세특례제한법 시행령", "조세특례제한법 시행규칙",
    }
    actual = {c["law_name"] for c in all_chunks}
    missing = expected - actual
    assert not missing, f"누락된 법령: {missing}"


def test_no_empty_full_text(all_chunks):
    """full_text가 비어 있는 청크 없음"""
    empty = [c["id"] for c in all_chunks if not c.get("full_text", "").strip()]
    assert not empty, f"full_text 비어 있는 청크: {empty[:5]}"


def test_metadata_consistency(all_chunks):
    """metadata.law_name == law_name"""
    for chunk in all_chunks:
        meta_name = chunk.get("metadata", {}).get("law_name", "")
        assert meta_name == chunk["law_name"], (
            f"metadata.law_name 불일치: {meta_name!r} != {chunk['law_name']!r} (id={chunk['id']})"
        )


def test_clauses_structure(all_chunks):
    """clauses가 있으면 항번호/항내용 키 보유"""
    for chunk in all_chunks:
        for clause in chunk.get("clauses", []):
            assert "항번호" in clause, f"항번호 없음 (id={chunk['id']})"
            assert "항내용" in clause, f"항내용 없음 (id={chunk['id']})"


def test_key_article_exists(income_tax_chunks):
    """소득세법 제89조(비과세 양도소득) 반드시 존재"""
    articles = {c["article_number"] for c in income_tax_chunks}
    assert "89" in articles, "소득세법 제89조 없음 — 핵심 비과세 조문 누락"


def test_effective_date_format(all_chunks):
    """시행일자가 YYYYMMDD 형식 (비어있지 않은 경우)"""
    for chunk in all_chunks:
        date = chunk.get("effective_date", "")
        if date:
            assert len(date) == 8 and date.isdigit(), (
                f"시행일자 형식 오류: {date!r} (id={chunk['id']})"
            )
