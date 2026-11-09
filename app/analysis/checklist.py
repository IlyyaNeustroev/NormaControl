import json
import re

import ollama

from app.config.settings import settings
from app.db.models import db, Document, ChecklistItem, Finding


CRITERIA = [
    "цель документа",
    "роли и ответственность",
    "входы процесса",
    "выходы процесса",
    "измеримые показатели",
    "сроки выполнения",
    "порядок эскалации",
    "актуальность ссылок",
    "корректность оформления"
]

CHECKLIST_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "criterion": {"type": "string"},
                    "status": {
                        "type": "string",
                        "enum": ["green", "yellow", "red"]
                    },
                    "score": {"type": "number"},
                    "evidence": {"type": "string"},
                    "recommendation": {"type": "string"}
                },
                "required": [
                    "criterion",
                    "status",
                    "score",
                    "evidence",
                    "recommendation"
                ]
            }
        },
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "finding_type": {
                        "type": "string",
                        "enum": [
                            "version_conflict",
                            "cross_document_conflict",
                            "internal_inconsistency",
                            "methodological_gap",
                            "formatting_defect"
                        ]
                    },
                    "severity": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "critical"]
                    },
                    "priority": {"type": "integer"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "evidence": {"type": "string"},
                    "recommendation": {"type": "string"}
                },
                "required": [
                    "finding_type",
                    "severity",
                    "priority",
                    "title",
                    "description",
                    "evidence",
                    "recommendation"
                ]
            }
        }
    },
    "required": ["items", "findings"]
}


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
    text = clean_json(text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)

    if not match:
        return None

    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def ask_llm(prompt: str) -> dict:
    response = ollama.chat(
        model=settings.OLLAMA_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "Ты — инженер по анализу корпоративной документации. "
                    "Анализируй только предоставленный текст. "
                    "Не придумывай требования и факты. "
                    "Отвечай строго JSON по заданной схеме."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        format=CHECKLIST_SCHEMA,
        options={
            "temperature": 0,
            "num_ctx": 4096
        }
    )

    content = response["message"]["content"]

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        data = extract_json(content)

        if data:
            return data

        print("LLM вернул некорректный JSON:")
        print(content[:1000])
        return {}


def analyze_document(document):
    text = document.markdown or ""

    if not text.strip():
        print(f"Пропущен: {document.file_name} — нет текста")
        return

    prompt = f"""
Проанализируй корпоративный документ по чек-листу.

Критерии:
{json.dumps(CRITERIA, ensure_ascii=False)}

Для каждого критерия заполни items.

Если критерий не найден в документе, ставь:
- status: "red"
- score: 0.0
- evidence: ""
- recommendation: "Критерий не найден в документе"

Если найдены проблемы, добавь findings.

Документ:
{text[:7000]}
"""

    result = ask_llm(prompt)

    if not result:
        print(f"Пропущен из-за некорректного ответа LLM: {document.file_name}")
        return

    items = result.get("items", [])

    if not items:
        print(f"Чек-лист не заполнен: {document.file_name}")
        return

    for item in items:
        db.session.add(
            ChecklistItem(
                document_id=document.id,
                criterion=item.get("criterion"),
                status=item.get("status"),
                score=item.get("score"),
                evidence=item.get("evidence"),
                recommendation=item.get("recommendation")
            )
        )

    for finding in result.get("findings", []):
        db.session.add(
            Finding(
                document_id=document.id,
                finding_type=finding.get("finding_type"),
                severity=finding.get("severity"),
                priority=finding.get("priority"),
                title=finding.get("title"),
                description=finding.get("description"),
                evidence=finding.get("evidence"),
                recommendation=finding.get("recommendation")
            )
        )

    print(f"Чек-лист сохранён: {document.file_name}")


def analyze_all(app):
    with app.app_context():
        ChecklistItem.query.delete()
        Finding.query.delete()
        db.session.commit()

        for document in Document.query.all():
            print(f"Анализ: {document.file_name}")

            try:
                analyze_document(document)
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                print(f"Ошибка при анализе {document.file_name}: {e}")


if __name__ == "__main__":
    from app.web.app import create_app

    app = create_app()
    analyze_all(app)