from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from database import get_connection

router = APIRouter(tags=["商品留言"])

class CommentCreate(BaseModel):
    user_id: int
    content: str
    rating: int = Field(..., ge=1, le=5)

class CommentLike(BaseModel):
    user_id: int


# 取得某商品所有留言（支援排序）
@router.get("/products/{product_id}/comments")
def get_product_comments(product_id: int, sort: str = Query("latest")):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id FROM products
        WHERE id = %s AND is_active = TRUE
    """, (product_id,))
    product = cursor.fetchone()

    if not product:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=404, detail="商品不存在")

    if sort == "popular":
        order_clause = "pc.like_count DESC, pc.created_at DESC"
    else:
        order_clause = "pc.created_at DESC"

    query = f"""
        SELECT
            pc.id,
            pc.user_id,
            u.username,
            pc.content,
            pc.rating,
            pc.like_count,
            pc.created_at
        FROM product_comments pc
        JOIN users u ON pc.user_id = u.id
        WHERE pc.product_id = %s
        ORDER BY {order_clause}
    """

    cursor.execute(query, (product_id,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    return [
        {
            "id": row[0],
            "user_id": row[1],
            "user_name": row[2],
            "content": row[3],
            "rating": row[4],
            "like_count": row[5],
            "created_at": row[6]
        }
        for row in rows
    ]


# 新增留言（含評分）
@router.post("/products/{product_id}/comments", status_code=201)
def create_product_comment(product_id: int, comment: CommentCreate):
    if not comment.content.strip():
        raise HTTPException(status_code=400, detail="留言內容不可為空")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id FROM products
        WHERE id = %s AND is_active = TRUE
    """, (product_id,))
    product = cursor.fetchone()

    if not product:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=404, detail="商品不存在")

    cursor.execute("""
        SELECT id, username FROM users
        WHERE id = %s
    """, (comment.user_id,))
    user = cursor.fetchone()

    if not user:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=404, detail="使用者不存在")

    cursor.execute("""
        INSERT INTO product_comments (product_id, user_id, content, rating, like_count)
        VALUES (%s, %s, %s, %s, 0)
        RETURNING id, created_at
    """, (product_id, comment.user_id, comment.content.strip(), comment.rating))

    new_comment = cursor.fetchone()

    cursor.execute("""
        UPDATE products
        SET
            reviews = (
                SELECT COUNT(*) FROM product_comments WHERE product_id = %s
            ),
            rating = COALESCE((
                SELECT ROUND(AVG(rating)::numeric, 1)
                FROM product_comments
                WHERE product_id = %s
            ), 0)
        WHERE id = %s
    """, (product_id, product_id, product_id))

    conn.commit()
    cursor.close()
    conn.close()

    return {
        "id": new_comment[0],
        "user_id": comment.user_id,
        "user_name": user[1],
        "content": comment.content.strip(),
        "rating": comment.rating,
        "like_count": 0,
        "created_at": new_comment[1]
    }


# 按讚留言
@router.post("/comments/{comment_id}/like")
def like_comment(comment_id: int, payload: CommentLike):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id FROM product_comments
        WHERE id = %s
    """, (comment_id,))
    comment = cursor.fetchone()

    if not comment:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=404, detail="留言不存在")

    cursor.execute("""
        SELECT id FROM users
        WHERE id = %s
    """, (payload.user_id,))
    user = cursor.fetchone()

    if not user:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=404, detail="使用者不存在")

    cursor.execute("""
        SELECT id FROM comment_likes
        WHERE comment_id = %s AND user_id = %s
    """, (comment_id, payload.user_id))
    existing_like = cursor.fetchone()

    if existing_like:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=400, detail="你已經按過讚了")

    cursor.execute("""
        INSERT INTO comment_likes (comment_id, user_id)
        VALUES (%s, %s)
    """, (comment_id, payload.user_id))

    cursor.execute("""
        UPDATE product_comments
        SET like_count = like_count + 1
        WHERE id = %s
        RETURNING like_count
    """, (comment_id,))
    updated_like_count = cursor.fetchone()[0]

    conn.commit()
    cursor.close()
    conn.close()

    return {
        "message": "按讚成功",
        "comment_id": comment_id,
        "like_count": updated_like_count
    }


# 取消按讚
@router.delete("/comments/{comment_id}/like")
def unlike_comment(comment_id: int, user_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id FROM product_comments
        WHERE id = %s
    """, (comment_id,))
    comment = cursor.fetchone()

    if not comment:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=404, detail="留言不存在")

    cursor.execute("""
        SELECT id FROM comment_likes
        WHERE comment_id = %s AND user_id = %s
    """, (comment_id, user_id))
    existing_like = cursor.fetchone()

    if not existing_like:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=400, detail="你尚未按讚")

    cursor.execute("""
        DELETE FROM comment_likes
        WHERE comment_id = %s AND user_id = %s
    """, (comment_id, user_id))

    cursor.execute("""
        UPDATE product_comments
        SET like_count = GREATEST(like_count - 1, 0)
        WHERE id = %s
        RETURNING like_count
    """, (comment_id,))
    updated_like_count = cursor.fetchone()[0]

    conn.commit()
    cursor.close()
    conn.close()

    return {
        "message": "已取消按讚",
        "comment_id": comment_id,
        "like_count": updated_like_count
    }


# 刪除留言
@router.delete("/comments/{comment_id}")
def delete_comment(comment_id: int, user_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, product_id, user_id
        FROM product_comments
        WHERE id = %s
    """, (comment_id,))
    row = cursor.fetchone()

    if not row:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=404, detail="留言不存在")

    _, product_id, comment_user_id = row

    if comment_user_id != user_id:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=403, detail="只能刪除自己的留言")

    cursor.execute("""
        DELETE FROM product_comments
        WHERE id = %s
    """, (comment_id,))

    cursor.execute("""
        UPDATE products
        SET
            reviews = (
                SELECT COUNT(*) FROM product_comments WHERE product_id = %s
            ),
            rating = COALESCE((
                SELECT ROUND(AVG(rating)::numeric, 1)
                FROM product_comments
                WHERE product_id = %s
            ), 0)
        WHERE id = %s
    """, (product_id, product_id, product_id))

    conn.commit()
    cursor.close()
    conn.close()

    return {"message": "留言已刪除"}