import json
import re
from datetime import datetime

import dateparser
import requests

from app.db.models import db, Document, DocumentRelation
from app.config.settings import settings

DOC_TYPES = [
    "приказ", "распоряжение", "инструкция", "регламент",
    "положение", "стандарт", "политика", "методика","чертеж"
]

NUMBER_RE = re.compile(
    r"(?:приказ|распоряжение|инструкция|регламент|положение|стандарт|политика|методика|чертеж)\s*№\s*([A-Za-zА-Яа-я0-9\-\/]+)",
    re.IGNORECASE
)

DATE_RE = re.compile(
    r"от\s*(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4}|\d{1,2}\s+[а-яё]+\s+\d{4})",
    re.IGNORECASE
)

REPLACES_RE = re.compile(
    r"(?:взамен|взамен ранее действовавш\w+|взамен отмен\w+)\s+(.{5,250}?)(?:\.|;|\n)",
    re.IGNORECASE
)

CANCELLED_RE = re.compile(
    r"(считать\s+утративш\w+\s+силу|утрачивает\s+силу|отмен\w+)",
    re.IGNORECASE
)

def extract_title(text):
    for line in text.splitlines()[:40]:
        clean = line.strip()
        if len(clean) > 10 and any(t in clean.lower() for t in DOC_TYPES):
            return clean
    return None

def extract_document_type(text):
    lowered = text.lower()[:5000]
    for doc_type in DOC_TYPES:
        if doc_type in lowered:
            return doc_type
    return None

def extract_code(text):
    match = NUMBER_RE.search(text[:8000])
    return match.group(1) if match else None

def extract_date(text):
    match = DATE_RE.search(text[:8000])
    if not match:
        return None

    parsed = dateparser.parse(
        match.group(1),
        languages=["ru"],
        settings={"DATE_ORDER": "DMY"}
    )
    return parsed.date() if parsed else None

def extract_status(text):
    if CANCELLED_RE.search(text[:10000]):
        return "утратил силу"
    return "действует"

def extract_replaces(text):
    return [
        match.group(1).strip()
        for match in REPLACES_RE.finditer(text[:10000])
    ]

def llm_metadata(text):
    prompt = f"""
Извлеки паспорт корпоративного документа. Верни только JSON:
{{
  "code": null,
  "title": null,
  "document_type": null,
  "version": null,
  "effective_date": null,
  "owner": null,
  "approving_order": null,
  "approving_order_date": null,
  "review_period_months": null,
  "status": null,
  "replaces": [],
  "references": []
}}

Текст:
{text[:6000]}
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

    raw = response.json()["response"]
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    return json.loads(match.group()) if match else {}

def enrich_document(document, text):
    try:
        data = llm_metadata(text)
    except Exception as exc:
        print(f"LLM fallback не сработал: {exc}")
        return

    fields = [
        "code", "title", "document_type", "version", "owner",
        "approving_order", "status"
    ]

    for field in fields:
        if not getattr(document, field, None) and data.get(field):
            setattr(document, field, data[field])

    if not document.effective_date and data.get("effective_date"):
        parsed = dateparser.parse(
            str(data["effective_date"]),
            languages=["ru"],
            settings={"DATE_ORDER": "DMY"}
        )
        if parsed:
            document.effective_date = parsed.date()

    if not document.approving_order_date and data.get("approving_order_date"):
        parsed = dateparser.parse(
            str(data["approving_order_date"]),
            languages=["ru"],
            settings={"DATE_ORDER": "DMY"}
        )
        if parsed:
            document.approving_order_date = parsed.date()

def extract_all(app):
    with app.app_context():
        documents = Document.query.all()

        for document in documents:
            text = document.markdown or ""

            document.title = document.title or extract_title(text)
            document.document_type = document.document_type or extract_document_type(text)
            document.code = document.code or extract_code(text)
            document.effective_date = document.effective_date or extract_date(text)
            document.status = extract_status(text)

            enrich_document(document, text)

            for replaced_title in extract_replaces(text):
                relation = DocumentRelation(
                    source_document_id=document.id,
                    relation_type="REPLACES",
                    evidence=replaced_title,
                    confidence=0.7
                )
                db.session.add(relation)

            db.session.commit()
            print(f"Метаданные: {document.file_name}")

if __name__ == "__main__":
    from app.web.app import create_app
    app = create_app()
    extract_all(app)