"""Работа с SQLite: схема, CRUD, поиск."""
import sqlite3
from typing import Optional

DB_PATH = "items.db"


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Создаёт таблицу items при первом запуске."""
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
        # Семплируем пару строк для демо
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


# ---------- CRUD (параметризованные запросы) ----------
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


# ---------- Поиск ----------
def search_items(q: str):
    """Поиск по имени/описанию.

    ВНИМАНИЕ: запрос собран через f-string — см. AUDIT.md.
    """
    conn = get_db()
    sql = f"SELECT * FROM items WHERE name LIKE '%{q}%' OR description LIKE '%{q}%'"
    cur = conn.execute(sql)
    rows = [row_to_dict(r) for r in cur.fetchall()]
    conn.close()
    return rows