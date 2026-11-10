запуск:
1. python -m app.ingestion.parse_documents  
2. python -m app.extraction.extract_metadata
3. python -m app.indexing.build_index 
3. python -m app.graph.build_graph      
4. python -m app.analysis.checklist 

#Команда:
Неустроев Илья (ИМО)
Роман Лещишин (ИМО)
Денис Савельвев (ИМО)
Максим Харлов (ИМО)
Мария Худякова (ПИИ)
Масликов Павел (ИМО)
Цуркан Владислав (ИМО)
Кочеткова Арина (ПИИ)


# NormaControl

NormaControl — локальная демонстрационная GraphRAG-система для анализа корпоративных документов предприятия.

Система позволяет:

- загружать PDF и JPG-документы;
- распознавать текст через OCR;
- извлекать метаданные документов;
- строить векторный индекс для семантического поиска;
- строить граф знаний между документами;
- выявлять версии, замены и связи между документами;
- анализировать документы по чек-листу;
- извлекать этапы процессов;
- отвечать на вопросы по документам с указанием источников.

Проект рассчитан на локальный запуск и не требует внешних LLM API.

## Архитектура

```text
PDF / JPG
    |
    v
Docling + OCR
    |
    v
Markdown / JSON
    |
    v
PostgreSQL
    |
    +--> Qdrant (векторный поиск)
    |
    +--> Kuzu (граф знаний)
    |
    +--> Ollama + Qwen (метаданные, анализ, ответы)
    |
    v
Streamlit / FastAPI UI
```

## Основные компоненты

- Python 3.13
- Flask + Flask-SQLAlchemy
- PostgreSQL
- Docling
- Tesseract OCR
- Sentence Transformers
- Qdrant Local
- Kuzu
- Ollama
- Qwen2.5-7B-Instruct
- Streamlit или FastAPI для UI

## Структура проекта

```text
NormaControl/
├── app/
│   ├── analysis/
│   │   ├── checklist.py
│   │   └── build_process.py
│   ├── config/
│   │   └── settings.py
│   ├── db/
│   │   └── models.py
│   ├── graph/
│   │   └── build_graph.py
│   ├── ingestion/
│   │   └── parse_documents.py
│   ├── indexing/
│   │   ├── build_index.py
│   │   └── test_search.py
│   ├── web/
│   │   └── app.py
│   └── utils/
├── data/
│   ├── raw/
│   ├── processed/
│   ├── chunks/
│   ├── qdrant_local/
│   ├── kuzu/
│   └── eval/
├── scripts/
├── tests/
├── .env
├── requirements.txt
└── README.md
```

## Установка

### 1. Клонировать проект

```powershell
git clone <repository_url>
cd NormaControl
```

### 2. Создать виртуальное окружение

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Установить зависимости

```powershell
pip install -r requirements.txt
```

### 4. Установить Tesseract

```powershell
winget install --id UB-Mannheim.TesseractOCR -e
```

После установки добавить в PATH:

```powershell
$p = "C:\Program Files\Tesseract-OCR"
[Environment]::SetEnvironmentVariable("Path", [Environment]::GetEnvironmentVariable("Path","User") + ";$p", "User")
```

Перезапустить PowerShell и проверить:

```powershell
tesseract --version
tesseract --list-langs
```

Для русского языка должен быть установлен `rus`:

```powershell
tesseract --list-langs
```

Если `rus` отсутствует, скачать:

```text
[https://github.com/tesseract-ocr/tessdata/raw/main/rus.traineddata](https://github.com/tesseract-ocr/tessdata/raw/main/rus.traineddata)
```

и положить файл в:

```text
C:\Program Files\Tesseract-OCR\tessdata\rus.traineddata
```

### 5. Установить Ollama и модель

```powershell
winget install Ollama.Ollama
ollama pull qwen2.5:7b-instruct
ollama list
```

## Конфигурация

Создайте `.env` в корне проекта.

Пример:

```env
FLASK_APP=app.web.app:create_app
FLASK_ENV=development

DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/doc_graphrag

OLLAMA_MODEL=qwen2.5:7b-instruct
OLLAMA_HOST=http://localhost:11434

EMBEDDING_MODEL=intfloat/multilingual-e5-base

QDRANT_COLLECTION=norma_control
QDRANT_LOCAL_PATH=data/qdrant_local

KUZU_DB_PATH=data/kuzu/norma_control.kuzu
```

## Подготовка базы данных

Создайте базу PostgreSQL:

```sql
CREATE DATABASE doc_graphrag;
```

Затем инициализируйте таблицы:

```powershell
python -m app.db.init_db
```

Если у вас нет отдельного `init_db.py`, можно использовать:

```powershell
python -c "from app.web.app import create_app; from app.db.models import db; app=create_app(); 
with app.app_context(): db.create_all()"
```

## Полный pipeline

### 1. Подготовка входных документов

Положите документы в:

```text
data/raw/
```

Поддерживаемые форматы:

- PDF
- JPG
- JPEG
- PNG

Пример:

```text
data/raw/
├── document_01.pdf
├── document_02.pdf
├── scan_01.jpg
└── scan_02.png
```

### 2. Ingestion

Команда:

```powershell
python -m app.ingestion.parse_documents
```

Что происходит:

- читаются файлы из `data/raw/`;
- PDF и изображения передаются в Docling;
- для сканов запускается OCR;
- текст конвертируется в Markdown;
- создаётся или обновляется запись `Document` в PostgreSQL;
- сохраняются `markdown` и `raw_text`.

Результат:

- записи в таблице `documents`;
- текст документа в PostgreSQL.

### 3. Извлечение метаданных

Команда:

```powershell
python -m app.extraction.extract_metadata
```

Что происходит:

- читается markdown из PostgreSQL;
- текст передаётся в Qwen через Ollama;
- извлекаются метаданные;
- заполняются поля документа;
- определяются связи между документами.

Извлекаемые поля:

- `code`
- `title`
- `document_type`
- `status`
- `version`
- `effective_date`
- `summary`
- `replaces_document`

Результат:

- заполненные метаданные в PostgreSQL;
- связи `REPLACES` между документами.

### 4. Векторное индексирование

Команда:

```powershell
python -m app.indexing.build_index
```

Что происходит:

- читаются документы из PostgreSQL;
- markdown разбивается на чанки;
- для каждого чанка создаётся embedding;
- векторы и payload сохраняются в Qdrant;
- чанки сохраняются в PostgreSQL.

Результат:

- папка `data/qdrant_local/`;
- коллекция Qdrant;
- записи в `document_chunks`.

### 5. Построение графа

Команда:

```powershell
python -m app.graph.build_graph
```

Что происходит:

- читаются документы из PostgreSQL;
- создаются узлы `Document` в Kuzu;
- создаются связи `REPLACES`;
- сохраняются метаданные документов в графе.

Результат:

- папка `data/kuzu/`;
- граф знаний между документами.

### 6. Анализ по чек-листу

Команда:

```powershell
python -m app.analysis.checklist
```

Что происходит:

- читается текст документа;
- формируется промпт для Qwen;
- модель оценивает документ по критериям;
- сохраняются `ChecklistItem`;
- сохраняются `Finding`.

Критерии:

- цель документа;
- роли и ответственность;
- входы процесса;
- выходы процесса;
- измеримые показатели;
- сроки выполнения;
- порядок эскалации;
- актуальность ссылок;
- корректность оформления.

Результат:

- записи в `checklist_items`;
- записи в `findings`.

### 7. Извлечение процессов

Команда:

```powershell
python -m app.analysis.build_process
```

Что происходит:

- читается текст документа;
- Qwen извлекает этапы процесса;
- создаётся JSON с этапами;
- создаётся граф процесса в Kuzu.

Результат:

- JSON в `data/processed/process/`;
- узлы `Process`;
- узлы `ProcessStep`;
- связи `HAS_STEP`;
- связи `NEXT_STEP`;
- связи `BASED_ON_DOCUMENT`.

### 8. Поиск и ответы

Поиск и ответы реализованы через Flask API.

Команда запуска веб-интерфейса:

```powershell
python -m app.web.app
```

API endpoint:

```text
POST /api/ask
```

Пример запроса:

```json
{
  "question": "Какая версия инструкции действует сейчас?"
}
```

Что происходит:

- пользователь вводит вопрос в UI;
- JavaScript отправляет POST /api/ask;
- Flask вызывает `answer_question()` из `app/retrieval/rag_service.py`;
- вопрос преобразуется в embedding;
- Qdrant возвращает релевантные чанки;
- Kuzu возвращает контекст связей документов;
- формируется промпт для Qwen;
- Qwen формирует ответ;
- Flask возвращает JSON;
- JavaScript выводит ответ в `<pre id="answer">`.

## Полный сценарий запуска

```powershell
python -m app.ingestion.parse_documents
python -m app.extraction.extract_metadata
python -m app.indexing.build_index
python -m app.graph.build_graph
python -m app.analysis.checklist
python -m app.analysis.build_process
python -m app.search.ask
```

## Сброс системы

Для теста на новом наборе документов:

```powershell
python -m scripts.reset_db
```

Затем удалить производственные артефакты:

```powershell
@(
    "data\processed",
    "data\chunks",
    "data\qdrant_local",
    "data\kuzu",
    "data\eval\results"
) | ForEach-Object {
    if (Test-Path $_) {
        Remove-Item -Recurse -Force $_
        Write-Host "Удалено: $_"
    }
}
```

Заменить документы в `data/raw/` и запустить pipeline заново.

## Проверка состояния

Создайте `scripts/check_status.py`:

```python
from app.web.app import create_app
from app.db.models import Document, DocumentChunk, ChecklistItem, Finding


def check_status():
    app = create_app()

    with app.app_context():
        print("Documents:", Document.query.count())
        print("DocumentChunks:", DocumentChunk.query.count())
        print("ChecklistItems:", ChecklistItem.query.count())
        print("Findings:", Finding.query.count())


if __name__ == "__main__":
    check_status()
```

Запуск:

```powershell
python -m scripts.check_status
```

## Известные ограничения MVP

- Качество OCR зависит от качества скана.
- Для сложных таблиц и формул возможны ошибки распознавания.
- Qwen 7B может ошибаться при длинных документах.
- GraphRAG пока работает на упрощённой модели графа.
- Нет полноценной оценки качества ответов.
- Нет авторизации и многопользовательского режима.
- Нет production-grade обработки ошибок и логирования.

## Дальнейшие шаги

- Реализовать полноценный `/api/ask`.
- Подключить Qdrant search к UI.
- Добавить цитирование источников.
- Добавить сравнение версий документов.
- Добавить оценку качества через golden dataset.
- Добавить Docker Compose.
- Добавить тесты.
- Добавить логирование и мониторинг.