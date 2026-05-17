# CLAUDE.md

AI 코딩 어시스턴트(Claude Code, Codex 등)가 이 프로젝트에서 올바르게 동작하도록 안내합니다.

---

## Project Overview

`tax-rag` is the RAW agent for Korean capital gains tax exemption determination, focused on **양도소득세 비과세 / 감면 / 중과 여부 판단**.

The system must answer tax-law questions by retrieving and reasoning over Korean legal sources, not by relying on model memory.

Primary goals:
- Hackathon phase: KAIST SW Education Center Track C (required: LangChain, CrewAI, MCP)

Core stack:
- Agent orchestration: CrewAI
- RAG framework: LlamaIndex
- API layer: FastAPI + MCP server
- Vector DB: Pinecone Serverless
- Embeddings: Upstage Solar (fallback: OpenAI text-embedding-3-large)
- Reranker: BAAI BGE-Reranker-v2-m3
- UI: Streamlit
- LLMs: Claude 3.5 Sonnet / Claude Opus 4.7
- Data source: Korean law XML from law.go.kr DRF API (`OC=jctax`)

Current corpus:
- 6 Korean tax statutes (소득세법, 시행령, 시행규칙 + 조세특례제한법, 시행령, 시행규칙)
- 2,238 structure-aware chunks
- Parsed by Korean legal hierarchy: `조 / 항 / 호 / 목`

---

## Architecture Constraints

Follow this pipeline strictly:

```text
law.go.kr DRF XML
  -> src/collect.py      (data collection)
  -> XML parser          (structure-aware: 조-항-호-목 metadata preserved)
  -> src/embed.py        (Upstage Solar embeddings)
  -> Pinecone Serverless (vector index)
  -> src/rag.py          (retrieval + BGE reranking)
  -> CrewAI agents       (reasoning over retrieved law)
  -> src/mcp_server.py   (MCP tools / FastAPI)
  -> src/ui.py           (Streamlit debug UI)
```

AI assistants must preserve the RAG-first architecture. All legal answers must flow through:
1. Query understanding
2. Retrieval from indexed Korean law chunks
3. BGE reranking
4. Evidence-grounded reasoning
5. Answer with legal citations

**Direct LLM-only legal answers are not acceptable.**

---

## Directory Structure

```text
tax-rag/
├── CLAUDE.md
├── README.md
├── requirements.txt
├── .env.example             # Template — copy to .env and fill in keys
├── data/
│   ├── raw/                 # Original XML from law.go.kr (.gitignore)
│   ├── processed/           # Parsed JSON chunks (.gitignore)
│   └── samples/             # Small test fixtures for unit tests
├── src/
│   ├── collect.py           # Fetch Korean law XML from law.go.kr DRF API
│   ├── embed.py             # Build embeddings and upsert to Pinecone
│   ├── rag.py               # Retrieval, reranking, citation assembly
│   ├── mcp_server.py        # FastAPI + MCP tool server
│   ├── ui.py                # Streamlit debug UI
│   └── agents/
│       ├── __init__.py
│       ├── crew.py          # CrewAI Crew definition and kickoff
│       ├── tools.py         # Agent tools (RAG tool, MCP tool)
│       ├── roles.py         # Agent role definitions
│       └── prompts.py       # System/task prompts (versioned here)
├── tests/
│   ├── test_collect.py
│   ├── test_chunking.py
│   ├── test_rag.py
│   └── fixtures/
└── scripts/
    └── dev_*.ps1            # Local helper scripts (Windows PowerShell)
```

Keep responsibilities separated:
- `collect.py`: data collection only
- `embed.py`: embedding/indexing only
- `rag.py`: retrieval/reranking/citation logic only
- `agents/`: CrewAI orchestration only
- `mcp_server.py`: MCP interface only
- `ui.py`: user interface only — no legal reasoning logic here

---

## Critical DO NOTs

- **Do not hardcode API keys**, tokens, Pinecone index names, or law.go.kr OC credentials
- **Do not commit** `.env`, credentials, or raw secrets
- **Do not bypass RAG** — never answer Korean tax-law questions directly from LLM memory
- **Do not skip the BGE reranker** for final legal context selection
- **Do not change the chunking strategy** without explicit approval (조문단위 기준은 법적 정확성의 핵심)
- **Do not flatten** Korean law structure — `조 / 항 / 호 / 목` metadata must be preserved in every chunk
- **Do not merge** unrelated law articles into a single chunk
- **Do not silently change** Pinecone namespace, index dimension, or embedding model
- **Do not invent legal citations** — only cite articles that were retrieved from the indexed corpus
- **Do not present answers as final legal advice** — always include appropriate disclaimers
- **Do not modify** the required hackathon technologies (LangChain, CrewAI, MCP)
- **Do not add logic** to `ui.py` beyond display and input collection

---

## Environment Variables

Required vars — load from `.env` via `python-dotenv`. Fail with a clear error if missing.

```env
# law.go.kr DRF API
LAW_API_OC=jctax
LAW_API_BASE_URL=https://www.law.go.kr/DRF

# LLM
ANTHROPIC_API_KEY=sk-ant-...
CLAUDE_MODEL=claude-opus-4-7

# Embeddings (Upstage Solar 우선, fallback OpenAI)
UPSTAGE_API_KEY=
UPSTAGE_EMBEDDING_MODEL=solar-embedding-1-large
OPENAI_API_KEY=sk-proj-...

# Pinecone
PINECONE_API_KEY=
PINECONE_INDEX_NAME=tax-rag
PINECONE_NAMESPACE=tax-law
PINECONE_CLOUD=aws
PINECONE_REGION=us-east-1

# Reranker
BGE_RERANKER_MODEL=BAAI/bge-reranker-v2-m3

# Ports
FASTAPI_PORT=8000
MCP_PORT=8001
STREAMLIT_PORT=8501
```

---

## Development Workflow

### Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in your API keys
```

> **Windows note**: If `python` is not on PATH, use the full path:
> `C:\Users\next0\AppData\Local\Programs\Python\Python312\python.exe`

### Step-by-step execution

```bash
# 1. Collect law XML (cached after first run)
python -m src.collect

# 2. Embed and upload to Pinecone
python -m src.embed

# 3. Test RAG retrieval locally
python -m src.rag

# 4. Run MCP server
uvicorn src.mcp_server:app --host 0.0.0.0 --port 8001 --reload

# 5. Run Streamlit UI
streamlit run src/ui.py --server.port 8501

# Run tests
pytest
```

Before changing retrieval, chunking, or reranking behavior — add or update tests under `tests/`.

---

## Korean Law Domain Rules

양도소득세 판단은 단순 키워드 검색으로 처리하면 안 된다. 반드시 법령의 계층 구조를 보존해야 한다.

### 한국 법령 구조

```text
법률 / 시행령 / 시행규칙
  └── 조 (Article)
      └── 항 (Paragraph)
          └── 호 (Subparagraph)
              └── 목 (Item)
```

예시:
- `소득세법 제89조 제1항 제3호` — 1세대 1주택 비과세 핵심 규정
- `소득세법 시행령 제154조 제1항` — 1주택 요건 세부사항
- `조세특례제한법 제99조의2` — 각종 특례

### Why structure-aware chunking matters

- 비과세 요건은 보통 여러 `항`과 `호`에 분산되어 있다
- 예외 규정은 같은 `조` 안의 다른 `항` 또는 시행령에 존재할 수 있다
- "1세대 1주택" 판단은 법률 + 시행령 + 시행규칙이 함께 연결된다
- 조문 번호 없이 텍스트만 저장하면 citation과 legal traceability가 깨진다

### Required chunk metadata

```json
{
  "id": "{mst}_{조문키}",
  "law_name": "소득세법",
  "law_category": "법률",
  "article_number": "89",
  "article_title": "비과세 양도소득",
  "effective_date": "YYYYMMDD",
  "content": "조문 본문",
  "clauses": [...],
  "full_text": "제89조(비과세 양도소득) 본문 + 항/호 전체",
  "metadata": { "law_name": "...", "article": "89", "source": "law.go.kr" }
}
```

### 양도소득세 비과세 핵심 판단 요소

사용자 질문에서 반드시 확인해야 할 사실관계:
- 취득일 / 양도일
- 보유기간 / 거주기간
- 세대원 구성
- 양도 당시 보유 주택 수
- 조정대상지역 여부
- 일시적 2주택 여부
- 상속 / 증여 / 혼인 / 동거봉양 여부
- 농어촌주택 / 장기임대주택 / 조특법 특례 여부

---

## Agent Design

CrewAI agents must have narrow, single responsibilities:

| Agent | Role |
|-------|------|
| `TaxIssueAnalyzer` | 사실관계 정리 + 부족한 정보 식별 |
| `LawRetriever` | RAG/MCP 도구 호출만 담당 |
| `ExemptionReasoner` | 검색된 조문 적용해 비과세 판단 |
| `CitationVerifier` | 인용 조문이 검색 결과에 실제 존재하는지 검증 |
| `AnswerComposer` | 한국어 사용자 응답 작성 |

> MVP 해커톤: TaxIssueAnalyzer + LawRetriever를 Tax Researcher로 합치고, ExemptionReasoner + CitationVerifier + AnswerComposer를 Tax Advisor로 합쳐 2-agent 구성 가능.

Agents must not independently invent legal rules. Every legal proposition must be grounded in retrieved chunks.

---

## MCP Tools

The MCP server must expose:

```text
search_tax_law            - 법령 벡터 검색
retrieve_article          - 특정 조문 직접 조회
analyze_exemption         - 비과세 요건 분석
verify_citations          - 인용 조문 검증
```

Each tool returns structured JSON:
```json
{
  "answer": "...",
  "citations": ["소득세법 제89조 제1항", ...],
  "chunk_ids": ["285523_0890000", ...],
  "confidence": 0.87,
  "missing_facts": ["거주기간", "세대원 구성"],
  "warnings": ["조정대상지역 여부 미확인"]
}
```

---

## Legal Answer Format

AI agents must follow this answer template:

```text
[요약 판단]
비과세 해당 / 비해당 / 추가 확인 필요

[근거 법령]
- 소득세법 제89조 제1항 제3호
- 소득세법 시행령 제154조 제1항

[판단 과정]
1. ...
2. ...

[추가 확인 필요]
- 취득일
- 거주기간
- 보유 주택 수

[유의사항]
본 답변은 법률 자문이 아닌 정보 제공 목적입니다. 정확한 판단은 세무사와 상담하세요.
```

불확실한 사실관계가 있으면 확신 있는 결론을 내리지 말 것.

---

## RAG Interface

`src/rag.py` must expose:

```python
def retrieve_tax_law(query: str, top_k: int = 20, rerank_top_n: int = 5) -> list[LawChunk]: ...
def answer_with_citations(question: str) -> TaxAnswer: ...
```

Retrieval must include:
- Vector search from Pinecone
- Metadata filtering where applicable
- BGE reranking before final context selection
- Citation formatting with source chunk IDs
- No hallucinated law references

---

## Coding Standards

- Python type hints for all public functions
- Pydantic models or dataclasses for `LawChunk`, `TaxAnswer` etc.
- Korean for domain prompts and user-facing text
- English for function names, variable names, code comments
- All prompts versioned in `src/agents/prompts.py` (never inline)
- No business logic in `ui.py`

## Git Commit Convention

- **모든 커밋 메시지는 한국어로 작성한다**
- 형식: `타입: 변경 내용 요약`
- 타입 예시: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`
- 예시: `docs: README 제목 및 LinkTax 언급 수정`

---

## Testing Priorities

- XML parser preserves `조 / 항 / 호 / 목` structure
- Every chunk has `law_name`, `article_number`, `effective_date`
- Retrieval returns source chunk IDs (not just text)
- BGE reranker is called before final context selection
- Citations only reference chunks that were retrieved
- Missing facts are surfaced — never guessed
- Streamlit `ui.py` contains no legal reasoning logic

---

## Hackathon MVP Scope

| 포함 (Week 1-4) | 제외 (v2 이후) |
|----------------|--------------|
| 구조화 텍스트 입력폼 | OCR / 문서 파싱 (Agent 1) |
| 2-agent CrewAI workflow | 판례 데이터 수집 |
| LlamaIndex RAG + Pinecone | 멀티유저 인증 |
| MCP 서버 (FastAPI) | 결과 PDF 출력 |
| Streamlit 디버그 UI | 실시간 법령 업데이트 |

---

## Final Principle

> This project is a legal RAG system, not a chatbot with tax-law flavor.
>
> Every legal answer must be: **retrieved → reranked → cited → traceable → cautious about missing facts.**
