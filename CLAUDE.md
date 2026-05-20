# CLAUDE.md

AI 코딩 어시스턴트(Claude Code 등)가 이 프로젝트에서 올바르게 동작하도록 안내하는 문서이다.

---

## Backlog (Claude Code 전용)

세션 시작 시 이 목록을 확인한다.
사용자가 다른 작업을 요청하시면 그것을 우선하고, 완료한 항목은 즉시 삭제한다.

### 진행 중 / 단기

- [ ] E2E 테스트 러너 작성 — 5개 케이스 실행, verdict/confidence 검증, chunk_ids 수집 → golden qa_pairs.json 기록
- [ ] 세액 산출 모듈 개발 (src/calculator/) — TaxCalculator, 장기보유특별공제 표1/표2, 세율표, TaxCalculation 모델
- [ ] 부칙(buchik) 별도 수집 구현 — collect.py에서 부칙을 본칙과 분리된 청크로 추출, linked_buchik_ids 연결
- [ ] chunk_id 포맷 마이그레이션 — {법령명}_{조문}_{항}_{시행일} 형식으로 변경 후 Pinecone reindex (부칙 수집 완료 후)

### 법령 변경 취약점 보강 — 단기 (코드 변경만)

- [ ] **TaxConstantsRegistry** — `src/domain/tax_constants.py` 신규 생성
  - `HIGH_VALUE_THRESHOLD`, `SANGSAENG_WINDOW_END`, `SANGSAENG_MAX_INCREASE_RATE`, `iota_period_years`를 transfer_date 기준 버전 dict로 이전
  - `query_input.py` 상수 참조 → `get_constants(transfer_date)` 조회로 교체
  - `prompts.py`도 이 레지스트리 값을 동적 주입 (LLM 앵커링 문제 해결)
- [ ] **Multi-anchor versioning** — `retriever_impl.py` Pinecone 필터 날짜 앵커 분기
  - 이월과세 → `gift_date`, 상속주택 → `death_date`, 조합원입주권 → `management_disposal_date`, 일반 → `transfer_date`
  - `PineconeTaxLawRetriever.retrieve_with_buchik()`에서 `special_cases` 기반 앵커 선택
- [ ] **embed.py article_tag_map.json** — `_tag_chunk()` 조문→태그 매핑을 하드코딩에서 `src/infra/article_tag_map.json`으로 이전
  - 신규 조문 추가 시 코드 수정 없이 JSON만 업데이트 가능

### 루프 강화 — Verifiable Reward (RLVR)

- [x] **RLVR 검색 품질 분석기** — `src/eval/retrieval_analyzer.py` 구현 완료
  - danger_flag별 recall@k / verdict_match / citation_precision 집계
  - 누락 청크 텍스트에서 키워드 후보 자동 추출 → `DANGER_KEYWORD_MAP` 업데이트 제안
  - `auto_apply_map_updates()`: recall 미달 flag 키워드 자동 적용 + `keyword_map_patch.json` 저장
  - `query_enrichment._load_keyword_patch()`: 모듈 임포트 시 패치 자동 반영 (재시작 후에도 유지)

- [ ] **유권해석 DB 수집기 — 1단계: 구조화 JSON DB 구축**
  - 수집 대상 (우선순위 순):
    - 1순위: 국세법령정보시스템 (ntis.go.kr) — 국세청 예규·질의회신 + 기재부 세법해석 통합
    - 2순위: 조세심판원 결정례 (tt.go.kr) — 납세자 불복 케이스, binary 정답 명확
    - 3순위: 대법원 판결 (law.go.kr 판례) — 최종 권위, 건수 적음
  - 출력 스키마: `data/rulings/{source}/{id}.json`
    ```json
    {
      "ruling_id": "서면-2023-부동산-12345",
      "answer_date": "20230520",
      "transaction_date": "20230101",
      "applicable_law_version": "20230101",
      "verdict": "비과세",
      "fact_json": { ... },
      "summary": "...",
      "source_url": "..."
    }
    ```
  - 날짜 매칭 기준: `transaction_date`가 우리 케이스 `transfer_date`와 같은 법령 시행 구간 내, `answer_date` 5년 이내 우선
  - 이 DB가 구축되어야 Red-Blue 논쟁이 proxy reward → true verifiable reward로 전환된다.
- [ ] **유권해석 DB 수집기 — 2단계: 청킹·임베딩 → Pinecone 업로드** (1단계 500건+ 수집 후 진행)
  - 유권해석 1건 → 2개 청크: 질의 요지(사실관계) + 회신 내용(판단+근거)
  - Pinecone 별도 네임스페이스 `tax-ruling` 사용
  - 날짜 메타: `answer_date`, `transaction_date`, `applicable_law_version`
  - L4 검색 시 법령 조문(`tax-law`)과 함께 병렬 검색 후 통합 reranking
- [ ] **자동 판정 매칭기** (`src/eval/verdict_matcher.py`) — pipeline verdict와 유권해석 DB를 매칭해 binary reward(1/0) 자동 계산
- [ ] **L4 ReAct 반복 검색 에이전트** (`src/agents/react_agent.py`) — thought→action→observation 루프, missing_facts 있으면 추가 쿼리 자동 생성 후 재검색 (최대 3 round)
- [ ] **BGE reranker 파인튜닝 파이프라인** — debate `red_won` 케이스에서 positive/negative pair 추출 → `data/finetune/reranker_pairs.jsonl`
- [ ] **합성 케이스 생성기** (`src/eval/case_generator.py`) — 실무 케이스에서 변수 1개씩 변형해 경계 케이스 자동 생성

### 중기 아키텍처 (데이터 수집 필요)

- [ ] **법령 버전 이력 수집** — law.go.kr 연혁조회(`LRR`)로 개정 전 조문 수집 → expiration_date 포함 Pinecone 재업로드
  - 해결 문제: Namespace ghosting (구버전·신버전 경쟁), transfer_date 필터 누락 시 stale 법령 반환
- [ ] **유권해석 DB** → true verifiable reward 전환 (RLVR 1·2단계 완료 후)
  - 해결 문제: Correlated failure — 테스트와 golden labels가 동일한 stale 법령 가정을 공유하는 문제
- [ ] **멀티턴 사실관계 수집** — blocked_at_l2 발생 시 missing_facts를 후속 질문으로 자동 변환
- [ ] **세액 계산 연동** — verdict 이후 calculator 모듈 호출, 예상 세액·공제액 포함 답변
- [ ] **MCP 도구 확장** — calculate_tax, lookup_ruling 추가

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
    └── L5: output_validator.py   phantom citation 검사, 신뢰도 상한 조정, expert_review_signals 생성
    ▼
TaxAnswer (verdict / confidence / citations / missing_facts / warnings / expert_review_signals)
    ▼  [confidence<0.8 또는 danger_flags>=2일 때]
src/eval/debate.py  — Red-Blue 논쟁 엔진
    ├── Red Team: 6가지 오류 유형 검증 (별도 Claude 호출)
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

### RAGQueryInput 직접 입력 (내부 파이프라인)

```python
from src.domain.pipeline import run_rag_pipeline
from src.retrieval.retriever_impl import PineconeTaxLawRetriever
from src.retrieval.llm_fn import llm_fn

result = await run_rag_pipeline(
    query=RAGQueryInput.from_fact_ledger(fact_ledger, owner_profile, user_property),
    retriever=PineconeTaxLawRetriever(),
    llm_fn=llm_fn,
    fact_json=fact_json,    # optional — debate/few-shot 활성화용
    enable_debate=True,
)
# result.answer.verdict     → TaxVerdict 한글 값
# result.blocked_at_l2      → True이면 크리티컬 사실 누락
# result.debate_record      → 논쟁 결과 (실행된 경우)
```

---

## 도메인 계약

### TaxVerdict (7종)

```python
class TaxVerdict(str, Enum):
    EXEMPT           = "비과세"      # 소득세법 §89
    REDUCED          = "감면"        # 조특법 감면
    HEAVY_TAX        = "중과"        # 다주택자 +20%/+30%
    GENERAL          = "일반과세"    # 기본세율 6~45%
    SHORT_TERM       = "단기세율"    # 보유 1년 미만 70%, 1~2년 60%
    PARTIALLY_EXEMPT = "고가주택"    # 12억 초과분 과세
    NEEDS_VERIFICATION = "사실관계부족"
```

### TaxAnswer (출력)

```python
@dataclass
class TaxAnswer:
    answer: str               # 한국어 판단 상세
    verdict: str              # TaxVerdict 한글 값
    confidence: float         # 0.0~1.0 (L5에서 조정 가능)
    citations: List[Citation] # chunk_id 포함 — 없으면 phantom 처리
    chunk_ids: List[str]
    missing_facts: List[str]
    warnings: List[str]
    expert_review_signals: List[ExpertReviewSignal]  # 예규/판례 의존 영역 탐지 → 세무사 아이템 신호

@dataclass
class ExpertReviewSignal:
    category: str          # "예규공백" | "판례의존" | "조세불복가능" | "해석다툼"
    description: str       # 상황 설명 (상담 화면 노출)
    opportunity: str       # 세무사 활용 포인트
    related_article: str   # 관련 조문
```

### RAGQueryInput (입력)

```python
@dataclass
class RAGQueryInput:
    date_bundle: DateBundle   # transfer_date, acquisition_date
    tax_type: TaxType         # TaxType.TRANSFER
    entity_scope: EntityScope # "주택" | "분양권" | "입주권" | ...
    fact_vector: FactVector   # to_text()로 벡터 검색 텍스트 생성
    top_k: int = 10
    include_buchik: bool = True
```

`SpecialCaseFlags`에 이월과세/상생임대/일시적2주택/상속/재건축 등 14개 특례 유형이 정의되어 있다.

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
│   │   └── admin_notices.py     # 행정/금융 고시 수집 (조정대상지역 API, DSR/LTV) — API키 발급 후 구현
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
│   │   └── retrieval_analyzer.py # RLVR 검색 품질 분석 + DANGER_KEYWORD_MAP 자동 보강
│   ├── agents/
│   │   ├── prompts.py           # RAG_SYSTEM, RED_TEAM, BLUE_DEFENSE 프롬프트
│   │   ├── crew.py / roles.py / tools.py  # CrewAI 대안 경로 (선택적)
│   ├── rag.py                   # 레거시 shim (신규 로직 추가 금지)
│   └── ui.py                    # Streamlit 채팅 UI (판단 로직 추가 금지)
├── data/
│   ├── golden/        # qa_pairs.json (debate 누적), example_cases.json
│   ├── debates/       # 개별 논쟁 기록 ({debate_id}.json)
│   ├── red_wins/      # Red 승리 케이스
│   ├── blue_wins/     # Blue 방어 성공 케이스
│   ├── rulings/       # 유권해석 DB (ntis/, tt/, court/ 하위 디렉터리)
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
OPENAI_API_KEY=          # Upstage fallback

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
| **is_related_party_transaction** | **§101 부당행위계산부인 — 특수관계자 저가양도 시 양도가액을 시가로 재계산. 비과세 판단이 완전히 바뀔 수 있어 JSON 입력에서 항상 수신 필요** |

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

**비크리티컬 경고 (차단하지 않음, danger_flag + expert_review_signal 생성):**

| 필드 | 이유 |
|------|------|
| is_related_party_transaction=True | §101 부당행위계산부인 — 양도가액 시가 재계산 가능, 조세불복 아이템 |

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
