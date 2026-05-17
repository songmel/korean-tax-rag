# upstream/ — 레거시 참조 폴더

이 폴더는 **수정하지 않습니다.** 업스트림 팀이 제공한 계약 파일의 복사본입니다.

## 목적

- 업스트림 계약 구조 파악 및 참조
- 실제 구현의 출발점 (이미 `src/domain/`으로 통합됨)

## 폴더 구조

```
upstream/domain/rag/           → src/domain/ 으로 통합됨 (정식 구현)
upstream/domain/calculator/    → 2차 MVP 범위 (세액 산출, 아직 미구현)
upstream/domain/rules/         → 2차 MVP 범위 (결정론적 세액 규칙)
upstream/domain/models.py      → 참조용
upstream/domain/fact_ledger_schema.py → 상위 플랫폼 DB 스키마 참조
```

## 통합 완료된 파일 (src/domain/ 에 있음)

| upstream/domain/rag/ | src/domain/ | 상태 |
|---------------------|-------------|------|
| query_input.py | query_input.py | ✅ 통합 |
| chunk_metadata.py | chunk_metadata.py | ✅ 통합 |
| tax_answer.py | tax_answer.py | ✅ 통합 |
| retriever.py | retriever.py | ✅ 통합 |
| fact_checker.py | fact_checker.py | ✅ 통합 |
| output_validator.py | output_validator.py | ✅ 통합 |
| query_enrichment.py | query_enrichment.py | ✅ 통합 |
| pipeline.py | pipeline.py | ✅ 통합 |

## 2차 MVP 예정

- `upstream/domain/calculator/` — TaxCalculator (세액 산출)
- `upstream/domain/rules/` — BLK_PERIOD / BLK_RATE 결정론적 블록
- RAG verdict → Calculator Scenario 브리지 (우리가 설계)
