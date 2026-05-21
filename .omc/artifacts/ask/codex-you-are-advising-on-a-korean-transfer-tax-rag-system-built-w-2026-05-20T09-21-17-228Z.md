# codex advisor artifact

- Provider: codex
- Exit code: 0
- Created at: 2026-05-20T09:21:17.231Z

## Original task

You are advising on a Korean transfer tax (양도소득세) RAG system built with Pinecone + Claude + BGE Reranker. The system takes structured JSON fact inputs and runs L2-L5 pipeline to determine tax verdict (비과세/감면/중과/일반과세/단기세율/고가주택/사실관계부족).

Current stack: law.go.kr DRF API for law collection, Upstage Solar embeddings (dim=4096), Pinecone serverless, BGE-Reranker-v2-m3, Claude Sonnet/Opus for LLM reasoning, Red-Blue debate engine for low-confidence cases, golden set accumulation loop.

YOUR TASK: What additional DATA, INFRASTRUCTURE, or TECHNICAL CONTEXT is still missing to make this system production-perfect? Ask every question you can think of that would expose critical gaps. Cover: (1) law version coverage gaps, (2) missing fact fields in FactInput schema, (3) Pinecone index schema limitations, (4) evaluation harness blind spots, (5) pipeline accuracy risks, (6) missing ruling/precedent data, (7) deployment/ops gaps. Be exhaustive — list every question that must be answered before claiming the system is complete.

## Final prompt

You are advising on a Korean transfer tax (양도소득세) RAG system built with Pinecone + Claude + BGE Reranker. The system takes structured JSON fact inputs and runs L2-L5 pipeline to determine tax verdict (비과세/감면/중과/일반과세/단기세율/고가주택/사실관계부족).

Current stack: law.go.kr DRF API for law collection, Upstage Solar embeddings (dim=4096), Pinecone serverless, BGE-Reranker-v2-m3, Claude Sonnet/Opus for LLM reasoning, Red-Blue debate engine for low-confidence cases, golden set accumulation loop.

YOUR TASK: What additional DATA, INFRASTRUCTURE, or TECHNICAL CONTEXT is still missing to make this system production-perfect? Ask every question you can think of that would expose critical gaps. Cover: (1) law version coverage gaps, (2) missing fact fields in FactInput schema, (3) Pinecone index schema limitations, (4) evaluation harness blind spots, (5) pipeline accuracy risks, (6) missing ruling/precedent data, (7) deployment/ops gaps. Be exhaustive — list every question that must be answered before claiming the system is complete.

## Raw output

```text
Below is the question set I would use before anyone claims this Korean transfer tax RAG system is production-complete.

**1. Law Version Coverage**

**Corpus scope**
- Which exact statutes are indexed today?
- Are all relevant laws included, not only 소득세법 and 조특법?
- Do you include 지방세법 or only national 양도소득세?
- Do you include 국세기본법 provisions relevant to filing, penalties, burden of proof, or limitation periods?
- Do you include 국세징수법 where collection or payment deferral matters?
- Do you include 시행령 and 시행규칙 for every indexed statute?
- Are 별표, 서식, 부칙, 경과규정 indexed?
- Are deleted/repealed provisions preserved when they apply historically?
- Are amended article histories retained, or only current text?

**Temporal correctness**
- Given 취득일, 양도일, 계약일, 잔금일, 등기일, and 시행일, can the system select the correct law version?
- Does each chunk include `effective_start_date` and `effective_end_date`, not just one effective date?
- Can the system distinguish 공포일, 시행일, 적용시기, and 부칙 적용일?
- Are grandfathering rules from 부칙 indexed and retrievable?
- Can it answer cases where acquisition occurred under one law version but transfer occurred under another?
- Can it handle law amendments that apply from “2021.1.1 이후 양도분” or similar conditional effective language?
- Are historical versions from law.go.kr collected systematically?
- How far back does historical law coverage go?
- What is the minimum supported tax year?
- What happens if the user asks about a year outside coverage?
- Does the answer explicitly warn when historical law coverage is incomplete?

**Article structure**
- Are 조 / 항 / 호 / 목 / 단서 / 각 목 / 본문 / 후단 / 전단 preserved?
- Are article titles preserved separately from body text?
- Are cross-references resolved or at least indexed?
- Can the retriever follow “대통령령으로 정하는” from law to 시행령?
- Can it connect 법률 제89조 to 시행령 제154조 automatically?
- Can it retrieve 조특법 special cases alongside 소득세법 baseline rules?
- Can it handle “준용한다” provisions?
- Are exception clauses indexed in a way that prevents them from being missed?

**Administrative guidance**
- Are 기획재정부 예규 included?
- Are 국세청 질의회신 included?
- Are 국세청 집행기준 included?
- Are 기본통칙 included?
- Are 사전답변 and 유권해석 included?
- Are 심사/심판 decisions included?
- Are Tax Tribunal 조세심판원 decisions included?
- Are Supreme Court / lower court cases included?
- Are these sources versioned by decision date and issue date?
- Does the system distinguish binding law from persuasive administrative interpretation?

---

**2. FactInput Schema Gaps**

**Transaction basics**
- Does `FactInput` capture 취득일?
- 양도일?
- 계약일?
- 잔금일?
- 등기접수일?
- 실제 인도일?
- 취득가액?
- 양도가액?
- 필요경비?
- 양도비?
- 취득세, 중개수수료, 법무사비, 자본적 지출?
- 공동명의 여부?
- 지분율?
- 양도 지분만 일부인지 전체인지?
- 증여 취득인지 매매 취득인지 상속 취득인지?
- 부담부증여인지?
- 교환인지?
- 수용인지?
- 경매/공매인지?
- 법인 전환 또는 현물출자인지?

**Asset classification**
- 주택인지?
- 조합원입주권인지?
- 분양권인지?
- 토지인지?
- 건물인지?
- 상가겸용주택인지?
- 오피스텔인지?
- 농지인지?
- 임야인지?
- 비사업용토지 여부?
- 고가주택 여부 판단용 실지거래가?
- 주택 부수토지 면적?
- 도시지역 여부?
- 주거용 사용 여부?
- 공부상 용도와 실제 용도가 다른지?
- 무허가/미등기 건물 여부?
- 미등기양도자산 여부?

**Residence and household**
- 거주자/비거주자 여부?
- 국내 거주기간?
- 세대주 여부?
- 세대원 목록?
- 배우자 여부?
- 사실혼 여부?
- 생계를 같이하는 가족 여부?
- 주민등록상 세대와 실제 생계 세대가 다른 경우?
- 세대분리일?
- 혼인일?
- 이혼일?
- 동거봉양 합가일?
- 자녀 연령?
- 부모 연령?
- 세대원 각각의 주택 보유 현황?
- 세대원 각각의 취득/양도 내역?

**1세대 1주택**
- 양도 당시 세대 기준 보유 주택 수?
- 보유기간?
- 거주기간?
- 조정대상지역 취득 여부?
- 조정대상지역 지정일/해제일?
- 취득 당시 조정대상지역인지?
- 양도 당시 조정대상지역인지?
- 2년 거주요건 적용 대상인지?
- 일시적 2주택인지?
- 신규주택 취득일?
- 종전주택 양도일?
- 신규주택 전입일?
- 종전주택 처분기한?
- 상속주택 포함 여부?
- 농어촌주택 포함 여부?
- 장기임대주택 포함 여부?
- 공동상속주택 소수지분 여부?
- 주택 수 제외 특례 적용 여부?

**Special situations**
- 상속 취득일과 피상속인 취득일을 모두 받는가?
- 피상속인과 동일세대 여부?
- 증여자의 취득일 승계 여부 판단에 필요한 정보가 있는가?
- 이혼 재산분할인지?
- 혼인합가로 인한 2주택인지?
- 동거봉양 합가인지?
- 노부모 연령 조건이 있는지?
- 대체취득인지?
- 재개발/재건축 관련 조합원입주권인지?
- 종전주택 멸실일?
- 관리처분계획인가일?
- 준공일?
- 입주권 취득 경위?
- 분양권 취득일?
- 전매 여부?

**Tax-rate classification**
- 보유기간 계산용 취득/양도 기준일이 명확한가?
- 단기세율 대상인지?
- 다주택 중과 대상인지?
- 중과 배제 주택인지?
- 비사업용토지 여부 판단 필드가 있는가?
- 미등기양도 여부가 있는가?
- 장기보유특별공제 계산에 필요한 거주/보유 기간이 있는가?
- 고가주택 과세분 계산 가능 필드가 있는가?
- 감면 한도, 농특세, 중복감면 제한 판단 필드가 있는가?

**Evidence confidence**
- 각 fact에 출처가 있는가?
- 사용자가 직접 입력한 값인지, 문서에서 추출한 값인지?
- 확정값인지 추정값인지?
- 날짜 정밀도는 일/월/년 중 무엇인지?
- 모순되는 fact를 표현할 수 있는가?
- missing fact와 unknown fact를 구분하는가?
- “해당 없음”과 “미확인”을 구분하는가?

---

**3. Pinecone Index Schema Limitations**

**Index design**
- Is one index used for all legal sources, or separate indexes by source type?
- Is namespace separated by statute, law version, source type, or environment?
- Does the namespace strategy support blue/green reindexing?
- Can production and staging indexes coexist safely?
- Is index dimension locked to Upstage Solar 4096?
- What happens if embedding model changes?
- Is there an embedding version field?
- Is there a chunker version field?
- Is there a parser version field?
- Is there a source document checksum?
- Can stale vectors be detected and deleted?

**Metadata**
- Does each vector include law name?
- law ID / MST?
- article number?
- paragraph number?
- subparagraph number?
- item number?
- effective start/end date?
- promulgation date?
- amendment ID?
- source URL?
- source type?
- hierarchy path?
- chunk type: article, paragraph, appendix, addendum, ruling, case?
- jurisdiction/source authority?
- confidence or parser quality?
- language field?
- citation display string?

**Filtering**
- Can retrieval filter by transfer date?
- Can it filter by law version?
- Can it filter by statute family?
- Can it filter by source authority?
- Can it filter out repealed law unless historically applicable?
- Can it retrieve both current and historical provisions when needed?
- Can it filter by asset type: 주택, 토지, 분양권, 입주권?
- Can it filter by issue type: 비과세, 감면, 중과, 단기세율, 고가주택?

**Chunking**
- Are chunks too large for precise reranking?
- Are 항/호-level chunks retrievable independently?
- Are article-level parent chunks retrievable for context?
- Is parent-child retrieval implemented?
- Are neighboring clauses pulled after initial retrieval?
- Are exception clauses attached to main clauses?
- Are definitions indexed separately and linked?
- Is there a citation-safe chunk boundary?
- Are long articles split without losing citation traceability?

**Hybrid retrieval**
- Is dense-only retrieval enough for article numbers like “제89조”?
- Is sparse/BM25 search used alongside embeddings?
- Is exact citation lookup available?
- Is Korean legal term normalization handled?
- Are synonyms handled: 양도세 vs 양도소득세, 비과세 vs 과세제외?
- Are Hangul/number variants normalized?
- Can it retrieve by statute abbreviation?

---

**4. Evaluation Harness Blind Spots**

**Golden set**
- How many golden cases exist?
- Are they real cases, synthetic cases, or mixed?
- Who labeled them?
- Are labels reviewed by tax professionals?
- Does each golden case include expected verdict and expected citations?
- Does it include missing-fact expected outputs?
- Does it include calculation expected outputs where applicable?
- Are edge cases overrepresented or underrepresented?
- Are ordinary easy cases included?
- Are historical-law cases included?
- Are law-amendment boundary cases included?
- Are ambiguous cases included?
- Are adversarial cases included?
- Are contradictory fact cases included?

**Verdict coverage**
- Are there cases for 비과세?
- 감면?
- 중과?
- 일반과세?
- 단기세율?
- 고가주택?
- 사실관계부족?
- mixed verdicts, e.g. 고가주택 partially taxable but otherwise 1세대1주택?
- 중과 배제?
- 장특공제 allowed/disallowed?
- 일시적 2주택?
- 상속주택?
- 농어촌주택?
- 조합원입주권?
- 분양권?
- 비사업용토지?
- 미등기양도?

**Metrics**
- Do you measure retrieval recall@k?
- reranker recall@n?
- citation precision?
- citation recall?
- verdict accuracy?
- missing-fact detection accuracy?
- hallucinated citation rate?
- unsupported legal proposition rate?
- abstention accuracy?
- calibration of confidence scores?
- latency p50/p95/p99?
- cost per answer?
- Red-Blue debate win/loss correctness?
- regression from corpus update?
- regression from prompt update?
- regression from model update?

**Test levels**
- Unit tests for XML parsing?
- Unit tests for date applicability?
- Unit tests for chunk metadata?
- Unit tests for citation formatting?
- Integration tests against Pinecone?
- Offline retrieval tests using fixed embeddings?
- End-to-end tests with frozen model outputs?
- LLM-as-judge tests with human audit?
- Mutation tests where key facts are removed?
- Tests where retrieved law is intentionally incomplete?
- Tests for refusal/uncertainty when facts are missing?

**Ground truth**
- Is the expected answer based on actual tax filing outcome?
- Tax accountant opinion?
- Court/ruling outcome?
- Internal legal analysis?
- Are disagreements tracked?
- Is there an appeal process for mislabeled golden cases?
- Are golden labels versioned with law version and prompt version?

---

**5. Pipeline Accuracy Risks**

**Fact interpretation**
- Does the L2-L5 pipeline validate schema before retrieval?
- Does it detect impossible dates?
- Does it calculate holding period deterministically?
- Does it calculate residence period deterministically?
- Does it calculate household ownership count deterministically?
- Does the LLM ever perform arithmetic that should be done by code?
- Are date intervals inclusive/exclusive according to Korean tax rules?
- Are acquisition date rules source-specific?
- Are inheritance/gift acquisition date rules handled explicitly?

**Retrieval**
- Can query expansion accidentally retrieve irrelevant special cases?
- Can top-k miss exceptions?
- Does reranking overfavor semantically similar but legally inapplicable provisions?
- Does reranking receive enough structured facts?
- Are negative conditions retrieved?
- Are definitions retrieved when terms are ambiguous?
- Are related 시행령 provisions guaranteed to be retrieved?
- Is there a fallback exact-article retrieval after semantic retrieval?
- Is there a rule graph or citation graph supplementing vector search?

**Reasoning**
- Are deterministic rule checks used before LLM reasoning?
- Does Claude receive only retrieved context, or can it use latent legal memory?
- Are prompts explicitly prohibiting unsupported legal claims?
- Is every legal proposition tied to a chunk ID?
- Does the answer distinguish rule, fact, application, conclusion?
- Does it explain uncertainty when facts are missing?
- Does it avoid final verdict when required facts are unknown?
- Does it support multiple possible outcomes based on missing facts?
- Does Red-Blue debate improve accuracy or just add persuasive hallucination?
- Is debate output citation-verified afterward?
- Are both Red and Blue constrained to retrieved evidence?

**Citation verification**
- Does `CitationVerifier` check exact article existence in retrieved chunks?
- Does it check that cited paragraph/subparagraph exists?
- Does it check that citation supports the proposition being made?
- Does it reject citations from non-applicable law versions?
- Does it detect invented citations?
- Does it detect correct citation but wrong interpretation?
- Does it trace every verdict element to supporting evidence?

**Confidence**
- What does confidence mean?
- Is it calibrated against observed accuracy?
- Is confidence based on retrieval score, reranker score, LLM self-rating, or ensemble?
- Are low-confidence thresholds empirically selected?
- Does confidence decrease for missing facts?
- Does confidence decrease for conflicting retrieved authorities?
- Does confidence decrease when only administrative guidance supports the answer?

---

**6. Missing Ruling / Precedent Data**

**Administrative rulings**
- Are 국세청 질의회신 collected?
- Are 사전답변 collected?
- Are 서면질의 collected?
- Are 재산세과 rulings collected?
- Are 기획재정부 해석 collected?
- Are rulings mapped to statutes/articles?
- Are ruling dates indexed?
- Are obsolete rulings marked obsolete?
- Are contradictory rulings detected?
- Are rulings ranked below statutes but above weak secondary sources?

**Tax appeals and litigation**
- Are 조세심판원 decisions collected?
- Are 감사원 심사 decisions collected?
- Are 국세청 심사청구 decisions collected?
- Are administrative court decisions collected?
- Are Supreme Court cases collected?
- Are case outcomes structured?
- Are facts from cases structured separately from holdings?
- Are holdings linked to issues?
- Can the system distinguish similar facts from materially different facts?

**Authority hierarchy**
- Does the system rank authority as:
  statute > enforcement decree > enforcement rule > binding interpretation > court precedent > tribunal decision > administrative ruling?
- Does it explain when a source is not binding?
- Does it surface conflicts between authority types?
- Does it avoid treating one taxpayer-specific ruling as universally applicable?
- Are recent amendments checked against older rulings before using them?

**Data licensing**
- Are you allowed to store and serve each ruling/case source?
- Are there redistribution restrictions?
- Are source URLs retained?
- Is there a takedown/update process?

---

**7. Deployment / Ops Gaps**

**Security**
- Are API keys stored in a secrets manager?
- Are keys rotated?
- Is Pinecone access scoped?
- Are Claude/OpenAI/Upstage keys separated by environment?
- Are user fact inputs encrypted at rest?
- Are logs redacted for personally identifiable information?
- Are 주민등록번호, addresses, transaction amounts, family info protected?
- Is there access control?
- Is there tenant isolation?
- Is there audit logging?
- Is prompt injection handled?
- Can retrieved legal text or user input override system instructions?
- Is MCP tool access authenticated?

**Reliability**
- What is the fallback if Pinecone is down?
- What is the fallback if Upstage embedding fails?
- What is the fallback if BGE reranker fails?
- What is the fallback if Claude times out?
- Are retries idempotent?
- Are partial failures visible to users?
- Are circuit breakers implemented?
- Is there queueing for long-running debate cases?
- Are timeouts defined per stage?
- Are p95 and p99 latency targets defined?

**Observability**
- Do you log query, facts hash, retrieved chunk IDs, reranked chunk IDs, prompt version, model version, verdict, citations, confidence?
- Do you store full traces for later audit?
- Are traces privacy-safe?
- Can you replay a past answer exactly?
- Are corpus version, index version, embedding version, prompt version, and model version attached to every answer?
- Are hallucinated citation incidents tracked?
- Are low-confidence cases reviewed?
- Is there alerting for retrieval degradation?
- Is there alerting for cost spikes?
- Is there alerting for latency spikes?

**Release management**
- Is there staging before production?
- Is there blue/green index deployment?
- Is there rollback for corpus updates?
- Is there rollback for prompt updates?
- Is there rollback for model updates?
- Are golden tests required before release?
- Are law updates automatically tested before publishing?
- Is there a human approval gate for new law versions?
- Is there a changelog of legal corpus updates?

**Compliance and product risk**
- Is the system positioned as legal/tax information, not final tax advice?
- Is there a mandatory disclaimer?
- Is there escalation to tax professional review?
- Are high-value or low-confidence cases blocked from definitive answers?
- Are users told which facts are missing?
- Are users told which law version was applied?
- Are users told the answer may differ based on local tax office interpretation?
- Is there an audit package export for professionals?

**Cost and scaling**
- What is cost per normal case?
- Cost per debate case?
- Max concurrent users?
- Pinecone QPS limits?
- Claude rate limits?
- Upstage rate limits?
- Reranker GPU/CPU capacity?
- Are embeddings cached?
- Are retrieval results cached?
- Are repeated structured fact cases deduplicated?
- Is batch evaluation affordable?

---

**8. Additional Production-Completeness Questions**

**Schema governance**
- Is `FactInput` versioned?
- Can old saved cases be replayed after schema changes?
- Are unknown fields rejected or preserved?
- Are enum values controlled?
- Is Korean address normalization supported?
- Is date normalization strict?
- Are monetary values validated for currency/unit?

**Deterministic tax engine**
- Which parts are deterministic code versus LLM reasoning?
- Are tax rate tables encoded as data?
- Are thresholds versioned?
- Are annual limits versioned?
- Are 고가주택 thresholds versioned by year?
- Are 감면 caps versioned?
- Are calculations unit-tested separately from legal reasoning?

**Human review**
- What cases require human review?
- Can reviewers correct verdict, citations, or facts?
- Do corrections feed the golden set?
- Are reviewer disagreements tracked?
- Is there a reviewer UI?
- Is there a professional audit trail?

**User experience**
- Does the system ask targeted follow-up questions?
- Does it avoid asking irrelevant questions?
- Can it explain why each missing fact matters?
- Can it produce both short and professional-detail answers?
- Can it output a structured JSON verdict for downstream systems?
- Can it output Korean natural-language reasoning with citations?

**Final readiness question**
- For any production answer, can you reconstruct:
  `input facts -> normalized facts -> retrieved chunks -> reranked chunks -> applied law versions -> reasoning steps -> citations -> final verdict -> confidence -> missing facts -> model/prompt/index/corpus versions`?

If the answer to that final question is not “yes, deterministically and auditably,” the system is not production-perfect yet.


OpenAI Codex v0.130.0
--------
workdir: c:\Users\next0\claude-test\tax-rag
model: gpt-5.5
provider: openai
approval: never
sandbox: danger-full-access
reasoning effort: medium
reasoning summaries: none
session id: 019e44af-149e-75e1-b7c5-db78484d3728
--------
user
You are advising on a Korean transfer tax (양도소득세) RAG system built with Pinecone + Claude + BGE Reranker. The system takes structured JSON fact inputs and runs L2-L5 pipeline to determine tax verdict (비과세/감면/중과/일반과세/단기세율/고가주택/사실관계부족).

Current stack: law.go.kr DRF API for law collection, Upstage Solar embeddings (dim=4096), Pinecone serverless, BGE-Reranker-v2-m3, Claude Sonnet/Opus for LLM reasoning, Red-Blue debate engine for low-confidence cases, golden set accumulation loop.

YOUR TASK: What additional DATA, INFRASTRUCTURE, or TECHNICAL CONTEXT is still missing to make this system production-perfect? Ask every question you can think of that would expose critical gaps. Cover: (1) law version coverage gaps, (2) missing fact fields in FactInput schema, (3) Pinecone index schema limitations, (4) evaluation harness blind spots, (5) pipeline accuracy risks, (6) missing ruling/precedent data, (7) deployment/ops gaps. Be exhaustive — list every question that must be answered before claiming the system is complete.
codex
Below is the question set I would use before anyone claims this Korean transfer tax RAG system is production-complete.

**1. Law Version Coverage**

**Corpus scope**
- Which exact statutes are indexed today?
- Are all relevant laws included, not only 소득세법 and 조특법?
- Do you include 지방세법 or only national 양도소득세?
- Do you include 국세기본법 provisions relevant to filing, penalties, burden of proof, or limitation periods?
- Do you include 국세징수법 where collection or payment deferral matters?
- Do you include 시행령 and 시행규칙 for every indexed statute?
- Are 별표, 서식, 부칙, 경과규정 indexed?
- Are deleted/repealed provisions preserved when they apply historically?
- Are amended article histories retained, or only current text?

**Temporal correctness**
- Given 취득일, 양도일, 계약일, 잔금일, 등기일, and 시행일, can the system select the correct law version?
- Does each chunk include `effective_start_date` and `effective_end_date`, not just one effective date?
- Can the system distinguish 공포일, 시행일, 적용시기, and 부칙 적용일?
- Are grandfathering rules from 부칙 indexed and retrievable?
- Can it answer cases where acquisition occurred under one law version but transfer occurred under another?
- Can it handle law amendments that apply from “2021.1.1 이후 양도분” or similar conditional effective language?
- Are historical versions from law.go.kr collected systematically?
- How far back does historical law coverage go?
- What is the minimum supported tax year?
- What happens if the user asks about a year outside coverage?
- Does the answer explicitly warn when historical law coverage is incomplete?

**Article structure**
- Are 조 / 항 / 호 / 목 / 단서 / 각 목 / 본문 / 후단 / 전단 preserved?
- Are article titles preserved separately from body text?
- Are cross-references resolved or at least indexed?
- Can the retriever follow “대통령령으로 정하는” from law to 시행령?
- Can it connect 법률 제89조 to 시행령 제154조 automatically?
- Can it retrieve 조특법 special cases alongside 소득세법 baseline rules?
- Can it handle “준용한다” provisions?
- Are exception clauses indexed in a way that prevents them from being missed?

**Administrative guidance**
- Are 기획재정부 예규 included?
- Are 국세청 질의회신 included?
- Are 국세청 집행기준 included?
- Are 기본통칙 included?
- Are 사전답변 and 유권해석 included?
- Are 심사/심판 decisions included?
- Are Tax Tribunal 조세심판원 decisions included?
- Are Supreme Court / lower court cases included?
- Are these sources versioned by decision date and issue date?
- Does the system distinguish binding law from persuasive administrative interpretation?

---

**2. FactInput Schema Gaps**

**Transaction basics**
- Does `FactInput` capture 취득일?
- 양도일?
- 계약일?
- 잔금일?
- 등기접수일?
- 실제 인도일?
- 취득가액?
- 양도가액?
- 필요경비?
- 양도비?
- 취득세, 중개수수료, 법무사비, 자본적 지출?
- 공동명의 여부?
- 지분율?
- 양도 지분만 일부인지 전체인지?
- 증여 취득인지 매매 취득인지 상속 취득인지?
- 부담부증여인지?
- 교환인지?
- 수용인지?
- 경매/공매인지?
- 법인 전환 또는 현물출자인지?

**Asset classification**
- 주택인지?
- 조합원입주권인지?
- 분양권인지?
- 토지인지?
- 건물인지?
- 상가겸용주택인지?
- 오피스텔인지?
- 농지인지?
- 임야인지?
- 비사업용토지 여부?
- 고가주택 여부 판단용 실지거래가?
- 주택 부수토지 면적?
- 도시지역 여부?
- 주거용 사용 여부?
- 공부상 용도와 실제 용도가 다른지?
- 무허가/미등기 건물 여부?
- 미등기양도자산 여부?

**Residence and household**
- 거주자/비거주자 여부?
- 국내 거주기간?
- 세대주 여부?
- 세대원 목록?
- 배우자 여부?
- 사실혼 여부?
- 생계를 같이하는 가족 여부?
- 주민등록상 세대와 실제 생계 세대가 다른 경우?
- 세대분리일?
- 혼인일?
- 이혼일?
- 동거봉양 합가일?
- 자녀 연령?
- 부모 연령?
- 세대원 각각의 주택 보유 현황?
- 세대원 각각의 취득/양도 내역?

**1세대 1주택**
- 양도 당시 세대 기준 보유 주택 수?
- 보유기간?
- 거주기간?
- 조정대상지역 취득 여부?
- 조정대상지역 지정일/해제일?
- 취득 당시 조정대상지역인지?
- 양도 당시 조정대상지역인지?
- 2년 거주요건 적용 대상인지?
- 일시적 2주택인지?
- 신규주택 취득일?
- 종전주택 양도일?
- 신규주택 전입일?
- 종전주택 처분기한?
- 상속주택 포함 여부?
- 농어촌주택 포함 여부?
- 장기임대주택 포함 여부?
- 공동상속주택 소수지분 여부?
- 주택 수 제외 특례 적용 여부?

**Special situations**
- 상속 취득일과 피상속인 취득일을 모두 받는가?
- 피상속인과 동일세대 여부?
- 증여자의 취득일 승계 여부 판단에 필요한 정보가 있는가?
- 이혼 재산분할인지?
- 혼인합가로 인한 2주택인지?
- 동거봉양 합가인지?
- 노부모 연령 조건이 있는지?
- 대체취득인지?
- 재개발/재건축 관련 조합원입주권인지?
- 종전주택 멸실일?
- 관리처분계획인가일?
- 준공일?
- 입주권 취득 경위?
- 분양권 취득일?
- 전매 여부?

**Tax-rate classification**
- 보유기간 계산용 취득/양도 기준일이 명확한가?
- 단기세율 대상인지?
- 다주택 중과 대상인지?
- 중과 배제 주택인지?
- 비사업용토지 여부 판단 필드가 있는가?
- 미등기양도 여부가 있는가?
- 장기보유특별공제 계산에 필요한 거주/보유 기간이 있는가?
- 고가주택 과세분 계산 가능 필드가 있는가?
- 감면 한도, 농특세, 중복감면 제한 판단 필드가 있는가?

**Evidence confidence**
- 각 fact에 출처가 있는가?
- 사용자가 직접 입력한 값인지, 문서에서 추출한 값인지?
- 확정값인지 추정값인지?
- 날짜 정밀도는 일/월/년 중 무엇인지?
- 모순되는 fact를 표현할 수 있는가?
- missing fact와 unknown fact를 구분하는가?
- “해당 없음”과 “미확인”을 구분하는가?

---

**3. Pinecone Index Schema Limitations**

**Index design**
- Is one index used for all legal sources, or separate indexes by source type?
- Is namespace separated by statute, law version, source type, or environment?
- Does the namespace strategy support blue/green reindexing?
- Can production and staging indexes coexist safely?
- Is index dimension locked to Upstage Solar 4096?
- What happens if embedding model changes?
- Is there an embedding version field?
- Is there a chunker version field?
- Is there a parser version field?
- Is there a source document checksum?
- Can stale vectors be detected and deleted?

**Metadata**
- Does each vector include law name?
- law ID / MST?
- article number?
- paragraph number?
- subparagraph number?
- item number?
- effective start/end date?
- promulgation date?
- amendment ID?
- source URL?
- source type?
- hierarchy path?
- chunk type: article, paragraph, appendix, addendum, ruling, case?
- jurisdiction/source authority?
- confidence or parser quality?
- language field?
- citation display string?

**Filtering**
- Can retrieval filter by transfer date?
- Can it filter by law version?
- Can it filter by statute family?
- Can it filter by source authority?
- Can it filter out repealed law unless historically applicable?
- Can it retrieve both current and historical provisions when needed?
- Can it filter by asset type: 주택, 토지, 분양권, 입주권?
- Can it filter by issue type: 비과세, 감면, 중과, 단기세율, 고가주택?

**Chunking**
- Are chunks too large for precise reranking?
- Are 항/호-level chunks retrievable independently?
- Are article-level parent chunks retrievable for context?
- Is parent-child retrieval implemented?
- Are neighboring clauses pulled after initial retrieval?
- Are exception clauses attached to main clauses?
- Are definitions indexed separately and linked?
- Is there a citation-safe chunk boundary?
- Are long articles split without losing citation traceability?

**Hybrid retrieval**
- Is dense-only retrieval enough for article numbers like “제89조”?
- Is sparse/BM25 search used alongside embeddings?
- Is exact citation lookup available?
- Is Korean legal term normalization handled?
- Are synonyms handled: 양도세 vs 양도소득세, 비과세 vs 과세제외?
- Are Hangul/number variants normalized?
- Can it retrieve by statute abbreviation?

---

**4. Evaluation Harness Blind Spots**

**Golden set**
- How many golden cases exist?
- Are they real cases, synthetic cases, or mixed?
- Who labeled them?
- Are labels reviewed by tax professionals?
- Does each golden case include expected verdict and expected citations?
- Does it include missing-fact expected outputs?
- Does it include calculation expected outputs where applicable?
- Are edge cases overrepresented or underrepresented?
- Are ordinary easy cases included?
- Are historical-law cases included?
- Are law-amendment boundary cases included?
- Are ambiguous cases included?
- Are adversarial cases included?
- Are contradictory fact cases included?

**Verdict coverage**
- Are there cases for 비과세?
- 감면?
- 중과?
- 일반과세?
- 단기세율?
- 고가주택?
- 사실관계부족?
- mixed verdicts, e.g. 고가주택 partially taxable but otherwise 1세대1주택?
- 중과 배제?
- 장특공제 allowed/disallowed?
- 일시적 2주택?
- 상속주택?
- 농어촌주택?
- 조합원입주권?
- 분양권?
- 비사업용토지?
- 미등기양도?

**Metrics**
- Do you measure retrieval recall@k?
- reranker recall@n?
- citation precision?
- citation recall?
- verdict accuracy?
- missing-fact detection accuracy?
- hallucinated citation rate?
- unsupported legal proposition rate?
- abstention accuracy?
- calibration of confidence scores?
- latency p50/p95/p99?
- cost per answer?
- Red-Blue debate win/loss correctness?
- regression from corpus update?
- regression from prompt update?
- regression from model update?

**Test levels**
- Unit tests for XML parsing?
- Unit tests for date applicability?
- Unit tests for chunk metadata?
- Unit tests for citation formatting?
- Integration tests against Pinecone?
- Offline retrieval tests using fixed embeddings?
- End-to-end tests with frozen model outputs?
- LLM-as-judge tests with human audit?
- Mutation tests where key facts are removed?
- Tests where retrieved law is intentionally incomplete?
- Tests for refusal/uncertainty when facts are missing?

**Ground truth**
- Is the expected answer based on actual tax filing outcome?
- Tax accountant opinion?
- Court/ruling outcome?
- Internal legal analysis?
- Are disagreements tracked?
- Is there an appeal process for mislabeled golden cases?
- Are golden labels versioned with law version and prompt version?

---

**5. Pipeline Accuracy Risks**

**Fact interpretation**
- Does the L2-L5 pipeline validate schema before retrieval?
- Does it detect impossible dates?
- Does it calculate holding period deterministically?
- Does it calculate residence period deterministically?
- Does it calculate household ownership count deterministically?
- Does the LLM ever perform arithmetic that should be done by code?
- Are date intervals inclusive/exclusive according to Korean tax rules?
- Are acquisition date rules source-specific?
- Are inheritance/gift acquisition date rules handled explicitly?

**Retrieval**
- Can query expansion accidentally retrieve irrelevant special cases?
- Can top-k miss exceptions?
- Does reranking overfavor semantically similar but legally inapplicable provisions?
- Does reranking receive enough structured facts?
- Are negative conditions retrieved?
- Are definitions retrieved when terms are ambiguous?
- Are related 시행령 provisions guaranteed to be retrieved?
- Is there a fallback exact-article retrieval after semantic retrieval?
- Is there a rule graph or citation graph supplementing vector search?

**Reasoning**
- Are deterministic rule checks used before LLM reasoning?
- Does Claude receive only retrieved context, or can it use latent legal memory?
- Are prompts explicitly prohibiting unsupported legal claims?
- Is every legal proposition tied to a chunk ID?
- Does the answer distinguish rule, fact, application, conclusion?
- Does it explain uncertainty when facts are missing?
- Does it avoid final verdict when required facts are unknown?
- Does it support multiple possible outcomes based on missing facts?
- Does Red-Blue debate improve accuracy or just add persuasive hallucination?
- Is debate output citation-verified afterward?
- Are both Red and Blue constrained to retrieved evidence?

**Citation verification**
- Does `CitationVerifier` check exact article existence in retrieved chunks?
- Does it check that cited paragraph/subparagraph exists?
- Does it check that citation supports the proposition being made?
- Does it reject citations from non-applicable law versions?
- Does it detect invented citations?
- Does it detect correct citation but wrong interpretation?
- Does it trace every verdict element to supporting evidence?

**Confidence**
- What does confidence mean?
- Is it calibrated against observed accuracy?
- Is confidence based on retrieval score, reranker score, LLM self-rating, or ensemble?
- Are low-confidence thresholds empirically selected?
- Does confidence decrease for missing facts?
- Does confidence decrease for conflicting retrieved authorities?
- Does confidence decrease when only administrative guidance supports the answer?

---

**6. Missing Ruling / Precedent Data**

**Administrative rulings**
- Are 국세청 질의회신 collected?
- Are 사전답변 collected?
- Are 서면질의 collected?
- Are 재산세과 rulings collected?
- Are 기획재정부 해석 collected?
- Are rulings mapped to statutes/articles?
- Are ruling dates indexed?
- Are obsolete rulings marked obsolete?
- Are contradictory rulings detected?
- Are rulings ranked below statutes but above weak secondary sources?

**Tax appeals and litigation**
- Are 조세심판원 decisions collected?
- Are 감사원 심사 decisions collected?
- Are 국세청 심사청구 decisions collected?
- Are administrative court decisions collected?
- Are Supreme Court cases collected?
- Are case outcomes structured?
- Are facts from cases structured separately from holdings?
- Are holdings linked to issues?
- Can the system distinguish similar facts from materially different facts?

**Authority hierarchy**
- Does the system rank authority as:
  statute > enforcement decree > enforcement rule > binding interpretation > court precedent > tribunal decision > administrative ruling?
- Does it explain when a source is not binding?
- Does it surface conflicts between authority types?
- Does it avoid treating one taxpayer-specific ruling as universally applicable?
- Are recent amendments checked against older rulings before using them?

**Data licensing**
- Are you allowed to store and serve each ruling/case source?
- Are there redistribution restrictions?
- Are source URLs retained?
- Is there a takedown/update process?

---

**7. Deployment / Ops Gaps**

**Security**
- Are API keys stored in a secrets manager?
- Are keys rotated?
- Is Pinecone access scoped?
- Are Claude/OpenAI/Upstage keys separated by environment?
- Are user fact inputs encrypted at rest?
- Are logs redacted for personally identifiable information?
- Are 주민등록번호, addresses, transaction amounts, family info protected?
- Is there access control?
- Is there tenant isolation?
- Is there audit logging?
- Is prompt injection handled?
- Can retrieved legal text or user input override system instructions?
- Is MCP tool access authenticated?

**Reliability**
- What is the fallback if Pinecone is down?
- What is the fallback if Upstage embedding fails?
- What is the fallback if BGE reranker fails?
- What is the fallback if Claude times out?
- Are retries idempotent?
- Are partial failures visible to users?
- Are circuit breakers implemented?
- Is there queueing for long-running debate cases?
- Are timeouts defined per stage?
- Are p95 and p99 latency targets defined?

**Observability**
- Do you log query, facts hash, retrieved chunk IDs, reranked chunk IDs, prompt version, model version, verdict, citations, confidence?
- Do you store full traces for later audit?
- Are traces privacy-safe?
- Can you replay a past answer exactly?
- Are corpus version, index version, embedding version, prompt version, and model version attached to every answer?
- Are hallucinated citation incidents tracked?
- Are low-confidence cases reviewed?
- Is there alerting for retrieval degradation?
- Is there alerting for cost spikes?
- Is there alerting for latency spikes?

**Release management**
- Is there staging before production?
- Is there blue/green index deployment?
- Is there rollback for corpus updates?
- Is there rollback for prompt updates?
- Is there rollback for model updates?
- Are golden tests required before release?
- Are law updates automatically tested before publishing?
- Is there a human approval gate for new law versions?
- Is there a changelog of legal corpus updates?

**Compliance and product risk**
- Is the system positioned as legal/tax information, not final tax advice?
- Is there a mandatory disclaimer?
- Is there escalation to tax professional review?
- Are high-value or low-confidence cases blocked from definitive answers?
- Are users told which facts are missing?
- Are users told which law version was applied?
- Are users told the answer may differ based on local tax office interpretation?
- Is there an audit package export for professionals?

**Cost and scaling**
- What is cost per normal case?
- Cost per debate case?
- Max concurrent users?
- Pinecone QPS limits?
- Claude rate limits?
- Upstage rate limits?
- Reranker GPU/CPU capacity?
- Are embeddings cached?
- Are retrieval results cached?
- Are repeated structured fact cases deduplicated?
- Is batch evaluation affordable?

---

**8. Additional Production-Completeness Questions**

**Schema governance**
- Is `FactInput` versioned?
- Can old saved cases be replayed after schema changes?
- Are unknown fields rejected or preserved?
- Are enum values controlled?
- Is Korean address normalization supported?
- Is date normalization strict?
- Are monetary values validated for currency/unit?

**Deterministic tax engine**
- Which parts are deterministic code versus LLM reasoning?
- Are tax rate tables encoded as data?
- Are thresholds versioned?
- Are annual limits versioned?
- Are 고가주택 thresholds versioned by year?
- Are 감면 caps versioned?
- Are calculations unit-tested separately from legal reasoning?

**Human review**
- What cases require human review?
- Can reviewers correct verdict, citations, or facts?
- Do corrections feed the golden set?
- Are reviewer disagreements tracked?
- Is there a reviewer UI?
- Is there a professional audit trail?

**User experience**
- Does the system ask targeted follow-up questions?
- Does it avoid asking irrelevant questions?
- Can it explain why each missing fact matters?
- Can it produce both short and professional-detail answers?
- Can it output a structured JSON verdict for downstream systems?
- Can it output Korean natural-language reasoning with citations?

**Final readiness question**
- For any production answer, can you reconstruct:
  `input facts -> normalized facts -> retrieved chunks -> reranked chunks -> applied law versions -> reasoning steps -> citations -> final verdict -> confidence -> missing facts -> model/prompt/index/corpus versions`?

If the answer to that final question is not “yes, deterministically and auditably,” the system is not production-perfect yet.
tokens used
19,368

```

## Concise summary

Provider completed successfully. Review the raw output for details.

## Action items

- Review the response and extract decisions you want to apply.
- Capture follow-up implementation tasks if needed.
