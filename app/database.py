"""Работа с SQLite: схема, CRUD, поиск (ИСПРАВЛЕННАЯ — ветка fix/sql-injection).

Параметризованные запросы — SQL-инъекция закрыта (CWE-89).
"""
import sqlite3
from typing import Optional

DB_PATH = "items.db"


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS items (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                description TEXT,
                price       REAL NOT NULL,
                is_offer    INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        cur = conn.execute("SELECT COUNT(*) AS c FROM items")
        if cur.fetchone()["c"] == 0:
            conn.execute(
                "INSERT INTO items (name, description, price, is_offer) VALUES (?,?,?,?)",
                ("Laptop", "Fast and shiny", 999.99, 0),
            )
            conn.execute(
                "INSERT INTO items (name, description, price, is_offer) VALUES (?,?,?,?)",
                ("Headphones", "Wireless, noise cancelling", 199.0, 1),
            )


def row_to_dict(row: sqlite3.Row):
    if row is None:
        return None
    d = dict(row)
    d["is_offer"] = bool(d["is_offer"])
    return d


def list_items(limit: int, offset: int):
    with get_db() as conn:
        cur = conn.execute(
            "SELECT * FROM items ORDER BY id LIMIT ? OFFSET ?", (limit, offset)
        )
        return [row_to_dict(r) for r in cur.fetchall()]


def get_item(item_id: int):
    with get_db() as conn:
        cur = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,))
        return row_to_dict(cur.fetchone())


def create_item(name: str, description: Optional[str], price: float, is_offer: bool):
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO items (name, description, price, is_offer) VALUES (?,?,?,?)",
            (name, description, price, int(is_offer)),
        )
        return cur.lastrowid


def update_item(item_id: int, name: str, description: Optional[str], price: float, is_offer: bool):
    with get_db() as conn:
        cur = conn.execute(
            "UPDATE items SET name=?, description=?, price=?, is_offer=? WHERE id=?",
            (name, description, price, int(is_offer), item_id),
        )
        if cur.rowcount == 0:
            return None
    return get_item(item_id)


def delete_item(item_id: int) -> bool:
    with get_db() as conn:
        cur = conn.execute("DELETE FROM items WHERE id=?", (item_id,))
        return cur.rowcount > 0


# ---------- Поиск (ИСПРАВЛЕНО: параметризованный запрос) ----------
def search_items(q: str):
    """Поиск по имени/описанию.

    FIX (CWE-89): параметризованный запрос — SQL не зависит от пользовательского ввода.
    """
    like = f"%{q}%"
    with get_db() as conn:
        cur = conn.execute(
            "SELECT * FROM items WHERE name LIKE ? OR description LIKE ?",
            (like, like),
        )
        return [row_to_dict(r) for r in cur.fetchall()]
