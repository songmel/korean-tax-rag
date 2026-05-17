# codex advisor artifact

- Provider: codex
- Exit code: 0
- Created at: 2026-05-17T11:13:46.008Z

## Original task

Deep architecture review for production-grade Korean tax law RAG engine. Current stack: Pinecone (vector DB) + Upstage Solar (embeddings) + BGE-Reranker-v2-m3 + Claude Sonnet (LLM) + CrewAI 2-agent (TaxResearcher + TaxAdvisor) + FastMCP server + Streamlit UI. Pipeline: collect law XML → version-aware chunking (조-항-호-목 hierarchy) → embed → Pinecone → query → rerank → LLM reasoning. The system will be embedded in a production tax advisory platform that receives structured case data (취득일, 양도일, 보유기간, 세대구성, 주택수 등) from an upstream process. Question: 1) What architectural patterns make this engine simple yet powerful at production scale? 2) How should agent learning/improvement work — feedback loops, golden datasets, retrieval quality tracking? 3) What's the minimum surface area this engine should expose as an API for clean integration? 4) Where are the failure modes and how to make them graceful?

## Final prompt

Deep architecture review for production-grade Korean tax law RAG engine. Current stack: Pinecone (vector DB) + Upstage Solar (embeddings) + BGE-Reranker-v2-m3 + Claude Sonnet (LLM) + CrewAI 2-agent (TaxResearcher + TaxAdvisor) + FastMCP server + Streamlit UI. Pipeline: collect law XML → version-aware chunking (조-항-호-목 hierarchy) → embed → Pinecone → query → rerank → LLM reasoning. The system will be embedded in a production tax advisory platform that receives structured case data (취득일, 양도일, 보유기간, 세대구성, 주택수 등) from an upstream process. Question: 1) What architectural patterns make this engine simple yet powerful at production scale? 2) How should agent learning/improvement work — feedback loops, golden datasets, retrieval quality tracking? 3) What's the minimum surface area this engine should expose as an API for clean integration? 4) Where are the failure modes and how to make them graceful?

## Raw output

```text
The right production shape is: **deterministic retrieval engine first, agentic explanation second**. In your code, the durable core is already `[src/rag.py](</C:/Users/user/cording2025/tax-rag/src/rag.py>)`; the CrewAI layer in `[src/agents/crew.py](</C:/Users/user/cording2025/tax-rag/src/agents/crew.py>)` should stay optional, not become the main contract. One concrete defect to fix before scaling: `[src/embed.py](</C:/Users/user/cording2025/tax-rag/src/embed.py>)` truncates `full_text` to 400 chars in Pinecone metadata, but reranking and answer synthesis read that field back. That will silently drop provisos, exceptions, and trailing clauses.

**1. Architecture**
- Make the online path a typed pipeline, not a free-form multi-agent conversation: `facts normalization -> issue framing -> temporal filter selection -> retrieval -> rerank -> constrained reasoning -> answer assembly`.
- Treat the engine as a **legal evidence service**. The LLM should explain over retrieved authority, not decide what the retrieval plan is from scratch.
- Keep **offline and online planes separate**. Offline: XML ingestion, version parsing, chunking, evals, index build, canary rollout. Online: low-latency retrieval and answering only.
- Make **time/version** first-class. Every request should carry at least `legal_basis_date` and often both `acquisition_date` and `disposition_date`. Transitional provisions are a top-tier failure mode in tax.
- Add **hybrid retrieval**. Tax law has exact strings (`제89조`, `1세대 1주택`, 시행령 조문번호) that dense search can miss; Pinecone explicitly supports hybrid dense+lexical patterns.
- Store a **chunk graph**, not only flat chunks: article, paragraph, item, parent article, sibling references, version MST, effective/expiration dates, law family. Retrieve the best node, then expand to parent/sibling when needed.
- Put **deterministic rule checks before the LLM** for obvious gaps: contradictory facts, missing residency period, unclear household count, unknown adjustment-target area status. Return `insufficient_facts` early when appropriate.
- Collapse the 2-agent design into a **single orchestrated flow with typed state** for production. CrewAI Flows are a better fit than open-ended roleplay because state is explicit and integration is cleaner.

**2. Learning / Improvement**
- Do **not** let the system “learn” online from raw user interactions. Use eval-driven improvement, not weight updates from production traffic.
- Build three golden sets:
  - `retrieval gold`: case -> required article IDs / forbidden article IDs / correct legal version
  - `reasoning gold`: case -> expected outcome / allowed ambiguity / required missing facts
  - `regression gold`: known hard edge cases, especially law amendments and exceptions
- Track retrieval separately from reasoning. Minimum metrics:
  - `Recall@k` on gold article IDs
  - `MRR` or `nDCG`
  - temporal version accuracy
  - citation precision: cited chunks must be retrieved chunks
  - unsupported-claim rate
  - missing-fact recall
  - abstention quality: does it escalate when it should?
- Log a full answer trace: normalized facts, generated search intents, retrieved chunk IDs, rerank scores, prompt version, model version, index version, final citations, latency, token cost.
- Use feedback in ranked order:
  - explicit reviewer corrections
  - advisor override / manual-review outcomes
  - user follow-up that indicates error or ambiguity
  - unresolved or escalated cases
- Re-run the full golden set on every change to chunking, retrieval, reranker, prompt, or model. Anthropic batch processing is useful for this because eval workloads are asynchronous and cheaper in batch.
- Improvement priority should usually be: `chunking/metadata -> retrieval -> reranker -> prompt -> agent behavior`. Most production gains come before the agent layer.

**3. API Surface**
Expose the smallest domain API possible:
- `POST /v1/case-analysis`
- Input: `case_id`, `facts`, `question`, `legal_basis_date`, `response_mode`, optional `jurisdiction/policy flags`
- Output: `status`, `conclusion`, `reasoning_summary`, `citations`, `missing_facts`, `warnings`, `confidence`, `trace_id`, `knowledge_snapshot`
- `POST /v1/feedback`
- `GET /v1/results/{trace_id}` if you support async
- `GET /healthz` and `GET /readyz`

Do **not** expose `search_tax_law`, `retrieve_article`, MCP tool shapes, or agent internals to the upstream platform. Those are internal debugging and tooling surfaces. Upstream systems should integrate with one domain object: “analyze this tax case.”

**4. Failure Modes**
- Wrong legal version or missed transitional rule
- Exact-term retrieval miss
- Chunk boundary loses an exception/proviso
- Structured facts are incomplete or contradictory
- LLM gives fluent but weakly grounded reasoning
- Pinecone freshness lag during reindex or amendment rollout
- External provider latency/outage
- Agent orchestration adds cost and non-determinism without accuracy gain

Make them graceful by:
- returning explicit statuses: `answerable`, `insufficient_facts`, `manual_review`, `no_authority_found`
- falling back to **evidence-only mode** if the LLM is unavailable
- requiring citations to map to retrieved chunk IDs only
- showing `knowledge_snapshot` on every response: corpus version, index version, prompt version, model version, legal basis date
- using dual-index or canary rollouts instead of in-place reindex swaps
- setting latency and token budgets with circuit breakers
- routing low-confidence or temporally complex cases to manual review instead of forcing a binary answer

One additional recommendation: for the final answering step, consider using Claude’s built-in document citations with your retrieved chunks as documents instead of prompt-only JSON citations. That gives tighter grounding and more reliable source pointers.

Sources:
- Pinecone architecture: https://docs.pinecone.io/guides/get-started/database-architecture
- Pinecone search overview: https://docs.pinecone.io/guides/search/search-overview
- Pinecone metadata/filtering: https://docs.pinecone.io/guides/index-data/indexing-overview
- Pinecone hybrid search: https://docs.pinecone.io/guides/search/hybrid-search
- Anthropic citations: https://platform.claude.com/docs/en/build-with-claude/citations
- Anthropic prompt caching: https://platform.claude.com/docs/en/build-with-claude/prompt-caching
- Anthropic batch processing: https://docs.anthropic.com/en/docs/build-with-claude/batch-processing
- CrewAI Flows: https://docs.crewai.com/en/concepts/flows
- MCP architecture: https://modelcontextprotocol.io/docs/learn/architecture
- Upstage Solar Embedding official post: https://www.upstage.ai/blog/en/solar-embedding-1-large

If you want, I can turn this into a concrete target architecture diagram plus a `v1` API schema for your FastMCP/FastAPI service.


OpenAI Codex v0.123.0 (research preview)
--------
workdir: c:\Users\user\cording2025\tax-rag
model: gpt-5.4
provider: openai
approval: never
sandbox: danger-full-access
reasoning effort: none
reasoning summaries: none
session id: 019e35a2-0fc6-7e11-ab1d-1d61f6e5a24e
--------
user
Deep architecture review for production-grade Korean tax law RAG engine. Current stack: Pinecone (vector DB) + Upstage Solar (embeddings) + BGE-Reranker-v2-m3 + Claude Sonnet (LLM) + CrewAI 2-agent (TaxResearcher + TaxAdvisor) + FastMCP server + Streamlit UI. Pipeline: collect law XML → version-aware chunking (조-항-호-목 hierarchy) → embed → Pinecone → query → rerank → LLM reasoning. The system will be embedded in a production tax advisory platform that receives structured case data (취득일, 양도일, 보유기간, 세대구성, 주택수 등) from an upstream process. Question: 1) What architectural patterns make this engine simple yet powerful at production scale? 2) How should agent learning/improvement work — feedback loops, golden datasets, retrieval quality tracking? 3) What's the minimum surface area this engine should expose as an API for clean integration? 4) Where are the failure modes and how to make them graceful?
codex
I’m reviewing the current codebase first so the architecture advice is grounded in what you actually have, then I’ll map that against current official product capabilities and production patterns.
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg --files' in c:\Users\user\cording2025\tax-rag
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-ChildItem -Force' in c:\Users\user\cording2025\tax-rag
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git status --short' in c:\Users\user\cording2025\tax-rag
 succeeded in 3374ms:
 M .env.example
 M src/collect.py
 M src/embed.py
 M src/mcp_server.py
 M src/rag.py
 M src/ui.py
?? .omc/

 succeeded in 3391ms:
tests\__init__.py
tests\test_rag.py
tests\test_chunking.py
src\__init__.py
src\ui.py
src\rag.py
src\mcp_server.py
src\embed.py
src\collect.py
CLAUDE.md
requirements.txt
README.md
scripts\claude_desktop_config.json
src\agents\__init__.py
src\agents\tools.py
src\agents\roles.py
src\agents\prompts.py
src\agents\crew.py

 succeeded in 3412ms:


    디렉터리: C:\Users\user\cording2025\tax-rag


Mode                 LastWriteTime         Length Name                                                                 
----                 -------------         ------ ----                                                                 
d--h--        2026-05-17   오후 7:55                .git                                                                 
d-----        2026-05-17   오후 7:51                .omc                                                                 
d-----        2026-05-17   오후 7:55                .pytest_cache                                                        
d-----        2026-05-17   오후 5:27                data                                                                 
d-----        2026-05-17   오후 7:44                scripts                                                              
d-----        2026-05-17   오후 8:06                src                                                                  
d-----        2026-05-17   오후 7:55                tests                                                                
-a----        2026-05-17   오후 7:56            947 .env                                                                 
-a----        2026-05-17   오후 7:56            739 .env.example                                                         
-a----        2026-05-17   오후 4:56            300 .gitignore                                                           
-a----        2026-05-17   오후 7:50          12278 CLAUDE.md                                                            
-a----        2026-05-17   오후 4:56           7742 README.md                                                            
-a----        2026-05-17   오후 7:50            384 requirements.txt                                                     



codex
I have the project shape now. Next I’m reading the retrieval, agent, and interface layers to identify what should stay separate and what should collapse for production simplicity.
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Path README.md' in c:\Users\user\cording2025\tax-rag
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content -Path src\\rag.py" in c:\Users\user\cording2025\tax-rag
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content -Path src\\agents\\crew.py" in c:\Users\user\cording2025\tax-rag
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content -Path src\\mcp_server.py" in c:\Users\user\cording2025\tax-rag
 succeeded in 3460ms:
# RAW agent ???묐룄?뚮뱷??AI

?묐룄?뚮뱷??愿???멸툑 ?먮떒??**?뚮뱷?몃쾿쨌議곗꽭?밸??쒗븳踰?議곕Ц??洹쇨굅**???섑뻾?섎뒗 RAG 湲곕컲 AI ?먯씠?꾪듃?낅땲??
怨듭떇 踰뺣졊 ?곗씠??law.go.kr)瑜?踰≫꽣 DB???몃뜳?깊븯怨? ?ъ슜??吏덈Ц?????洹쇨굅 議곕Ц??寃?됀룹젣?쑣룻뙋?⑦빀?덈떎.

> KAIST SW援먯쑁?쇳꽣 4二??댁빱???몃옓C 異쒗뭹??

---

## ?꾪궎?띿쿂

```
?ъ슜???낅젰 (?묐룄 ?뺣낫)
    ??
    ??
?뚢???????????????????
?? Streamlit UI   ?? ???붾쾭洹?UI: top-5 議곕Ц, ?좎궗???먯닔, ?먯씠?꾪듃 異붾줎 怨쇱젙
?붴?????????р??????????
         ??
    ??
?뚢???????????????????
??  MCP Server    ?? ??FastAPI 湲곕컲 Model Context Protocol
??  (FastAPI)     ??   tools: search_tax_law, retrieve_article,
?붴?????????р??????????          analyze_exemption, verify_citations
         ??
    ??
?뚢???????????????????????????????????????????
??          CrewAI Orchestration          ??
??                                        ??
?? Tax Researcher ????Tax Advisor         ??
?? (?ъ떎愿怨??뺣━ +   (議곕Ц ?곸슜 ??       ??
??  RAG 寃??         鍮꾧낵???먮떒)        ??
?붴?????????р??????????????????????????????????
         ??
    ??
?뚢???????????????????    ?뚢????????????????????
?? LlamaIndex RAG ?귘?????뷜봻 Pinecone 踰≫꽣 DB ??
?? + BGE Reranker ??    ??(2,238 踰뺣졊 泥?겕) ??
?붴???????????????????    ?붴????????????????????
         ??
    ??
?뚢???????????????????
?? Claude Opus    ?? ??理쒖쥌 ?먮떒 諛??쒓뎅???묐떟 ?앹꽦
?? 4.7 (Anthropic)??
?붴???????????????????
         ??
    ??
踰뺣졊 ?곗씠???먯쿇: law.go.kr DRF API
(?뚮뱷?몃쾿, ?쒗뻾?? ?쒗뻾洹쒖튃 + 議곗꽭?밸??쒗븳踰? ?쒗뻾?? ?쒗뻾洹쒖튃)
```

---

## 鍮좊Ⅸ ?쒖옉

### ?ъ쟾 ?붽굔

- Python 3.12+
- Pinecone 怨꾩젙 (Serverless ?몃뜳??
- Anthropic API ??
- OpenAI ?먮뒗 Upstage API ??(?꾨쿋?⑹슜)

### ?ㅼ튂

```bash
git clone https://github.com/JC0623/tax-rag-01.git
cd tax-rag-01
pip install -r requirements.txt
```

> **Windows**: `python`??PATH???놁쑝硫??꾩껜 寃쎈줈 ?ъ슜
> `C:\Users\{?ъ슜??\AppData\Local\Programs\Python\Python312\python.exe`

### ?섍꼍蹂???ㅼ젙

```bash
cp .env.example .env
```

`.env` ?뚯씪???댁뼱 ?꾨옒 ?ㅻ? ?낅젰?⑸땲??

| 蹂?섎챸 | ?ㅻ챸 |
|--------|------|
| `ANTHROPIC_API_KEY` | Anthropic Claude API ??|
| `PINECONE_API_KEY` | Pinecone 踰≫꽣 DB ??|
| `PINECONE_INDEX_NAME` | Pinecone ?몃뜳???대쫫 (?? `tax-rag`) |
| `OPENAI_API_KEY` | OpenAI ?꾨쿋????(text-embedding-3-large) |
| `UPSTAGE_API_KEY` | Upstage Solar ?꾨쿋????(?좏깮, ?곗꽑 ?곸슜) |
| `LAW_API_OC` | law.go.kr DRF OC ?뚮씪誘명꽣 (`jctax`) |

### ?ㅽ뻾 ?쒖꽌

```bash
# 1. 踰뺣졊 ?곗씠???섏쭛 (理쒖큹 1?? ?댄썑 罹먯떆 ?ъ슜)
python src/collect.py

# 2. ?꾨쿋???앹꽦 諛?Pinecone ?낅줈??
python src/embed.py

# 3. RAG ?뚯씠?꾨씪??濡쒖뺄 ?뚯뒪??
python src/rag.py

# 4. MCP ?쒕쾭 ?ㅽ뻾 (蹂꾨룄 ?곕???
uvicorn src.mcp_server:app --host 0.0.0.0 --port 8001 --reload

# 5. Streamlit UI ?ㅽ뻾
streamlit run src/ui.py --server.port 8501
```

釉뚮씪?곗??먯꽌 `http://localhost:8501` ?묒냽

---

## ?꾨줈?앺듃 援ъ“

```
tax-rag/
?쒋?? src/
??  ?쒋?? collect.py        # law.go.kr DRF API ??XML ??JSON 泥?겕 (2,238媛?
??  ?쒋?? embed.py          # ?꾨쿋???앹꽦 ??Pinecone ?낅줈??
??  ?쒋?? rag.py            # LlamaIndex 寃??+ BGE Reranker
??  ?쒋?? mcp_server.py     # FastAPI + MCP ?꾧뎄 ?쒕쾭
??  ?쒋?? ui.py             # Streamlit ?붾쾭洹?UI
??  ?붴?? agents/
??      ?쒋?? crew.py       # CrewAI Crew ?뺤쓽
??      ?쒋?? tools.py      # RAG/MCP ?꾧뎄 ?섑띁
??      ?쒋?? roles.py      # Agent ??븷 ?뺤쓽
??      ?붴?? prompts.py    # ?꾨＼?꾪듃 踰꾩쟾 愿由?
?쒋?? data/
??  ?쒋?? raw/              # XML ?먮낯 (.gitignore)
??  ?붴?? processed/        # JSON 泥?겕 (.gitignore)
?쒋?? tests/                # ?⑥쐞 ?뚯뒪??
?쒋?? .env.example          # ?섍꼍蹂???쒗뵆由?
?쒋?? requirements.txt
?쒋?? CLAUDE.md             # AI 肄붾뵫 ?댁떆?ㅽ꽩??媛?대뱶
?붴?? README.md
```

---

## ?섏쭛 踰뺣졊 紐⑸줉

| 踰뺣졊紐?| MST | 遺꾨쪟 |
|--------|-----|------|
| ?뚮뱷?몃쾿 | 285523 | 踰뺣쪧 |
| ?뚮뱷?몃쾿 ?쒗뻾??| 285631 | ??듬졊??|
| ?뚮뱷?몃쾿 ?쒗뻾洹쒖튃 | 284987 | 遺??|
| 議곗꽭?밸??쒗븳踰?| 285525 | 踰뺣쪧 |
| 議곗꽭?밸??쒗븳踰??쒗뻾??| 283625 | ??듬졊??|
| 議곗꽭?밸??쒗븳踰??쒗뻾洹쒖튃 | 284611 | 遺??|

珥?**2,238媛?泥?겕** (議곕Ц?⑥쐞 湲곗?, 議?????紐?援ъ“ 蹂댁〈)

---

## 媛쒕컻 濡쒕뱶留?(4二??댁빱??

| 二쇱감 | 紐⑺몴 | ?꾨즺 湲곗? |
|------|------|----------|
| **Week 1** | ?곗씠???뚯씠?꾨씪??| `collect.py` + `embed.py` ?꾩꽦, Pinecone ?몃뜳??援ъ텞 |
| **Week 2** | RAG + ?먯씠?꾪듃 | `rag.py` BGE reranker ?곸슜, CrewAI 2-agent ?뚰겕?뚮줈??|
| **Week 3** | MCP ?쒕쾭 + UI | FastAPI MCP ?꾧뎄, Streamlit ?붾쾭洹?UI (top-5 議곕Ц ?쒖떆) |
| **Week 4** | ?듯빀 + ?곕え | End-to-end ?뚯뒪?? ?댁빱??諛쒗몴 ?쒕굹由ъ삤 以鍮?|

---

## ???湲곗뿬 媛?대뱶

### 釉뚮옖移??꾨왂

```bash
main          # 諛쒗몴???덉젙 踰꾩쟾
dev           # ?듯빀 媛쒕컻 釉뚮옖移?
feature/*     # 湲곕뒫 媛쒕컻 (?? feature/rag-reranker)
fix/*         # 踰꾧렇 ?섏젙
```

### ??踰뺣졊 異붽? 諛⑸쾿

[src/collect.py](src/collect.py)??`TARGET_LAWS` 由ъ뒪?몄뿉 ??ぉ 異붽?:

```python
{"name": "踰뺣졊紐?, "mst": "MST踰덊샇", "category": "踰뺣쪧|??듬졊??遺??}
```

MST 踰덊샇??[law.go.kr](https://www.law.go.kr) ?먯꽌 ?대떦 踰뺣졊 寃????URL?먯꽌 ?뺤씤.

### ?먯씠?꾪듃 ?뺤옣 諛⑸쾿

1. `src/agents/roles.py`??????븷 ?뺤쓽
2. `src/agents/tools.py`???꾩슂???꾧뎄 異붽?
3. `src/agents/prompts.py`???꾨＼?꾪듃 踰꾩쟾 愿由?
4. `src/agents/crew.py`??Crew???먯씠?꾪듃/?쒖뒪???깅줉

### 而ㅻ컠 ??泥댄겕由ъ뒪??

- [ ] `.env`媛 而ㅻ컠???ы븿?섏? ?딆븯?붿? ?뺤씤
- [ ] `data/raw/`, `data/processed/` ?쒖쇅 ?뺤씤
- [ ] ??API ?ㅺ? 肄붾뱶???섎뱶肄붾뵫?섏? ?딆븯?붿? ?뺤씤
- [ ] 愿???뚯뒪??異붽? ?먮뒗 ?낅뜲?댄듃

---

## 踰뺣쪧 怨좎?

蹂??쒖뒪?쒖? **?뺣낫 ?쒓났** 紐⑹쟻?쇰줈 媛쒕컻?섏뿀?쇰ŉ, 踰뺣쪧 ?먮Ц???꾨떃?덈떎.
?묐룄?뚮뱷???좉퀬쨌?⑸???愿??理쒖쥌 ?먮떒? 諛섎뱶??怨듭씤 ?몃Т?ъ? ?곷떞?섏떆湲?諛붾엻?덈떎.

---

## 湲곗닠 ?ㅽ깮

![Python](https://img.shields.io/badge/Python-3.12-blue)
![CrewAI](https://img.shields.io/badge/CrewAI-0.95+-green)
![LlamaIndex](https://img.shields.io/badge/LlamaIndex-0.12+-orange)
![Pinecone](https://img.shields.io/badge/Pinecone-Serverless-purple)
![Claude](https://img.shields.io/badge/Claude-Opus%204.7-red)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-teal)
![Streamlit](https://img.shields.io/badge/Streamlit-1.40+-pink)

 succeeded in 3488ms:
"""
RAG 寃??紐⑤뱢
Pinecone 踰≫꽣 寃??+ BGE Reranker ??Claude 踰뺣졊 異붾줎
"""
import os
import json
from typing import Optional

import anthropic
from dotenv import load_dotenv
from openai import OpenAI
from pinecone import Pinecone
from pydantic import BaseModel
from sentence_transformers import CrossEncoder

load_dotenv()

from src.agents.prompts import RAG_SYSTEM_PROMPT, RAG_USER_TEMPLATE

# ?? ?섍꼍蹂????????????????????????????????????????????????????
UPSTAGE_API_KEY = os.getenv("UPSTAGE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "tax-rag")
PINECONE_NAMESPACE = os.getenv("PINECONE_NAMESPACE", "tax-law")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-4-7")
BGE_RERANKER_MODEL = os.getenv("BGE_RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")

# ?? Pydantic 紐⑤뜽 ?????????????????????????????????????????????

class LawChunk(BaseModel):
    id: str
    law_name: str
    article_number: str
    article_title: str
    effective_date: str
    expiration_date: str = ""  # 鍮?臾몄옄??= ?꾪뻾
    full_text: str
    score: float


class TaxAnswer(BaseModel):
    answer: str
    citations: list[str]
    chunk_ids: list[str]
    confidence: float
    missing_facts: list[str]
    warnings: list[str]


# ?? ?깃????대씪?댁뼵??(?ъ궗?? ?????????????????????????????????
_embed_client: Optional[OpenAI] = None
_embed_model: Optional[str] = None
_pinecone_index = None
_reranker: Optional[CrossEncoder] = None


def _get_embed_client() -> tuple[OpenAI, str]:
    global _embed_client, _embed_model
    if _embed_client is None:
        if UPSTAGE_API_KEY:
            _embed_client = OpenAI(
                api_key=UPSTAGE_API_KEY,
                base_url="https://api.upstage.ai/v1",
            )
            _embed_model = "solar-embedding-1-large-query"
        elif OPENAI_API_KEY:
            _embed_client = OpenAI(api_key=OPENAI_API_KEY)
            _embed_model = "text-embedding-3-large"
        else:
            raise RuntimeError("UPSTAGE_API_KEY ?먮뒗 OPENAI_API_KEY媛 ?꾩슂?⑸땲??)
    return _embed_client, _embed_model


def _get_pinecone_index():
    global _pinecone_index
    if _pinecone_index is None:
        if not PINECONE_API_KEY:
            raise RuntimeError("PINECONE_API_KEY媛 ?꾩슂?⑸땲??)
        pc = Pinecone(api_key=PINECONE_API_KEY)
        _pinecone_index = pc.Index(PINECONE_INDEX_NAME)
    return _pinecone_index


def _get_reranker() -> CrossEncoder:
    global _reranker
    if _reranker is None:
        print(f"BGE Reranker 濡쒕뱶 以? {BGE_RERANKER_MODEL}")
        _reranker = CrossEncoder(BGE_RERANKER_MODEL)
        print("Reranker 以鍮??꾨즺")
    return _reranker


# ?? ?듭떖 ?⑥닔 ?????????????????????????????????????????????????

def _embed_query(query: str) -> list[float]:
    client, model = _get_embed_client()
    resp = client.embeddings.create(model=model, input=[query[:2000]])
    return resp.data[0].embedding


def retrieve_tax_law(
    query: str,
    top_k: int = 20,
    rerank_top_n: int = 5,
    as_of_date: Optional[str] = None,
) -> list[LawChunk]:
    """
    踰뺣졊 踰≫꽣 寃??+ BGE reranking ???곸쐞 rerank_top_n媛?諛섑솚.
    as_of_date: "YYYYMMDD" ?뺤떇. 吏?????대떦 ?쒖젏???좏슚??議곕Ц留?寃??
                None?대㈃ ?꾪뻾 + 紐⑤뱺 踰꾩쟾 寃??
    """
    # 1. 荑쇰━ ?꾨쿋??
    query_vec = _embed_query(query)

    # 2. Pinecone ?좎쭨 ?꾪꽣 援ъ꽦
    pinecone_filter = None
    if as_of_date:
        # ?쒗뻾??<= as_of_date AND (留뚮즺???놁쓬(?꾪뻾) OR 留뚮즺??>= as_of_date)
        pinecone_filter = {
            "$and": [
                {"effective_date": {"$lte": as_of_date}},
                {"$or": [
                    {"expiration_date": {"$eq": ""}},
                    {"expiration_date": {"$gte": as_of_date}},
                ]},
            ]
        }

    # 3. Pinecone 踰≫꽣 寃??
    index = _get_pinecone_index()
    query_kwargs = dict(
        vector=query_vec,
        top_k=top_k,
        namespace=PINECONE_NAMESPACE,
        include_metadata=True,
    )
    if pinecone_filter:
        query_kwargs["filter"] = pinecone_filter
    result = index.query(**query_kwargs)
    matches = result.get("matches", [])
    if not matches:
        return []

    # 3. BGE Reranker
    reranker = _get_reranker()
    pairs = [(query, m["metadata"].get("full_text", "")) for m in matches]
    rerank_scores = reranker.predict(pairs)

    # ?먯닔 湲곗? ?뺣젹 ???곸쐞 N媛??좏깮
    ranked = sorted(
        zip(rerank_scores, matches),
        key=lambda x: x[0],
        reverse=True,
    )[:rerank_top_n]

    chunks = []
    for score, match in ranked:
        meta = match["metadata"]
        chunks.append(
            LawChunk(
                id=match["id"],
                law_name=meta.get("law_name", ""),
                article_number=meta.get("article_number", ""),
                article_title=meta.get("article_title", ""),
                effective_date=meta.get("effective_date", ""),
                expiration_date=meta.get("expiration_date", ""),
                full_text=meta.get("full_text", ""),
                score=float(score),
            )
        )
    return chunks


def answer_with_citations(question: str, as_of_date: Optional[str] = None) -> TaxAnswer:
    """寃????reranking ??LLM 異붾줎 ??TaxAnswer 諛섑솚"""
    chunks = retrieve_tax_law(question, as_of_date=as_of_date)

    if not chunks:
        return TaxAnswer(
            answer="愿??踰뺣졊??李얠쓣 ???놁뒿?덈떎.",
            citations=[],
            chunk_ids=[],
            confidence=0.0,
            missing_facts=[],
            warnings=["寃??寃곌낵 ?놁쓬"],
        )

    # ANTHROPIC_API_KEY ?놁쑝硫?LLM ?ㅽ궢, 寃??寃곌낵留?諛섑솚
    if not ANTHROPIC_API_KEY:
        return TaxAnswer(
            answer="[ANTHROPIC_API_KEY 誘몄꽕????寃??寃곌낵留?諛섑솚]\n\n"
            + "\n\n".join(f"[{c.law_name} ??c.article_number}議? {c.full_text[:300]}" for c in chunks),
            citations=[f"{c.law_name} ??c.article_number}議?{c.article_title}".strip() for c in chunks],
            chunk_ids=[c.id for c in chunks],
            confidence=0.0,
            missing_facts=[],
            warnings=["LLM 異붾줎 誘몄닔????ANTHROPIC_API_KEY ?꾩슂"],
        )

    # 而⑦뀓?ㅽ듃 議고빀
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        context_parts.append(
            f"[{i}] {chunk.law_name} ??chunk.article_number}議?{chunk.article_title}\n"
            f"(chunk_id: {chunk.id}, rerank_score: {chunk.score:.4f})\n"
            f"{chunk.full_text}"
        )
    context = "\n\n".join(context_parts)

    # Claude ?몄텧
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2048,
        system=RAG_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": RAG_USER_TEMPLATE.format(context=context, question=question),
            }
        ],
    )

    raw = message.content[0].text.strip()

    # JSON ?뚯떛 (肄붾뱶釉붾줉 ?쒓굅)
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = {
            "answer": raw,
            "citations": [f"{c.law_name} ??c.article_number}議? for c in chunks],
            "chunk_ids": [c.id for c in chunks],
            "confidence": 0.5,
            "missing_facts": [],
            "warnings": ["JSON ?뚯떛 ?ㅽ뙣 ???먮Ц 諛섑솚"],
        }

    return TaxAnswer(
        answer=data.get("answer", ""),
        citations=data.get("citations", []),
        chunk_ids=data.get("chunk_ids", []),
        confidence=float(data.get("confidence", 0.0)),
        missing_facts=data.get("missing_facts", []),
        warnings=data.get("warnings", []),
    )


# ?? ?뚯뒪??????????????????????????????????????????????????????

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    query = "1?몃? 1二쇳깮 鍮꾧낵???붽굔??臾댁뾿?멸???"
    print(f"=== 寃??荑쇰━: {query} ===\n")

    print("1?④퀎: 踰≫꽣 寃??+ BGE Reranking...")
    chunks = retrieve_tax_law(query, top_k=20, rerank_top_n=5)

    print(f"\n寃??寃곌낵 (reranking ???곸쐞 {len(chunks)}媛?:")
    print("-" * 60)
    for i, chunk in enumerate(chunks, 1):
        print(f"[{i}] {chunk.law_name} ??chunk.article_number}議?{chunk.article_title}")
        print(f"     chunk_id: {chunk.id} | rerank_score: {chunk.score:.4f}")
        print(f"     {chunk.full_text[:120]}...")
        print()

    print("\n2?④퀎: LLM 異붾줎...")
    answer = answer_with_citations(query)

    print("\n=== 理쒖쥌 ?듬? ===")
    print(f"[?붿빟 ?먮떒]\n{answer.answer}\n")
    print(f"[洹쇨굅 踰뺣졊]")
    for c in answer.citations:
        print(f"  - {c}")
    print(f"\n[?좊ː?? {answer.confidence:.2f}")
    if answer.missing_facts:
        print(f"\n[異붽? ?뺤씤 ?꾩슂]")
        for f in answer.missing_facts:
            print(f"  - {f}")
    if answer.warnings:
        print(f"\n[?좎쓽?ы빆]")
        for w in answer.warnings:
            print(f"  - {w}")

 succeeded in 3427ms:
"""
CrewAI Crew ?뺤쓽 諛??ㅽ뻾 吏꾩엯??"""
import os

from crewai import Crew, Task
from dotenv import load_dotenv

from src.agents.prompts import ADVISOR_TASK, RESEARCHER_TASK
from src.agents.roles import build_tax_advisor, build_tax_researcher

load_dotenv()

CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-4-7")


def _build_llm():
    """CrewAI??LLM 媛앹껜 諛섑솚 (Claude)"""
    from crewai import LLM
    return LLM(
        model=f"anthropic/{CLAUDE_MODEL}",
        api_key=os.getenv("ANTHROPIC_API_KEY"),
    )


def run_tax_crew(question: str) -> str:
    """
    ?묐룄?뚮뱷??吏덈Ц??2-agent CrewAI濡?泥섎━.
    諛섑솚媛? 理쒖쥌 ?듬? 臾몄옄??    """
    llm = _build_llm()

    researcher = build_tax_researcher(llm)
    advisor = build_tax_advisor(llm)

    research_task = Task(
        description=RESEARCHER_TASK.format(question=question),
        expected_output="寃?됰맂 踰뺣졊 議곕Ц 紐⑸줉 (chunk_id ?ы븿)",
        agent=researcher,
    )

    advice_task = Task(
        description=ADVISOR_TASK.format(
            question=question,
            research_result="{research_task_output}",
        ),
        expected_output="[?붿빟 ?먮떒] / [洹쇨굅 踰뺣졊] / [?먮떒 怨쇱젙] / [異붽? ?뺤씤 ?꾩슂] / [?좎쓽?ы빆] ?뺤떇???쒓뎅???듬?",
        agent=advisor,
        context=[research_task],
    )

    crew = Crew(
        agents=[researcher, advisor],
        tasks=[research_task, advice_task],
        verbose=True,
    )

    result = crew.kickoff()
    return str(result)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    question = "2??蹂댁쑀??1?몃? 1二쇳깮???묐룄?섎㈃ 鍮꾧낵?멸? ?섎굹??"
    print(f"吏덈Ц: {question}\n")
    answer = run_tax_crew(question)
    print("\n=== 理쒖쥌 ?듬? ===")
    print(answer)

 succeeded in 3455ms:
"""
MCP ?쒕쾭 ??tax-rag
FastMCP 湲곕컲: stdio(Claude Desktop) + SSE(HTTP ?대씪?댁뼵?? ?묒そ 吏??"""
import os
import json

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from src.rag import TaxAnswer, answer_with_citations, retrieve_tax_law

load_dotenv()

mcp = FastMCP(
    name="tax-rag",
    instructions=(
        "?쒓뎅 ?묐룄?뚮뱷??鍮꾧낵?맞룰컧硫는룹쨷怨??щ?瑜??먮떒?섎뒗 踰뺣졊 RAG ?쒕쾭?낅땲?? "
        "紐⑤뱺 ?듬?? law.go.kr 踰뺣졊 議곕Ц 寃??寃곌낵?먮쭔 洹쇨굅?⑸땲??"
    ),
)


# ?? Tool 1: 踰뺣졊 踰≫꽣 寃??????????????????????????????????????????????????????

@mcp.tool()
def search_tax_law(
    query: str,
    top_k: int = 20,
    rerank_top_n: int = 5,
    as_of_date: str = "",
) -> str:
    """
    ?쒓뎅 ?묐룄?뚮뱷??愿??踰뺣졊 議곕Ц??踰≫꽣 寃??+ BGE reranking?쇰줈 寃?됲빀?덈떎.

    Args:
        query: 寃?됲븷 踰뺣졊 ?ㅼ썙???먮뒗 吏덈Ц
        top_k: 踰≫꽣 寃???꾨낫 ??(湲곕낯 20)
        rerank_top_n: BGE reranking ??諛섑솚??議곕Ц ??(湲곕낯 5)
        as_of_date: 湲곗??쇱옄 YYYYMMDD (?? "20220101"). 鍮꾩썙?먮㈃ ?꾩껜 踰꾩쟾 寃??
    """
    chunks = retrieve_tax_law(
        query, top_k=top_k, rerank_top_n=rerank_top_n,
        as_of_date=as_of_date or None,
    )
    if not chunks:
        return "愿??踰뺣졊 議곕Ц??李얠쓣 ???놁뒿?덈떎."

    lines = []
    for i, chunk in enumerate(chunks, 1):
        lines.append(
            f"[{i}] {chunk.law_name} ??chunk.article_number}議?{chunk.article_title}\n"
            f"    chunk_id: {chunk.id} | rerank_score: {chunk.score:.4f}\n"
            f"    {chunk.full_text[:500]}"
        )
    return "\n\n".join(lines)


# ?? Tool 2: ?뱀젙 議곕Ц 吏곸젒 議고쉶 ???????????????????????????????????????????????

@mcp.tool()
def retrieve_article(law_name: str, article_number: str) -> str:
    """
    ?뱀젙 踰뺣졊??議곕Ц 踰덊샇濡?吏곸젒 議고쉶?⑸땲??

    Args:
        law_name: 踰뺣졊紐?(?? "?뚮뱷?몃쾿", "?뚮뱷?몃쾿 ?쒗뻾??)
        article_number: 議곕Ц 踰덊샇 (?? "89", "154")
    """
    query = f"{law_name} ??article_number}議?
    chunks = retrieve_tax_law(query, top_k=20, rerank_top_n=10)

    matched = [
        c for c in chunks
        if c.law_name == law_name and c.article_number == article_number
    ]

    if not matched:
        return f"{law_name} ??article_number}議곕? 李얠쓣 ???놁뒿?덈떎."

    lines = []
    for chunk in matched:
        lines.append(
            f"{chunk.law_name} ??chunk.article_number}議?{chunk.article_title}\n"
            f"chunk_id: {chunk.id}\n\n"
            f"{chunk.full_text}"
        )
    return "\n\n---\n\n".join(lines)


# ?? Tool 3: 鍮꾧낵???붽굔 遺꾩꽍 (RAG + LLM) ?????????????????????????????????????

@mcp.tool()
def analyze_exemption(question: str, as_of_date: str = "") -> str:
    """
    ?묐룄?뚮뱷??鍮꾧낵?맞룰컧硫는룹쨷怨??щ?瑜?RAG 寃????Claude濡?遺꾩꽍?⑸땲??
    寃?됰맂 踰뺣졊 議곕Ц?먮쭔 洹쇨굅?섎ŉ, 遺덊솗?ㅽ븳 ?ъ떎愿怨꾨뒗 異붽? ?뺤씤 ??ぉ?쇰줈 ?쒖떆?⑸땲??

    Args:
        question: ?ъ떎愿怨꾧? ?ы븿??吏덈Ц
                  (?? "2019??痍⑤뱷, 2024???묐룄, 蹂댁쑀 5?? 嫄곗＜ 3?? 1?몃? 1二쇳깮")
        as_of_date: 湲곗??쇱옄 YYYYMMDD (?? "20220101"). 痍⑤뱷???먮뒗 ?묐룄??湲곗?.
    """
    answer: TaxAnswer = answer_with_citations(question, as_of_date=as_of_date or None)

    result = {
        "answer": answer.answer,
        "citations": answer.citations,
        "chunk_ids": answer.chunk_ids,
        "confidence": answer.confidence,
        "missing_facts": answer.missing_facts,
        "warnings": answer.warnings,
    }
    return json.dumps(result, ensure_ascii=False, indent=2)


# ?? Tool 4: ?몄슜 議곕Ц 寃利?????????????????????????????????????????????????????

@mcp.tool()
def verify_citations(question: str, chunk_ids: list[str]) -> str:
    """
    ?몄슜??chunk_id媛 ?ㅼ젣 寃??寃곌낵??議댁옱?섎뒗吏 寃利앺빀?덈떎.
    議댁옱?섏? ?딅뒗 chunk_id瑜??몄슜?섎뒗 寃껋? ?덉슜?섏? ?딆뒿?덈떎.

    Args:
        question: ?먮옒 吏덈Ц (?ш??됱뿉 ?ъ슜)
        chunk_ids: 寃利앺븷 chunk_id 紐⑸줉
    """
    chunks = retrieve_tax_law(question, top_k=20, rerank_top_n=10)
    retrieved_ids = {c.id for c in chunks}

    verified = [cid for cid in chunk_ids if cid in retrieved_ids]
    unverified = [cid for cid in chunk_ids if cid not in retrieved_ids]

    result = {
        "verified_chunk_ids": verified,
        "unverified_chunk_ids": unverified,
        "warning": (
            f"{len(unverified)}媛?chunk_id媛 寃??寃곌낵???놁뒿?덈떎. ?몄슜 湲덉?."
            if unverified else "紐⑤뱺 chunk_id 寃利??꾨즺"
        ),
    }
    return json.dumps(result, ensure_ascii=False, indent=2)


# ?? ?ㅽ뻾 ??????????????????????????????????????????????????????????????????????

if __name__ == "__main__":
    import sys
    # ?몄옄 ?놁쑝硫?stdio (Claude Desktop), --sse ?대㈃ HTTP SSE
    if "--sse" in sys.argv:
        port = int(os.getenv("MCP_PORT", "8001"))
        mcp.run(transport="sse", host="0.0.0.0", port=port)
    else:
        mcp.run(transport="stdio")

codex
The current implementation is already showing the main simplification opportunity: retrieval is solid as a core service, while the 2-agent layer is orchestration sugar and should not be your primary integration boundary. I’m checking tests and prompts now to see where quality controls can be anchored.
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content -Path tests\\test_rag.py" in c:\Users\user\cording2025\tax-rag
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content -Path tests\\test_chunking.py" in c:\Users\user\cording2025\tax-rag
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content -Path src\\agents\\roles.py" in c:\Users\user\cording2025\tax-rag
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content -Path src\\agents\\prompts.py" in c:\Users\user\cording2025\tax-rag
 succeeded in 3627ms:
"""
RAG ?뚯씠?꾨씪???뚯뒪????寃???덉쭏 諛??몄슜 臾닿껐??寃利?"""
import os
import pytest
from unittest.mock import MagicMock, patch

# Pinecone/?꾨쿋???놁씠 ?⑥쐞 ?뚯뒪??媛?ν븯?꾨줉 紐⑦궧


MOCK_CHUNKS_RAW = [
    {
        "id": "285523_0089001",
        "law_name": "?뚮뱷?몃쾿",
        "law_mst": "285523",
        "law_category": "踰뺣쪧",
        "article_number": "89",
        "article_title": "鍮꾧낵???묐룄?뚮뱷",
        "effective_date": "20240101",
        "content": "?ㅼ쓬 媛??몄쓽 ?뚮뱷????댁꽌???묐룄?뚮뱷??????뚮뱷?몃? 怨쇱꽭?섏? ?꾨땲?쒕떎.",
        "clauses": [{"??쾲??: "??, "??궡??: "1?몃? 1二쇳깮", "??: []}],
        "full_text": "??9議?鍮꾧낵???묐룄?뚮뱷) ?ㅼ쓬 媛??몄쓽 ?뚮뱷????댁꽌???묐룄?뚮뱷??????뚮뱷?몃? 怨쇱꽭?섏? ?꾨땲?쒕떎.",
        "metadata": {
            "law_name": "?뚮뱷?몃쾿",
            "article": "89",
            "effective_date": "20240101",
            "category": "踰뺣쪧",
            "source": "law.go.kr",
        },
    },
    {
        "id": "285631_0154001",
        "law_name": "?뚮뱷?몃쾿 ?쒗뻾??,
        "law_mst": "285631",
        "law_category": "??듬졊??,
        "article_number": "154",
        "article_title": "1?몃?1二쇳깮??踰붿쐞",
        "effective_date": "20240101",
        "content": "踰???9議곗젣1??젣3?멸?紐⑹뿉????듬졊?뱀쑝濡??뺥븯???붽굔?대? ?ㅼ쓬 媛??몃? 留먰븳??",
        "clauses": [],
        "full_text": "??54議?1?몃?1二쇳깮??踰붿쐞) 踰???9議곗젣1??젣3?멸?紐⑹뿉????듬졊?뱀쑝濡??뺥븯???붽굔?대? 1?몃?媛 ?묐룄???꾩옱 援?궡??1二쇳깮??蹂댁쑀?섍퀬 ?대떦 二쇳깮??蹂댁쑀湲곌컙??2???댁긽??寃껋쓣 留먰븳??",
        "metadata": {
            "law_name": "?뚮뱷?몃쾿 ?쒗뻾??,
            "article": "154",
            "effective_date": "20240101",
            "category": "??듬졊??,
            "source": "law.go.kr",
        },
    },
]


def _make_mock_chunk(raw: dict, score: float = 0.9):
    from src.rag import LawChunk
    return LawChunk(
        id=raw["id"],
        law_name=raw["law_name"],
        article_number=raw["article_number"],
        article_title=raw["article_title"],
        effective_date=raw["effective_date"],
        full_text=raw["full_text"],
        score=score,
    )


# ?? 寃??寃곌낵 援ъ“ 寃利?????????????????????????????????????????????????????????

def test_law_chunk_has_required_fields():
    """LawChunk 紐⑤뜽??id, chunk_id ?ы븿 ?꾩닔 ?꾨뱶 議댁옱"""
    from src.rag import LawChunk
    chunk = _make_mock_chunk(MOCK_CHUNKS_RAW[0])
    assert chunk.id == "285523_0089001"
    assert chunk.law_name == "?뚮뱷?몃쾿"
    assert chunk.article_number == "89"
    assert chunk.score == 0.9
    assert chunk.full_text


def test_tax_answer_model():
    """TaxAnswer 紐⑤뜽 援ъ“ 寃利?""
    from src.rag import TaxAnswer
    answer = TaxAnswer(
        answer="鍮꾧낵???대떦",
        citations=["?뚮뱷?몃쾿 ??9議?????????],
        chunk_ids=["285523_0089001"],
        confidence=0.85,
        missing_facts=["嫄곗＜湲곌컙"],
        warnings=["議곗젙??곸????щ? 誘명솗??],
    )
    assert answer.confidence == 0.85
    assert len(answer.citations) == 1
    assert len(answer.chunk_ids) == 1


# ?? 寃???④퀎 紐⑦궧 ?뚯뒪???????????????????????????????????????????????????????

@patch("src.rag._get_pinecone_index")
@patch("src.rag._embed_query")
@patch("src.rag._get_reranker")
def test_retrieve_returns_law_chunks(mock_reranker, mock_embed, mock_index):
    """retrieve_tax_law媛 LawChunk 由ъ뒪??諛섑솚, chunk_id ?ы븿"""
    from src.rag import retrieve_tax_law

    # ?꾨쿋??紐⑦궧
    mock_embed.return_value = [0.1] * 4096

    # Pinecone 寃곌낵 紐⑦궧
    mock_match = {
        "id": "285631_0154001",
        "metadata": {
            "law_name": "?뚮뱷?몃쾿 ?쒗뻾??,
            "article_number": "154",
            "article_title": "1?몃?1二쇳깮??踰붿쐞",
            "effective_date": "20240101",
            "full_text": "??54議?1?몃?媛 ?묐룄???꾩옱 援?궡??1二쇳깮??蹂댁쑀?섍퀬 蹂댁쑀湲곌컙??2???댁긽",
        },
    }
    mock_index.return_value.query.return_value = {"matches": [mock_match]}

    # Reranker 紐⑦궧
    mock_reranker_instance = MagicMock()
    mock_reranker_instance.predict.return_value = [0.95]
    mock_reranker.return_value = mock_reranker_instance

    chunks = retrieve_tax_law("1?몃? 1二쇳깮 鍮꾧낵???붽굔", top_k=5, rerank_top_n=1)

    assert len(chunks) == 1
    assert chunks[0].id == "285631_0154001"
    assert chunks[0].law_name == "?뚮뱷?몃쾿 ?쒗뻾??
    assert chunks[0].score > 0


@patch("src.rag._get_pinecone_index")
@patch("src.rag._embed_query")
@patch("src.rag._get_reranker")
def test_retrieve_returns_chunk_ids_not_just_text(mock_reranker, mock_embed, mock_index):
    """寃??寃곌낵??chunk_id 諛섎뱶???ы븿 (?띿뒪?몃쭔 諛섑솚 湲덉?)"""
    from src.rag import retrieve_tax_law

    mock_embed.return_value = [0.1] * 4096
    mock_index.return_value.query.return_value = {
        "matches": [
            {"id": "285523_0089001", "metadata": {
                "law_name": "?뚮뱷?몃쾿", "article_number": "89",
                "article_title": "鍮꾧낵???묐룄?뚮뱷", "effective_date": "20240101",
                "full_text": "??9議?鍮꾧낵???묐룄?뚮뱷",
            }}
        ]
    }
    mock_reranker_instance = MagicMock()
    mock_reranker_instance.predict.return_value = [0.8]
    mock_reranker.return_value = mock_reranker_instance

    chunks = retrieve_tax_law("鍮꾧낵??, top_k=5, rerank_top_n=1)

    assert all(hasattr(c, "id") for c in chunks), "chunk_id ?녿뒗 寃곌낵 ?덉쓬"
    assert all(c.id for c in chunks), "chunk_id媛 鍮?臾몄옄?댁씤 寃곌낵 ?덉쓬"


# ?? ?몄슜 臾닿껐?????????????????????????????????????????????????????????????????

def test_citations_only_from_retrieved_chunks():
    """TaxAnswer.citations??retrieved chunk???덈뒗 踰뺣졊留??몄슜?댁빞 ??""
    from src.rag import TaxAnswer

    retrieved_ids = {"285523_0089001", "285631_0154001"}

    answer = TaxAnswer(
        answer="鍮꾧낵???대떦",
        citations=["?뚮뱷?몃쾿 ??9議?, "?뚮뱷?몃쾿 ?쒗뻾????54議?],
        chunk_ids=["285523_0089001", "285631_0154001"],
        confidence=0.9,
        missing_facts=[],
        warnings=[],
    )

    for cid in answer.chunk_ids:
        assert cid in retrieved_ids, f"寃??寃곌낵???녿뒗 chunk_id ?몄슜: {cid}"


def test_no_retrieved_chunks_returns_empty_answer():
    """寃??寃곌낵 ?놁쑝硫?鍮?TaxAnswer 諛섑솚 (hallucination 諛⑹?)"""
    from src.rag import TaxAnswer

    empty_answer = TaxAnswer(
        answer="愿??踰뺣졊??李얠쓣 ???놁뒿?덈떎.",
        citations=[],
        chunk_ids=[],
        confidence=0.0,
        missing_facts=[],
        warnings=["寃??寃곌낵 ?놁쓬"],
    )

    assert empty_answer.confidence == 0.0
    assert empty_answer.citations == []
    assert "寃??寃곌낵 ?놁쓬" in empty_answer.warnings


# ?? BGE Reranker ?몄텧 寃利?????????????????????????????????????????????????????

@patch("src.rag._get_pinecone_index")
@patch("src.rag._embed_query")
@patch("src.rag._get_reranker")
def test_reranker_is_called_before_final_selection(mock_reranker, mock_embed, mock_index):
    """BGE reranker媛 諛섎뱶???몄텧??(理쒖쥌 ?좏깮 ??"""
    from src.rag import retrieve_tax_law

    mock_embed.return_value = [0.1] * 4096
    mock_index.return_value.query.return_value = {
        "matches": [
            {"id": f"id_{i}", "metadata": {
                "law_name": "?뚮뱷?몃쾿", "article_number": str(i),
                "article_title": "", "effective_date": "20240101",
                "full_text": f"議곕Ц {i}",
            }} for i in range(5)
        ]
    }
    mock_reranker_instance = MagicMock()
    mock_reranker_instance.predict.return_value = [0.9, 0.8, 0.7, 0.6, 0.5]
    mock_reranker.return_value = mock_reranker_instance

    retrieve_tax_law("?뚯뒪??, top_k=5, rerank_top_n=3)

    mock_reranker_instance.predict.assert_called_once()

 succeeded in 3617ms:
"""
CrewAI Agent ??븷 ?뺤쓽
"""
from crewai import Agent
from src.agents.prompts import (
    ADVISOR_BACKSTORY,
    ADVISOR_GOAL,
    ADVISOR_ROLE,
    RESEARCHER_BACKSTORY,
    RESEARCHER_GOAL,
    RESEARCHER_ROLE,
)
from src.agents.tools import RAGSearchTool


def build_tax_researcher(llm) -> Agent:
    return Agent(
        role=RESEARCHER_ROLE,
        goal=RESEARCHER_GOAL,
        backstory=RESEARCHER_BACKSTORY,
        tools=[RAGSearchTool()],
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )


def build_tax_advisor(llm) -> Agent:
    return Agent(
        role=ADVISOR_ROLE,
        goal=ADVISOR_GOAL,
        backstory=ADVISOR_BACKSTORY,
        tools=[],
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )

 succeeded in 3622ms:
"""
泥?궧 ?덉쭏 ?뚯뒪????議?????紐?援ъ“ 蹂댁〈 寃利?"""
import json
from pathlib import Path

import pytest

CHUNKS_PATH = Path("data/processed/all_chunks.json")
SAMPLE_LAW = Path("data/processed/?뚮뱷?몃쾿_285523.json")


@pytest.fixture(scope="module")
def all_chunks():
    if not CHUNKS_PATH.exists():
        pytest.skip("data/processed/all_chunks.json ?놁쓬 ??collect.py 癒쇱? ?ㅽ뻾")
    return json.loads(CHUNKS_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def income_tax_chunks():
    if not SAMPLE_LAW.exists():
        pytest.skip("?뚮뱷?몃쾿 泥?겕 ?뚯씪 ?놁쓬")
    return json.loads(SAMPLE_LAW.read_text(encoding="utf-8"))


def test_total_chunk_count(all_chunks):
    """6媛?踰뺣졊 ??理쒖냼 500媛?泥?겕 ?댁긽"""
    assert len(all_chunks) >= 500, f"泥?겕 ???덈Т ?곸쓬: {len(all_chunks)}"


def test_required_fields(all_chunks):
    """紐⑤뱺 泥?겕???꾩닔 ?꾨뱶 議댁옱"""
    required = {"id", "law_name", "article_number", "effective_date", "full_text", "metadata"}
    for chunk in all_chunks:
        missing = required - set(chunk.keys())
        assert not missing, f"?꾩닔 ?꾨뱶 ?꾨씫: {missing} (id={chunk.get('id')})"


def test_chunk_id_format(all_chunks):
    """id = {mst}_{議곕Ц?? ?뺤떇"""
    for chunk in all_chunks:
        assert "_" in chunk["id"], f"id ?뺤떇 ?ㅻ쪟: {chunk['id']}"
        parts = chunk["id"].split("_")
        assert len(parts) >= 2, f"id ?뚰듃 遺議? {chunk['id']}"


def test_law_names_covered(all_chunks):
    """6媛?踰뺣졊??紐⑤몢 ?ы븿"""
    expected = {
        "?뚮뱷?몃쾿", "?뚮뱷?몃쾿 ?쒗뻾??, "?뚮뱷?몃쾿 ?쒗뻾洹쒖튃",
        "議곗꽭?밸??쒗븳踰?, "議곗꽭?밸??쒗븳踰??쒗뻾??, "議곗꽭?밸??쒗븳踰??쒗뻾洹쒖튃",
    }
    actual = {c["law_name"] for c in all_chunks}
    missing = expected - actual
    assert not missing, f"?꾨씫??踰뺣졊: {missing}"


def test_no_empty_full_text(all_chunks):
    """full_text媛 鍮꾩뼱 ?덈뒗 泥?겕 ?놁쓬"""
    empty = [c["id"] for c in all_chunks if not c.get("full_text", "").strip()]
    assert not empty, f"full_text 鍮꾩뼱 ?덈뒗 泥?겕: {empty[:5]}"


def test_metadata_consistency(all_chunks):
    """metadata.law_name == law_name"""
    for chunk in all_chunks:
        meta_name = chunk.get("metadata", {}).get("law_name", "")
        assert meta_name == chunk["law_name"], (
            f"metadata.law_name 遺덉씪移? {meta_name!r} != {chunk['law_name']!r} (id={chunk['id']})"
        )


def test_clauses_structure(all_chunks):
    """clauses媛 ?덉쑝硫???쾲????궡????蹂댁쑀"""
    for chunk in all_chunks:
        for clause in chunk.get("clauses", []):
            assert "??쾲?? in clause, f"??쾲???놁쓬 (id={chunk['id']})"
            assert "??궡?? in clause, f"??궡???놁쓬 (id={chunk['id']})"


def test_key_article_exists(income_tax_chunks):
    """?뚮뱷?몃쾿 ??9議?鍮꾧낵???묐룄?뚮뱷) 諛섎뱶??議댁옱"""
    articles = {c["article_number"] for c in income_tax_chunks}
    assert "89" in articles, "?뚮뱷?몃쾿 ??9議??놁쓬 ???듭떖 鍮꾧낵??議곕Ц ?꾨씫"


def test_effective_date_format(all_chunks):
    """?쒗뻾?쇱옄媛 YYYYMMDD ?뺤떇 (鍮꾩뼱?덉? ?딆? 寃쎌슦)"""
    for chunk in all_chunks:
        date = chunk.get("effective_date", "")
        if date:
            assert len(date) == 8 and date.isdigit(), (
                f"?쒗뻾?쇱옄 ?뺤떇 ?ㅻ쪟: {date!r} (id={chunk['id']})"
            )

 succeeded in 3625ms:
"""
紐⑤뱺 ?꾨＼?꾪듃瑜??ш린??踰꾩쟾 愿由?"""

# ?? Tax Researcher (TaxIssueAnalyzer + LawRetriever ?⑹튇 MVP ??븷) ??????????
RESEARCHER_ROLE = "?쒓뎅 ?묐룄?뚮뱷??踰뺣졊 議곗궗愿"
RESEARCHER_GOAL = (
    "?ъ슜?먯쓽 ?ъ떎愿怨꾨? ?뺣━?섍퀬, RAG ?꾧뎄濡?愿??踰뺣졊 議곕Ц???뺥솗??寃?됲빐 "
    "?꾨떖?쒕떎. 踰뺣졊 議곕Ц ?먮Ц ?댁쇅???댁슜? 異붿륫?섏? ?딅뒗??"
)
RESEARCHER_BACKSTORY = (
    "?섎뀈媛??뚮뱷?몃쾿쨌議곗꽭?밸??쒗븳踰?踰뺣졊 ?곗씠?곕쿋?댁뒪瑜?愿由ы빐???꾨Ц媛. "
    "議곕Ц??怨꾩링 援ъ“(議?????紐?瑜??뺥솗???뚯븙?섍퀬 "
    "?꾩슂??議곕Ц??鍮좎쭚?놁씠 寃?됲븯??寃껋쓣 理쒖슦?좎쑝濡??쒕떎."
)

RESEARCHER_TASK = """\
?꾨옒 ?ъ슜??吏덈Ц??遺꾩꽍?섍퀬 RAG 寃???꾧뎄瑜??몄텧?섎씪.

吏덈Ц: {question}

?섑뻾 ?④퀎:
1. 吏덈Ц?먯꽌 ?듭떖 ?ъ떎愿怨???ぉ 異붿텧 (痍⑤뱷?? ?묐룄?? 蹂댁쑀湲곌컙, ?몃??? 二쇳깮 ????
2. 寃???ㅼ썙???ㅺ퀎 (踰뺣졊 ?⑹뼱 ?곗꽑)
3. search_tax_law ?꾧뎄 ?몄텧
4. 寃?됰맂 議곕Ц 紐⑸줉怨?chunk_id瑜?洹몃?濡?異쒕젰

異쒕젰 ?뺤떇:
- ?뺤씤???ъ떎愿怨? ...
- 遺덊솗???꾨씫 ?뺣낫: ...
- 寃?됰맂 議곕Ц: (?꾧뎄 寃곌낵 洹몃?濡?
"""

# ?? Tax Advisor (ExemptionReasoner + CitationVerifier + AnswerComposer ?⑹튇 MVP ??븷) ?
ADVISOR_ROLE = "?쒓뎅 ?묐룄?뚮뱷??踰뺣졊 ?댁꽍 ?꾨Ц媛"
ADVISOR_GOAL = (
    "議곗궗愿??寃?됲븳 議곕Ц?먮쭔 洹쇨굅??鍮꾧낵?맞룰컧硫는룹쨷怨??щ?瑜??먮떒?섍퀬, "
    "?몄슜 議곕Ц???ㅼ젣 寃??寃곌낵??議댁옱?섎뒗吏 寃利앺븳 ??理쒖쥌 ?듬????묒꽦?쒕떎."
)
ADVISOR_BACKSTORY = (
    "10??寃쎈젰???몃Т??異쒖떊 AI ?대뱶諛붿씠?. 議곕Ц???녿뒗 ?댁슜? ?덈? ?몄슜?섏? ?딆쑝硫? "
    "遺덊솗?ㅽ븳 ?ъ떎愿怨꾧? ?덉쑝硫?寃곕줎???좊낫?섍퀬 異붽? ?뺤씤 ?ы빆??紐낆떆?쒕떎."
)

ADVISOR_TASK = """\
議곗궗愿??寃??寃곌낵瑜?諛뷀깢?쇰줈 理쒖쥌 ?멸툑 ?먮떒???섑뻾?섎씪.

吏덈Ц: {question}
議곗궗愿 寃곌낵: {research_result}

?섑뻾 ?④퀎:
1. 議곗궗愿???쒓났??chunk_id 紐⑸줉 ?뺤씤
2. 媛??몄슜 議곕Ц???ㅼ젣 寃??寃곌낵 ?덉뿉 ?덈뒗吏 寃利?(?놁쑝硫??몄슜 湲덉?)
3. 寃利앸맂 議곕Ц留??ъ슜??鍮꾧낵??媛먮㈃/以묎낵 ?щ? ?먮떒
4. ?꾨옒 ?뺤떇?쇰줈 ?쒓뎅??理쒖쥌 ?듬? ?묒꽦

[?붿빟 ?먮떒]
鍮꾧낵???대떦 / 鍮꾪빐??/ 異붽? ?뺤씤 ?꾩슂

[洹쇨굅 踰뺣졊]
- ?뚮뱷?몃쾿 ?쏰O議??쏰???쏰??- ...

[?먮떒 怨쇱젙]
1. ...
2. ...

[異붽? ?뺤씤 ?꾩슂]
- (?꾨씫???ъ떎愿怨?

[?좎쓽?ы빆]
蹂??듬?? 踰뺣쪧 ?먮Ц???꾨땶 ?뺣낫 ?쒓났 紐⑹쟻?낅땲?? ?뺥솗???먮떒? ?몃Т?ъ? ?곷떞?섏꽭??
"""

# ?? rag.py?먯꽌 ?ъ슜?섎뒗 ?⑥씪 LLM ?꾨＼?꾪듃 ??????????????????????????????????
RAG_SYSTEM_PROMPT = """?뱀떊? ?쒓뎅 ?묐룄?뚮뱷??踰뺣졊 ?꾨Ц AI ?댁떆?ㅽ꽩?몄엯?덈떎.
諛섎뱶???꾨옒 洹쒖튃???곕Ⅴ?몄슂:
1. ?쒓났??踰뺣졊 議곕Ц?먮쭔 洹쇨굅???듬??⑸땲?? 議곕Ц???녿뒗 ?댁슜? 異붿륫?섏? ?딆뒿?덈떎.
2. 遺덊솗?ㅽ븳 ?ъ떎愿怨꾧? ?덉쑝硫?'異붽? ?뺤씤 ?꾩슂' ??ぉ??紐낆떆?⑸땲??
3. ?듬?? 諛섎뱶???ㅼ쓬 JSON ?뺤떇?쇰줈留?異쒕젰?⑸땲??

{
  "answer": "?붿빟 ?먮떒 諛?洹쇨굅",
  "citations": ["?뚮뱷?몃쾿 ??9議?????????, ...],
  "chunk_ids": ["285523_0890000", ...],
  "confidence": 0.0~1.0,
  "missing_facts": ["?뺤씤???꾩슂???ъ떎愿怨?紐⑸줉"],
  "warnings": ["二쇱쓽?ы빆 紐⑸줉"]
}"""

RAG_USER_TEMPLATE = """?ㅼ쓬 踰뺣졊 議곕Ц??李멸퀬??吏덈Ц???듯븯?몄슂.

=== 寃?됰맂 踰뺣졊 議곕Ц ===
{context}

=== 吏덈Ц ===
{question}

諛섎뱶??JSON ?뺤떇?쇰줈留??듯븯?몄슂."""

web search: 
web search: Pinecone official docs metadata filtering serverless namespaces search rerank official
web search: 
web search: CrewAI official docs flows production reliability official
web search: 
web search: site:developers.upstage.ai solar embedding official api docs
web search: 
web search: Anthropic official docs JSON output structured output tool use messages API official
web search: 
web search: https://docs.pinecone.io/guides/data/query-data
codex
I found one concrete implementation risk worth checking before I finalize recommendations: whether document chunks and user queries are embedded with the correct Upstage model pair. I’m verifying that now because it affects retrieval quality more than agent design.
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content -Path src\\embed.py" in c:\Users\user\cording2025\tax-rag
 succeeded in 2882ms:
"""
?꾨쿋??+ Pinecone ?낅줈???ㅽ겕由쏀듃
data/processed/all_chunks.json ??Pinecone Serverless
"""
import os
import json
import time
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec
from tqdm import tqdm

load_dotenv()

UPSTAGE_API_KEY = os.getenv("UPSTAGE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "tax-rag")
PINECONE_NAMESPACE = os.getenv("PINECONE_NAMESPACE", "tax-law")
PINECONE_CLOUD = os.getenv("PINECONE_CLOUD", "aws")
PINECONE_REGION = os.getenv("PINECONE_REGION", "us-east-1")
UPSTAGE_EMBEDDING_MODEL = os.getenv("UPSTAGE_EMBEDDING_MODEL", "solar-embedding-1-large-passage")

PROCESSED_DIR = Path("data/processed")
BATCH_SIZE = 100  # Pinecone upsert 諛곗튂 ?ш린


def _build_embed_client() -> tuple[OpenAI, str, int]:
    """(client, model_name, dimension) 諛섑솚"""
    if UPSTAGE_API_KEY:
        client = OpenAI(
            api_key=UPSTAGE_API_KEY,
            base_url="https://api.upstage.ai/v1",
        )
        return client, UPSTAGE_EMBEDDING_MODEL, 4096
    if OPENAI_API_KEY:
        client = OpenAI(api_key=OPENAI_API_KEY)
        return client, "text-embedding-3-large", 3072
    raise RuntimeError("UPSTAGE_API_KEY ?먮뒗 OPENAI_API_KEY 以??섎굹媛 ?꾩슂?⑸땲??)


def _embed_texts(client: OpenAI, model: str, texts: list[str]) -> list[list[float]]:
    """?띿뒪??諛곗튂瑜??꾨쿋??踰≫꽣濡?蹂??""
    truncated = [t[:3000] for t in texts]
    resp = client.embeddings.create(model=model, input=truncated)
    return [item.embedding for item in resp.data]


def _get_or_create_index(pc: Pinecone, dimension: int):
    """Pinecone ?몃뜳??議고쉶 ?먮뒗 ?앹꽦"""
    existing = [idx.name for idx in pc.list_indexes()]
    if PINECONE_INDEX_NAME not in existing:
        print(f"?몃뜳???앹꽦 以? {PINECONE_INDEX_NAME} (dim={dimension})")
        pc.create_index(
            name=PINECONE_INDEX_NAME,
            dimension=dimension,
            metric="cosine",
            spec=ServerlessSpec(cloud=PINECONE_CLOUD, region=PINECONE_REGION),
        )
        # ?몃뜳??以鍮??湲?        while not pc.describe_index(PINECONE_INDEX_NAME).status["ready"]:
            print("  ?몃뜳??以鍮?以?..")
            time.sleep(3)
        print("  ?몃뜳??以鍮??꾨즺")
    else:
        print(f"湲곗〈 ?몃뜳???ъ슜: {PINECONE_INDEX_NAME}")
    return pc.Index(PINECONE_INDEX_NAME)


def embed_and_upload(chunks_path: Optional[Path] = None) -> int:
    """
    JSON 泥?겕 ?뚯씪???쎌뼱 ?꾨쿋????Pinecone???낅줈??
    諛섑솚媛? upsert??踰≫꽣 ??    """
    if chunks_path is None:
        chunks_path = PROCESSED_DIR / "all_chunks.json"

    if not chunks_path.exists():
        raise FileNotFoundError(
            f"{chunks_path} ?놁쓬 ??癒쇱? `python src/collect.py` ?ㅽ뻾"
        )

    if not PINECONE_API_KEY:
        raise RuntimeError("PINECONE_API_KEY媛 ?꾩슂?⑸땲??)

    # 泥?겕 濡쒕뱶
    chunks = json.loads(chunks_path.read_text(encoding="utf-8"))
    print(f"珥?{len(chunks)}媛?泥?겕 濡쒕뱶 ?꾨즺")

    # ?꾨쿋???대씪?댁뼵??    embed_client, embed_model, dimension = _build_embed_client()
    print(f"?꾨쿋??紐⑤뜽: {embed_model} (dim={dimension})")

    # Pinecone ?몃뜳??    pc = Pinecone(api_key=PINECONE_API_KEY)
    index = _get_or_create_index(pc, dimension)

    # 諛곗튂 ?낅줈??    total_upserted = 0
    batches = [chunks[i : i + BATCH_SIZE] for i in range(0, len(chunks), BATCH_SIZE)]

    for batch in tqdm(batches, desc="Pinecone ?낅줈??):
        texts = [c.get("full_text", "") for c in batch]
        try:
            vectors = _embed_texts(embed_client, embed_model, texts)
        except Exception as e:
            print(f"\n?꾨쿋???ㅻ쪟 (諛곗튂 嫄대꼫?): {e}")
            continue

        upsert_payload = []
        for chunk, vec in zip(batch, vectors):
            metadata = {
                "law_name": chunk.get("law_name", ""),
                "article_number": chunk.get("article_number", ""),
                "article_title": chunk.get("article_title", ""),
                "effective_date": chunk.get("effective_date", ""),
                "expiration_date": chunk.get("expiration_date", ""),  # 鍮?臾몄옄??= ?꾪뻾
                "version_mst": chunk.get("version_mst", chunk.get("law_mst", "")),
                "law_category": chunk.get("law_category", ""),
                "source": "law.go.kr",
                # full_text??reranker媛 ?ъ슜 ??Pinecone 硫뷀??곗씠???쒕룄 怨좊젮??400?먮줈 ???                "full_text": chunk.get("full_text", "")[:400],
            }
            upsert_payload.append(
                {"id": chunk["id"], "values": vec, "metadata": metadata}
            )

        index.upsert(vectors=upsert_payload, namespace=PINECONE_NAMESPACE)
        total_upserted += len(upsert_payload)
        time.sleep(0.2)  # rate limit 諛⑹?

    print(f"\n[?꾨즺] {total_upserted}媛?踰≫꽣 ?낅줈????{PINECONE_INDEX_NAME}/{PINECONE_NAMESPACE}")
    return total_upserted


if __name__ == "__main__":
    embed_and_upload()

codex
There is a concrete retrieval-quality issue in the current implementation: the Pinecone metadata only keeps the first 400 characters of each chunk, but reranking and answer synthesis read `metadata.full_text` back out of Pinecone. I’m confirming the chunking/version fields so I can separate architecture advice from fixable implementation defects.
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content -Path src\\collect.py" in c:\Users\user\cording2025\tax-rag
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -n \"expiration_date|effective_date|version_mst|clauses|hierarchy|article_number\" src\\collect.py src\\embed.py src\\rag.py" in c:\Users\user\cording2025\tax-rag
 succeeded in 3054ms:
src\embed.py:117:                "article_number": chunk.get("article_number", ""),
src\embed.py:119:                "effective_date": chunk.get("effective_date", ""),
src\embed.py:120:                "expiration_date": chunk.get("expiration_date", ""),  # 빈 문자열 = 현행
src\embed.py:121:                "version_mst": chunk.get("version_mst", chunk.get("law_mst", "")),
src\rag.py:35:    article_number: str
src\rag.py:37:    effective_date: str
src\rag.py:38:    expiration_date: str = ""  # 빈 문자열 = 현행
src\rag.py:123:                {"effective_date": {"$lte": as_of_date}},
src\rag.py:125:                    {"expiration_date": {"$eq": ""}},
src\rag.py:126:                    {"expiration_date": {"$gte": as_of_date}},
src\rag.py:165:                article_number=meta.get("article_number", ""),
src\rag.py:167:                effective_date=meta.get("effective_date", ""),
src\rag.py:168:                expiration_date=meta.get("expiration_date", ""),
src\rag.py:194:            + "\n\n".join(f"[{c.law_name} 제{c.article_number}조] {c.full_text[:300]}" for c in chunks),
src\rag.py:195:            citations=[f"{c.law_name} 제{c.article_number}조 {c.article_title}".strip() for c in chunks],
src\rag.py:206:            f"[{i}] {chunk.law_name} 제{chunk.article_number}조 {chunk.article_title}\n"
src\rag.py:238:            "citations": [f"{c.law_name} 제{c.article_number}조" for c in chunks],
src\rag.py:270:        print(f"[{i}] {chunk.law_name} 제{chunk.article_number}조 {chunk.article_title}")
src\collect.py:7:- 각 버전(MST)에 effective_date + expiration_date 부여
src\collect.py:8:- chunk ID = {version_mst}_{조문키} → 버전별 고유성 보장
src\collect.py:38:    반환: [{"mst", "effective_date", "promulgation_date", "expiration_date"}, ...]
src\collect.py:82:            "effective_date": eff_date,
src\collect.py:84:            "expiration_date": "",
src\collect.py:91:    versions.sort(key=lambda x: x["effective_date"])
src\collect.py:95:        next_eff = versions[i + 1]["effective_date"]
src\collect.py:98:            v["expiration_date"] = exp_dt.strftime("%Y%m%d")
src\collect.py:119:    version: {"mst", "effective_date", "promulgation_date", "expiration_date"}
src\collect.py:120:    chunk ID = {version_mst}_{조문키}
src\collect.py:139:        시행일자 = 시행일자_elem.text.strip() if 시행일자_elem is not None and 시행일자_elem.text else version["effective_date"]
src\collect.py:177:            "version_mst": version["mst"],        # 이 버전의 MST
src\collect.py:179:            "article_number": 조문번호,
src\collect.py:182:            "effective_date": 시행일자,
src\collect.py:183:            "expiration_date": version["expiration_date"],  # 빈 문자열 = 현행
src\collect.py:186:            "clauses": 항_list,
src\collect.py:191:                "article_number": 조문번호,
src\collect.py:193:                "effective_date": 시행일자,
src\collect.py:194:                "expiration_date": version["expiration_date"],
src\collect.py:196:                "version_mst": version["mst"],
src\collect.py:224:                "effective_date": "",
src\collect.py:226:                "expiration_date": "",
src\collect.py:234:                    "effective_date": "",
src\collect.py:236:                    "expiration_date": "",
src\collect.py:246:                print(f"  → 캐시 사용: {v['mst']} (시행일: {v['effective_date'] or '불명'})")
src\collect.py:251:                    print(f"  → XML 저장: {v['mst']} (시행일: {v['effective_date'] or '불명'}, {len(xml_text):,} bytes)")
src\collect.py:258:            print(f"     청크: {len(chunks)}개 | 만료일: {v['expiration_date'] or '현행'}")

 succeeded in 3056ms:
"""
踰뺣졊 ?곗씠???섏쭛 ?ㅽ겕由쏀듃
www.law.go.kr DRF API ??data/raw/ (XML) + data/processed/ (JSON chunks)

踰꾩쟾 愿由??꾨왂:
- 媛?踰뺣졊??媛쒖젙 ?대젰??紐⑤몢 ?섏쭛 (理쒓렐 YEARS_BACK??
- 媛?踰꾩쟾(MST)??effective_date + expiration_date 遺??- chunk ID = {version_mst}_{議곕Ц?? ??踰꾩쟾蹂?怨좎쑀??蹂댁옣
"""
import json
import time
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path

OC = "jctax"
BASE_URL = "https://www.law.go.kr/DRF"
RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")
YEARS_BACK = 10  # 理쒓렐 N?꾩튂 媛쒖젙 踰꾩쟾 ?섏쭛

TARGET_LAWS = [
    {"name": "?뚮뱷?몃쾿",                    "mst": "285523", "category": "踰뺣쪧"},
    {"name": "?뚮뱷?몃쾿 ?쒗뻾??,              "mst": "285631", "category": "??듬졊??},
    {"name": "?뚮뱷?몃쾿 ?쒗뻾洹쒖튃",            "mst": "284987", "category": "遺??},
    {"name": "議곗꽭?밸??쒗븳踰?,              "mst": "285525", "category": "踰뺣쪧"},
    {"name": "議곗꽭?밸??쒗븳踰??쒗뻾??,        "mst": "283625", "category": "??듬졊??},
    {"name": "議곗꽭?밸??쒗븳踰??쒗뻾洹쒖튃",      "mst": "284611", "category": "遺??},
]


# ?? 踰꾩쟾 ?대젰 議고쉶 ????????????????????????????????????????????????????????????

def fetch_law_version_list(law_name: str) -> list[dict]:
    """
    踰뺣졊紐낆쑝濡?媛쒖젙 ?대젰 ?곸쓽 紐⑤뱺 踰꾩쟾 議고쉶.
    諛섑솚: [{"mst", "effective_date", "promulgation_date", "expiration_date"}, ...]
    ?쒗뻾???ㅻ쫫李⑥닚 ?뺣젹, 留뚮즺???먮룞 怨꾩궛.
    """
    url = f"{BASE_URL}/lawSearch.do"
    params = {
        "OC": OC,
        "target": "law",
        "query": law_name,
        "display": 100,
        "type": "XML",
    }
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    resp.encoding = "utf-8"

    try:
        root = ET.fromstring(resp.text.encode("utf-8"))
    except ET.ParseError:
        print(f"  ??{law_name} ?대젰 XML ?뚯떛 ?ㅽ뙣, ?꾪뻾 踰꾩쟾留??ъ슜")
        return []

    cutoff = (datetime.now() - timedelta(days=YEARS_BACK * 365)).strftime("%Y%m%d")

    versions = []
    for law_elem in root.findall(".//踰뺣졊"):
        name_elem = law_elem.find("踰뺣졊紐낇븳湲")
        if name_elem is None or name_elem.text is None:
            continue
        if name_elem.text.strip() != law_name:
            continue

        mst_elem = law_elem.find("踰뺣졊?쇰젴踰덊샇")
        eff_elem = law_elem.find("?쒗뻾?쇱옄")
        prom_elem = law_elem.find("怨듯룷?쇱옄")

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

    # ?쒗뻾???ㅻ쫫李⑥닚 ?뺣젹
    versions.sort(key=lambda x: x["effective_date"])

    # 留뚮즺??= ?ㅼ쓬 踰꾩쟾 ?쒗뻾???꾨궇
    for i, v in enumerate(versions[:-1]):
        next_eff = versions[i + 1]["effective_date"]
        if next_eff:
            exp_dt = datetime.strptime(next_eff, "%Y%m%d") - timedelta(days=1)
            v["expiration_date"] = exp_dt.strftime("%Y%m%d")

    # 留덉?留??꾪뻾) 踰꾩쟾? 留뚮즺???놁쓬
    return versions


# ?? XML ?섏쭛 ??????????????????????????????????????????????????????????????????

def fetch_law_xml(mst: str) -> str:
    url = f"{BASE_URL}/lawService.do"
    params = {"OC": OC, "target": "law", "MST": mst, "type": "XML"}
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    return resp.text


# ?? XML ?뚯떛 ??泥?겕 ???????????????????????????????????????????????????????????

def parse_xml_to_chunks(xml_text: str, law_info: dict, version: dict) -> list[dict]:
    """
    version: {"mst", "effective_date", "promulgation_date", "expiration_date"}
    chunk ID = {version_mst}_{議곕Ц??
    """
    root = ET.fromstring(xml_text.encode("utf-8"))
    chunks = []

    law_name_elem = root.find(".//踰뺣졊紐낇븳湲")
    law_name = law_name_elem.text.strip() if law_name_elem is not None else law_info["name"]

    for 議곕Ц?⑥쐞 in root.findall(".//議곕Ц?⑥쐞"):
        議곕Ц??= 議곕Ц?⑥쐞.get("議곕Ц??, "")
        議곕Ц踰덊샇_elem = 議곕Ц?⑥쐞.find("議곕Ц踰덊샇")
        議곕Ц?щ?_elem = 議곕Ц?⑥쐞.find("議곕Ц?щ?")
        議곕Ц?쒕ぉ_elem = 議곕Ц?⑥쐞.find("議곕Ц?쒕ぉ")
        ?쒗뻾?쇱옄_elem = 議곕Ц?⑥쐞.find("議곕Ц?쒗뻾?쇱옄")
        ?댁슜_elem = 議곕Ц?⑥쐞.find("議곕Ц?댁슜")

        議곕Ц踰덊샇 = 議곕Ц踰덊샇_elem.text.strip() if 議곕Ц踰덊샇_elem is not None and 議곕Ц踰덊샇_elem.text else ""
        議곕Ц?щ? = 議곕Ц?щ?_elem.text.strip() if 議곕Ц?щ?_elem is not None and 議곕Ц?щ?_elem.text else ""
        議곕Ц?쒕ぉ = 議곕Ц?쒕ぉ_elem.text.strip() if 議곕Ц?쒕ぉ_elem is not None and 議곕Ц?쒕ぉ_elem.text else ""
        ?쒗뻾?쇱옄 = ?쒗뻾?쇱옄_elem.text.strip() if ?쒗뻾?쇱옄_elem is not None and ?쒗뻾?쇱옄_elem.text else version["effective_date"]
        ?댁슜 = ?댁슜_elem.text.strip() if ?댁슜_elem is not None and ?댁슜_elem.text else ""

        ??list = []
        for ??in 議곕Ц?⑥쐞.findall(".//??):
            ??쾲??elem = ??find("??쾲??)
            ??궡??elem = ??find("??궡??)
            ??list = []
            for ??in ??findall(".//??):
                ?몃쾲??elem = ??find("?몃쾲??)
                ?몃궡??elem = ??find("?몃궡??)
                ??list.append({
                    "?몃쾲??: ?몃쾲??elem.text.strip() if ?몃쾲??elem is not None and ?몃쾲??elem.text else "",
                    "?몃궡??: ?몃궡??elem.text.strip() if ?몃궡??elem is not None and ?몃궡??elem.text else "",
                })
            ??list.append({
                "??쾲??: ??쾲??elem.text.strip() if ??쾲??elem is not None and ??쾲??elem.text else "",
                "??궡??: ??궡??elem.text.strip() if ??궡??elem is not None and ??궡??elem.text else "",
                "??: ??list,
            })

        if not ?댁슜 and not ??list:
            continue

        full_text_parts = []
        if ?댁슜:
            full_text_parts.append(?댁슜)
        for ??in ??list:
            if ??"??궡??]:
                full_text_parts.append(f"  {??'??궡??]}")
            for ??in ??"??]:
                if ??"?몃궡??]:
                    full_text_parts.append(f"    {??'?몃궡??]}")

        chunk = {
            "id": f"{version['mst']}_{議곕Ц??",
            "law_name": law_name,
            "law_mst": law_info["mst"],          # 踰뺣졊 怨좎쑀 ID (踰꾩쟾 臾닿?)
            "version_mst": version["mst"],        # ??踰꾩쟾??MST
            "law_category": law_info["category"],
            "article_number": 議곕Ц踰덊샇,
            "article_type": 議곕Ц?щ?,
            "article_title": 議곕Ц?쒕ぉ,
            "effective_date": ?쒗뻾?쇱옄,
            "expiration_date": version["expiration_date"],  # 鍮?臾몄옄??= ?꾪뻾
            "promulgation_date": version["promulgation_date"],
            "content": ?댁슜,
            "clauses": ??list,
            "full_text": "\n".join(full_text_parts),
            "metadata": {
                "law_name": law_name,
                "article": 議곕Ц踰덊샇,
                "article_number": 議곕Ц踰덊샇,
                "article_title": 議곕Ц?쒕ぉ,
                "effective_date": ?쒗뻾?쇱옄,
                "expiration_date": version["expiration_date"],
                "category": law_info["category"],
                "version_mst": version["mst"],
                "source": "law.go.kr",
            },
        }
        chunks.append(chunk)

    return chunks


# ?? 硫붿씤 ?섏쭛 ?????????????????????????????????????????????????????????????????

def collect_all():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    all_chunks = []

    for law in TARGET_LAWS:
        print(f"\n[{law['name']}] 媛쒖젙 ?대젰 議고쉶 以?..")

        # 踰꾩쟾 紐⑸줉 議고쉶
        versions = fetch_law_version_list(law["name"])

        if not versions:
            # ?대젰 議고쉶 ?ㅽ뙣 ???꾪뻾 踰꾩쟾 ?⑤룆 ?섏쭛
            print(f"  ???대젰 ?놁쓬, ?꾪뻾 踰꾩쟾留??섏쭛 (MST={law['mst']})")
            versions = [{
                "mst": law["mst"],
                "effective_date": "",
                "promulgation_date": "",
                "expiration_date": "",
            }]
        else:
            # ?꾪뻾 MST媛 紐⑸줉???놁쑝硫?異붽?
            existing_msts = {v["mst"] for v in versions}
            if law["mst"] not in existing_msts:
                versions.append({
                    "mst": law["mst"],
                    "effective_date": "",
                    "promulgation_date": "",
                    "expiration_date": "",
                })
            print(f"  ??{len(versions)}媛?踰꾩쟾 諛쒓껄")

        law_chunks = []
        for v in versions:
            raw_path = RAW_DIR / f"{law['name'].replace(' ', '_')}_{v['mst']}.xml"

            if raw_path.exists():
                xml_text = raw_path.read_text(encoding="utf-8")
                print(f"  ??罹먯떆 ?ъ슜: {v['mst']} (?쒗뻾?? {v['effective_date'] or '遺덈챸'})")
            else:
                try:
                    xml_text = fetch_law_xml(v["mst"])
                    raw_path.write_text(xml_text, encoding="utf-8")
                    print(f"  ??XML ??? {v['mst']} (?쒗뻾?? {v['effective_date'] or '遺덈챸'}, {len(xml_text):,} bytes)")
                    time.sleep(0.5)
                except Exception as e:
                    print(f"  ??{v['mst']} ?섏쭛 ?ㅽ뙣: {e}")
                    continue

            chunks = parse_xml_to_chunks(xml_text, law, v)
            print(f"     泥?겕: {len(chunks)}媛?| 留뚮즺?? {v['expiration_date'] or '?꾪뻾'}")
            law_chunks.extend(chunks)

        # 踰뺣졊蹂??듯빀 JSON
        processed_path = PROCESSED_DIR / f"{law['name'].replace(' ', '_')}_{law['mst']}.json"
        processed_path.write_text(
            json.dumps(law_chunks, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        all_chunks.extend(law_chunks)

    # ?꾩껜 ?듯빀 JSON
    all_path = PROCESSED_DIR / "all_chunks.json"
    all_path.write_text(
        json.dumps(all_chunks, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n[?꾨즺] 珥?{len(all_chunks)}媛?泥?겕 ??{all_path}")
    return all_chunks


if __name__ == "__main__":
    collect_all()

codex
The right production shape is: **deterministic retrieval engine first, agentic explanation second**. In your code, the durable core is already `[src/rag.py](</C:/Users/user/cording2025/tax-rag/src/rag.py>)`; the CrewAI layer in `[src/agents/crew.py](</C:/Users/user/cording2025/tax-rag/src/agents/crew.py>)` should stay optional, not become the main contract. One concrete defect to fix before scaling: `[src/embed.py](</C:/Users/user/cording2025/tax-rag/src/embed.py>)` truncates `full_text` to 400 chars in Pinecone metadata, but reranking and answer synthesis read that field back. That will silently drop provisos, exceptions, and trailing clauses.

**1. Architecture**
- Make the online path a typed pipeline, not a free-form multi-agent conversation: `facts normalization -> issue framing -> temporal filter selection -> retrieval -> rerank -> constrained reasoning -> answer assembly`.
- Treat the engine as a **legal evidence service**. The LLM should explain over retrieved authority, not decide what the retrieval plan is from scratch.
- Keep **offline and online planes separate**. Offline: XML ingestion, version parsing, chunking, evals, index build, canary rollout. Online: low-latency retrieval and answering only.
- Make **time/version** first-class. Every request should carry at least `legal_basis_date` and often both `acquisition_date` and `disposition_date`. Transitional provisions are a top-tier failure mode in tax.
- Add **hybrid retrieval**. Tax law has exact strings (`제89조`, `1세대 1주택`, 시행령 조문번호) that dense search can miss; Pinecone explicitly supports hybrid dense+lexical patterns.
- Store a **chunk graph**, not only flat chunks: article, paragraph, item, parent article, sibling references, version MST, effective/expiration dates, law family. Retrieve the best node, then expand to parent/sibling when needed.
- Put **deterministic rule checks before the LLM** for obvious gaps: contradictory facts, missing residency period, unclear household count, unknown adjustment-target area status. Return `insufficient_facts` early when appropriate.
- Collapse the 2-agent design into a **single orchestrated flow with typed state** for production. CrewAI Flows are a better fit than open-ended roleplay because state is explicit and integration is cleaner.

**2. Learning / Improvement**
- Do **not** let the system “learn” online from raw user interactions. Use eval-driven improvement, not weight updates from production traffic.
- Build three golden sets:
  - `retrieval gold`: case -> required article IDs / forbidden article IDs / correct legal version
  - `reasoning gold`: case -> expected outcome / allowed ambiguity / required missing facts
  - `regression gold`: known hard edge cases, especially law amendments and exceptions
- Track retrieval separately from reasoning. Minimum metrics:
  - `Recall@k` on gold article IDs
  - `MRR` or `nDCG`
  - temporal version accuracy
  - citation precision: cited chunks must be retrieved chunks
  - unsupported-claim rate
  - missing-fact recall
  - abstention quality: does it escalate when it should?
- Log a full answer trace: normalized facts, generated search intents, retrieved chunk IDs, rerank scores, prompt version, model version, index version, final citations, latency, token cost.
- Use feedback in ranked order:
  - explicit reviewer corrections
  - advisor override / manual-review outcomes
  - user follow-up that indicates error or ambiguity
  - unresolved or escalated cases
- Re-run the full golden set on every change to chunking, retrieval, reranker, prompt, or model. Anthropic batch processing is useful for this because eval workloads are asynchronous and cheaper in batch.
- Improvement priority should usually be: `chunking/metadata -> retrieval -> reranker -> prompt -> agent behavior`. Most production gains come before the agent layer.

**3. API Surface**
Expose the smallest domain API possible:
- `POST /v1/case-analysis`
- Input: `case_id`, `facts`, `question`, `legal_basis_date`, `response_mode`, optional `jurisdiction/policy flags`
- Output: `status`, `conclusion`, `reasoning_summary`, `citations`, `missing_facts`, `warnings`, `confidence`, `trace_id`, `knowledge_snapshot`
- `POST /v1/feedback`
- `GET /v1/results/{trace_id}` if you support async
- `GET /healthz` and `GET /readyz`

Do **not** expose `search_tax_law`, `retrieve_article`, MCP tool shapes, or agent internals to the upstream platform. Those are internal debugging and tooling surfaces. Upstream systems should integrate with one domain object: “analyze this tax case.”

**4. Failure Modes**
- Wrong legal version or missed transitional rule
- Exact-term retrieval miss
- Chunk boundary loses an exception/proviso
- Structured facts are incomplete or contradictory
- LLM gives fluent but weakly grounded reasoning
- Pinecone freshness lag during reindex or amendment rollout
- External provider latency/outage
- Agent orchestration adds cost and non-determinism without accuracy gain

Make them graceful by:
- returning explicit statuses: `answerable`, `insufficient_facts`, `manual_review`, `no_authority_found`
- falling back to **evidence-only mode** if the LLM is unavailable
- requiring citations to map to retrieved chunk IDs only
- showing `knowledge_snapshot` on every response: corpus version, index version, prompt version, model version, legal basis date
- using dual-index or canary rollouts instead of in-place reindex swaps
- setting latency and token budgets with circuit breakers
- routing low-confidence or temporally complex cases to manual review instead of forcing a binary answer

One additional recommendation: for the final answering step, consider using Claude’s built-in document citations with your retrieved chunks as documents instead of prompt-only JSON citations. That gives tighter grounding and more reliable source pointers.

Sources:
- Pinecone architecture: https://docs.pinecone.io/guides/get-started/database-architecture
- Pinecone search overview: https://docs.pinecone.io/guides/search/search-overview
- Pinecone metadata/filtering: https://docs.pinecone.io/guides/index-data/indexing-overview
- Pinecone hybrid search: https://docs.pinecone.io/guides/search/hybrid-search
- Anthropic citations: https://platform.claude.com/docs/en/build-with-claude/citations
- Anthropic prompt caching: https://platform.claude.com/docs/en/build-with-claude/prompt-caching
- Anthropic batch processing: https://docs.anthropic.com/en/docs/build-with-claude/batch-processing
- CrewAI Flows: https://docs.crewai.com/en/concepts/flows
- MCP architecture: https://modelcontextprotocol.io/docs/learn/architecture
- Upstage Solar Embedding official post: https://www.upstage.ai/blog/en/solar-embedding-1-large

If you want, I can turn this into a concrete target architecture diagram plus a `v1` API schema for your FastMCP/FastAPI service.
tokens used
90,348

```

## Concise summary

Provider completed successfully. Review the raw output for details.

## Action items

- Review the response and extract decisions you want to apply.
- Capture follow-up implementation tasks if needed.
