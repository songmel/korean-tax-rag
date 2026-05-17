"""
임베딩 + Pinecone 업로드 스크립트
data/processed/all_chunks.json → Pinecone Serverless
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
BATCH_SIZE = 100  # Pinecone upsert 배치 크기


def _build_embed_client() -> tuple[OpenAI, str, int]:
    """(client, model_name, dimension) 반환"""
    if UPSTAGE_API_KEY:
        client = OpenAI(
            api_key=UPSTAGE_API_KEY,
            base_url="https://api.upstage.ai/v1",
        )
        return client, UPSTAGE_EMBEDDING_MODEL, 4096
    if OPENAI_API_KEY:
        client = OpenAI(api_key=OPENAI_API_KEY)
        return client, "text-embedding-3-large", 3072
    raise RuntimeError("UPSTAGE_API_KEY 또는 OPENAI_API_KEY 중 하나가 필요합니다")


def _embed_texts(client: OpenAI, model: str, texts: list[str]) -> list[list[float]]:
    """텍스트 배치를 임베딩 벡터로 변환"""
    truncated = [t[:3000] for t in texts]
    resp = client.embeddings.create(model=model, input=truncated)
    return [item.embedding for item in resp.data]


def _get_or_create_index(pc: Pinecone, dimension: int):
    """Pinecone 인덱스 조회 또는 생성"""
    existing = [idx.name for idx in pc.list_indexes()]
    if PINECONE_INDEX_NAME not in existing:
        print(f"인덱스 생성 중: {PINECONE_INDEX_NAME} (dim={dimension})")
        pc.create_index(
            name=PINECONE_INDEX_NAME,
            dimension=dimension,
            metric="cosine",
            spec=ServerlessSpec(cloud=PINECONE_CLOUD, region=PINECONE_REGION),
        )
        # 인덱스 준비 대기
        while not pc.describe_index(PINECONE_INDEX_NAME).status["ready"]:
            print("  인덱스 준비 중...")
            time.sleep(3)
        print("  인덱스 준비 완료")
    else:
        print(f"기존 인덱스 사용: {PINECONE_INDEX_NAME}")
    return pc.Index(PINECONE_INDEX_NAME)


def embed_and_upload(chunks_path: Optional[Path] = None) -> int:
    """
    JSON 청크 파일을 읽어 임베딩 후 Pinecone에 업로드.
    반환값: upsert된 벡터 수
    """
    if chunks_path is None:
        chunks_path = PROCESSED_DIR / "all_chunks.json"

    if not chunks_path.exists():
        raise FileNotFoundError(
            f"{chunks_path} 없음 — 먼저 `python src/collect.py` 실행"
        )

    if not PINECONE_API_KEY:
        raise RuntimeError("PINECONE_API_KEY가 필요합니다")

    # 청크 로드
    chunks = json.loads(chunks_path.read_text(encoding="utf-8"))
    print(f"총 {len(chunks)}개 청크 로드 완료")

    # 임베딩 클라이언트
    embed_client, embed_model, dimension = _build_embed_client()
    print(f"임베딩 모델: {embed_model} (dim={dimension})")

    # Pinecone 인덱스
    pc = Pinecone(api_key=PINECONE_API_KEY)
    index = _get_or_create_index(pc, dimension)

    # 배치 업로드
    total_upserted = 0
    batches = [chunks[i : i + BATCH_SIZE] for i in range(0, len(chunks), BATCH_SIZE)]

    for batch in tqdm(batches, desc="Pinecone 업로드"):
        texts = [c.get("full_text", "") for c in batch]
        try:
            vectors = _embed_texts(embed_client, embed_model, texts)
        except Exception as e:
            print(f"\n임베딩 오류 (배치 건너뜀): {e}")
            continue

        upsert_payload = []
        for chunk, vec in zip(batch, vectors):
            metadata = {
                "law_name": chunk.get("law_name", ""),
                "article_number": chunk.get("article_number", ""),
                "article_title": chunk.get("article_title", ""),
                "effective_date": chunk.get("effective_date", ""),
                "expiration_date": chunk.get("expiration_date", ""),  # 빈 문자열 = 현행
                "version_mst": chunk.get("version_mst", chunk.get("law_mst", "")),
                "law_category": chunk.get("law_category", ""),
                "source": "law.go.kr",
                # Pinecone 벡터당 메타데이터 한도 40KB — 4000자까지 저장 (reranker + LLM 모두 이 필드 사용)
                "full_text": chunk.get("full_text", "")[:4000],
            }
            upsert_payload.append(
                {"id": chunk["id"], "values": vec, "metadata": metadata}
            )

        index.upsert(vectors=upsert_payload, namespace=PINECONE_NAMESPACE)
        total_upserted += len(upsert_payload)
        time.sleep(0.2)  # rate limit 방지

    print(f"\n[완료] {total_upserted}개 벡터 업로드 → {PINECONE_INDEX_NAME}/{PINECONE_NAMESPACE}")
    return total_upserted


if __name__ == "__main__":
    embed_and_upload()
