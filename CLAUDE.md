# CLAUDE.md

AI 코딩 어시스턴트(Claude Code, Codex 등)가 이 프로젝트에서 올바르게 동작하도록 안내합니다.

---

## Project Overview

`tax-rag`은 한국 **양도소득세 비과세 / 감면 / 중과 여부 판단**을 위한 법령 RAG 엔진입니다.

상위 플랫폼(세무 어드바이저리 서비스)이 사실관계를 수집·가공하여 구조화된 형태로 전달하면,
이 엔진이 법령 검색 → 추론 → 인용 검증 → 판단을 수행하고 결과를 반환합니다.

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
| 버전 관리 | 개정 이력 10년치 수집, effective_date / expiration_date 메타데이터 |
| 임베딩 | Upstage Solar (solar-embedding-1-large-passage/query), fallback: OpenAI text-embedding-3-large |
| 벡터 DB | Pinecone Serverless (cosine, dim=4096) |
| Reranker | BAAI/bge-reranker-v2-m3 (CrossEncoder) |
| Agent | CrewAI 2-agent: TaxResearcher + TaxAdvisor |
| API | FastMCP (search_tax_law / retrieve_article / analyze_exemption / verify_citations) |
| LLM | Claude Sonnet 4.6 (기본), Claude Opus 4.7 (고정밀 모드) |
| UI | Streamlit (내부 디버그 + 피드백 수집) |
| 학습 | src/feedback.py → data/feedback/ JSONL → src/eval.py 품질 추적 |

---

## Architecture

```text
[상위 플랫폼]
    │  TaxCase (구조화된 사실관계)
    ▼
src/mcp_server.py  ←── FastMCP API (analyze_exemption / search_tax_law / ...)
    │
    ▼
src/agents/crew.py  ←── CrewAI: TaxResearcher → TaxAdvisor
    │                    TaxResearcher: 사실관계 분석 + RAG 검색
    │                    TaxAdvisor: 조문 적용 + 인용 검증 + 판단
    ▼
src/rag.py  ←── retrieve_tax_law(query, as_of_date) + answer_with_citations()
    │             1. 쿼리 임베딩 (Upstage Solar)
    │             2. Pinecone 벡터 검색 (날짜 필터 포함)
    │             3. BGE Reranking
    │             4. Claude 추론 (검색 조문 기반)
    ▼
Pinecone Index  ←── src/embed.py (배치 업로드)
    ▲
src/collect.py  ←── law.go.kr DRF XML (버전별 수집 + 만료일 계산)

[학습 루프]
src/ui.py → 피드백 수집 → src/feedback.py → data/feedback/
src/eval.py ← data/golden/ (골든 Q&A 데이터셋) → 검색 품질 지표 추적
```

---

## API Contract (상위 플랫폼 연동)

상위 플랫폼은 다음 두 인터페이스만 사용합니다:

### 1. analyze_exemption (메인)

```python
# 입력
class TaxCase(BaseModel):
    acquisition_date: str        # YYYYMMDD — 취득일 (기준일자 자동 적용)
    transfer_date: str           # YYYYMMDD — 양도일
    holding_months: int          # 보유기간(월)
    residence_months: int        # 거주기간(월), 0이면 미거주
    household_members: list[str] # 세대원 구성
    property_count: int          # 양도 당시 보유 주택 수
    is_adjustment_area: bool     # 조정대상지역 여부
    special_situations: list[str] # ["일시적2주택", "상속", "혼인", ...]
    additional_context: str = "" # 자유 텍스트 보충 사항

# 출력
class TaxDecision(BaseModel):
    verdict: str                 # "exempt" | "not_exempt" | "needs_verification"
    answer: str                  # 상세 판단 (법령 근거 포함)
    citations: list[str]         # ["소득세법 제89조 제1항 제3호", ...]
    chunk_ids: list[str]         # 검색된 조문 ID (감사용)
    confidence: float            # 0.0 ~ 1.0
    missing_facts: list[str]     # 판단에 필요한 추가 정보
    warnings: list[str]          # 주의사항
    as_of_date: str              # 적용된 법령 기준일 (YYYYMMDD)
    trace_id: str                # 요청 추적 ID
```

### 2. search_tax_law (조문 검색)

```python
search_tax_law(query: str, as_of_date: str = "", top_k: int = 20, rerank_top_n: int = 5)
```

---

## Directory Structure

```text
tax-rag/
├── CLAUDE.md
├── README.md
├── requirements.txt
├── .env.example
├── data/
│   ├── raw/                  # law.go.kr XML (버전별, .gitignore)
│   ├── processed/            # 파싱된 JSON 청크 (버전별, .gitignore)
│   ├── golden/               # 골든 Q&A 데이터셋 (평가용)
│   │   └── qa_pairs.json
│   └── feedback/             # 사용자 피드백 JSONL (.gitignore)
│       └── feedback.jsonl
├── src/
│   ├── collect.py            # 법령 XML 수집 (버전 이력 포함)
│   ├── embed.py              # 임베딩 + Pinecone 업로드
│   ├── rag.py                # 검색 + reranking + LLM 추론
│   ├── feedback.py           # 피드백 수집 + 검색 품질 추적
│   ├── eval.py               # 골든 데이터셋 평가
│   ├── mcp_server.py         # FastMCP API 서버
│   ├── ui.py                 # Streamlit (디버그 + 피드백)
│   └── agents/
│       ├── __init__.py
│       ├── crew.py           # CrewAI Crew 실행
│       ├── tools.py          # RAG 검색 도구
│       ├── roles.py          # Agent 역할 정의
│       └── prompts.py        # 프롬프트 버전 관리
├── tests/
│   ├── __init__.py
│   ├── test_chunking.py
│   ├── test_rag.py
│   └── fixtures/
└── scripts/
    ├── claude_desktop_config.json
    └── reindex.ps1           # 재인덱싱 헬퍼
```

---

## Critical DO NOTs

- **API 키, OC 코드, 인덱스명 하드코딩 금지** — 반드시 .env에서 로드
- **.env 커밋 금지**
- **RAG 우회 금지** — 법령 질문에 LLM 직접 답변 불허
- **BGE Reranker 생략 금지** — 최종 조문 선택은 반드시 reranking 후
- **청킹 전략 무단 변경 금지** — 조문단위 기준은 법적 정확성의 핵심
- **법령 계층 구조 평탄화 금지** — 조/항/호/목 메타데이터 반드시 보존
- **인용 조문 날조 금지** — 검색된 chunk_id에 있는 조문만 인용
- **ui.py에 판단 로직 추가 금지** — UI는 입력/표시/피드백 수집만
- **Pinecone namespace/dimension/임베딩 모델 무단 변경 금지**

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

# Gemini (CCG / omc ask gemini 용)
GEMINI_API_KEY=

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

# 1. 법령 수집 (버전 이력 포함, 초회 실행 시 10~20분 소요)
python -m src.collect

# 2. Pinecone 업로드 (기존 인덱스 삭제 후 재구축)
python -m src.embed

# 3. RAG 테스트
python -m src.rag

# 4. MCP 서버
python -m src.mcp_server          # stdio 모드 (Claude Desktop)
python -m src.mcp_server --sse    # HTTP SSE 모드

# 5. Streamlit UI
python -m streamlit run src/ui.py --server.headless true --server.port 8501

# 6. 평가
python -m src.eval

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
```

### 핵심 판단 요소

사용자 질문에서 반드시 확인해야 할 사실관계:
- 취득일 / 양도일
- 보유기간 / 거주기간
- 세대원 구성
- 양도 당시 보유 주택 수
- 조정대상지역 여부 (취득일 기준)
- 일시적 2주택 여부
- 상속 / 증여 / 혼인 / 동거봉양 여부
- 농어촌주택 / 장기임대주택 / 조특법 특례 여부

### 버전 관리 원칙

- 취득일 기준으로 당시 유효한 법령 조문을 검색 (`as_of_date = acquisition_date`)
- 각 청크에 `effective_date` + `expiration_date` 메타데이터 보존
- Pinecone 필터: `effective_date <= as_of_date AND (expiration_date = "" OR expiration_date >= as_of_date)`

### Required Chunk Metadata

```json
{
  "id": "{version_mst}_{조문키}",
  "law_name": "소득세법",
  "law_mst": "285523",
  "version_mst": "285523",
  "law_category": "법률",
  "article_number": "89",
  "article_title": "비과세 양도소득",
  "effective_date": "YYYYMMDD",
  "expiration_date": "YYYYMMDD or ''",
  "promulgation_date": "YYYYMMDD",
  "content": "조문 본문",
  "clauses": [...],
  "full_text": "제89조(비과세 양도소득) ...",
  "metadata": { "law_name": "...", "article_number": "89", "effective_date": "...", "expiration_date": "...", "source": "law.go.kr" }
}
```

---

## Agent Design

| Agent | 역할 |
|-------|------|
| `TaxResearcher` | 사실관계 분석 + 검색 키워드 설계 + RAG 도구 호출 |
| `TaxAdvisor` | 검색 조문 기반 비과세 판단 + 인용 검증 + 최종 답변 작성 |

**원칙:** TaxResearcher가 검색한 chunk_id 목록 안에서만 TaxAdvisor가 인용할 수 있다.

---

## Agent 학습 루프

```text
1. 판단 실행 → TaxDecision (trace_id 부여)
2. UI/API를 통해 피드백 수집 → src/feedback.py → data/feedback/feedback.jsonl
   {"trace_id", "question", "chunk_ids", "answer", "feedback": "correct|incorrect|partial", "correction": "..."}
3. src/eval.py → data/golden/qa_pairs.json 대비 검색 품질 지표 계산
   - Retrieval Precision@K
   - Citation Accuracy (인용 조문이 실제 retrieved 조문에 있는 비율)
   - Answer Correctness (골든 답변 대비)
4. 지표 저장 → 프롬프트 버전 업 판단 (src/agents/prompts.py)
5. BGE Reranker 도메인 파인튜닝 후보 선정 (data/feedback/ → training pairs)
```

---

## MCP Tools

```text
analyze_exemption(question, as_of_date)  → TaxDecision JSON
search_tax_law(query, as_of_date, top_k, rerank_top_n)  → 조문 목록
retrieve_article(law_name, article_number)  → 특정 조문 전문
verify_citations(question, chunk_ids)  → 인용 검증 결과
```

---

## Legal Answer Format

```text
[요약 판단]
비과세 해당 / 비해당 / 추가 확인 필요

[근거 법령]
- 소득세법 제89조 제1항 제3호 (시행: 20230101~)
- 소득세법 시행령 제154조 제1항 (시행: 20230101~)

[판단 과정]
1. ...
2. ...

[추가 확인 필요]
- (누락된 사실관계)

[유의사항]
본 답변은 법률 자문이 아닌 정보 제공 목적입니다. 정확한 판단은 세무사와 상담하세요.
```

---

## RAG Interface

```python
def retrieve_tax_law(
    query: str,
    top_k: int = 20,
    rerank_top_n: int = 5,
    as_of_date: Optional[str] = None,  # YYYYMMDD
) -> list[LawChunk]: ...

def answer_with_citations(
    question: str,
    as_of_date: Optional[str] = None,
) -> TaxAnswer: ...
```

---

## Coding Standards

- 모든 public 함수에 Python type hints
- `LawChunk`, `TaxAnswer`, `TaxCase`, `TaxDecision` 등 도메인 모델은 Pydantic
- 도메인 프롬프트·사용자 노출 텍스트는 한국어
- 함수명·변수명·코드 주석은 영어
- 모든 프롬프트는 `src/agents/prompts.py`에서 버전 관리 (인라인 금지)
- `ui.py`에 판단 로직 없음

## Git Commit Convention

- **모든 커밋 메시지는 한국어로 작성한다**
- 형식: `타입: 변경 내용 요약`
- 타입: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`

---

## Testing Priorities

- XML 파서가 조/항/호/목 구조 보존
- 모든 청크에 `law_name`, `article_number`, `effective_date`, `expiration_date` 존재
- 검색 결과에 chunk_id 반드시 포함
- BGE Reranker가 최종 선택 전에 반드시 호출됨
- 인용 조문은 검색된 청크에만 해당
- missing_facts는 추측하지 않고 명시
- `ui.py`에 판단 로직 없음
- `as_of_date` 필터가 정확히 동작함 (취득일 기준)
