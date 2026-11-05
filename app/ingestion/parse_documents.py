from pathlib import Path
import json
import truststore
truststore.inject_into_ssl()

from docling.document_converter import DocumentConverter

RAW_DIR = Path("data/raw")
OUT_DIR = Path("data/processed/json")

converter = DocumentConverter()

def parse_all():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for file in RAW_DIR.glob("*"):
        if file.suffix.lower() not in {".pdf", ".jpg", ".jpeg", ".png"}:
            continue

        print(f"Обработка: {file.name}")

        result = converter.convert(str(file))
        doc = result.document

        output = {
            "file_name": file.name,
            "file_path": str(file),
            "markdown": doc.export_to_markdown(),
        }

        out_file = OUT_DIR / f"{file.stem}.json"
        out_file.write_text(
            json.dumps(output, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

if __name__ == "__main__":
    parse_all()