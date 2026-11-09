from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Document(db.Model):
    __tablename__ = "documents"

    id = db.Column(db.Integer, primary_key=True)
    file_name = db.Column(db.String(512), unique=True, nullable=False)
    file_path = db.Column(db.String(1024))
    file_hash = db.Column(db.String(128), index=True)

    code = db.Column(db.String(128), index=True)
    title = db.Column(db.String(1024))
    document_type = db.Column(db.String(128))
    status = db.Column(db.String(64), default="неизвестно")

    version = db.Column(db.String(64))
    effective_date = db.Column(db.Date)
    review_period_months = db.Column(db.Integer)
    next_review_date = db.Column(db.Date)

    owner = db.Column(db.String(256))
    approving_order = db.Column(db.String(512))
    approving_order_date = db.Column(db.Date)

    raw_text = db.Column(db.Text)
    markdown = db.Column(db.Text)
    summary = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class DocumentRelation(db.Model):
    __tablename__ = "document_relations"

    id = db.Column(db.Integer, primary_key=True)
    source_document_id = db.Column(db.Integer, db.ForeignKey("documents.id"))
    target_document_id = db.Column(db.Integer, db.ForeignKey("documents.id"))

    relation_type = db.Column(db.String(64))
    evidence = db.Column(db.Text)
    confidence = db.Column(db.Float, default=0.5)

class DocumentChunk(db.Model):
    __tablename__ = "document_chunks"

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"))
    chunk_id = db.Column(db.Integer)
    page_number = db.Column(db.Integer)
    section = db.Column(db.String(512))
    text = db.Column(db.Text)

class ChecklistItem(db.Model):
    __tablename__ = "checklist_items"

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"))

    criterion = db.Column(db.String(256))
    status = db.Column(db.String(32))
    score = db.Column(db.Float)
    evidence = db.Column(db.Text)
    recommendation = db.Column(db.Text)

class Finding(db.Model):
    __tablename__ = "findings"

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"))

    finding_type = db.Column(db.String(64))
    severity = db.Column(db.String(32))
    priority = db.Column(db.Integer)
    title = db.Column(db.String(512))
    description = db.Column(db.Text)
    evidence = db.Column(db.Text)
    recommendation = db.Column(db.Text)

class ProcessStep(db.Model):
    __tablename__ = "process_steps"

    id = db.Column(db.Integer, primary_key=True)
    process_name = db.Column(db.String(256), index=True)
    step_order = db.Column(db.Integer)
    name = db.Column(db.String(512))
    performer = db.Column(db.String(256))
    input_data = db.Column(db.Text)
    output_data = db.Column(db.Text)
    system = db.Column(db.String(256))
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"))

class RaciAssignment(db.Model):
    __tablename__ = "raci_assignments"

    id = db.Column(db.Integer, primary_key=True)
    process_name = db.Column(db.String(256), index=True)
    activity = db.Column(db.String(512))
    role = db.Column(db.String(256))
    raci = db.Column(db.String(16))

class CalendarActivity(db.Model):
    __tablename__ = "calendar_activities"

    id = db.Column(db.Integer, primary_key=True)
    process_name = db.Column(db.String(256), index=True)
    activity = db.Column(db.String(512))
    owner = db.Column(db.String(256))
    frequency = db.Column(db.String(64))
    next_due_date = db.Column(db.Date)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"))