import hashlib
import json
from pathlib import Path

from docling.document_converter import DocumentConverter

from app.db.models import db, Document
from app.config.settings import settings
from docling.datamodel.pipeline_options import OcrMode

RAW_DIR = Path("data/raw")

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions,
    TesseractCliOcrOptions,
)
from docling.document_converter import DocumentConverter, PdfFormatOption

pipeline_options = PdfPipelineOptions()
pipeline_options.do_ocr = True
pipeline_options.ocr_options = TesseractCliOcrOptions(
    lang=["rus", "eng"],
    mode=OcrMode.FULL_PAGE
)

converter = DocumentConverter(
    format_options={
        InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
    }
)

def file_hash(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()

def ingest_documents(app):
    with app.app_context():
        for file in RAW_DIR.glob("*"):
            if file.suffix.lower() not in {".pdf", ".jpg", ".jpeg", ".png"}:
                continue

            print(f"Обработка: {file.name}")

            result = converter.convert(str(file))
            markdown = result.document.export_to_markdown()

            existing = Document.query.filter_by(file_name=file.name).first()

            if existing:
                document = existing
            else:
                document = Document(file_name=file.name)
                db.session.add(document)

            document.file_path = str(file)
            document.file_hash = file_hash(file)
            document.markdown = markdown
            document.raw_text = markdown

            db.session.commit()
            print(f"Сохранено: {document.file_name}")

if __name__ == "__main__":
    from app.web.app import create_app
    app = create_app()
    ingest_documents(app)