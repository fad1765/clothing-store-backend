from fastapi import APIRouter, HTTPException
from database import get_connection

router = APIRouter(prefix="/admin/coupons", tags=["admin-coupons"])


# 取得所有優惠券（後台用）
@router.get("")
def get_all_coupons():
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT
                id,
                code,
                name,
                discount_type,
                discount_value,
                min_spend,
                applicable_category::text,
                min_category_qty,
                usage_limit,
                used_count,
                is_active,
                created_at
            FROM coupons
            ORDER BY created_at DESC
        """)

        rows = cursor.fetchall()

        return [
            {
                "id": row[0],
                "code": row[1],
                "name": row[2],
                "discount_type": row[3],
                "discount_value": float(row[4]),
                "min_spend": float(row[5] or 0),
                "applicable_category": row[6],
                "min_category_qty": row[7],
                "usage_limit": row[8],
                "used_count": row[9],
                "is_active": row[10],
                "created_at": str(row[11]),
            }
            for row in rows
        ]

    finally:
        cursor.close()
        conn.close()


# 新增優惠券
@router.post("")
def create_coupon(data: dict):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO coupons
            (code, name, discount_type, discount_value, min_spend,
             applicable_category, min_category_qty, usage_limit, is_active)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, (
            data.get("code"),
            data.get("name"),
            data.get("discount_type"),
            data.get("discount_value"),
            data.get("min_spend", 0),
            data.get("applicable_category"),
            data.get("min_category_qty", 0),
            data.get("usage_limit"),
            data.get("is_active", True),
        ))

        new_id = cursor.fetchone()[0]
        conn.commit()

        return {"message": "新增成功", "id": new_id}

    finally:
        cursor.close()
        conn.close()


# 修改優惠券
@router.put("/{coupon_id}")
def update_coupon(coupon_id: int, data: dict):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE coupons
            SET
                code = %s,
                name = %s,
                discount_type = %s,
                discount_value = %s,
                min_spend = %s,
                applicable_category = %s,
                min_category_qty = %s,
                usage_limit = %s,
                is_active = %s
            WHERE id = %s
        """, (
            data.get("code"),
            data.get("name"),
            data.get("discount_type"),
            data.get("discount_value"),
            data.get("min_spend", 0),
            data.get("applicable_category"),
            data.get("min_category_qty", 0),
            data.get("usage_limit"),
            data.get("is_active", True),
            coupon_id,
        ))

        conn.commit()
        return {"message": "更新成功"}

    finally:
        cursor.close()
        conn.close()


# 啟用 / 停用
@router.patch("/{coupon_id}/toggle")
def toggle_coupon(coupon_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE coupons
            SET is_active = NOT is_active
            WHERE id = %s
            RETURNING is_active
        """, (coupon_id,))

        result = cursor.fetchone()
        conn.commit()

        return {"is_active": result[0]}

    finally:
        cursor.close()
        conn.close()


# 刪除
@router.delete("/{coupon_id}")
def delete_coupon(coupon_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("DELETE FROM coupons WHERE id = %s", (coupon_id,))
        conn.commit()
        return {"message": "刪除成功"}

    finally:
        cursor.close()
        conn.close()