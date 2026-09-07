# FastAPI CRUD + SQLite (учебный аудит)

Простой CRUD-пример из документации FastAPI на SQLite (встроенный `sqlite3`, без ORM).

## Запуск

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Документация: http://127.0.0.1:8000/docs

## Эндпоинты

| Метод | Путь            | Описание                |
|-------|-----------------|-------------------------|
| GET   | `/`             | Hello World             |
| GET   | `/health`       | Статус                  |
| POST  | `/items`        | Создать товар           |
| GET   | `/items`        | Список (limit/offset)   |
| GET   | `/items/{id}`   | Товар по id             |
| PUT   | `/items/{id}`   | Обновить товар          |
| DELETE| `/items/{id}`   | Удалить товар           |
| GET   | `/search?q=...` | Поиск по имени/описанию |

## Материалы для лекции SRE по безопасности

- [`lecture/PROMPTS.md`](lecture/PROMPTS.md) — 8 готовых промптов для ИИ (code review, эксплойты, фаззинг, CVE-объяснение)
- [`lecture/PAYLOADS.md`](lecture/PAYLOADS.md) — проверенные curl-эксплойты с пояснениями
- [`lecture/LECTURE_OUTLINE.md`](lecture/LECTURE_OUTLINE.md) — структура лекции «Как легко взломать приложение / найти дыры с помощью ИИ»
- [`lecture/demo_ai_fuzz.py`](lecture/demo_ai_fuzz.py) — живой фаззер (гоняет вредоносные значения, ловит 500-ки)
- [`screenshots/`](screenshots/) — скриншоты для слайдов: Swagger, SQL-инъекция, фаззер, 500