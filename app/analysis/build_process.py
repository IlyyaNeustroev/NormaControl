import json
import re
from pathlib import Path

import kuzu
import ollama

from app.config.settings import settings
from app.db.models import db, Document


PROCESS_OUTPUT_DIR = Path("data/processed/process")

SYSTEM_PROMPT = """
Ты — инженер по анализу технической документации.

Твоя задача — извлечь из текста документа этапы технологического или производственного процесса.

Правила:
1. Извлекай только информацию, которая прямо есть в тексте.
2. Не придумывай этапы.
3. Если этапов нет, верни пустой список.
4. Отвечай строго валидным JSON без markdown, без пояснений и без лишнего текста.
5. Каждый этап должен быть коротким и понятным.
6. Сохраняй порядок этапов.
7. Если в тексте есть номера операций, используй их в поле step_number.
8. Если номера нет, ставь пустую строку.

Формат ответа:
{
  "process_name": "Название процесса",
  "steps": [
    {
      "step_number": "1",
      "name": "Название этапа",
      "description": "Краткое описание этапа",
      "document_ref": "Ссылка на документ или пункт, если есть"
    }
  ]
}
"""


def clean_json(text: str) -> str:
    text = text.strip()

    if text.startswith("```json"):
        text = text.replace("```json", "", 1)

    if text.startswith("```"):
        text = text.replace("```", "", 1)

    if text.endswith("```"):
        text = text.replace("```", "", 1)

    return text.strip()


def extract_json(text: str):
    try:
        return json.loads(clean_json(text))
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)

        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return None

    return None


def build_context(document, max_chars: int = 6000) -> str:
    text = document.markdown or document.raw_text or ""

    if len(text) > max_chars:
        text = text[:max_chars]

    return text


def extract_process(document) -> dict | None:
    context = build_context(document)

    if not context.strip():
        print(f"Пропущен: {document.file_name} — нет текста")
        return None

    prompt = f"""
Документ:
{context}

Извлеки этапы процесса из этого документа.
"""

    response = ollama.chat(
        model=settings.OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        options={
            "temperature": 0,
            "num_ctx": 4096
        }
    )

    content = response["message"]["content"]
    data = extract_json(content)

    if not data:
        print(f"Не удалось распарсить JSON для: {document.file_name}")
        print(content[:500])
        return None

    return data


def save_process_result(document, data: dict):
    PROCESS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    safe_name = re.sub(r"[^\w\-]+", "_", document.file_name)
    output_path = PROCESS_OUTPUT_DIR / f"{safe_name}.json"

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return output_path


def build_process_graph(app):
    db_path = settings.KUZU_DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)

    database = kuzu.Database(str(db_path))
    connection = kuzu.Connection(database)

    connection.execute("""
        CREATE NODE TABLE IF NOT EXISTS Process (
            name STRING,
            PRIMARY KEY(name)
        )
    """)

    connection.execute("""
        CREATE NODE TABLE IF NOT EXISTS ProcessStep (
            id STRING,
            step_number STRING,
            name STRING,
            description STRING,
            document_ref STRING,
            PRIMARY KEY(id)
        )
    """)

    connection.execute("""
        CREATE REL TABLE IF NOT EXISTS HAS_STEP (
            FROM Process TO ProcessStep
        )
    """)

    connection.execute("""
        CREATE REL TABLE IF NOT EXISTS NEXT_STEP (
            FROM ProcessStep TO ProcessStep
        )
    """)

    connection.execute("""
        CREATE REL TABLE IF NOT EXISTS BASED_ON_DOCUMENT (
            FROM ProcessStep TO Document
        )
    """)

    with app.app_context():
        documents = Document.query.all()

        for document in documents:
            print(f"Анализ: {document.file_name}")

            data = extract_process(document)

            if not data:
                continue

            process_name = data.get("process_name") or document.title or document.file_name
            steps = data.get("steps") or []

            if not steps:
                print(f"Этапы не найдены: {document.file_name}")
                continue

            save_process_result(document, data)

            connection.execute(
                """
                MERGE (p:Process {name: $process_name})
                """,
                parameters={
                    "process_name": process_name
                }
            )

            previous_step_id = None

            for index, step in enumerate(steps):
                step_id = f"{document.id}_{index}"

                connection.execute(
                    """
                    MERGE (s:ProcessStep {id: $step_id})
                    SET s.step_number = $step_number,
                        s.name = $name,
                        s.description = $description,
                        s.document_ref = $document_ref
                    """,
                    parameters={
                        "step_id": step_id,
                        "step_number": str(step.get("step_number") or ""),
                        "name": step.get("name") or "",
                        "description": step.get("description") or "",
                        "document_ref": step.get("document_ref") or ""
                    }
                )

                connection.execute(
                    """
                    MATCH (p:Process {name: $process_name}), (s:ProcessStep {id: $step_id})
                    MERGE (p)-[:HAS_STEP]->(s)
                    """,
                    parameters={
                        "process_name": process_name,
                        "step_id": step_id
                    }
                )

                connection.execute(
                    """
                    MATCH (s:ProcessStep {id: $step_id}), (d:Document {id: $document_id})
                    MERGE (s)-[:BASED_ON_DOCUMENT]->(d)
                    """,
                    parameters={
                        "step_id": step_id,
                        "document_id": document.id
                    }
                )

                if previous_step_id:
                    connection.execute(
                        """
                        MATCH (a:ProcessStep {id: $previous_step_id}), (b:ProcessStep {id: $step_id})
                        MERGE (a)-[:NEXT_STEP]->(b)
                        """,
                        parameters={
                            "previous_step_id": previous_step_id,
                            "step_id": step_id
                        }
                    )

                previous_step_id = step_id

            print(f"Обработано этапов: {len(steps)} — {document.file_name}")

    connection.close()
    database.close()

    print("Граф процессов построен")


if __name__ == "__main__":
    from app.web.app import create_app

    app = create_app()
    build_process_graph(app)