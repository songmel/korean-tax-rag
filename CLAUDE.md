# CLAUDE.md

AI 코딩 어시스턴트(Claude Code, Codex 등)가 이 프로젝트에서 올바르게 동작하도록 안내합니다.

---

## Project Overview

`tax-rag`은 한국 **양도소득세 비과세 / 감면 / 중과 여부 판단**을 위한 법령 RAG 엔진입니다.

상위 플랫폼(LinkTax)이 사실관계를 `RAGQueryInput`으로 정리해 넘기면,
이 엔진이 L2(팩트체크) → L3(쿼리 보강) → L4(법령 검색 + LLM 추론) → L5(출력 검증)
파이프라인을 실행하고 `TaxAnswer`를 반환합니다.

**핵심 원칙:**
- 모든 법령 답변은 반드시 검색된 조문에 근거한다. LLM 기억에서 직접 답변하는 것은 허용하지 않는다.
- 조문 인용은 실제 검색된 chunk_id가 있는 것만 허용한다.
- 불확실한 사실관계가 있으면 결론을 내리지 말고 missing_facts에 명시한다.
- 모든 판단은 추적 가능(traceable)하고 감사 가능(auditable)해야 한다.

---

## Core Stack

| 역할 | 구성요소 |
|------|---------|
| 법령 수집 | law.go.kr DRF API (OC=jctax) |
| 버전 관리 | effective_date / expiration_date 정수(YYYYMMDD) + effective_to=None(현행) |
| 임베딩 | Upstage Solar (solar-embedding-1-large-passage/query), fallback: OpenAI text-embedding-3-large |
| 벡터 DB | Pinecone Serverless (cosine, dim=4096) |
| Reranker | BAAI/bge-reranker-v2-m3 (CrossEncoder) |
| LLM | Claude Sonnet 4.6 (기본), Claude Opus 4.7 (고정밀 모드) |
| 파이프라인 | src/domain/pipeline.py — L2~L5 오케스트레이터 |
| API | FastMCP (search_tax_law / analyze_exemption / verify_citations) |
| UI | Streamlit (내부 디버그 + 피드백 수집) |
| 평가 | src/eval/feedback.py → data/feedback/ JSONL → src/eval/eval.py 품질 추적 |

---

## Architecture

```text
[LinkTax 상위 플랫폼]
    │  RAGQueryInput (from_fact_ledger로 생성)
    ▼
src/domain/pipeline.py  ←── L1~L5 파이프라인 오케스트레이터
    │
    ├── L2: src/domain/fact_checker.py       (사실관계 완전성 검사, LLM 차단 여부 결정)
    ├── L3: src/domain/query_enrichment.py   (danger_flags → 조문 키워드 주입)
    │
    ├── L4a: src/retrieval/retriever_impl.py (PineconeTaxLawRetriever)
    │         Stage 1 — Pinecone 날짜/entity_scope 필터
    │         Stage 2 — BGE Reranker 순위
    │         retrieve_with_buchik() — 부칙 자동 포함
    │
    ├── L4b: src/retrieval/llm_fn.py         (async llm_fn → Claude API)
    │
    └── L5: src/domain/output_validator.py   (phantom citation 검사 / 신뢰도 상한)
    ▼
TaxAnswer (verdict / confidence / citations / missing_facts / warnings)

[법령 인덱스 구축]
src/ingestion/collect.py  ←── law.go.kr DRF XML 수집
src/ingestion/embed.py    ←── 임베딩 + entity_scopes 태깅 + Pinecone 업로드

[평가 루프]
src/ui.py → 피드백 수집 → src/eval/feedback.py → data/feedback/
src/eval/eval.py ← data/golden/qa_pairs.json → 검색 품질 지표
```

---

## 파이프라인 진입점

```python
from src.domain.pipeline import run_rag_pipeline
from src.domain.query_input import RAGQueryInput
from src.retrieval.retriever_impl import PineconeTaxLawRetriever
from src.retrieval.llm_fn import llm_fn

result = await run_rag_pipeline(
    query=RAGQueryInput.from_fact_ledger(fact_ledger, owner_profile, user_property),
    retriever=PineconeTaxLawRetriever(),
    llm_fn=llm_fn,
)
# result.answer.verdict  → "비과세" | "과세" | "조건부비과세" | "needs_verification"
# result.answer.confidence
# result.blocked_at_l2   → True이면 크리티컬 사실 누락으로 LLM 미호출
```

---

## 도메인 계약 (src/domain/)

### RAGQueryInput — 파이프라인 입력

```python
@dataclass
class RAGQueryInput:
    date_bundle: DateBundle      # transfer_date, acquisition_date (required)
    tax_type: TaxType            # TaxType.TRANSFER
    entity_scope: EntityScope    # "주택" | "분양권" | "입주권" | ...
    fact_vector: FactVector      # 사실관계 (to_text()로 벡터 검색 텍스트 생성)
    top_k: int = 10
    include_buchik: bool = True  # 부칙 자동 포함
```

`FactVector.to_text()`는 이월과세/상생임대/재건축 등 조문 키워드를 자동으로 포함해
벡터 검색 정확도를 높입니다. `SpecialCaseFlags`에 14개 특례 유형이 정의돼 있습니다.

### TaxAnswer — 파이프라인 출력

```python
@dataclass
class TaxAnswer:
    answer: str          # 한국어 판단 상세
    verdict: str         # "비과세" | "과세" | "조건부비과세" | "needs_verification"
    confidence: float    # 0.0 ~ 1.0 (L5에서 조정될 수 있음)
    citations: List[Citation]   # chunk_id 포함 — 검색 결과에 없으면 phantom 처리
    chunk_ids: List[str]
    missing_facts: List[str]
    warnings: List[str]
```

---

## Directory Structure

```text
tax-rag/
├── CLAUDE.md
├── README.md
├── requirements.txt
├── .env.example
│
├── data/
│   ├── raw/           # law.go.kr XML (.gitignore)
│   ├── processed/     # 파싱된 JSON 청크 (.gitignore)
│   ├── golden/        # 골든 Q&A 데이터셋 (평가용)
│   │   ├── qa_pairs.json
│   │   └── example_cases.json
│   ├── feedback/      # 피드백 JSONL (.gitignore)
│   └── eval_results/  # 평가 결과
│
├── src/
│   ├── domain/        # 업스트림 계약 + 파이프라인 로직 (인터페이스·타입·L2~L5)
│   │   ├── chunk_metadata.py    # LawChunkMetadata + ApplicabilitySpec
│   │   ├── query_input.py       # RAGQueryInput + FactVector + SpecialCaseFlags
│   │   ├── tax_answer.py        # TaxAnswer + Citation
│   │   ├── retriever.py         # TaxLawRetriever ABC + RetrievedChunk
│   │   ├── fact_checker.py      # L2: 사실관계 완전성 검사
│   │   ├── query_enrichment.py  # L3: danger_flags → 조문 키워드 주입
│   │   ├── output_validator.py  # L5: phantom citation / 신뢰도 상한
│   │   └── pipeline.py          # L1~L5 오케스트레이터
│   │
│   ├── retrieval/     # 구현체 (domain 인터페이스 구현)
│   │   ├── retriever_impl.py    # PineconeTaxLawRetriever (Stage1+2)
│   │   └── llm_fn.py            # async llm_fn → Claude API
│   │
│   ├── infra/         # 외부 서비스 어댑터
│   │   ├── embedder.py          # Upstage Solar / OpenAI fallback
│   │   ├── pinecone_client.py   # Pinecone index 연결
│   │   └── reranker.py          # BGE-Reranker-v2-m3
│   │
│   ├── ingestion/     # 법령 수집 · 임베딩 파이프라인
│   │   ├── collect.py           # law.go.kr XML 수집
│   │   └── embed.py             # 임베딩 + entity_scopes 태깅 + Pinecone 업로드
│   │
│   ├── api/           # FastMCP 서버
│   │   ├── mcp_server.py
│   │   └── schema.py            # MCP용 Pydantic 스키마 (레거시 shim 호환)
│   │
│   ├── eval/          # 평가 루프
│   │   ├── feedback.py          # trace 로깅 + 검색 품질 지표
│   │   └── eval.py              # 골든셋 배치 평가
│   │
│   ├── agents/        # CrewAI 대안 경로 (선택적)
│   │   ├── prompts.py           # 프롬프트 버전 관리 (llm_fn에서도 사용)
│   │   ├── crew.py
│   │   ├── roles.py
│   │   └── tools.py
│   │
│   ├── rag.py         # 레거시 shim — tests/mcp_server 호환용 (신규 코드 금지)
│   └── ui.py          # Streamlit (디버그 + 피드백 수집)
│
├── tests/
│   ├── test_rag.py
│   └── test_chunking.py
│
└── scripts/
    ├── claude_desktop_config.json
    └── reindex.ps1
```

---

## Critical DO NOTs

- **API 키, OC 코드, 인덱스명 하드코딩 금지** — 반드시 .env에서 로드
- **.env 커밋 금지**
- **RAG 우회 금지** — 법령 질문에 LLM 직접 답변 불허
- **BGE Reranker 생략 금지** — 최종 조문 선택은 반드시 reranking 후
- **청킹 전략 무단 변경 금지** — 조문 단위 기준은 법적 정확성의 핵심
- **법령 계층 구조 평탄화 금지** — 조/항/호/목 메타데이터 반드시 보존
- **인용 조문 날조 금지** — 검색된 chunk_id에 있는 조문만 인용
- **ui.py에 판단 로직 추가 금지** — UI는 입력/표시/피드백 수집만
- **Pinecone namespace/dimension/임베딩 모델 무단 변경 금지**
- **src/rag.py에 신규 로직 추가 금지** — 레거시 shim, 테스트 호환 유지용

---

## Environment Variables

```env
# law.go.kr DRF API
LAW_API_OC=jctax
LAW_API_BASE_URL=https://www.law.go.kr/DRF

# LLM
ANTHROPIC_API_KEY=
CLAUDE_MODEL=claude-sonnet-4-6

# Embeddings
UPSTAGE_API_KEY=
UPSTAGE_EMBEDDING_MODEL=solar-embedding-1-large-passage
OPENAI_API_KEY=                  # Upstage 없을 때 fallback

# Pinecone
PINECONE_API_KEY=
PINECONE_INDEX_NAME=tax-rag
PINECONE_NAMESPACE=tax-law
PINECONE_CLOUD=aws
PINECONE_REGION=us-east-1

# Reranker
BGE_RERANKER_MODEL=BAAI/bge-reranker-v2-m3

# Retriever tuning
RETRIEVER_TOP_K=20
RETRIEVER_RERANK_TOP_N=5

# Ports
MCP_PORT=8001
STREAMLIT_PORT=8501
```

---

## Development Workflow

```bash
# 설치
pip install -r requirements.txt
cp .env.example .env   # API 키 입력

# 1. 법령 수집
python -m src.ingestion.collect

# 2. Pinecone 업로드
python -m src.ingestion.embed

# 3. RAG 레거시 테스트 (shim 경로)
python -m src.rag

# 4. MCP 서버
python -m src.api.mcp_server          # stdio 모드 (Claude Desktop)
python -m src.api.mcp_server --sse    # HTTP SSE 모드

# 5. Streamlit UI
streamlit run src/ui.py --server.headless true --server.port 8501

# 6. 평가
python -m src.eval.eval

# 테스트
pytest
```

---

## Korean Law Domain Rules

### 법령 계층 구조

```text
법률 / 시행령 / 시행규칙
  └── 조 (Article)
      └── 항 (Paragraph)
          └── 호 (Subparagraph)
              └── 목 (Item)
부칙 (Supplementary Provisions) — 반드시 본칙과 별도 청크로 분리
별표 (Attached Tables) — 장기보유특별공제율 표1/표2 등
```

### 핵심 판단 요소

`FactVector`와 `SpecialCaseFlags`로 구조화해 전달해야 할 사실관계:

| 필드 | 조문 연결 |
|------|---------|
| transfer_date / acquisition_date | §89, §154 보유기간 기산 |
| household_house_count (COMPUTED) | §89 1세대1주택 판단 |
| adjustment_area_at_acquisition | §154 거주요건 2년 발생 여부 |
| adjustment_area_at_transfer | §104 다주택 중과세율 |
| transfer_price | §156의2 고가주택(12억) 판단 |
| SpecialCaseFlags.rollover_taxation | §97의2 이월과세 (가장 위험) |
| SpecialCaseFlags.sangsaeng_rental | §155의3 상생임대 거주요건 면제 |
| SpecialCaseFlags.is_temporary_two_house | §155① 일시적2주택 |
| SpecialCaseFlags.inheritance | §155② 상속주택 |
| SpecialCaseFlags.reconstruction | §156의2 조합원입주권 |

### 버전 관리 원칙

- Pinecone에 `effective_date`(정수 YYYYMMDD), `expiration_date`(정수, 현행=99991231) 저장
- Stage 1 필터: `effective_date <= transfer_date AND expiration_date >= transfer_date`
- 결과 없으면 fallback: 필터 없이 재검색 (법령 버전 이력 미수집 상태 대응)
- 부칙 경과조치: `applicability.anchors`가 `acquisition_date`인 경우 취득일 기준으로 체크

### Pinecone 메타데이터 스키마

```json
{
  "law_name": "소득세법 시행령",
  "article_number": "154",
  "article_title": "1세대1주택의 범위",
  "effective_date": 20240101,
  "expiration_date": 99991231,
  "version_mst": "285631",
  "law_category": "대통령령",
  "entity_scopes": ["주택"],
  "topic_tags": ["1세대1주택비과세"],
  "tax_types": ["transfer"],
  "full_text": "제154조(1세대1주택의 범위) ..."
}
```

---

## L2 팩트체크 — 크리티컬 규칙

`src/domain/fact_checker.py`의 `check_facts()`가 LLM 호출 전 실행합니다.
크리티컬 항목이 1개라도 누락되면 `can_proceed=False` → LLM 미호출 → 재질문 반환.

| 우선순위 | 누락 필드 | 이유 |
|---------|---------|------|
| 1 | transfer_price | 고가주택(12억) 여부 불가 |
| 2 | is_gift_from_spouse_or_lineal | 이월과세 적용 여부 (조용히 틀릴 위험 최고) |
| 3 | death_date (상속) | §155 5년 기간 기산 불가 |
| 4 | temp_two_house.new_acquisition_date | 종전주택 3년 기한 계산 불가 |
| 5 | management_disposal_date (입주권) | 보유기간 기산 불가 |

---

## Coding Standards

- 모든 public 함수에 Python type hints
- 도메인 모델은 `src/domain/`의 dataclass (Pydantic은 MCP API 스키마만)
- 도메인 프롬프트·사용자 노출 텍스트는 한국어
- 함수명·변수명·코드 주석은 영어
- 모든 프롬프트는 `src/agents/prompts.py`에서 버전 관리 (인라인 금지)
- `ui.py`에 판단 로직 없음
- `src/rag.py`는 레거시 shim — 신규 로직 추가 금지

## Git Commit Convention

- **모든 커밋 메시지는 한국어로 작성한다**
- 형식: `타입: 변경 내용 요약`
- 타입: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`

---

## Testing Priorities

- XML 파서가 조/항/호/목 구조 보존
- 모든 청크에 `law_name`, `article_number`, `effective_date`, `expiration_date` 존재
- Pinecone 날짜 필터가 정수(YYYYMMDD) 타입으로 동작
- 검색 결과에 chunk_id 반드시 포함
- BGE Reranker가 최종 선택 전에 반드시 호출됨
- 인용 조문은 검색된 청크에만 해당 (phantom citation 없음)
- missing_facts는 추측하지 않고 명시
- `ui.py`에 판단 로직 없음
- L2 크리티컬 누락 시 LLM 미호출 확인
- L5 phantom citation 검출 시 confidence 0.3 이하 확인
