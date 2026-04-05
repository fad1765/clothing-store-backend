from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from decimal import Decimal
from typing import List, Optional
from database import get_connection

router = APIRouter(tags=["訂單"])


class OrderItem(BaseModel):
    product_id: Optional[int] = None
    name: str
    price: Decimal
    quantity: int
    size: str
    image: Optional[str] = None


class OrderCreate(BaseModel):
    user_id: Optional[int] = None
    name: str
    phone: str
    email: str
    delivery: str
    city: Optional[str] = None
    district: Optional[str] = None
    address: Optional[str] = None
    payment: str
    total_price: Decimal
    items: List[OrderItem]


class OrderStatusUpdate(BaseModel):
    status: str


def build_full_address(city, district, address):
    return f"{city or ''}{district or ''}{address or ''}"


@router.post("/orders", status_code=201)
def create_order(order: OrderCreate):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        if not order.items or len(order.items) == 0:
            raise HTTPException(status_code=400, detail="訂單商品不可為空")

        # 1. 先檢查每個商品庫存是否足夠
        for item in order.items:
            if not item.product_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"商品「{item.name}」缺少 product_id，無法建立訂單"
                )

            cursor.execute("""
                SELECT stock, name
                FROM products
                WHERE id = %s
                  AND is_active = TRUE
                FOR UPDATE
            """, (item.product_id,))
            product_row = cursor.fetchone()

            if not product_row:
                raise HTTPException(
                    status_code=404,
                    detail=f"找不到商品「{item.name}」"
                )

            current_stock = product_row[0]
            product_name = product_row[1]

            if current_stock is None:
                current_stock = 0

            if current_stock < item.quantity:
                raise HTTPException(
                    status_code=400,
                    detail=f"商品「{product_name}」庫存不足，目前剩餘 {current_stock} 件"
                )

        # 2. 建立訂單主資料
        cursor.execute("""
            INSERT INTO orders (
                user_id, name, phone, email, delivery, city, district, address, payment, total_price
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            order.user_id,
            order.name,
            order.phone,
            order.email,
            order.delivery,
            order.city,
            order.district,
            order.address,
            order.payment,
            order.total_price
        ))
        order_id = cursor.fetchone()[0]

        # 3. 新增訂單明細 + 扣庫存
        for item in order.items:
            item_image = item.image

            # 前端沒傳 image，就從 product_images 抓主圖
            if not item_image and item.product_id:
                cursor.execute("""
                    SELECT image_url
                    FROM product_images
                    WHERE product_id = %s
                    ORDER BY sort_order ASC, id ASC
                    LIMIT 1
                """, (item.product_id,))
                image_row = cursor.fetchone()
                if image_row:
                    item_image = image_row[0]

            cursor.execute("""
                INSERT INTO order_items (
                    order_id, product_id, name, price, quantity, size, image
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                order_id,
                item.product_id,
                item.name,
                item.price,
                item.quantity,
                item.size,
                item_image
            ))

            # 扣庫存
            cursor.execute("""
                UPDATE products
                SET stock = stock - %s
                WHERE id = %s
            """, (item.quantity, item.product_id))

        # 4. 如果有登入，清空資料庫購物車
        if order.user_id:
            cursor.execute("""
                DELETE FROM cart_items
                WHERE user_id = %s
            """, (order.user_id,))

        conn.commit()
        return {
            "message": "訂單建立成功",
            "order_id": order_id
        }

    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"訂單建立失敗: {str(e)}")

    finally:
        cursor.close()
        conn.close()


@router.get("/orders/user/{user_id}")
def get_user_orders(user_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT
                id,
                total_price,
                status,
                delivery,
                payment,
                created_at,
                completed_at
            FROM orders
            WHERE user_id = %s
            ORDER BY id DESC
        """, (user_id,))
        rows = cursor.fetchall()

        return [
            {
                "id": row[0],
                "total_price": float(row[1]),
                "status": row[2],
                "delivery": row[3],
                "payment": row[4],
                "created_at": row[5],
                "completed_at": row[6],
            }
            for row in rows
        ]

    finally:
        cursor.close()
        conn.close()


@router.get("/orders")
def get_all_orders():
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT
                o.id,
                o.user_id,
                o.name,
                o.phone,
                o.email,
                o.delivery,
                o.city,
                o.district,
                o.address,
                o.payment,
                o.total_price,
                o.status,
                o.created_at,
                o.completed_at
            FROM orders o
            ORDER BY o.id DESC
        """)
        order_rows = cursor.fetchall()

        results = []

        for row in order_rows:
            order_id = row[0]

            cursor.execute("""
                SELECT
                    oi.id,
                    oi.product_id,
                    oi.name,
                    oi.price,
                    oi.quantity,
                    oi.size,
                    COALESCE(
                        oi.image,
                        (
                            SELECT pi.image_url
                            FROM product_images pi
                            WHERE pi.product_id = oi.product_id
                            ORDER BY pi.sort_order ASC, pi.id ASC
                            LIMIT 1
                        )
                    ) AS image
                FROM order_items oi
                WHERE oi.order_id = %s
                ORDER BY oi.id ASC
            """, (order_id,))
            item_rows = cursor.fetchall()

            items = [
                {
                    "id": item[0],
                    "product_id": item[1],
                    "name": item[2],
                    "price": float(item[3]),
                    "quantity": item[4],
                    "size": item[5],
                    "image": item[6],
                }
                for item in item_rows
            ]

            results.append({
                "id": row[0],
                "user_id": row[1],
                "customerName": row[2],
                "phone": row[3],
                "customerEmail": row[4],
                "delivery": row[5],
                "city": row[6],
                "district": row[7],
                "address": row[8],
                "fullAddress": build_full_address(row[6], row[7], row[8]),
                "paymentMethod": row[9],
                "totalPrice": float(row[10]),
                "status": row[11],
                "createdAt": row[12],
                "completedAt": row[13],
                "items": items,
            })

        return results

    finally:
        cursor.close()
        conn.close()


@router.get("/orders/detail/{order_id}")
def get_order_detail(order_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT
                id,
                user_id,
                name,
                phone,
                email,
                delivery,
                city,
                district,
                address,
                payment,
                total_price,
                status,
                created_at,
                completed_at
            FROM orders
            WHERE id = %s
        """, (order_id,))
        row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="找不到訂單")

        cursor.execute("""
            SELECT
                oi.id,
                oi.product_id,
                oi.name,
                oi.price,
                oi.quantity,
                oi.size,
                COALESCE(
                    oi.image,
                    (
                        SELECT pi.image_url
                        FROM product_images pi
                        WHERE pi.product_id = oi.product_id
                        ORDER BY pi.sort_order ASC, pi.id ASC
                        LIMIT 1
                    )
                ) AS image
            FROM order_items oi
            WHERE oi.order_id = %s
            ORDER BY oi.id ASC
        """, (order_id,))
        item_rows = cursor.fetchall()

        items = [
            {
                "id": item[0],
                "product_id": item[1],
                "name": item[2],
                "price": float(item[3]),
                "quantity": item[4],
                "size": item[5],
                "image": item[6],
            }
            for item in item_rows
        ]

        return {
            "id": row[0],
            "user_id": row[1],
            "customerName": row[2],
            "phone": row[3],
            "customerEmail": row[4],
            "delivery": row[5],
            "city": row[6],
            "district": row[7],
            "address": row[8],
            "fullAddress": build_full_address(row[6], row[7], row[8]),
            "paymentMethod": row[9],
            "totalPrice": float(row[10]),
            "status": row[11],
            "createdAt": row[12],
            "completedAt": row[13],
            "items": items,
        }

    finally:
        cursor.close()
        conn.close()


@router.put("/orders/{order_id}/status")
def update_order_status(order_id: int, data: OrderStatusUpdate):
    allowed_status = ["pending", "shipped", "completed", "cancelled"]

    if data.status not in allowed_status:
        raise HTTPException(status_code=400, detail="無效的訂單狀態")

    conn = get_connection()
    cursor = conn.cursor()

    try:
        if data.status == "completed":
            cursor.execute("""
                UPDATE orders
                SET status = %s,
                    completed_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                RETURNING id
            """, (data.status, order_id))
        else:
            cursor.execute("""
                UPDATE orders
                SET status = %s,
                    completed_at = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                RETURNING id
            """, (data.status, order_id))

        updated = cursor.fetchone()

        if not updated:
            raise HTTPException(status_code=404, detail="找不到訂單")

        conn.commit()
        return {
            "message": "訂單狀態更新成功",
            "order_id": order_id,
            "status": data.status
        }

    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"更新失敗: {str(e)}")

    finally:
        cursor.close()
        conn.close()


@router.delete("/orders/cleanup/completed")
def cleanup_completed_orders():
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            DELETE FROM orders
            WHERE status = 'completed'
              AND completed_at IS NOT NULL
              AND completed_at < NOW() - INTERVAL '30 days'
            RETURNING id
        """)
        deleted_rows = cursor.fetchall()
        conn.commit()

        return {
            "message": "清除完成",
            "deleted_count": len(deleted_rows),
            "deleted_order_ids": [row[0] for row in deleted_rows]
        }

    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"清除失敗: {str(e)}")

    finally:
        cursor.close()
        conn.close()