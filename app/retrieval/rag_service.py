import json
import re
import requests
from pathlib import Path

import kuzu
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient

from app.config.settings import settings

def get_clients():
    qdrant = QdrantClient(path=str(settings.QDRANT_LOCAL_PATH))
    embedder = SentenceTransformer(settings.EMBEDDING_MODEL)
    database = kuzu.Database(str(settings.KUZU_DB_PATH))
    graph = kuzu.Connection(database)

    return qdrant, embedder, graph

def vector_search(question, limit=5):
    qdrant, embedder, _ = get_clients()
    vector = embedder.encode(question).tolist()

    results = qdrant.search(
        collection_name=settings.QDRANT_COLLECTION,
        query_vector=vector,
        limit=limit
    )

    return [
        {
            "document_id": item.payload["document_id"],
            "file_name": item.payload["file_name"],
            "text": item.payload["text"]
        }
        for item in results
    ]

def graph_context(document_ids):
    _, _, graph = get_clients()
    context = []

    for document_id in document_ids:
        result = graph.query(
            """
            MATCH (d:Document {id: $id})
            OPTIONAL MATCH (d)-[r:REPLACES]->(old:Document)
            RETURN d.title, d.status, d.effective_date, collect(old.title)
            """,
            parameters={"id": document_id}
        )

        for row in result:
            context.append({
                "document": row[0],
                "status": row[1],
                "effective_date": row[2],
                "replaces": row[3]
            })

    return context

def answer_question(question):
    chunks = vector_search(question)
    document_ids = list({chunk["document_id"] for chunk in chunks})
    graph = graph_context(document_ids)

    prompt = f"""
Ты анализируешь корпоративные документы предприятия.

Вопрос:
{question}

Фрагменты документов:
{json.dumps(chunks, ensure_ascii=False, indent=2)}

Данные графа знаний:
{json.dumps(graph, ensure_ascii=False, indent=2)}

Ответь на русском.
Укажи актуальный документ, устаревшие документы, связи, риски и использованные файлы.
Если данных недостаточно, прямо скажи об этом.
"""

    response = requests.post(
        f"{settings.OLLAMA_BASE_URL}/api/generate",
        json={
            "model": settings.OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0}
        },
        timeout=300
    )
    response.raise_for_status()

    return {
        "answer": response.json()["response"],
        "sources": chunks,
        "graph": graph
    }