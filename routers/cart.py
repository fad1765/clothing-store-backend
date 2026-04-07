import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from database import get_connection

router = APIRouter(tags=["購物車"])

BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "").rstrip("/")


class CartItemAdd(BaseModel):
    user_id: int
    product_id: int
    quantity: int
    size: str


class CartItemUpdate(BaseModel):
    quantity: int


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


# 取得使用者的購物車
@router.get("/cart/{user_id}")
def get_cart(user_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT
                ci.id,
                ci.product_id,
                p.name,
                p.price,
                p.category::text,
                (
                    SELECT pi.image_url
                    FROM product_images pi
                    WHERE pi.product_id = p.id
                    ORDER BY pi.sort_order ASC, pi.id ASC
                    LIMIT 1
                ) AS image_url,
                ci.quantity,
                ci.size
            FROM cart_items ci
            JOIN products p ON ci.product_id = p.id
            WHERE ci.user_id = %s
            ORDER BY ci.created_at DESC, ci.id DESC
        """, (user_id,))
        rows = cursor.fetchall()

        return [
            {
                "id": row[0],
                "product_id": row[1],
                "name": row[2],
                "price": float(row[3]),
                "category": row[4],
                "image": build_image_url(row[5]),
                "quantity": row[6],
                "size": row[7],
            }
            for row in rows
        ]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"取得購物車失敗: {str(e)}")

    finally:
        cursor.close()
        conn.close()


# 新增商品到購物車
@router.post("/cart", status_code=201)
def add_to_cart(item: CartItemAdd):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT id, quantity
            FROM cart_items
            WHERE user_id = %s AND product_id = %s AND size = %s
        """, (item.user_id, item.product_id, item.size))
        existing = cursor.fetchone()

        if existing:
            new_quantity = existing[1] + item.quantity
            cursor.execute("""
                UPDATE cart_items
                SET quantity = %s
                WHERE id = %s
            """, (new_quantity, existing[0]))
        else:
            cursor.execute("""
                INSERT INTO cart_items (user_id, product_id, quantity, size)
                VALUES (%s, %s, %s, %s)
            """, (item.user_id, item.product_id, item.quantity, item.size))

        conn.commit()
        return {"message": "已加入購物車"}

    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"加入購物車失敗: {str(e)}")

    finally:
        cursor.close()
        conn.close()


# 更新購物車數量
@router.put("/cart/{cart_item_id}")
def update_cart_item(cart_item_id: int, item: CartItemUpdate):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE cart_items
            SET quantity = %s
            WHERE id = %s
        """, (item.quantity, cart_item_id))

        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="購物車商品不存在")

        conn.commit()
        return {"message": "已更新數量"}

    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"更新購物車失敗: {str(e)}")

    finally:
        cursor.close()
        conn.close()


# 刪除購物車裡的商品
@router.delete("/cart/{cart_item_id}")
def remove_from_cart(cart_item_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("DELETE FROM cart_items WHERE id = %s", (cart_item_id,))

        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="購物車商品不存在")

        conn.commit()
        return {"message": "已從購物車移除"}

    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"刪除購物車商品失敗: {str(e)}")

    finally:
        cursor.close()
        conn.close()


# 清空購物車
@router.delete("/cart/clear/{user_id}")
def clear_cart(user_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("DELETE FROM cart_items WHERE user_id = %s", (user_id,))
        conn.commit()
        return {"message": "購物車已清空"}

    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"清空購物車失敗: {str(e)}")

    finally:
        cursor.close()
        conn.close()