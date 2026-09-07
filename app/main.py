"""FastAPI CRUD Example — простой пример в стиле официальной документации.

SQLite через встроенный sqlite3 (без ORM) + Pydantic-схемы.
"""
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .database import (
    init_db,
    list_items,
    get_item,
    create_item,
    update_item,
    delete_item,
    search_items,
)

app = FastAPI(
    title="FastAPI CRUD Example",
    description="Простое CRUD-приложение из документации FastAPI (SQLite).",
    version="0.1.0",
)

# --- CORS: разрешаем всё (упрощение для демо) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()


# ---------- Схемы ----------
class Item(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: Optional[str] = None
    price: float = Field(..., gt=0)
    is_offer: bool = False


class ItemOut(Item):
    id: int

    class Config:
        from_attributes = True


# ---------- Роуты ----------
@app.get("/")
def read_root():
    """Корень API (пример из документации)."""
    return {"message": "Hello World"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/items", response_model=ItemOut, status_code=status.HTTP_201_CREATED)
def create_new_item(item: Item):
    """Создать товар."""
    item_id = create_item(item.name, item.description, item.price, item.is_offer)
    return get_item(item_id)


@app.get("/items", response_model=List[ItemOut])
def read_items(limit: int = Query(10, ge=1, le=100), offset: int = Query(0, ge=0)):
    """Список товаров с пагинацией."""
    return list_items(limit, offset)


@app.get("/items/{item_id}", response_model=ItemOut)
def read_item(item_id: int):
    """Получить товар по id."""
    row = get_item(item_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return row


@app.put("/items/{item_id}", response_model=ItemOut)
def update_existing_item(item_id: int, item: Item):
    """Обновить товар."""
    updated = update_item(item_id, item.name, item.description, item.price, item.is_offer)
    if updated is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return updated


@app.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_existing_item(item_id: int):
    """Удалить товар."""
    deleted = delete_item(item_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Item not found")


@app.get("/search")
def search(q: str = Query(..., min_length=1)):
    """Поиск товаров по имени или описанию."""
    return search_items(q)