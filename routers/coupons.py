from fastapi import APIRouter
from database import get_connection

router = APIRouter(prefix="/coupons", tags=["coupons"])


def calculate_subtotal(cart_items):
    return round(
        sum(float(item.get("price", 0)) * int(item.get("quantity", 0)) for item in cart_items),
        2
    )


def get_item_category(cursor, item):
    category = item.get("category")
    if category:
        return str(category).lower()

    product_id = item.get("product_id")
    if not product_id:
        return None

    cursor.execute("""
        SELECT category::text
        FROM products
        WHERE id = %s
        LIMIT 1
    """, (product_id,))
    row = cursor.fetchone()

    return row[0].lower() if row and row[0] else None


def get_matched_items(cursor, cart_items, applicable_category):
    if not applicable_category:
        return cart_items

    matched = []
    for item in cart_items:
        item_category = get_item_category(cursor, item)
        if item_category == applicable_category.lower():
            matched.append(item)

    return matched


def evaluate_coupon(cursor, coupon_row, cart_items, user_id=None, email=None):
    coupon_id = coupon_row[0]
    coupon_code = coupon_row[1]
    coupon_name = coupon_row[2]
    discount_type = coupon_row[3]
    discount_value = float(coupon_row[4])
    min_spend = float(coupon_row[5] or 0)
    applicable_category = coupon_row[6]
    min_category_qty = int(coupon_row[7] or 0)
    usage_limit = int(coupon_row[8] or 0)
    used_count = int(coupon_row[9] or 0)
    is_active = coupon_row[10]

    result = {
        "coupon_id": coupon_id,
        "coupon_code": coupon_code,
        "coupon_name": coupon_name,
        "discount_type": discount_type,
        "discount_value": discount_value,
        "min_spend": min_spend,
        "applicable_category": applicable_category,
        "min_category_qty": min_category_qty,
        "usage_limit": usage_limit,
        "used_count": used_count,
        "is_active": is_active,
        "usable": False,
        "reason": "",
        "discount_amount": 0,
        "final_price": 0,
        "matched_qty": 0,
        "matched_subtotal": 0,
    }

    if not is_active:
        result["reason"] = "此優惠券已停用"
        return result

    if usage_limit and used_count >= usage_limit:
        result["reason"] = "此優惠券已使用完畢"
        return result

    if user_id:
        cursor.execute("""
            SELECT 1
            FROM coupon_usages
            WHERE coupon_id = %s AND user_id = %s
            LIMIT 1
        """, (coupon_id, user_id))
        if cursor.fetchone():
            result["reason"] = "此優惠券你已使用過"
            return result
    elif email:
        cursor.execute("""
            SELECT 1
            FROM coupon_usages
            WHERE coupon_id = %s AND email = %s
            LIMIT 1
        """, (coupon_id, email))
        if cursor.fetchone():
            result["reason"] = "此優惠券你已使用過"
            return result

    subtotal_price = calculate_subtotal(cart_items)

    if subtotal_price < min_spend:
        result["reason"] = f"需滿 NT$ {int(min_spend)} 才可使用"
        return result

    matched_items = get_matched_items(cursor, cart_items, applicable_category)
    matched_qty = sum(int(item.get("quantity", 0)) for item in matched_items)
    matched_subtotal = round(
        sum(float(item.get("price", 0)) * int(item.get("quantity", 0)) for item in matched_items),
        2
    )

    result["matched_qty"] = matched_qty
    result["matched_subtotal"] = matched_subtotal

    if applicable_category and matched_subtotal <= 0:
        result["reason"] = "購物車中沒有符合分類的商品"
        return result

    if applicable_category and matched_qty < min_category_qty:
        result["reason"] = f"{applicable_category} 商品需至少 {min_category_qty} 件"
        return result

    if discount_type == "fixed":
        base_amount = matched_subtotal if applicable_category else subtotal_price
        discount_amount = min(discount_value, base_amount)
    elif discount_type == "percent":
        base_amount = matched_subtotal if applicable_category else subtotal_price
        discount_amount = round(base_amount * (discount_value / 100), 2)
    else:
        discount_amount = 0

    final_price = max(0, round(subtotal_price - discount_amount, 2))

    result["usable"] = True
    result["reason"] = "可使用"
    result["discount_amount"] = discount_amount
    result["final_price"] = final_price

    return result


@router.post("/list")
def list_coupons(data: dict):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cart_items = data.get("cart_items", [])
        user_id = data.get("user_id")
        email = data.get("email")

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
                is_active
            FROM coupons
            ORDER BY created_at DESC, id DESC
        """)
        rows = cursor.fetchall()

        return [
            evaluate_coupon(cursor, row, cart_items, user_id, email)
            for row in rows
        ]

    finally:
        cursor.close()
        conn.close()


@router.post("/available")
def get_available_coupons(data: dict):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cart_items = data.get("cart_items", [])
        user_id = data.get("user_id")
        email = data.get("email")

        if not cart_items:
            return []

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
                is_active
            FROM coupons
            ORDER BY created_at DESC, id DESC
        """)
        rows = cursor.fetchall()

        available = []
        for row in rows:
            result = evaluate_coupon(cursor, row, cart_items, user_id, email)
            if result["usable"]:
                available.append(result)

        return available

    finally:
        cursor.close()
        conn.close()


@router.post("/validate")
def validate_coupon(data: dict):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        code = (data.get("code") or "").strip()
        cart_items = data.get("cart_items", [])
        user_id = data.get("user_id")
        email = data.get("email")

        if not code:
            return {"valid": False, "message": "請輸入優惠碼"}

        if not cart_items:
            return {"valid": False, "message": "購物車是空的，無法使用優惠券"}

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
                is_active
            FROM coupons
            WHERE LOWER(code) = LOWER(%s)
            LIMIT 1
        """, (code,))
        coupon = cursor.fetchone()

        if not coupon:
            return {"valid": False, "message": "優惠碼不存在"}

        result = evaluate_coupon(cursor, coupon, cart_items, user_id, email)

        if not result["usable"]:
            return {"valid": False, "message": result["reason"]}

        return {
            "valid": True,
            "message": "優惠券套用成功",
            **result
        }

    finally:
        cursor.close()
        conn.close()

@router.get("/marquee")
def get_coupon_marquee():
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
                is_active
            FROM coupons
            WHERE is_active = TRUE
            ORDER BY created_at DESC, id DESC
        """)
        rows = cursor.fetchall()

        result = []
        for row in rows:
            coupon_id = row[0]
            coupon_code = row[1]
            coupon_name = row[2]
            discount_type = row[3]
            discount_value = float(row[4])
            min_spend = float(row[5] or 0)
            applicable_category = row[6]
            usage_limit = int(row[8] or 0)
            used_count = int(row[9] or 0)

            if usage_limit and used_count >= usage_limit:
                continue

            if discount_type == "fixed":
                discount_text = f"現折 NT$ {int(discount_value)}"
            elif discount_type == "percent":
                discount_text = f"享 {int(discount_value)}% 折扣"
            else:
                discount_text = "優惠活動"

            min_spend_text = (
                f"全館滿 NT$ {int(min_spend)}"
                if min_spend > 0
                else "不限金額"
            )

            category_text = (
                f"｜限 {applicable_category}"
                if applicable_category
                else "｜全館適用"
            )

            marquee_text = (
                f"優惠活動｜{coupon_name}｜{min_spend_text}{discount_text}"
                f"{category_text}｜優惠碼 {coupon_code}"
            )

            result.append({
                "coupon_id": coupon_id,
                "coupon_code": coupon_code,
                "coupon_name": coupon_name,
                "marquee_text": marquee_text,
            })

        return result

    finally:
        cursor.close()
        conn.close()