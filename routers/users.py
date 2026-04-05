from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from database import get_connection
import bcrypt

router = APIRouter(tags=["使用者"])

class UserRegister(BaseModel):
    username: str
    email: str
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

# 註冊
@router.post("/users/register", status_code=201)
def register(user: UserRegister):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT id, username, password, role FROM users WHERE email = %s
""", (user.email,))
    existing = cursor.fetchone()
    if existing:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=400, detail="此 email 已被註冊")

    hashed_password = bcrypt.hashpw(user.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


    cursor.execute("""
    INSERT INTO users (username, email, password, role)
    VALUES (%s, %s, %s, %s)
    RETURNING id
""", (user.username, user.email, hashed_password, "user"))

    new_id = cursor.fetchone()[0]
    conn.commit()
    cursor.close()
    conn.close()

    return {"message": "註冊成功", "id": new_id}

# 登入
@router.post("/users/login")
def login(user: UserLogin):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, username, password, role FROM users WHERE email = %s
    """, (user.email,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()

    if row is None:
        raise HTTPException(status_code=401, detail="帳號或密碼錯誤")

    user_id, username, hashed_password, role = row

    print("🔍 輸入密碼:", user.password)
    print("🔍 DB 密碼:", hashed_password)


    if not bcrypt.checkpw(user.password.encode("utf-8"), hashed_password.encode("utf-8")):
        raise HTTPException(status_code=401, detail="帳號或密碼錯誤")

    return {
        "message": "登入成功",
        "id": user_id,
        "username": username,
        "email": user.email,
        "role": role
    }

