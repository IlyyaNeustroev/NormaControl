import json
import re
import requests

from app.db.models import db, Document, ProcessStep, RaciAssignment, CalendarActivity
from app.config.settings import settings

def ask_llm(prompt):
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

def build_process_model(document):
    text = document.markdown or ""

    prompt = f"""
Извлеки из документа модель бизнес-процесса.

Верни JSON:
{{
  "process_name": "",
  "steps": [
    {{
      "step_order": 1,
      "name": "",
      "performer": "",
      "input_data": "",
      "output_data": "",
      "system": ""
    }}
  ],
  "raci": [
    {{
      "activity": "",
      "role": "",
      "raci": "R|A|C|I"
    }}
  ],
  "calendar": [
    {{
      "activity": "",
      "owner": "",
      "frequency": "",
      "next_due_date": null
    }}
  ]
}}

Документ:
{text[:7000]}
"""

    return ask_llm(prompt)

def save_process(document, model_result):
    process_name = model_result.get("process_name") or document.title or "Неизвестный процесс"

    for step in model_result.get("steps", []):
        db.session.add(ProcessStep(
            process_name=process_name,
            step_order=step.get("step_order"),
            name=step.get("name"),
            performer=step.get("performer"),
            input_data=step.get("input_data"),
            output_data=step.get("output_data"),
            system=step.get("system"),
            document_id=document.id
        ))

    for item in model_result.get("raci", []):
        db.session.add(RaciAssignment(
            process_name=process_name,
            activity=item.get("activity"),
            role=item.get("role"),
            raci=item.get("raci")
        ))

    for item in model_result.get("calendar", []):
        db.session.add(CalendarActivity(
            process_name=process_name,
            activity=item.get("activity"),
            owner=item.get("owner"),
            frequency=item.get("frequency"),
            document_id=document.id
        ))

def build_all(app):
    with app.app_context():
        ProcessStep.query.delete()
        RaciAssignment.query.delete()
        CalendarActivity.query.delete()

        for document in Document.query.all():
            print(f"Процесс: {document.file_name}")
            result = build_process_model(document)
            save_process(document, result)
            db.session.commit()

if __name__ == "__main__":
    from app.web.app import create_app
    app = create_app()
    build_all(app)