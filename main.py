import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from routers import products, comments, cart, wishlist, coupons, users

app = FastAPI()

if not os.path.exists("uploads"):
    os.makedirs("uploads")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://my-react-two-zeta.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

@app.get("/")
def root():
    return {"message": "railway ok"}

app.include_router(products.router)
app.include_router(comments.router)
app.include_router(cart.router)

app.include_router(wishlist.router)
app.include_router(coupons.router)
app.include_router(users.router)

# ❗ 第三段（先保留 debug）
try:
    from routers import orders
    app.include_router(orders.router)
    print("orders router loaded")
except Exception as e:
    print("orders router error:", e)

try:
    from routers import admin_users
    app.include_router(admin_users.router)
    print("admin_users router loaded")
except Exception as e:
    print("admin_users router error:", e)

try:
    from routers import dashboard
    app.include_router(dashboard.router)
    print("dashboard router loaded")
except Exception as e:
    print("dashboard router error:", e)

try:
    from routers import admin_coupons
    app.include_router(admin_coupons.router)
    print("admin_coupons router loaded")
except Exception as e:
    print("admin_coupons router error:", e)