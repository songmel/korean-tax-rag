# gemini advisor artifact

- Provider: gemini
- Exit code: 0
- Created at: 2026-05-11T07:32:53.588Z

## Original task

Analyze this Korean tax consultation AI PRD for a 4-week hackathon. PRODUCT: RAG-based AI for capital gains tax exemption eligibility in Korea. Tech stack: CrewAI, LlamaIndex, Pinecone, FastAPI MCP server, Claude LLM, Streamlit debug UI. Three agents: fact extractor, tax law researcher, tax advisor. QUESTIONS: 1. What is missing from PRD that would block development? 2. What should Streamlit debug UI show for hackathon demo? 3. Key edge cases in 1-household 1-property exemption? 4. How to handle ambiguous missing data from documents? 5. What makes this demo stand out for LangChain/CrewAI/MCP hackathon judges?

## Final prompt

Analyze this Korean tax consultation AI PRD for a 4-week hackathon. PRODUCT: RAG-based AI for capital gains tax exemption eligibility in Korea. Tech stack: CrewAI, LlamaIndex, Pinecone, FastAPI MCP server, Claude LLM, Streamlit debug UI. Three agents: fact extractor, tax law researcher, tax advisor. QUESTIONS: 1. What is missing from PRD that would block development? 2. What should Streamlit debug UI show for hackathon demo? 3. Key edge cases in 1-household 1-property exemption? 4. How to handle ambiguous missing data from documents? 5. What makes this demo stand out for LangChain/CrewAI/MCP hackathon judges?

## Raw output

```text
This analysis evaluates the proposed Korean Tax Consultation AI (RAG-based) for a 4-week hackathon, focusing on technical feasibility, demo impact, and domain-specific nuances.

### 1. Missing from PRD (Development Blockers)
*   **OCR/Document Parsing Strategy:** Korean property documents (Resident Registration - *Jumin-Deungrok*, Sale Agreements - *Maemae-Gyeyakseo*) are often scanned PDFs or images. Without a clear OCR pipeline (e.g., Upstage Document AI, AWS Textract, or Tesseract), the Fact Extractor will fail.
*   **Tax Data Source & Schema:** LlamaIndex needs structured/unstructured data. Will you scrape the *National Law Information Center* (law.go.kr) or use pre-processed tax guides? The lack of a "Tax Knowledge Base" definition is a major risk.
*   **PII Masking:** Korean privacy laws (GDPR-equivalent) are strict. Handling Resident Registration Numbers (RRNs) requires a masking step before sending data to Claude/OpenAI.
*   **Agent Hand-off Protocol:** How does the "Fact Extractor" pass data to the "Researcher"? A structured schema (JSON) for "Extracted Facts" is needed to prevent the Researcher from hallucinating missing variables.

### 2. Streamlit Debug UI: Impressing the Judges
For a hackathon, the "black box" nature of AI is your enemy. The UI should visualize the **Agentic Workflow**:
*   **The "Brain" Trace:** Use a sidebar to show the **CrewAI agent thought process** in real-time (e.g., "Researcher: I am looking for Article 89 of the Income Tax Act...").
*   **RAG Provenance:** Don't just show retrieved text; show the **Source Mapping**. Highlight which specific sentence in the user's contract triggered a specific law lookup.
*   **MCP Tool Inspector:** A dedicated tab showing the **JSON-RPC traffic** through the MCP server. This proves the "Agentic" nature of the system (Claude calling your FastAPI tools).
*   **"What If" Simulator:** Allow judges to toggle a variable (e.g., "What if this house was in a Regulated Area?") and see how the Tax Advisor’s judgment changes instantly.

### 3. Key Edge Cases in 1-Household 1-Property (Korea)
Your system must handle these "trap" scenarios to be credible:
*   **Temporary 2-Household (*Ilsi-jeok 2-jutack*):** The "disposal window" (e.g., selling the old house within 3 years of buying the new one) is the most common user query.
*   **High-Priced Housing (>1.2 Billion KRW):** Exemption is not 100% for houses over 1.2bn. The system must calculate the taxable portion of the gain proportionally.
*   **Residence vs. Ownership:** Distinguishing between the 2-year *ownership* requirement and the 2-year *residence* requirement (mandatory in "Regulated Areas" - *Jojeong-daesang-jiyeok*).
*   **Household Composition:** A child living with parents but earning income might count as a separate household, or vice versa. This is a high-ambiguity area.

### 4. Handling Ambiguous/Missing Data
*   **The "Confidence Score" Pattern:** The Fact Extractor should tag each field (e.g., `sale_date: 90% confidence`).
*   **Clarification Agent:** If a critical field (e.g., "Is it a regulated area?") is missing, the system shouldn't guess. It should output: *"I cannot determine exemption because the 'Residence Duration' is missing. Please confirm if you lived there for 2+ years."*
*   **Scenario Branching:** The Advisor should provide conditional logic: *"Based on the docs, you qualify. **However**, if you own another 'officetel' not shown here, you will be disqualified."*

### 5. Standing Out for Hackathon Judges
*   **MCP as the "Glue":** Most participants will use standard API calls. Using the **Model Context Protocol (MCP)** to expose your Tax Law Index as a tool to Claude shows you are at the cutting edge of the ecosystem.
*   **Citation-First RAG:** Ensure every claim made by the Tax Advisor includes a hyperlinked citation to the specific Korean Law Article. This builds "Trustworthy AI."
*   **Multi-Agent Collaborative Reasoning:** Show a "Conflict Resolution" scenario. For example, the Researcher finds a law, but the Advisor realizes a specific *Administrative Interpretation* (*Yu-gwon-hae-seok*) overrides it. This justifies the "CrewAI" overhead.
*   **Local Nuance:** Include a "Tax Savings Tip" section (e.g., "Long-term special deduction") to move from a "Checker" to a "Consultant."


Warning: 256-color support not detected. Using a terminal with at least 256-color support is recommended for a better visual experience.
YOLO mode is enabled. All tool calls will be automatically approved.
YOLO mode is enabled. All tool calls will be automatically approved.
Ripgrep is not available. Falling back to GrepTool.

```

## Concise summary

Provider completed successfully. Review the raw output for details.

## Action items

- Review the response and extract decisions you want to apply.
- Capture follow-up implementation tasks if needed.
