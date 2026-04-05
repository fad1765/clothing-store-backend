from fastapi import APIRouter
from database import get_connection

router = APIRouter(prefix="/admin", tags=["後台總覽"])


@router.get("/dashboard")
def get_dashboard():
    conn = get_connection()
    cursor = conn.cursor()

    # 商品總數
    cursor.execute("""
        SELECT COUNT(*)
        FROM products
        WHERE is_active = TRUE
    """)
    total_products = cursor.fetchone()[0]

    # 會員總數
    cursor.execute("""
        SELECT COUNT(*)
        FROM users
    """)
    total_users = cursor.fetchone()[0]

    # 訂單總數
    cursor.execute("""
        SELECT COUNT(*)
        FROM orders
    """)
    total_orders = cursor.fetchone()[0]

    # 待處理訂單
    cursor.execute("""
        SELECT COUNT(*)
        FROM orders
        WHERE status = 'pending'
    """)
    pending_orders = cursor.fetchone()[0]

    # 累積營業額
    cursor.execute("""
        SELECT COALESCE(SUM(total_price), 0)
        FROM orders
        WHERE status IN ('pending', 'shipped', 'completed')
    """)
    total_revenue = cursor.fetchone()[0]

    # 低庫存商品數
    cursor.execute("""
        SELECT COUNT(*)
        FROM products
        WHERE stock <= 5 AND is_active = TRUE
    """)
    low_stock_count = cursor.fetchone()[0]

    # 今日訂單數
    cursor.execute("""
        SELECT COUNT(*)
        FROM orders
        WHERE DATE(created_at) = CURRENT_DATE
    """)
    today_orders = cursor.fetchone()[0]

    # 今日營收
    cursor.execute("""
        SELECT COALESCE(SUM(total_price), 0)
        FROM orders
        WHERE DATE(created_at) = CURRENT_DATE
          AND status IN ('pending', 'shipped', 'completed')
    """)
    today_revenue = cursor.fetchone()[0]

    # 最近 5 筆訂單
    cursor.execute("""
        SELECT
            id,
            name,
            total_price,
            status,
            created_at
        FROM orders
        ORDER BY created_at DESC
        LIMIT 5
    """)
    recent_order_rows = cursor.fetchall()

    recent_orders = []
    for row in recent_order_rows:
        recent_orders.append({
            "id": row[0],
            "name": row[1],
            "total_price": float(row[2]) if row[2] is not None else 0,
            "status": row[3],
            "created_at": row[4],
        })

    # 低庫存商品前 5 筆
    cursor.execute("""
        SELECT
            id,
            name,
            category,
            stock,
            price
        FROM products
        WHERE stock <= 5 AND is_active = TRUE
        ORDER BY stock ASC, id ASC
        LIMIT 5
    """)
    low_stock_rows = cursor.fetchall()

    low_stock_products = []
    for row in low_stock_rows:
        low_stock_products.append({
            "id": row[0],
            "name": row[1],
            "category": row[2],
            "stock": row[3],
            "price": float(row[4]) if row[4] is not None else 0,
        })

    # 近 7 日訂單趨勢
    cursor.execute("""
        SELECT
            TO_CHAR(day_series.day, 'MM/DD') AS label,
            COALESCE(COUNT(o.id), 0) AS orders
        FROM (
            SELECT generate_series(
                CURRENT_DATE - INTERVAL '6 days',
                CURRENT_DATE,
                INTERVAL '1 day'
            )::date AS day
        ) AS day_series
        LEFT JOIN orders o
            ON DATE(o.created_at) = day_series.day
        GROUP BY day_series.day
        ORDER BY day_series.day
    """)
    trend_rows = cursor.fetchall()

    order_trend = []
    for row in trend_rows:
        order_trend.append({
            "label": row[0],
            "orders": row[1],
        })

    cursor.close()
    conn.close()

    return {
        "summary": {
            "total_products": total_products,
            "total_users": total_users,
            "total_orders": total_orders,
            "pending_orders": pending_orders,
            "total_revenue": float(total_revenue) if total_revenue is not None else 0,
            "low_stock_count": low_stock_count,
            "today_orders": today_orders,
            "today_revenue": float(today_revenue) if today_revenue is not None else 0,
        },
        "recent_orders": recent_orders,
        "low_stock_products": low_stock_products,
        "order_trend": order_trend,
    }