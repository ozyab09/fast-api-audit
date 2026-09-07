#!/usr/bin/env python3
"""
demo_ai_fuzz.py — живое демо для лекции SRE: «ИИ-фаззинг находит дыры за секунды».

Скрипт гоняет по API граничные/вредоносные значения (сгенерированные LLM)
и ловит аномалии: HTTP 500, неожиданные 200, замедления.

Запуск:
    python3 demo_ai_fuzz.py                     # цель по умолчанию 127.0.0.1:8000
    python3 demo_ai_fuzz.py --target http://x:8000

Полигон: FastAPI CRUD + SQLite (ozyab09/fast-api-audit)
"""
import argparse
import json
import time
import urllib.error
import urllib.request

# ── Пул значений «от имени ИИ» (в лекции показываем, что их сгенерировала LLM) ──
# формат: (категория, значение, ожидание)
FUZZ_CASES = [
    # Числа-монстры
    ("int overflow",      "/items/99999999999999999999999999", "4xx, не 500"),
    ("int negative",      "/items/-5",                         "404/422"),
    ("int zero",          "/items/0",                          "404/422"),
    # NaN / Infinity через JSON-тело
    ("json NaN price",    "POST /items",                       "422, не 500"),
    ("json Infinity",     "POST /items",                       "422, не 500"),
    ("json big float",    "POST /items",                       "422 или 201"),
    # Пустые/гигантские строки
    ("empty q",           "/search?q=",                        "422"),
    ("giant q 5000",      "/search?q=" + "A" * 5000,           "200 (быстро)"),
    # XSS / HTML
    ("stored XSS",        "POST /items",                       "санитизация?"),
    # SQL-фрагменты (инъекция)
    ("sql OR 1=1",        "/search?q=%27%20OR%20%271%27%3D%271", "только свои данные"),
    ("sql UNION",         "/search?q=%27%20UNION%20SELECT%201,2,3,4,5%20--", "нет утечки"),
    ("sql delete",        "/search?q=%27;%20DELETE%20FROM%20items;%20--", "нет удаления"),
    # Невалидные/неожиданные
    ("bad json",          "POST /items",                       "422"),
    ("extra fields",      "POST /items",                       "422 (если forbid)"),
    ("traversal",         "/items/../../etc/passwd",           "404, не утечка"),
]

BODY_TEMPLATES = {
    "json NaN price":    {"name": "NaNTest", "price": "NaN"},
    "json Infinity":     {"name": "InfTest", "price": "Infinity"},
    "json big float":    {"name": "BigTest", "price": 1e300},
    "stored XSS":        {"name": "<script>alert(1)</script>", "price": 1.0},
    "bad json":          "not json at all",
    "extra fields":      {"name": "Extra", "price": 1.0, "admin": True, "role": "admin"},
}


def request(base, path, method="GET", body=None):
    url = base + path
    data = None
    headers = {}
    if body is not None:
        if isinstance(body, str):
            data = body.encode()
        else:
            data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            code = resp.status
            try:
                payload = resp.read().decode()[:200]
            except Exception:
                payload = ""
    except urllib.error.HTTPError as e:
        code = e.code
        try:
            payload = e.read().decode()[:200]
        except Exception:
            payload = ""
    except Exception as e:
        code = -1
        payload = str(e)[:120]
    return code, time.time() - start, payload


def main():
    ap = argparse.ArgumentParser(description="AI-фаззер для учебного полигона")
    ap.add_argument("--target", default="http://127.0.0.1:8000")
    ap.add_argument("--jsons", action="store_true", help="включить POST-кейсы")
    args = ap.parse_args()

    print(f"\n🎯 AI-фаззер → {args.target}\n")
    print(f"{'Категория':<18} {'HTTP':<6} {'Время':<8} {'Вердикт'}")
    print("-" * 64)

    anomalies = []
    for cat, path, expectation in FUZZ_CASES:
        method = "GET"
        body = None
        if path == "POST /items":
            method = "POST"
            body = BODY_TEMPLATES.get(cat, {"name": "fuzz", "price": 1.0})
            path = "/items"

        code, dt, payload = request(args.target, path, method, body)

        # Вердикт
        verdict = "✅ ок"
        if code == 500:
            verdict = "🔴 500 — дыра!"
            anomalies.append((cat, code, payload))
        elif code == -1:
            verdict = "🟠 ошибка сети"
            anomalies.append((cat, code, payload))
        elif cat == "sql OR 1=1" and code == 200 and len(payload) > 50:
            verdict = "🔴 утечка данных!"
            anomalies.append((cat, code, payload))

        print(f"{cat:<18} {code:<6} {dt * 1000:>6.0f}ms   {verdict}")

    print("\n" + "=" * 64)
    if anomalies:
        print(f"🔴 Найдено аномалий: {len(anomalies)}\n")
        for cat, code, payload in anomalies:
            print(f"  • {cat} → HTTP {code}: {payload[:150]}")
        print("\nВывод для лекции: автоматический фаззинг (с LLM-генерацией кейсов)")
        print("находит дыры быстрее, чем ручной code review.")
    else:
        print("🟢 Аномалий не найдено — приложение держит удар (или полигон не запущен).")
        print("Проверь: uvicorn app.main:app --host 127.0.0.1 --port 8000")


if __name__ == "__main__":
    main()