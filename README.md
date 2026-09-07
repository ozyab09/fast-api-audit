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