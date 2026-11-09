import json
import requests

import kuzu
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient

from app.config.settings import settings


_qdrant_client = None
_embedder = None


def get_qdrant():
    global _qdrant_client

    if _qdrant_client is None:
        _qdrant_client = QdrantClient(
            path=str(settings.QDRANT_LOCAL_PATH)
        )

    return _qdrant_client


def get_embedder():
    global _embedder

    if _embedder is None:
        _embedder = SentenceTransformer(
            settings.EMBEDDING_MODEL
        )

    return _embedder


def vector_search(question, limit=5):
    qdrant = get_qdrant()
    embedder = get_embedder()

    vector = embedder.encode(question).tolist()

    response = qdrant.query_points(
        collection_name=settings.QDRANT_COLLECTION,
        query=vector,
        limit=limit
    )

    chunks = []

    for item in response.points:
        chunks.append(
            {
                "document_id": item.payload.get("document_id"),
                "file_name": item.payload.get("file_name"),
                "chunk_id": item.payload.get("chunk_id"),
                "score": item.score,
                "text": item.payload.get("text")
            }
        )

    return chunks


def graph_context(document_ids):
    database = kuzu.Database(
        str(settings.KUZU_DB_PATH)
    )

    graph = kuzu.Connection(database)

    context = []

    try:
        for document_id in document_ids:
            result = graph.execute(
                """
                MATCH (d:Document {id: $id})
                OPTIONAL MATCH (d)-[r:REPLACES]->(old:Document)
                RETURN d.title, d.status, d.effective_date, collect(old.title)
                """,
                parameters={"id": document_id}
            )

            for row in result:
                context.append(
                    {
                        "document": row[0],
                        "status": row[1],
                        "effective_date": row[2],
                        "replaces": row[3]
                    }
                )

    finally:
        graph.close()
        database.close()

    return context


def answer_question(question):
    chunks = vector_search(question)

    if not chunks:
        return {
            "answer": "В базе нет релевантных документов.",
            "sources": [],
            "graph": []
        }

    document_ids = list(
        {
            chunk["document_id"]
            for chunk in chunks
            if chunk["document_id"] is not None
        }
    )

    graph = graph_context(document_ids)

    prompt = f"""
Ты анализируешь корпоративные документы предприятия.

Вопрос:
{question}

Фрагменты документов:
{json.dumps(chunks, ensure_ascii=False, indent=2)}

Данные графа знаний:
{json.dumps(graph, ensure_ascii=False, indent=2)}

Правила:
1. Отвечай только на основе предоставленных данных.
2. Не придумывай документы, версии, даты или связи.
3. Если данных недостаточно, прямо скажи об этом.
4. Укажи, какие документы использованы.
5. Если есть признаки устаревшего документа, укажи это.
6. Если есть связи REPLACES, объясни их.

Ответь на русском.
"""

    response = requests.post(
        f"{settings.OLLAMA_BASE_URL}/api/generate",
        json={
            "model": settings.OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0,
                "num_ctx": 4096
            }
        },
        timeout=300
    )

    response.raise_for_status()

    data = response.json()

    return {
        "answer": data.get("response", ""),
        "sources": chunks,
        "graph": graph
    }