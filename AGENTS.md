# AGENTS.md

AI 코딩 어시스턴트(Codex, Gemini 등)가 이 프로젝트에서 올바르게 동작하도록 안내하는 문서이다.

---

## 프로젝트 개요

한국 **양도소득세 비과세 / 감면 / 중과 여부 판단**을 위한 법령 RAG 엔진이다.

JSON 사실관계 입력 → L2(팩트체크) → L3(쿼리 보강) → L4(법령 검색 + LLM 추론) → L5(출력 검증) → TaxAnswer 반환.

**핵심 원칙:**
- 모든 답변은 반드시 검색된 조문에 근거해야 한다. LLM 기억에서 직접 답변하는 것은 허용하지 않는다.
- 조문 인용은 실제 검색된 chunk_id가 있는 것만 허용한다. (phantom citation 금지)
- 불확실한 사실관계가 있으면 결론을 내리지 말고 missing_facts에 명시한다.
- 모든 판단은 추적 가능(traceable)하고 감사 가능(auditable)해야 한다.

---

## 핵심 스택

| 역할 | 구성요소 |
|------|---------|
| 법령 수집 | law.go.kr DRF API (OC=jctax) |
| 버전 관리 | effective_date / expiration_date 정수(YYYYMMDD) |
| 임베딩 | Upstage Solar (solar-embedding-1-large-passage), fallback: OpenAI text-embedding-3-large |
| 벡터 DB | Pinecone Serverless (cosine, dim=4096) |
| Reranker | BAAI/bge-reranker-v2-m3 (CrossEncoder) |
| LLM | Claude Sonnet 4.6 (기본), Claude Opus 4.7 (고정밀) |
| 파이프라인 | src/domain/pipeline.py — L2~L5 오케스트레이터 |
| 채팅 API | src/api/chat_api.py — POST /api/v1/chat + chat_turn() |
| UI | Streamlit (src/ui.py) — 입력/표시/피드백 수집만 담당 |
| 평가·루프 | src/eval/debate.py → golden_injector.py → llm_fn.py (우로보로스 루프) |

---

## 아키텍처

```text
[입력 경로]
  JSON fact_json ─► src/api/fact_input.py  (FactInput → RAGQueryInput 변환)
                    src/api/chat_api.py    (chat_turn / POST /api/v1/chat)
                    src/api/sample_cases.py (35개 실무 케이스)
  자연어 question ─► src/rag.py answer_with_citations (레거시 경로)

    ▼
src/domain/pipeline.py  — L1~L5 오케스트레이터
    ├── L2: fact_checker.py       사실관계 완전성 검사, can_proceed=False → LLM 차단
    ├── L3: query_enrichment.py   danger_flags → 조문 키워드 주입
    ├── L4a: retriever_impl.py    Pinecone 날짜/entity_scope 필터 → BGE Reranker
    ├── L4b: llm_fn.py            Claude API 추론 (golden_injector few-shot 포함)
    └── L5: output_validator.py   phantom citation 검사, 신뢰도 상한 조정
    ▼
TaxAnswer (verdict / confidence / citations / missing_facts / warnings)
    ▼  [confidence<0.8 또는 danger_flags>=2일 때]
src/eval/debate.py  — Red-Blue 논쟁 엔진
    ├── Red Team: 6가지 오류 유형 검증
    ├── Blue Team: missing_articles 재검색 후 반박
    └── 결과 → data/debates/ + data/red_wins/ or data/blue_wins/
         └── blue_won/no_contest → data/golden/qa_pairs.json (골든셋 누적)
              └── src/eval/golden_injector.py → 다음 L4 few-shot 주입 (우로보로스 루프)
```

---

## 파이프라인 진입점

### JSON 입력 (UI / REST API)

```python
from src.api.chat_api import chat_turn

result = await chat_turn(
    fact_json={"transfer_date": "20240601", "property_type": "아파트", ...},
    enable_debate=True,
)
# result["verdict"]  → "비과세" | "감면" | "중과" | "일반과세" | "단기세율" | "고가주택" | "사실관계부족"
# result["blocked"]  → True이면 missing_facts 채워 재요청
```

---

## 도메인 계약

### TaxVerdict (7종)

```python
class TaxVerdict(str, Enum):
    EXEMPT             = "비과세"       # 소득세법 §89
    REDUCED            = "감면"         # 조특법 감면
    HEAVY_TAX          = "중과"         # 다주택자 +20%/+30%
    GENERAL            = "일반과세"     # 기본세율 6~45%
    SHORT_TERM         = "단기세율"     # 보유 1년 미만 70%, 1~2년 60%
    PARTIALLY_EXEMPT   = "고가주택"     # 12억 초과분 과세
    NEEDS_VERIFICATION = "사실관계부족"
```

### TaxAnswer (출력)

```python
@dataclass
class TaxAnswer:
    answer: str
    verdict: str
    confidence: float
    citations: List[Citation]   # chunk_id 포함 — 없으면 phantom 처리
    chunk_ids: List[str]
    missing_facts: List[str]
    warnings: List[str]
    expert_review_signals: List[ExpertReviewSignal]
```

---

## 디렉터리 구조

```text
tax-rag/
├── src/
│   ├── domain/        # 인터페이스·타입·L2~L5 로직
│   │   ├── query_input.py       # RAGQueryInput + FactVector + SpecialCaseFlags
│   │   ├── tax_answer.py        # TaxAnswer + Citation + TaxVerdict
│   │   ├── fact_checker.py      # L2: 사실관계 완전성 검사
│   │   ├── query_enrichment.py  # L3: 조문 키워드 주입
│   │   ├── output_validator.py  # L5: phantom citation / 신뢰도 상한
│   │   ├── pipeline.py          # L1~L5 오케스트레이터 + debate 훅
│   │   ├── chunk_metadata.py    # LawChunkMetadata + ApplicabilitySpec
│   │   └── retriever.py         # TaxLawRetriever ABC
│   ├── retrieval/
│   │   ├── retriever_impl.py    # PineconeTaxLawRetriever
│   │   └── llm_fn.py            # async llm_fn → Claude API (few-shot 포함)
│   ├── infra/
│   │   ├── embedder.py          # Upstage Solar / OpenAI fallback
│   │   ├── pinecone_client.py
│   │   └── reranker.py          # BGE-Reranker-v2-m3
│   ├── ingestion/
│   │   ├── collect.py           # law.go.kr XML 수집
│   │   ├── embed.py             # 임베딩 + Pinecone 업로드
│   │   └── admin_notices.py     # 행정/금융 고시 수집
│   ├── api/
│   │   ├── chat_api.py          # POST /api/v1/chat + chat_turn()
│   │   ├── fact_input.py        # FactInput → RAGQueryInput 변환 팩토리
│   │   ├── sample_cases.py      # 35개 실무 케이스
│   │   ├── mcp_server.py        # FastMCP (search_tax_law 등)
│   │   └── schema.py            # Pydantic 스키마 (레거시 shim)
│   ├── eval/
│   │   ├── debate.py            # Red-Blue 논쟁 엔진
│   │   ├── golden_injector.py   # 유사 케이스 few-shot 블록 생성
│   │   ├── feedback.py          # trace 로깅
│   │   ├── eval.py              # 골든셋 배치 평가
│   │   └── retrieval_analyzer.py # RLVR 검색 품질 분석
│   ├── agents/
│   │   └── prompts.py           # RAG_SYSTEM, RED_TEAM, BLUE_DEFENSE 프롬프트
│   ├── pages/
│   │   └── admin.py             # Streamlit 어드민 페이지
│   ├── rag.py                   # 레거시 shim (신규 로직 추가 금지)
│   └── ui.py                    # Streamlit 채팅 UI (판단 로직 추가 금지)
├── data/
│   ├── golden/        # qa_pairs.json (debate 누적)
│   ├── debates/       # 개별 논쟁 기록
│   ├── red_wins/      # Red 승리 케이스
│   ├── blue_wins/     # Blue 방어 성공 케이스
│   ├── rulings/       # 유권해석 DB (ntis/, tt/, court/)
│   ├── feedback/      # 피드백 JSONL (.gitignore)
│   ├── raw/           # law.go.kr XML (.gitignore)
│   └── processed/     # 파싱 JSON 청크 (.gitignore)
├── tests/
└── scripts/
```

---

## 환경 변수

```env
LAW_API_OC=jctax
LAW_API_BASE_URL=https://www.law.go.kr/DRF

ANTHROPIC_API_KEY=
CLAUDE_MODEL=claude-sonnet-4-6

UPSTAGE_API_KEY=
UPSTAGE_EMBEDDING_MODEL=solar-embedding-1-large-passage
OPENAI_API_KEY=

PINECONE_API_KEY=
PINECONE_INDEX_NAME=tax-rag
PINECONE_NAMESPACE=tax-law
PINECONE_CLOUD=aws
PINECONE_REGION=us-east-1

BGE_RERANKER_MODEL=BAAI/bge-reranker-v2-m3
RETRIEVER_TOP_K=20
RETRIEVER_RERANK_TOP_N=5

MCP_PORT=8001
STREAMLIT_PORT=8501
```

---

## 개발 워크플로

```bash
pip install -r requirements.txt
cp .env.example .env

python -m src.ingestion.collect       # 법령 수집
python -m src.ingestion.embed         # Pinecone 업로드
streamlit run src/ui.py               # UI 실행
python -m src.api.mcp_server --sse    # MCP 서버 (HTTP SSE)
python -m src.eval.eval               # 골든셋 평가
pytest                                # 테스트
```

---

## 한국 법령 도메인 규칙

### 법령 계층 구조

```text
법률 / 시행령 / 시행규칙
  └── 조 → 항 → 호 → 목
부칙 (Supplementary Provisions) — 본칙과 별도 청크로 분리한다.
별표 (Attached Tables) — 장기보유특별공제율 표1/표2 등
```

### 유권해석 계층 (구속력 순서)

| 기관 | 종류 | 특징 |
|------|------|------|
| 기획재정부 | 세법해석 사전답변, 예규 | 최상위 — 국세청도 따라야 함 |
| 국세청 (ntis.go.kr) | 예규, 질의회신, 심사결정 | 실무 기준, 건수 가장 많음 |
| 조세심판원 (tt.go.kr) | 결정례 | 납세자 불복 케이스, binary 정답 |
| 대법원 | 판결 | 최종 권위, 건수 적음 |

### 핵심 판단 요소

| 필드 | 연결 조문 |
|------|---------|
| transfer_date / acquisition_date | §89, §154 보유기간 기산 |
| household_house_count | §89 1세대1주택 판단 |
| adjustment_area_at_acquisition | §154 거주요건 2년 |
| adjustment_area_at_transfer | §104 다주택 중과 |
| transfer_price | §156의2 고가주택(12억) |
| rollover_taxation | §97의2 이월과세 (오류 위험 최고) |
| sangsaeng_rental | §155의3 상생임대 |
| is_temporary_two_house | §155① 일시적2주택 |
| inheritance | §155② 상속주택 |
| reconstruction | §156의2 조합원입주권 |
| is_related_party_transaction | §101 부당행위계산부인 — 특수관계자 저가양도 시 양도가액 시가 재계산 |

### Pinecone 버전 관리

- 메타데이터: `effective_date`(YYYYMMDD 정수), `expiration_date`(현행=99991231)
- Stage 1 필터: `effective_date <= transfer_date AND expiration_date >= transfer_date`
- 결과가 없으면 필터 없이 재검색한다. (법령 이력 미수집 대응)

---

## L2 팩트체크 — 크리티컬 규칙

크리티컬 항목이 1개라도 누락되면 `can_proceed=False` → LLM 미호출 → 재질문을 반환한다.

| 우선순위 | 누락 필드 | 이유 |
|---------|---------|------|
| 1 | transfer_price | 고가주택(12억) 판단 불가 |
| 2 | is_gift_from_spouse_or_lineal | 이월과세 (조용히 틀릴 위험 최고) |
| 3 | death_date (상속) | §155 5년 기산 불가 |
| 4 | temp_two_house.new_acquisition_date | 종전주택 3년 기한 계산 불가 |
| 5 | management_disposal_date (입주권) | 보유기간 기산 불가 |

---

## 코딩 규칙

- 모든 public 함수에 Python type hints를 작성한다.
- 도메인 모델은 `src/domain/` dataclass를 사용한다. Pydantic은 API 스키마 전용이다.
- 사용자 노출 텍스트는 한국어, 함수명·변수명·코드 주석은 영어로 작성한다.
- 모든 프롬프트는 `src/agents/prompts.py`에서 버전 관리한다. 인라인 작성은 금지이다.
- 커밋 메시지: 한국어, `타입: 요약` 형식 (feat/fix/docs/refactor/test/chore)

---

## 절대 금지 사항 (Critical DO NOTs)

- API 키, OC 코드, 인덱스명 **하드코딩 금지** — .env에서만 로드한다.
- **.env 커밋 금지**
- **RAG 우회 금지** — 법령 질문에 LLM 직접 답변은 허용되지 않는다.
- **BGE Reranker 생략 금지** — 최종 조문 선택은 반드시 reranking 이후에 진행한다.
- **청킹 전략 무단 변경 금지** — 조문 단위 기준은 법적 정확성의 핵심이다.
- **법령 계층 구조 평탄화 금지** — 조/항/호/목 메타데이터를 반드시 보존한다.
- **인용 조문 날조 금지** — 검색된 chunk_id에 있는 조문만 인용한다.
- **ui.py에 판단 로직 추가 금지** — 입력/표시/피드백 수집만 담당한다.
- **Pinecone namespace/dimension/임베딩 모델 무단 변경 금지**
- **src/rag.py에 신규 로직 추가 금지** — 레거시 shim 유지 전용이다.

---

## 테스트 우선순위

- XML 파서가 조/항/호/목 구조를 보존하는지 확인한다.
- 모든 청크에 `law_name`, `article_number`, `effective_date`, `expiration_date`가 존재해야 한다.
- Pinecone 날짜 필터가 정수(YYYYMMDD) 타입으로 동작하는지 확인한다.
- BGE Reranker가 최종 선택 전 반드시 호출되어야 한다.
- 인용 조문은 검색된 청크에만 해당해야 한다. (phantom citation 없음)
- L2 크리티컬 누락 시 LLM이 미호출되는지 확인한다.
- L5 phantom citation 검출 시 confidence가 0.3 이하인지 확인한다.
