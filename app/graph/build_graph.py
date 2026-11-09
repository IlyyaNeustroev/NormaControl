from pathlib import Path

import kuzu

from app.db.models import db, Document, DocumentRelation
from app.config.settings import settings

def build_graph(app):
    settings.KUZU_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    database = kuzu.Database(str(settings.KUZU_DB_PATH))
    connection = kuzu.Connection(database)

    connection.execute("CREATE NODE TABLE IF NOT EXISTS Document (id INT64, file_name STRING, title STRING, code STRING, status STRING, effective_date STRING, PRIMARY KEY(id))")
    connection.execute("CREATE REL TABLE IF NOT EXISTS REPLACES (FROM Document TO Document)")
    connection.execute("CREATE REL TABLE IF NOT EXISTS REFERENCES (FROM Document TO Document)")
    connection.execute("CREATE REL TABLE IF NOT EXISTS BELONGS_TO_PROCESS (FROM Document TO Document)")

    with app.app_context():
        documents = Document.query.all()

        for document in documents:
            connection.execute(
                """
                MERGE (d:Document {id: $id})
                SET d.file_name = $file_name,
                    d.title = $title,
                    d.code = $code,
                    d.status = $status,
                    d.effective_date = $effective_date
                """,
                parameters={
                    "id": document.id,
                    "file_name": document.file_name,
                    "title": document.title or "",
                    "code": document.code or "",
                    "status": document.status or "",
                    "effective_date": str(document.effective_date or "")
                }
            )

        relations = DocumentRelation.query.all()

        for relation in relations:
            if relation.relation_type == "REPLACES":
                query = """
                MATCH (a:Document {id: $source}), (b:Document {id: $target})
                MERGE (a)-[:REPLACES]->(b)
                """
            else:
                query = """
                MATCH (a:Document {id: $source}), (b:Document {id: $target})
                MERGE (a)-[:REFERENCES]->(b)
                """

            connection.execute(
                query,
                parameters={
                    "source": relation.source_document_id,
                    "target": relation.target_document_id
                }
            )

    print("Граф Kuzu построен")

if __name__ == "__main__":
    from app.web.app import create_app
    app = create_app()
    build_graph(app)