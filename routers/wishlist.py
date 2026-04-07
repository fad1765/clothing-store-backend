import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from database import get_connection

router = APIRouter(tags=["收藏商品"])

BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "").rstrip("/")


class WishlistCreate(BaseModel):
    user_id: int
    product_id: int


def build_image_url(image_path: str | None):
    if not image_path:
        return None

    if image_path.startswith("http://") or image_path.startswith("https://"):
        return image_path

    if image_path.startswith("/images"):
        return image_path

    clean_path = image_path.lstrip("/")

    if BACKEND_BASE_URL:
        return f"{BACKEND_BASE_URL}/{clean_path}"

    return f"/{clean_path}"


# 新增收藏
@router.post("/wishlist", status_code=201)
def add_to_wishlist(payload: WishlistCreate):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT id FROM users
            WHERE id = %s
        """, (payload.user_id,))
        user = cursor.fetchone()

        if not user:
            raise HTTPException(status_code=404, detail="使用者不存在")

        cursor.execute("""
            SELECT id FROM products
            WHERE id = %s AND is_active = TRUE
        """, (payload.product_id,))
        product = cursor.fetchone()

        if not product:
            raise HTTPException(status_code=404, detail="商品不存在")

        cursor.execute("""
            SELECT id FROM wishlist_items
            WHERE user_id = %s AND product_id = %s
        """, (payload.user_id, payload.product_id))
        existing = cursor.fetchone()

        if existing:
            raise HTTPException(status_code=400, detail="商品已在收藏清單中")

        cursor.execute("""
            INSERT INTO wishlist_items (user_id, product_id)
            VALUES (%s, %s)
            RETURNING id, created_at
        """, (payload.user_id, payload.product_id))

        new_item = cursor.fetchone()
        conn.commit()

        return {
            "message": "已加入收藏",
            "id": new_item[0],
            "user_id": payload.user_id,
            "product_id": payload.product_id,
            "created_at": new_item[1]
        }

    finally:
        cursor.close()
        conn.close()


# 取消收藏
@router.delete("/wishlist")
def remove_from_wishlist(user_id: int, product_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT id FROM wishlist_items
            WHERE user_id = %s AND product_id = %s
        """, (user_id, product_id))
        existing = cursor.fetchone()

        if not existing:
            raise HTTPException(status_code=404, detail="收藏資料不存在")

        cursor.execute("""
            DELETE FROM wishlist_items
            WHERE user_id = %s AND product_id = %s
        """, (user_id, product_id))

        conn.commit()

        return {
            "message": "已取消收藏",
            "user_id": user_id,
            "product_id": product_id
        }

    finally:
        cursor.close()
        conn.close()


# 檢查是否已收藏
@router.get("/wishlist/check")
def check_wishlist(user_id: int, product_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT EXISTS(
                SELECT 1
                FROM wishlist_items
                WHERE user_id = %s AND product_id = %s
            )
        """, (user_id, product_id))

        is_favorite = cursor.fetchone()[0]

        return {
            "is_favorite": is_favorite
        }

    finally:
        cursor.close()
        conn.close()


# 取得使用者收藏清單
@router.get("/wishlist/{user_id}")
def get_user_wishlist(user_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT id FROM users
            WHERE id = %s
        """, (user_id,))
        user = cursor.fetchone()

        if not user:
            raise HTTPException(status_code=404, detail="使用者不存在")

        cursor.execute("""
            SELECT
                p.id,
                p.name,
                p.price,
                p.category,
                p.description,
                p.rating,
                p.reviews,
                p.stock,
                p.is_hot,
                p.is_limited,
                pi.image_url,
                w.created_at
            FROM wishlist_items w
            JOIN products p
                ON w.product_id = p.id
            LEFT JOIN product_images pi
                ON p.id = pi.product_id
               AND pi.sort_order = 0
            WHERE w.user_id = %s
              AND p.is_active = TRUE
            ORDER BY w.created_at DESC
        """, (user_id,))

        rows = cursor.fetchall()

        return [
            {
                "id": row[0],
                "name": row[1],
                "price": float(row[2]),
                "category": row[3],
                "description": row[4],
                "rating": float(row[5] or 0),
                "reviews": row[6] or 0,
                "stock": row[7],
                "is_hot": row[8],
                "is_limited": row[9],
                "image": build_image_url(row[10]),
                "wishlisted_at": row[11]
            }
            for row in rows
        ]

    finally:
        cursor.close()
        conn.close()