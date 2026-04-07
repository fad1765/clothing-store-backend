from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from decimal import Decimal
from typing import List
from database import get_connection
import shutil
import uuid
import os

router = APIRouter(tags=["商品"])


class ProductCreate(BaseModel):
    name: str
    price: Decimal
    category: str
    description: str
    stock: int
    is_hot: bool = False
    is_limited: bool = False


BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "").rstrip("/")
print("BACKEND_BASE_URL =", BACKEND_BASE_URL)
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


# 取得所有商品（含多張圖片）
@router.get("/products")
def get_products():
    conn = get_connection()
    cursor = conn.cursor()

    try:
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
                p.created_at
            FROM products p
            WHERE p.is_active = TRUE
            ORDER BY p.id DESC
        """)
        product_rows = cursor.fetchall()

        results = []

        for row in product_rows:
            product_id = row[0]

            cursor.execute("""
                SELECT image_url
                FROM product_images
                WHERE product_id = %s
                ORDER BY sort_order ASC, id ASC
            """, (product_id,))
            image_rows = cursor.fetchall()

            image_list = [build_image_url(img[0]) for img in image_rows if img[0]]
            main_image = image_list[0] if image_list else None

            results.append({
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
                "created_at": row[10],
                "image": main_image,   # 主圖
                "images": image_list,  # 所有圖片
            })

        return results

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"取得商品失敗: {str(e)}")

    finally:
        cursor.close()
        conn.close()


# 取得單一商品（含多張圖片）
@router.get("/products/{product_id}")
def get_product(product_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    try:
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
                p.created_at
            FROM products p
            WHERE p.id = %s AND p.is_active = TRUE
        """, (product_id,))
        row = cursor.fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail="商品不存在")

        cursor.execute("""
            SELECT image_url
            FROM product_images
            WHERE product_id = %s
            ORDER BY sort_order ASC, id ASC
        """, (product_id,))
        image_rows = cursor.fetchall()

        image_list = [build_image_url(img[0]) for img in image_rows if img[0]]
        main_image = image_list[0] if image_list else None

        return {
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
            "created_at": row[10],
            "image": main_image,   # 主圖
            "images": image_list,  # 所有圖片
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"取得商品失敗: {str(e)}")

    finally:
        cursor.close()
        conn.close()


# 新增商品（含多張圖片）
@router.post("/products", status_code=201)
def create_product(
    name: str = Form(...),
    price: Decimal = Form(...),
    category: str = Form(...),
    description: str = Form(...),
    stock: int = Form(...),
    is_hot: bool = Form(False),
    is_limited: bool = Form(False),
    images: List[UploadFile] = File(...)
):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        os.makedirs("uploads", exist_ok=True)

        cursor.execute("""
            INSERT INTO products (name, price, category, description, stock, is_hot, is_limited)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (name, price, category, description, stock, is_hot, is_limited))

        new_id = cursor.fetchone()[0]

        image_urls = []

        for index, image in enumerate(images):
            file_extension = os.path.splitext(image.filename)[1]
            unique_filename = f"{uuid.uuid4()}{file_extension}"
            file_path = f"uploads/{unique_filename}"

            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(image.file, buffer)

            cursor.execute("""
                INSERT INTO product_images (product_id, image_url, sort_order)
                VALUES (%s, %s, %s)
            """, (new_id, file_path, index))

            image_urls.append(build_image_url(file_path))

        conn.commit()

        return {
            "message": "商品新增成功",
            "id": new_id,
            "image": image_urls[0] if image_urls else None,
            "images": image_urls
        }

    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"商品新增失敗: {str(e)}")

    finally:
        cursor.close()
        conn.close()


# 更新商品
@router.put("/products/{product_id}")
def update_product(product_id: int, product: ProductCreate):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE products
            SET name = %s,
                price = %s,
                category = %s,
                description = %s,
                stock = %s,
                is_hot = %s,
                is_limited = %s
            WHERE id = %s AND is_active = TRUE
        """, (
            product.name,
            product.price,
            product.category,
            product.description,
            product.stock,
            product.is_hot,
            product.is_limited,
            product_id
        ))

        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="商品不存在或已下架")

        conn.commit()
        return {"message": "商品更新成功"}

    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"商品更新失敗: {str(e)}")

    finally:
        cursor.close()
        conn.close()


# 刪除商品（軟刪除）
@router.delete("/products/{product_id}")
def delete_product(product_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE products
            SET is_active = FALSE
            WHERE id = %s
        """, (product_id,))

        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="商品不存在")

        conn.commit()
        return {"message": "商品已下架"}

    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"商品刪除失敗: {str(e)}")

    finally:
        cursor.close()
        conn.close()