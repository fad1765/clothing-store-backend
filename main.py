import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from routers import (
    products,
    comments,
    cart,
    wishlist,
    coupons,
    users,
    orders,
    admin_users,
    dashboard,
    admin_coupons,
)

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

app.include_router(orders.router)
app.include_router(admin_users.router)
app.include_router(dashboard.router)
app.include_router(admin_coupons.router)