import json
import re
from pathlib import Path

import dateparser
import requests

JSON_DIR = Path("data/processed/json")
META_DIR = Path("data/processed/metadata")

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:7b-instruct"

DOC_TYPES = [
    "приказ", "распоряжение", "инструкция", "регламент",
    "положение", "стандарт", "политика", "методика", "чертеж"
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
    r"(?:взамен|взамен ранее действовавшего\w+|взамен отменного\w+)\s+(.{5,250}?)(?:\.|;|\n)",
    re.IGNORECASE
)

CANCELLED_RE = re.compile(
    r"(считать\s+утратившим\w+\s+силу|утрачивает\s+силу|отменен\w+)",
    re.IGNORECASE
)

def extract_title(text: str):
    for line in text.splitlines()[:30]:
        clean = line.strip()
        if len(clean) > 10 and any(t in clean.lower() for t in DOC_TYPES):
            return clean
    return None

def extract_document_type(text: str):
    lowered = text.lower()[:3000]
    for doc_type in DOC_TYPES:
        if doc_type in lowered:
            return doc_type
    return None

def extract_number(text: str):
    match = NUMBER_RE.search(text[:5000])
    return match.group(1) if match else None

def extract_date(text: str):
    match = DATE_RE.search(text[:5000])
    if not match:
        return None

    parsed = dateparser.parse(
        match.group(1),
        languages=["ru"],
        settings={"DATE_ORDER": "DMY"}
    )
    return parsed.strftime("%Y-%m-%d") if parsed else None

def extract_status(text: str):
    if CANCELLED_RE.search(text[:8000]):
        return "утратил силу"
    return "действует"

def extract_replaces(text: str):
    return [
        match.group(1).strip()
        for match in REPLACES_RE.finditer(text[:8000])
    ]

def llm_metadata(text: str):
    prompt = f"""
Извлеки метаданные документа и верни только JSON:
{{
  "title": null,
  "document_type": null,
  "document_number": null,
  "effective_date": null,
  "status": null,
  "replaces": []
}}

Текст:
{text[:6000]}
"""

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
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

def enrich_with_llm(metadata: dict, text: str):
    missing = [
        key for key in [
            "title", "document_type", "document_number", "effective_date"
        ]
        if not metadata.get(key)
    ]

    if not missing and not metadata.get("replaces"):
        return metadata

    try:
        llm_result = llm_metadata(text)
    except Exception as exc:
        print(f"LLM fallback не сработал: {exc}")
        return metadata

    for key in missing:
        if not metadata.get(key) and llm_result.get(key):
            metadata[key] = llm_result[key]

    if not metadata.get("replaces") and llm_result.get("replaces"):
        metadata["replaces"] = llm_result["replaces"]

    return metadata

def run():
    META_DIR.mkdir(parents=True, exist_ok=True)

    for file in JSON_DIR.glob("*.json"):
        data = json.loads(file.read_text(encoding="utf-8"))
        text = data["markdown"]

        metadata = {
            "file_name": data["file_name"],
            "file_path": data["file_path"],
            "title": extract_title(text),
            "document_type": extract_document_type(text),
            "document_number": extract_number(text),
            "effective_date": extract_date(text),
            "status": extract_status(text),
            "replaces": extract_replaces(text),
            "extraction_source": "rules"
        }

        metadata = enrich_with_llm(metadata, text)

        out = META_DIR / file.name
        out.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        print(f"Готово: {data['file_name']}")

if __name__ == "__main__":
    run()