# AUDIT.md — Результаты сканирования уязвимостей

**Проект:** FastAPI CRUD + SQLite (учебный пример)
**Дата аудита:** 2026-09-07
**Инструменты:** Bandit 1.9.4 (статический анализ), pip-audit 2.10.1 (зависимости), safety, ruff, ручная проверка эксплойтов (curl)

---

## Сводка

| # | Уязвимость | CWE | Severity | Статус |
|---|-----------|-----|----------|--------|
| 1 | SQL-инъекция в `GET /search` | CWE-89 | 🔴 Critical | ✅ подтверждена эксплойтом |
| 2 | Отсутствие аутентификации/авторизации | CWE-306 | 🟠 High | подтверждено |
| 3 | Необработанные исключения → HTTP 500 (NaN, переполнение id) | CWE-248 | 🟠 High | ✅ подтверждено |
| 4 | Хранимый XSS (имя товара не экранируется) | CWE-79 | 🟡 Medium | ✅ подтверждено |
| 5 | Небезопасная CORS-конфигурация | CWE-942 | 🟡 Medium | подтверждено |
| 6 | Открытая документация API (/docs, /openapi.json) | CWE-200 | 🟡 Medium | подтверждено |
| 7 | Отсутствие защитных заголовков | CWE-693 | 🟡 Medium | подтверждено |
| 8 | Отсутствие rate limiting (DoS-вектор) | CWE-770 | 🟢 Low | подтверждено |
| 9 | Уязвимости системных пакетов (вне проекта) | — | 🟢 Low | вне scope приложения |

---

## 1. 🔴 SQL-инъекция в `/search` (CWE-89) — CRITICAL

**Где:** `app/database.py:97` — поиск по имени/описанию.

```python
# ВНИМАНИЕ: небезопасно! Запрос собран через f-string.
sql = f"SELECT * FROM items WHERE name LIKE '%{q}%' OR description LIKE '%{q}%'"
cur = conn.execute(sql)
```

**Обнаружено:** Bandit `B608 hardcoded_sql_expressions` (Medium/Low confidence по статике, но эксплойт подтверждён — фактическая критичность высокая).

### Воспроизведение (реальные атаки, проверено curl-ом)

**a) Обход фильтра — вернуть все записи:**
```bash
curl "http://127.0.0.1:8000/search?q=%27%20OR%20%271%27%3D%271"
# q = ' OR '1'='1  →  возвращает ВСЕ товары БД
```

**b) UNION-инъекция — чтение произвольных данных из БД:**
```bash
curl "http://127.0.0.1:8000/search?q=%27%20UNION%20SELECT%201,name,price,1,1%20FROM%20items%20--"
# q = ' UNION SELECT 1,name,price,1,1 FROM items --  →  SQLite выполняет вторую SELECT
```

**c) Эксфильтрация схемы БД (критично):**
```bash
curl "http://127.0.0.1:8000/search?q=%27%20UNION%20SELECT%20name,sql,1,1,1%20FROM%20sqlite_master%20--"
# → злоумышленник читает полную структуру БД (CREATE TABLE items ..., sqlite_sequence)
```

**d) Деструктивная операция:** `'; DELETE FROM items; --` — возвращает 500 (ограничение sqlite3 API на multi-statements), но точка входа для модификации/удаления данных открыта.

### Исправление (обязательно)
**Параметризованный запрос — никогда не конкатенировать пользовательский ввод в SQL:**
```python
def search_items(q: str):
    like = f"%{q}%"
    with get_db() as conn:
        cur = conn.execute(
            "SELECT * FROM items WHERE name LIKE ? OR description LIKE ?",
            (like, like),
        )
        return [row_to_dict(r) for r in cur.fetchall()]
```

---

## 2. 🟠 Отсутствие аутентификации и авторизации (CWE-306)

**Где:** весь `app/main.py` — все эндпоинты (`POST/PUT/DELETE /items`) публично доступны.

- Любой может создать/изменить/удалить записи и читать каталог без токена.
- Нет проверки прав, нет rate limiting на изменение данных.

**Исправление:** добавить слой аутентификации (OAuth2 / JWT / API-key middleware), роли и проверку владельца ресурса.

---

## 3. 🟠 Необработанные исключения → HTTP 500 (CWE-248) — HIGH

**Где:** роуты `/items/{id}` и `POST /items`. Необработанные исключения отдают 500.

### Воспроизведение (проверено curl-ом)

**a) Переполнение id → HTTP 500 вместо 404/422:**
```bash
curl "http://127.0.0.1:8000/items/99999999999999999999999999"
# → Internal Server Error (500), в логе: ValueError: Out of range float values are not JSON compliant
```
**b) NaN-цена → HTTP 500 при записи:**
```bash
curl -X POST http://127.0.0.1:8000/items -H "Content-Type: application/json" \
  -d '{"name":"NaNTest","price":NaN}'
# → Internal Server Error (500), ValueError: Out of range float values are not JSON compliant: nan
```
- NaN не записался в БД (проверено: в таблице нет записи NaNTest), но сервер вместо валидации отдаёт 500.
- Веер 500-ответов даёт злоумышленнику сигналы о внутреннем устройстве и создаёт шум в логах (информационная утечка + вектор DoS через нагрузку на обработку исключений).

**Исправление:** глобальный exception-handler, явная валидация (`allow_inf_nan=False` в Pydantic), конвертация переполнения в 422/404:
```python
class Item(BaseModel):
    price: float = Field(..., gt=0, allow_inf_nan=False)

@app.exception_handler(Exception)
async def unhandled(request, exc):
    return JSONResponse(status_code=500, content={"detail": "Internal error"})
```

---

## 4. 🟡 Хранимый XSS — имя товара не экранируется (CWE-79) — MEDIUM

**Где:** `POST /items` и `PUT /items/{id}` — поле `name` принимается без санитизации и возвращается в JSON.

### Воспроизведение
```bash
curl -X POST http://127.0.0.1:8000/items -H "Content-Type: application/json" \
  -d '{"name":"<script>alert(1)</script>","price":1.0}'
# → 201, имя сохранено как есть, отдаётся в ответах /items и /search
```
- Если фронтенд рендерит `name` как HTML (не экранируя), выполняется произвольный JS — классический stored XSS.
- API сам по себе JSON не исполняет, но **не проводит санитизацию** и никак не помечает опасные значения.

**Исправление:** санитизация на входе (черный/белый список символов), экранирование на фронтенде; при необходимости — библиотека типа `bleach`.

---

## 5. 🟡 Небезопасная CORS-конфигурация (CWE-942)

**Где:** `app/main.py:26-31`

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # любые источники
    allow_credentials=True,   # + разрешены credentials — противоречие
    ...
)
```

- Комбинация `allow_origins=["*"]` + `allow_credentials=True` — анти-паттерн: браузеры её блокируют, но конфигурация небезопасна и ломает семантику CORS.
- При публичном API любой сайт сможет делать запросы от имени пользователя в браузере.

**Исправление:** задать явный список доверенных origins либо убрать `allow_credentials`:
```python
allow_origins=["https://example.com"],
allow_credentials=True,
```

---

## 6. 🟡 Открытая документация API (CWE-200 — раскрытие информации)

**Где:** FastAPI по умолчанию включает `/docs`, `/redoc`, `/openapi.json`.

- Злоумышленник получает полную карту эндпоинтов и схем.
- В демо-примере допустимо, в проде — раскрытие поверхности атаки.

**Исправление:** в проде отключать:
```python
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
```

---

## 7. 🟡 Отсутствие защитных заголовков (CWE-693) — MEDIUM

**Где:** все ответы. Проверено: `curl -D -` отдаёт только `server: uvicorn`, без security-заголовков.

Отсутствуют: `X-Content-Type-Options`, `X-Frame-Options`, `Content-Security-Policy`, `Strict-Transport-Security`, `Referrer-Policy`, `Permissions-Policy`.

**Исправление:** middleware, добавляющий заголовки:
```python
@app.middleware("http")
async def security_headers(request, call_next):
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Content-Security-Policy"] = "default-src 'none'"
    resp.headers["Referrer-Policy"] = "no-referrer"
    return resp
```

---

## 8. 🟢 Отсутствие rate limiting (CWE-770)

**Где:** все эндпоинты без ограничения частоты запросов.

- Публичные эндпоинты доступны для спама/DoS.
- `GET /search` с тяжёлой LIKE-инъекцией — вектор исчерпания ресурсов.
- Тест: большая `q` (5000 символов) обрабатывается без ограничений (HTTP 200 за 4мс на малой БД).

**Исправление:** middleware rate limiting (slowapi / limits), тайм-ауты, пагинация с жёстким лимитом.

---

## 9. 🟢 Уязвимости системного окружения (вне проекта)

**Инструмент:** `pip-audit` (по всему окружению хоста).

| Пакет | Версия | Уязвимость | Fix |
|-------|--------|-----------|-----|
| setuptools | 68.1.2 | PYSEC-2025-49, PYSEC-2026-1918, PYSEC-2026-3447 | 83.0.0 |
| urllib3 | 2.0.7 | PYSEC-2026-141, 1994–1999 | 2.6.3+ |
| twisted | 24.3.0 | PYSEC-2024-75, PYSEC-2026-160, 1992 | 26.4.0 |

**Важно:** эти пакеты — системные (Ubuntu/Debian), **не являются зависимостями приложения**. Зависимости проекта (fastapi 0.141.1, uvicorn 0.52.4, starlette 1.6.0, pydantic 2.13.5, anyio, h11) — **уязвимостей не содержат** (проверено pip-audit и safety).

---

## Примечания по инструментам

- **Bandit:** 1 находка по коду — `B608` (SQL-инъекция). Остальные уязвимости найдены ручным пентестом.
- **ruff:** только стилевые замечания (`Optional[X]` → `X | None`), не security.
- **safety:** устаревшая команда `check`; перешли на `scan`. Зависимостей проекта в базах уязвимостей не найдено.
- **Ручные тесты грансей:**
  - `q=` (пустой) → 422 ✅
  - `limit=1000000` → 422 ✅ (схема ограничивает до 100)
  - `offset=-1` → 422 ✅
  - `item_id=abc` → 422 ✅
  - `item_id=-5` → 404 ✅
  - `price=-5` → 422 ✅
  - `name` из 1000 символов → 422 ✅ (max_length=120)
  - `TRACE/OPTIONS/HEAD /items` → 405 (безопасно)
  - невалидный JSON → 422 ✅

---

## Заключение

Приложение содержит **1 критическую уязвимость (SQL-инъекция, подтверждена эксплойтом)**, 2 высокие (нет аутентификации, 500-ки) и 4 средние. Уязвимости зависимостей проекта — **отсутствуют**.

Критический фикс — параметризованный SQL в `search_items()` (п. 1). Остальные рекомендации зависят от цели приложения: демо-пример из документации — норм, публичный продакшен — обязательно исправить пп. 1–8.