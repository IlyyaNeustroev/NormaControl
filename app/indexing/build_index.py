from pathlib import Path

from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

from app.db.models import db, Document, DocumentChunk
from app.config.settings import settings

client = None
model = None

def chunk_text(text, size=900, overlap=150):
    chunks = []
    start = 0

    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start = end - overlap

    return chunks

def build_index(app):
    global client, model

    settings.QDRANT_LOCAL_PATH.mkdir(parents=True, exist_ok=True)

    client = QdrantClient(path=str(settings.QDRANT_LOCAL_PATH))
    model = SentenceTransformer(settings.EMBEDDING_MODEL)

    try:
        with app.app_context():
            if not client.collection_exists(settings.QDRANT_COLLECTION):
                client.create_collection(
                    collection_name=settings.QDRANT_COLLECTION,
                    vectors_config=VectorParams(
                        size=model.get_sentence_embedding_dimension(),
                        distance=Distance.COSINE
                    )
                )

            documents = Document.query.all()
            point_id = 1

            for document in documents:
                DocumentChunk.query.filter_by(document_id=document.id).delete()

                for i, chunk in enumerate(chunk_text(document.markdown or "")):
                    vector = model.encode(chunk).tolist()

                    client.upsert(
                        collection_name=settings.QDRANT_COLLECTION,
                        points=[
                            PointStruct(
                                id=point_id,
                                vector=vector,
                                payload={
                                    "document_id": document.id,
                                    "file_name": document.file_name,
                                    "chunk_id": i,
                                    "text": chunk
                                }
                            )
                        ]
                    )

                    db.session.add(
                        DocumentChunk(
                            document_id=document.id,
                            chunk_id=i,
                            text=chunk
                        )
                    )

                    point_id += 1

                db.session.commit()
                print(f"Индексирован: {document.file_name}")

    finally:
        client.close()
        print("Qdrant client закрыт")

if __name__ == "__main__":
    from app.web.app import create_app
    app = create_app()
    build_index(app)