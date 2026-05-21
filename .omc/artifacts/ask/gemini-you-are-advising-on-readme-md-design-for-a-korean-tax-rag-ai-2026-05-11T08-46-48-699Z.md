# gemini advisor artifact

- Provider: gemini
- Exit code: 41
- Created at: 2026-05-11T08:46:48.708Z

## Original task

You are advising on README.md design for a Korean tax RAG AI project.

PROJECT: RAW agent - tax-rag — AI that determines Korean capital gains tax (양도소득세) exemption eligibility using RAG over official statutes.
STACK: CrewAI, LlamaIndex, FastAPI + MCP, Pinecone, Claude Opus 4.7, Streamlit.
AUDIENCE: Team members onboarding to a 4-week hackathon project. Some may be junior developers. Korean speakers.
LONG-TERM: Core engine for LinkTax commercial SaaS.

Design a README.md that covers:
1. Project introduction (Korean, 2-3 sentences) — what problem it solves
2. Architecture diagram in ASCII — show data flow: user query → MCP → CrewAI agents → LlamaIndex RAG → Pinecone → Claude LLM → response
3. Quick start guide — prerequisites, env setup (.env file vars), install steps, running each component
4. Required environment variables list with descriptions (ANTHROPIC_API_KEY, PINECONE_API_KEY, OPENAI_API_KEY for embeddings, LAW_API_OC)
5. Project structure (file tree with one-line descriptions)
6. Development roadmap — Week 1-4 milestones for the hackathon
7. Team contribution guide — branch strategy, how to add new laws, how to extend agents

Output the actual README.md content. Use Korean for section text, code blocks for commands. Make it professional enough for GitHub.

## Final prompt

You are advising on README.md design for a Korean tax RAG AI project.

PROJECT: RAW agent - tax-rag — AI that determines Korean capital gains tax (양도소득세) exemption eligibility using RAG over official statutes.
STACK: CrewAI, LlamaIndex, FastAPI + MCP, Pinecone, Claude Opus 4.7, Streamlit.
AUDIENCE: Team members onboarding to a 4-week hackathon project. Some may be junior developers. Korean speakers.
LONG-TERM: Core engine for LinkTax commercial SaaS.

Design a README.md that covers:
1. Project introduction (Korean, 2-3 sentences) — what problem it solves
2. Architecture diagram in ASCII — show data flow: user query → MCP → CrewAI agents → LlamaIndex RAG → Pinecone → Claude LLM → response
3. Quick start guide — prerequisites, env setup (.env file vars), install steps, running each component
4. Required environment variables list with descriptions (ANTHROPIC_API_KEY, PINECONE_API_KEY, OPENAI_API_KEY for embeddings, LAW_API_OC)
5. Project structure (file tree with one-line descriptions)
6. Development roadmap — Week 1-4 milestones for the hackathon
7. Team contribution guide — branch strategy, how to add new laws, how to extend agents

Output the actual README.md content. Use Korean for section text, code blocks for commands. Make it professional enough for GitHub.

## Raw output

```text
YOLO mode is enabled. All tool calls will be automatically approved.
Approval mode overridden to "default" because the current folder is not trusted.
Please set an Auth method in your C:\Users\next0\.gemini\settings.json or specify one of the following environment variables before running: GEMINI_API_KEY, GOOGLE_GENAI_USE_VERTEXAI, GOOGLE_GENAI_USE_GCA

```

## Concise summary

Provider command failed (exit 41): YOLO mode is enabled. All tool calls will be automatically approved.

## Action items

- Inspect the raw output error details.
- Fix CLI/auth/environment issues and rerun the command.
