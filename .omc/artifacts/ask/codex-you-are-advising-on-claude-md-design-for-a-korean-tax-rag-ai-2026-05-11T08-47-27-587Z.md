# codex advisor artifact

- Provider: codex
- Exit code: 0
- Created at: 2026-05-11T08:47:27.590Z

## Original task

You are advising on CLAUDE.md design for a Korean tax RAG AI project.

PROJECT: RAW agent - tax-rag — capital gains tax (양도소득세) exemption determination AI.
STACK: CrewAI (agent orchestration), LlamaIndex (RAG), FastAPI + MCP server, Pinecone Serverless, Claude 3.5/Opus 4.7, Streamlit, Upstage Solar embeddings, BAAI BGE-Reranker.
DATA: Korean law XML from law.go.kr DRF API (OC=jctax). 2,238 chunks from 6 laws parsed into 조/항/호 hierarchy.
PHASE: 4-week hackathon (KAIST SW Education Center Track C: must use LangChain, CrewAI, MCP) → long-term LinkTax SaaS.

Design a CLAUDE.md file (for AI coding assistants) that covers:
1. Project overview and architecture constraints the AI must follow
2. Directory structure conventions (src/collect.py, src/embed.py, src/rag.py, src/agents/, src/mcp_server.py, src/ui.py)
3. Critical DO NOTs: what the AI must never do (e.g., hardcode API keys, bypass RAG with direct LLM answers, skip reranker, change chunking strategy)
4. Development workflow: how to run each component, env vars required
5. Korean law domain rules: article structure [조-항-호-목], why structure-aware chunking matters

Output the actual CLAUDE.md content in Korean/English mixed (Korean for domain rules, English for tech specs).

## Final prompt

You are advising on CLAUDE.md design for a Korean tax RAG AI project.

PROJECT: RAW agent - tax-rag — capital gains tax (양도소득세) exemption determination AI.
STACK: CrewAI (agent orchestration), LlamaIndex (RAG), FastAPI + MCP server, Pinecone Serverless, Claude 3.5/Opus 4.7, Streamlit, Upstage Solar embeddings, BAAI BGE-Reranker.
DATA: Korean law XML from law.go.kr DRF API (OC=jctax). 2,238 chunks from 6 laws parsed into 조/항/호 hierarchy.
PHASE: 4-week hackathon (KAIST SW Education Center Track C: must use LangChain, CrewAI, MCP) → long-term LinkTax SaaS.

Design a CLAUDE.md file (for AI coding assistants) that covers:
1. Project overview and architecture constraints the AI must follow
2. Directory structure conventions (src/collect.py, src/embed.py, src/rag.py, src/agents/, src/mcp_server.py, src/ui.py)
3. Critical DO NOTs: what the AI must never do (e.g., hardcode API keys, bypass RAG with direct LLM answers, skip reranker, change chunking strategy)
4. Development workflow: how to run each component, env vars required
5. Korean law domain rules: article structure [조-항-호-목], why structure-aware chunking matters

Output the actual CLAUDE.md content in Korean/English mixed (Korean for domain rules, English for tech specs).

## Raw output

```text
```markdown
# CLAUDE.md

This file guides AI coding assistants working on `tax-rag`, a Korean capital gains tax exemption RAG AI project.

## Project Overview

`tax-rag` is the RAW agent for Korean capital gains tax exemption determination, focused on **양도소득세 비과세 / 감면 / 중과 여부 판단**.

The system must answer tax-law questions by retrieving and reasoning over Korean legal sources, not by relying on model memory.

Primary goals:

- Hackathon phase: KAIST SW Education Center Track C
- Required technologies: LangChain, CrewAI, MCP
- Long-term direction: LinkTax SaaS tax advisory infrastructure

Core stack:

- Agent orchestration: CrewAI
- RAG framework: LlamaIndex
- API layer: FastAPI
- Tool protocol: MCP server
- Vector DB: Pinecone Serverless
- Embeddings: Upstage Solar embeddings
- Reranker: BAAI BGE-Reranker
- UI: Streamlit
- LLMs: Claude 3.5 / Claude Opus 4.7
- Data source: Korean law XML from law.go.kr DRF API using `OC=jctax`

Current corpus:

- 6 Korean tax-related laws
- 2,238 structure-aware chunks
- Parsed by Korean legal hierarchy: `조 / 항 / 호 / 목`

## Architecture Constraints

Follow this pipeline:

```text
law.go.kr DRF XML
  -> src/collect.py
  -> structure-aware legal parser
  -> chunks preserving 조-항-호-목 metadata
  -> src/embed.py
  -> Upstage Solar embeddings
  -> Pinecone Serverless
  -> src/rag.py
  -> retrieval + BGE reranking
  -> CrewAI agents
  -> MCP tools / FastAPI
  -> Streamlit UI
```

AI assistants must preserve the RAG-first architecture.

All legal answers must flow through:

1. Query understanding
2. Retrieval from indexed Korean law chunks
3. Reranking
4. Evidence-grounded reasoning
5. Answer with legal citations

Direct LLM-only legal answers are not acceptable.

## Directory Structure

Use the following conventions.

```text
tax-rag/
├── CLAUDE.md
├── README.md
├── requirements.txt
├── .env.example
├── data/
│   ├── raw/                 # Original XML from law.go.kr
│   ├── parsed/              # Parsed law JSON/chunks
│   └── samples/             # Small test fixtures
├── src/
│   ├── collect.py           # Fetch Korean law XML from law.go.kr DRF API
│   ├── embed.py             # Build embeddings and upsert to Pinecone
│   ├── rag.py               # Retrieval, reranking, citation assembly
│   ├── mcp_server.py        # MCP tool server for tax-law retrieval/reasoning
│   ├── ui.py                # Streamlit UI
│   └── agents/
│       ├── __init__.py
│       ├── crew.py          # CrewAI crew definition
│       ├── tools.py         # Agent tools, including MCP/RAG tools
│       ├── roles.py         # Agent role definitions
│       └── prompts.py       # System/task prompts
├── tests/
│   ├── test_collect.py
│   ├── test_chunking.py
│   ├── test_rag.py
│   └── fixtures/
└── scripts/
    └── dev_*.ps1            # Optional local helper scripts
```

Keep responsibilities separated:

- `collect.py`: data collection only
- `embed.py`: embedding/indexing only
- `rag.py`: retrieval/reranking/citation logic only
- `agents/`: CrewAI orchestration only
- `mcp_server.py`: MCP interface only
- `ui.py`: user interface only

Do not put business logic into the Streamlit UI.

## Critical DO NOTs

Never do the following:

- Do not hardcode API keys, tokens, Pinecone indexes, or law.go.kr credentials.
- Do not commit `.env`, credentials, raw secrets, or local API responses containing private keys.
- Do not bypass RAG and answer Korean tax-law questions directly from the LLM.
- Do not skip the BGE reranker for final legal context selection.
- Do not change the existing chunking strategy without explicit approval.
- Do not flatten Korean law structure into plain paragraphs if metadata would be lost.
- Do not remove `조 / 항 / 호 / 목` metadata from chunks.
- Do not merge unrelated laws into a single chunk.
- Do not silently change Pinecone namespace, index dimension, or embedding model.
- Do not replace Upstage Solar embeddings unless explicitly requested.
- Do not invent legal citations.
- Do not cite a law article unless it was retrieved from the indexed corpus.
- Do not treat model output as legal authority.
- Do not present answers as final legal advice without caveats.
- Do not modify hackathon-required technologies away from LangChain, CrewAI, or MCP.

## Environment Variables

Required environment variables should be loaded from `.env`.

```env
# law.go.kr DRF
LAW_GO_KR_OC=jctax
LAW_GO_KR_BASE_URL=https://www.law.go.kr/DRF/lawSearch.do

# LLM
ANTHROPIC_API_KEY=
CLAUDE_MODEL=claude-3-5-sonnet-latest

# Embeddings
UPSTAGE_API_KEY=
UPSTAGE_EMBEDDING_MODEL=

# Pinecone
PINECONE_API_KEY=
PINECONE_INDEX_NAME=
PINECONE_NAMESPACE=tax-law
PINECONE_CLOUD=aws
PINECONE_REGION=us-east-1

# Reranker
BGE_RERANKER_MODEL=BAAI/bge-reranker-v2-m3

# App
FASTAPI_HOST=0.0.0.0
FASTAPI_PORT=8000
MCP_HOST=0.0.0.0
MCP_PORT=8001
STREAMLIT_PORT=8501
```

If an env var is missing, fail clearly with an actionable error. Do not fall back to fake keys or hidden defaults.

## Development Workflow

Install dependencies:

```bash
pip install -r requirements.txt
```

Collect Korean law XML:

```bash
python src/collect.py
```

Parse and embed law chunks:

```bash
python src/embed.py
```

Run RAG locally:

```bash
python src/rag.py
```

Run MCP server:

```bash
python src/mcp_server.py
```

Run FastAPI server:

```bash
uvicorn src.mcp_server:app --host 0.0.0.0 --port 8001 --reload
```

Run Streamlit UI:

```bash
streamlit run src/ui.py --server.port 8501
```

Run tests:

```bash
pytest
```

Before changing retrieval, chunking, embeddings, or reranking behavior, add or update tests under `tests/`.

## Korean Law Domain Rules

양도소득세 판단은 단순 키워드 검색으로 처리하면 안 된다. 반드시 법령의 계층 구조를 보존해야 한다.

한국 법령 구조:

```text
법률 / 시행령 / 시행규칙
  └── 조
      └── 항
          └── 호
              └── 목
```

예시:

```text
소득세법 제89조 제1항 제3호
소득세법 시행령 제154조 제1항
조세특례제한법 제99조의2 제1항
```

각 단위의 의미:

- `조`: 핵심 법률 규정 단위
- `항`: 조문 내 주요 요건 분기
- `호`: 세부 요건 또는 예외 조건
- `목`: 더 세밀한 열거 조건

Structure-aware chunking matters because:

- 비과세 요건은 보통 여러 `항`과 `호`에 나누어져 있다.
- 예외 규정은 같은 `조` 안의 다른 `항` 또는 시행령에 존재할 수 있다.
- “1세대 1주택” 판단은 법률, 시행령, 시행규칙이 함께 연결된다.
- 같은 단어라도 위치한 조문 계층에 따라 법적 의미가 달라진다.
- 조문 번호 없이 텍스트만 저장하면 정확한 citation과 legal traceability가 깨진다.

따라서 모든 chunk는 최소한 다음 metadata를 가져야 한다.

```json
{
  "law_name": "소득세법",
  "law_type": "법률",
  "article_no": "제89조",
  "article_title": "비과세 양도소득",
  "paragraph_no": "제1항",
  "subparagraph_no": "제3호",
  "item_no": null,
  "effective_date": "YYYY-MM-DD",
  "source_url": "law.go.kr URL",
  "text": "..."
}
```

## Legal Answering Rules

When answering user tax questions:

1. 먼저 사실관계를 정리한다.
2. 필요한 판단요건을 식별한다.
3. RAG retrieval을 수행한다.
4. BGE reranker로 최종 근거 조문을 선별한다.
5. 조문 근거와 함께 판단한다.
6. 불확실한 사실관계는 질문으로 되묻는다.
7. 법률 자문이 아닌 정보 제공임을 명확히 한다.

Required answer style:

```text
요약 판단:
- ...

근거 법령:
- 소득세법 제89조 제1항 제3호
- 소득세법 시행령 제154조 제1항

판단 과정:
1. ...
2. ...

추가 확인 필요:
- 취득일
- 양도일
- 보유기간
- 거주기간
- 세대 구성
- 보유 주택 수
```

Do not produce confident conclusions when required facts are missing.

Important facts for 양도소득세 exemption analysis usually include:

- 취득일
- 양도일
- 양도가액
- 취득가액
- 보유기간
- 거주기간
- 세대원 구성
- 양도 당시 보유 주택 수
- 조정대상지역 여부
- 일시적 2주택 여부
- 상속 / 증여 / 혼인 / 동거봉양 여부
- 농어촌주택 / 장기임대주택 / 조특법 특례 여부

## Retrieval Requirements

`src/rag.py` should expose a stable interface similar to:

```python
retrieve_tax_law(query: str, top_k: int = 20, rerank_top_n: int = 5) -> list[LawChunk]
answer_with_citations(question: str) -> TaxAnswer
```

Retrieval must include:

- vector search from Pinecone
- metadata filtering where useful
- BGE reranking
- citation formatting
- source chunk IDs
- no hallucinated law references

Prefer returning structured objects over raw strings.

## Agent Design

CrewAI agents should have narrow responsibilities.

Recommended agents:

- `TaxIssueAnalyzer`: extracts facts and missing facts
- `LawRetriever`: calls RAG/MCP tools only
- `ExemptionReasoner`: applies retrieved law to facts
- `CitationVerifier`: checks that all cited laws exist in retrieved chunks
- `AnswerComposer`: writes Korean user-facing answer

Agents must not independently invent legal rules. Any legal proposition must be grounded in retrieved chunks.

## MCP Tooling

The MCP server should expose tools such as:

```text
search_tax_law
retrieve_article
analyze_capital_gains_exemption
verify_citations
```

MCP tools should return structured JSON with:

- answer
- citations
- retrieved chunk IDs
- confidence
- missing facts
- warnings

## Coding Standards

- Use Python type hints for public functions.
- Keep I/O, parsing, retrieval, and UI concerns separated.
- Prefer explicit dataclasses or Pydantic models for law chunks and answers.
- Add tests for chunk parsing, citation formatting, and retrieval behavior.
- Keep prompts versioned in `src/agents/prompts.py`.
- Use Korean for domain prompts and final user-facing legal explanations.
- Use English for code comments, function names, and technical identifiers.

## Testing Priorities

High-priority tests:

- XML parser preserves `조 / 항 / 호 / 목`
- chunk metadata includes law name and article number
- retrieval returns source chunk IDs
- reranker is called before final context selection
- citations only come from retrieved chunks
- missing facts are surfaced instead of guessed
- UI does not contain legal reasoning logic

## Final Principle

This project is a legal RAG system, not a chatbot with tax-law flavor.

Every legal answer must be:

- retrieved
- reranked
- cited
- traceable
- cautious about missing facts
```



OpenAI Codex v0.130.0
--------
workdir: C:\Users\next0\claude-test\tax-rag
model: gpt-5.5
provider: openai
approval: never
sandbox: danger-full-access
reasoning effort: none
reasoning summaries: none
session id: 019e1637-6e99-7cf2-8ad0-be6747736d41
--------
user
You are advising on CLAUDE.md design for a Korean tax RAG AI project.

PROJECT: RAW agent - tax-rag — capital gains tax (양도소득세) exemption determination AI.
STACK: CrewAI (agent orchestration), LlamaIndex (RAG), FastAPI + MCP server, Pinecone Serverless, Claude 3.5/Opus 4.7, Streamlit, Upstage Solar embeddings, BAAI BGE-Reranker.
DATA: Korean law XML from law.go.kr DRF API (OC=jctax). 2,238 chunks from 6 laws parsed into 조/항/호 hierarchy.
PHASE: 4-week hackathon (KAIST SW Education Center Track C: must use LangChain, CrewAI, MCP) → long-term LinkTax SaaS.

Design a CLAUDE.md file (for AI coding assistants) that covers:
1. Project overview and architecture constraints the AI must follow
2. Directory structure conventions (src/collect.py, src/embed.py, src/rag.py, src/agents/, src/mcp_server.py, src/ui.py)
3. Critical DO NOTs: what the AI must never do (e.g., hardcode API keys, bypass RAG with direct LLM answers, skip reranker, change chunking strategy)
4. Development workflow: how to run each component, env vars required
5. Korean law domain rules: article structure [조-항-호-목], why structure-aware chunking matters

Output the actual CLAUDE.md content in Korean/English mixed (Korean for domain rules, English for tech specs).
codex
```markdown
# CLAUDE.md

This file guides AI coding assistants working on `tax-rag`, a Korean capital gains tax exemption RAG AI project.

## Project Overview

`tax-rag` is the RAW agent for Korean capital gains tax exemption determination, focused on **양도소득세 비과세 / 감면 / 중과 여부 판단**.

The system must answer tax-law questions by retrieving and reasoning over Korean legal sources, not by relying on model memory.

Primary goals:

- Hackathon phase: KAIST SW Education Center Track C
- Required technologies: LangChain, CrewAI, MCP
- Long-term direction: LinkTax SaaS tax advisory infrastructure

Core stack:

- Agent orchestration: CrewAI
- RAG framework: LlamaIndex
- API layer: FastAPI
- Tool protocol: MCP server
- Vector DB: Pinecone Serverless
- Embeddings: Upstage Solar embeddings
- Reranker: BAAI BGE-Reranker
- UI: Streamlit
- LLMs: Claude 3.5 / Claude Opus 4.7
- Data source: Korean law XML from law.go.kr DRF API using `OC=jctax`

Current corpus:

- 6 Korean tax-related laws
- 2,238 structure-aware chunks
- Parsed by Korean legal hierarchy: `조 / 항 / 호 / 목`

## Architecture Constraints

Follow this pipeline:

```text
law.go.kr DRF XML
  -> src/collect.py
  -> structure-aware legal parser
  -> chunks preserving 조-항-호-목 metadata
  -> src/embed.py
  -> Upstage Solar embeddings
  -> Pinecone Serverless
  -> src/rag.py
  -> retrieval + BGE reranking
  -> CrewAI agents
  -> MCP tools / FastAPI
  -> Streamlit UI
```

AI assistants must preserve the RAG-first architecture.

All legal answers must flow through:

1. Query understanding
2. Retrieval from indexed Korean law chunks
3. Reranking
4. Evidence-grounded reasoning
5. Answer with legal citations

Direct LLM-only legal answers are not acceptable.

## Directory Structure

Use the following conventions.

```text
tax-rag/
├── CLAUDE.md
├── README.md
├── requirements.txt
├── .env.example
├── data/
│   ├── raw/                 # Original XML from law.go.kr
│   ├── parsed/              # Parsed law JSON/chunks
│   └── samples/             # Small test fixtures
├── src/
│   ├── collect.py           # Fetch Korean law XML from law.go.kr DRF API
│   ├── embed.py             # Build embeddings and upsert to Pinecone
│   ├── rag.py               # Retrieval, reranking, citation assembly
│   ├── mcp_server.py        # MCP tool server for tax-law retrieval/reasoning
│   ├── ui.py                # Streamlit UI
│   └── agents/
│       ├── __init__.py
│       ├── crew.py          # CrewAI crew definition
│       ├── tools.py         # Agent tools, including MCP/RAG tools
│       ├── roles.py         # Agent role definitions
│       └── prompts.py       # System/task prompts
├── tests/
│   ├── test_collect.py
│   ├── test_chunking.py
│   ├── test_rag.py
│   └── fixtures/
└── scripts/
    └── dev_*.ps1            # Optional local helper scripts
```

Keep responsibilities separated:

- `collect.py`: data collection only
- `embed.py`: embedding/indexing only
- `rag.py`: retrieval/reranking/citation logic only
- `agents/`: CrewAI orchestration only
- `mcp_server.py`: MCP interface only
- `ui.py`: user interface only

Do not put business logic into the Streamlit UI.

## Critical DO NOTs

Never do the following:

- Do not hardcode API keys, tokens, Pinecone indexes, or law.go.kr credentials.
- Do not commit `.env`, credentials, raw secrets, or local API responses containing private keys.
- Do not bypass RAG and answer Korean tax-law questions directly from the LLM.
- Do not skip the BGE reranker for final legal context selection.
- Do not change the existing chunking strategy without explicit approval.
- Do not flatten Korean law structure into plain paragraphs if metadata would be lost.
- Do not remove `조 / 항 / 호 / 목` metadata from chunks.
- Do not merge unrelated laws into a single chunk.
- Do not silently change Pinecone namespace, index dimension, or embedding model.
- Do not replace Upstage Solar embeddings unless explicitly requested.
- Do not invent legal citations.
- Do not cite a law article unless it was retrieved from the indexed corpus.
- Do not treat model output as legal authority.
- Do not present answers as final legal advice without caveats.
- Do not modify hackathon-required technologies away from LangChain, CrewAI, or MCP.

## Environment Variables

Required environment variables should be loaded from `.env`.

```env
# law.go.kr DRF
LAW_GO_KR_OC=jctax
LAW_GO_KR_BASE_URL=https://www.law.go.kr/DRF/lawSearch.do

# LLM
ANTHROPIC_API_KEY=
CLAUDE_MODEL=claude-3-5-sonnet-latest

# Embeddings
UPSTAGE_API_KEY=
UPSTAGE_EMBEDDING_MODEL=

# Pinecone
PINECONE_API_KEY=
PINECONE_INDEX_NAME=
PINECONE_NAMESPACE=tax-law
PINECONE_CLOUD=aws
PINECONE_REGION=us-east-1

# Reranker
BGE_RERANKER_MODEL=BAAI/bge-reranker-v2-m3

# App
FASTAPI_HOST=0.0.0.0
FASTAPI_PORT=8000
MCP_HOST=0.0.0.0
MCP_PORT=8001
STREAMLIT_PORT=8501
```

If an env var is missing, fail clearly with an actionable error. Do not fall back to fake keys or hidden defaults.

## Development Workflow

Install dependencies:

```bash
pip install -r requirements.txt
```

Collect Korean law XML:

```bash
python src/collect.py
```

Parse and embed law chunks:

```bash
python src/embed.py
```

Run RAG locally:

```bash
python src/rag.py
```

Run MCP server:

```bash
python src/mcp_server.py
```

Run FastAPI server:

```bash
uvicorn src.mcp_server:app --host 0.0.0.0 --port 8001 --reload
```

Run Streamlit UI:

```bash
streamlit run src/ui.py --server.port 8501
```

Run tests:

```bash
pytest
```

Before changing retrieval, chunking, embeddings, or reranking behavior, add or update tests under `tests/`.

## Korean Law Domain Rules

양도소득세 판단은 단순 키워드 검색으로 처리하면 안 된다. 반드시 법령의 계층 구조를 보존해야 한다.

한국 법령 구조:

```text
법률 / 시행령 / 시행규칙
  └── 조
      └── 항
          └── 호
              └── 목
```

예시:

```text
소득세법 제89조 제1항 제3호
소득세법 시행령 제154조 제1항
조세특례제한법 제99조의2 제1항
```

각 단위의 의미:

- `조`: 핵심 법률 규정 단위
- `항`: 조문 내 주요 요건 분기
- `호`: 세부 요건 또는 예외 조건
- `목`: 더 세밀한 열거 조건

Structure-aware chunking matters because:

- 비과세 요건은 보통 여러 `항`과 `호`에 나누어져 있다.
- 예외 규정은 같은 `조` 안의 다른 `항` 또는 시행령에 존재할 수 있다.
- “1세대 1주택” 판단은 법률, 시행령, 시행규칙이 함께 연결된다.
- 같은 단어라도 위치한 조문 계층에 따라 법적 의미가 달라진다.
- 조문 번호 없이 텍스트만 저장하면 정확한 citation과 legal traceability가 깨진다.

따라서 모든 chunk는 최소한 다음 metadata를 가져야 한다.

```json
{
  "law_name": "소득세법",
  "law_type": "법률",
  "article_no": "제89조",
  "article_title": "비과세 양도소득",
  "paragraph_no": "제1항",
  "subparagraph_no": "제3호",
  "item_no": null,
  "effective_date": "YYYY-MM-DD",
  "source_url": "law.go.kr URL",
  "text": "..."
}
```

## Legal Answering Rules

When answering user tax questions:

1. 먼저 사실관계를 정리한다.
2. 필요한 판단요건을 식별한다.
3. RAG retrieval을 수행한다.
4. BGE reranker로 최종 근거 조문을 선별한다.
5. 조문 근거와 함께 판단한다.
6. 불확실한 사실관계는 질문으로 되묻는다.
7. 법률 자문이 아닌 정보 제공임을 명확히 한다.

Required answer style:

```text
요약 판단:
- ...

근거 법령:
- 소득세법 제89조 제1항 제3호
- 소득세법 시행령 제154조 제1항

판단 과정:
1. ...
2. ...

추가 확인 필요:
- 취득일
- 양도일
- 보유기간
- 거주기간
- 세대 구성
- 보유 주택 수
```

Do not produce confident conclusions when required facts are missing.

Important facts for 양도소득세 exemption analysis usually include:

- 취득일
- 양도일
- 양도가액
- 취득가액
- 보유기간
- 거주기간
- 세대원 구성
- 양도 당시 보유 주택 수
- 조정대상지역 여부
- 일시적 2주택 여부
- 상속 / 증여 / 혼인 / 동거봉양 여부
- 농어촌주택 / 장기임대주택 / 조특법 특례 여부

## Retrieval Requirements

`src/rag.py` should expose a stable interface similar to:

```python
retrieve_tax_law(query: str, top_k: int = 20, rerank_top_n: int = 5) -> list[LawChunk]
answer_with_citations(question: str) -> TaxAnswer
```

Retrieval must include:

- vector search from Pinecone
- metadata filtering where useful
- BGE reranking
- citation formatting
- source chunk IDs
- no hallucinated law references

Prefer returning structured objects over raw strings.

## Agent Design

CrewAI agents should have narrow responsibilities.

Recommended agents:

- `TaxIssueAnalyzer`: extracts facts and missing facts
- `LawRetriever`: calls RAG/MCP tools only
- `ExemptionReasoner`: applies retrieved law to facts
- `CitationVerifier`: checks that all cited laws exist in retrieved chunks
- `AnswerComposer`: writes Korean user-facing answer

Agents must not independently invent legal rules. Any legal proposition must be grounded in retrieved chunks.

## MCP Tooling

The MCP server should expose tools such as:

```text
search_tax_law
retrieve_article
analyze_capital_gains_exemption
verify_citations
```

MCP tools should return structured JSON with:

- answer
- citations
- retrieved chunk IDs
- confidence
- missing facts
- warnings

## Coding Standards

- Use Python type hints for public functions.
- Keep I/O, parsing, retrieval, and UI concerns separated.
- Prefer explicit dataclasses or Pydantic models for law chunks and answers.
- Add tests for chunk parsing, citation formatting, and retrieval behavior.
- Keep prompts versioned in `src/agents/prompts.py`.
- Use Korean for domain prompts and final user-facing legal explanations.
- Use English for code comments, function names, and technical identifiers.

## Testing Priorities

High-priority tests:

- XML parser preserves `조 / 항 / 호 / 목`
- chunk metadata includes law name and article number
- retrieval returns source chunk IDs
- reranker is called before final context selection
- citations only come from retrieved chunks
- missing facts are surfaced instead of guessed
- UI does not contain legal reasoning logic

## Final Principle

This project is a legal RAG system, not a chatbot with tax-law flavor.

Every legal answer must be:

- retrieved
- reranked
- cited
- traceable
- cautious about missing facts
```

tokens used
4,792

```

## Concise summary

Provider completed successfully. Review the raw output for details.

## Action items

- Review the response and extract decisions you want to apply.
- Capture follow-up implementation tasks if needed.
