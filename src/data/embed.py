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

# ── Stage 1 필터 태깅 규칙 ─────────────────────────────────────────────────────
# (law_name, article_number_prefix) → (entity_scopes, topic_tags)
# 업스트림 Stage 1 symbolic filter 의 entity_scope / tax_type 매칭에 사용

def _tag_chunk(law_name: str, article_number: str, full_text: str) -> dict:
    """
    조문 정보 기반 규칙 태깅.
    entity_scopes: ["주택", "분양권", "조합원입주권", "토지", ...]
    topic_tags: ["1세대1주택비과세", "장기보유특별공제", ...]
    tax_types: ["transfer"] (현재 수집 대상 전체)
    """
    art = article_number.strip().lstrip("제").split("조")[0].replace("의", ".")
    # "89", "97.2", "154" 등으로 정규화

    entity_scopes: list[str] = []
    topic_tags: list[str] = []

    # 소득세법 / 소득세법 시행령 → 주택 중심 (분양권·입주권 포함)
    if "소득세법" in law_name:
        entity_scopes.append("주택")

        art_num = article_number.lstrip("제").split("조")[0]
        if art_num in ("89",):
            topic_tags += ["1세대1주택비과세"]
        if art_num in ("95",):
            topic_tags += ["장기보유특별공제"]
        if art_num in ("97의2", "97.2"):
            topic_tags += ["1세대1주택비과세", "이월과세"]
        if art_num in ("104",):
            topic_tags += ["다주택중과", "세율"]
        if "시행령" in law_name:
            if art_num in ("154",):
                topic_tags += ["1세대1주택비과세"]
            if art_num in ("155",):
                topic_tags += ["1세대1주택비과세", "일시적2주택", "상속주택"]
            if art_num in ("155의3",):
                topic_tags += ["1세대1주택비과세", "상생임대"]
                entity_scopes.append("상생임대")
            if art_num in ("156의2", "156의3"):
                topic_tags += ["분양권입주권"]
                entity_scopes += ["분양권", "조합원입주권"]
            if art_num in ("167의10",):
                topic_tags += ["다주택중과"]
            if art_num in ("159의4",):
                topic_tags += ["장기보유특별공제"]

    # 조세특례제한법 → 임대주택·농어촌주택 특례
    if "조세특례제한법" in law_name:
        entity_scopes.append("주택")
        topic_tags += ["조특법감면"]
        art_num = article_number.lstrip("제").split("조")[0]
        if art_num in ("97의3", "97의4", "97의5"):
            topic_tags += ["장기임대주택"]
        if art_num in ("99의4",):
            topic_tags += ["장기임대주택"]

    # 부칙/별표 태그
    if "부칙" in full_text[:50] or "부  칙" in full_text[:50]:
        topic_tags.append("부칙경과조치")

    return {
        "entity_scopes": list(dict.fromkeys(entity_scopes)),  # 순서 유지 중복 제거
        "topic_tags": list(dict.fromkeys(topic_tags)),
        "tax_types": ["transfer"],
    }


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
            law_name = chunk.get("law_name", "")
            article_number = chunk.get("article_number", "")
            full_text = chunk.get("full_text", "")
            tags = _tag_chunk(law_name, article_number, full_text)
            metadata = {
                "law_name": law_name,
                "article_number": article_number,
                "article_title": chunk.get("article_title", ""),
                # Pinecone $lte/$gte는 숫자 타입 전용 — YYYYMMDD 정수로 저장
                "effective_date": int(chunk["effective_date"]) if chunk.get("effective_date") else 0,
                "expiration_date": int(chunk["expiration_date"]) if chunk.get("expiration_date") else 99991231,
                "version_mst": chunk.get("version_mst", chunk.get("law_mst", "")),
                "law_category": chunk.get("law_category", ""),
                "source": "law.go.kr",
                # Stage 1 symbolic filter용 태그 (업스트림 entity_scope/tax_type 매칭)
                "entity_scopes": tags["entity_scopes"],
                "topic_tags": tags["topic_tags"],
                "tax_types": tags["tax_types"],
                # Pinecone 벡터당 메타데이터 한도 40KB — 4000자까지 저장 (reranker + LLM 모두 이 필드 사용)
                "full_text": full_text[:4000],
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
