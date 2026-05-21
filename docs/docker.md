# Docker 개발 환경

이 프로젝트는 협업 개발을 위해 하나의 공통 Python 이미지와 세 개의 실행 서비스를 사용합니다.

- `api`: FastAPI 채팅 API (`POST /api/v1/chat`, `GET /health`)
- `ui`: Streamlit 브라우저 UI
- `mcp`: MCP SSE 도구 서버

## 준비

```bash
cp .env.example .env
```

`.env`에 Pinecone, Anthropic, Upstage/OpenAI 키를 채웁니다. 실제 `.env`는 git에 커밋하지 않습니다.

## 이미지 빌드

```bash
docker compose build
```

Docker 빌드는 `constraints-docker.txt`를 사용해 CPU 개발 환경에 맞는 PyTorch 버전을 고정합니다.
테스트 도구는 `requirements-dev.txt`로 분리해 설치합니다.

## 서비스 실행

FastAPI:

```bash
docker compose up api
```

헬스체크:

```bash
curl http://localhost:8000/health
```

Streamlit UI:

```bash
docker compose up ui
```

브라우저에서 `http://localhost:8501`로 접속합니다.

MCP SSE 서버:

```bash
docker compose up mcp
```

MCP 클라이언트는 `http://localhost:8001`에 연결합니다.

## 일회성 명령

법령 수집:

```bash
docker compose run --rm api python -m src.ingestion.collect
```

임베딩 및 Pinecone 업로드:

```bash
docker compose run --rm api python -m src.ingestion.embed
```

테스트:

```bash
docker compose run --rm api python -m pytest
```

문법 검사:

```bash
docker compose run --rm api python -m compileall -q src tests
```

## 캐시와 데이터

`sentence-transformers` / HuggingFace / Torch 캐시는 Docker named volume에 저장됩니다. BGE reranker 모델은 첫 실행 때 다운로드되며, 이후에는 캐시를 재사용합니다.

`data/raw`와 `data/processed`는 git에 포함하지 않는 런타임 데이터입니다. 컨테이너에서는 repo bind mount를 통해 같은 경로를 사용합니다.
