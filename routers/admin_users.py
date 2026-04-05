from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from database import get_connection

router = APIRouter(prefix="/admin/users", tags=["後台使用者管理"])


class UserUpdate(BaseModel):
    username: str
    email: str
    role: str


@router.get("")
def get_users():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            u.id,
            u.username,
            u.email,
            u.role,
            u.created_at,
            u.updated_at,
            COUNT(o.id) AS total_orders,
            COALESCE(SUM(o.total_price), 0) AS total_spent,
            MAX(o.created_at) AS last_order_at
        FROM users u
        LEFT JOIN orders o ON u.id = o.user_id
        GROUP BY u.id, u.username, u.email, u.role, u.created_at, u.updated_at
        ORDER BY u.id DESC
    """)
    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    users = []
    for row in rows:
        users.append({
            "id": row[0],
            "username": row[1],
            "email": row[2],
            "role": row[3],
            "created_at": row[4],
            "updated_at": row[5],
            "total_orders": row[6],
            "total_spent": float(row[7]) if row[7] is not None else 0,
            "last_order_at": row[8]
        })

    return users


@router.get("/{user_id}")
def get_user(user_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            u.id,
            u.username,
            u.email,
            u.role,
            u.created_at,
            u.updated_at,
            COUNT(o.id) AS total_orders,
            COALESCE(SUM(o.total_price), 0) AS total_spent,
            MAX(o.created_at) AS last_order_at
        FROM users u
        LEFT JOIN orders o ON u.id = o.user_id
        WHERE u.id = %s
        GROUP BY u.id, u.username, u.email, u.role, u.created_at, u.updated_at
    """, (user_id,))
    row = cursor.fetchone()

    cursor.close()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="找不到使用者")

    return {
        "id": row[0],
        "username": row[1],
        "email": row[2],
        "role": row[3],
        "created_at": row[4],
        "updated_at": row[5],
        "total_orders": row[6],
        "total_spent": float(row[7]) if row[7] is not None else 0,
        "last_order_at": row[8]
    }


@router.put("/{user_id}")
def update_user(user_id: int, user: UserUpdate):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM users WHERE id = %s", (user_id,))
    existing_user = cursor.fetchone()

    if not existing_user:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=404, detail="找不到使用者")

    cursor.execute("""
        SELECT id
        FROM users
        WHERE (email = %s OR username = %s) AND id != %s
    """, (user.email, user.username, user_id))
    duplicate = cursor.fetchone()

    if duplicate:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=400, detail="帳號或 email 已被使用")

    cursor.execute("""
        UPDATE users
        SET username = %s,
            email = %s,
            role = %s
        WHERE id = %s
    """, (user.username, user.email, user.role, user_id))

    conn.commit()
    cursor.close()
    conn.close()

    return {"message": "更新成功"}


@router.delete("/{user_id}")
def delete_user(user_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM users WHERE id = %s", (user_id,))
    existing_user = cursor.fetchone()

    if not existing_user:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=404, detail="找不到使用者")

    cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
    conn.commit()
    cursor.close()
    conn.close()

    return {"message": "刪除成功"}


@router.get("/{user_id}/orders")
def get_user_orders(user_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM users WHERE id = %s", (user_id,))
    existing_user = cursor.fetchone()

    if not existing_user:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=404, detail="找不到使用者")

    cursor.execute("""
        SELECT
            id,
            name,
            phone,
            email,
            delivery,
            payment,
            total_price,
            status,
            created_at
        FROM orders
        WHERE user_id = %s
        ORDER BY created_at DESC
    """, (user_id,))

    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    orders = []
    for row in rows:
        orders.append({
            "id": row[0],
            "name": row[1],
            "phone": row[2],
            "email": row[3],
            "delivery": row[4],
            "payment": row[5],
            "total_price": float(row[6]) if row[6] is not None else 0,
            "status": row[7],
            "created_at": row[8]
        })

    return orders