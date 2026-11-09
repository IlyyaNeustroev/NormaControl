from flask import Flask, render_template, request, jsonify, send_file

from app.config.settings import settings
from app.db.models import db, Document, ChecklistItem, Finding, ProcessStep, RaciAssignment, CalendarActivity
from flask import jsonify, request


def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = settings.sqlalchemy_uri
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    with app.app_context():
        db.create_all()

    @app.route("/")
    def index():
        documents = Document.query.all()
        return render_template("index.html", documents=documents)

    @app.route("/document/<int:document_id>")
    def document_card(document_id):
        document = Document.query.get_or_404(document_id)
        checklist = ChecklistItem.query.filter_by(document_id=document_id).all()
        findings = Finding.query.filter_by(document_id=document_id).all()

        return render_template(
            "document.html",
            document=document,
            checklist=checklist,
            findings=findings
        )

    @app.route("/process")
    def process_page():
        steps = ProcessStep.query.order_by(ProcessStep.process_name, ProcessStep.step_order).all()
        raci = RaciAssignment.query.all()
        calendar = CalendarActivity.query.all()

        return render_template(
            "process.html",
            steps=steps,
            raci=raci,
            calendar=calendar
        )

    @app.route("/api/ask", methods=["POST"])
    def ask():
        from app.retrieval.rag_service import answer_question

        data = request.get_json()
        question = data.get("question", "")

        if not question:
            return jsonify({"error": "Вопрос не задан"}), 400

        result = answer_question(question)
        return jsonify(result)

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, port=5000)