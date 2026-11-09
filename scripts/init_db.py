from app.web.app import create_app
from app.db.models import db


def reset_database():
    app = create_app()

    with app.app_context():
        db.drop_all()
        db.create_all()

    print("База данных очищена и пересоздана")


if __name__ == "__main__":
    reset_database()