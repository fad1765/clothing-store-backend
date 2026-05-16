# Backend API

以 FastAPI + PostgreSQL 實作的完整電商後端系統，支援商品管理、購物流程、訂單與後台統計功能。

## 核心功能

- **商品系統**: 多圖上傳、庫存管理、商品評分與留言互動
- **購物流程**: 購物車、收藏清單、訂單建立與狀態追蹤
- **優惠券系統**: 動態驗證（類別限制、消費門檻、使用次數限制）
- **使用者管理**: 註冊、登入、會員資料、訂單查詢
- **後台管理**: 總覽統計、商品/使用者/優惠券後台管理

## 技術棧

| 項目 | 技術 |
|------|------|
| **框架** | FastAPI |
| **語言** | Python 3.11+ |
| **資料庫** | PostgreSQL |
| **ORM/查詢** | Raw SQL with psycopg2 |
| **認證** | bcrypt |
| **部署** | Docker |

## 快速開始

### 本機開發

```bash
# 安裝
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 設定環境變數 (PowerShell)
$env:DB_PASSWORD = "your_password"
$env:BACKEND_BASE_URL = "http://localhost:8080"

# 啟動伺服器
uvicorn main:app --host 0.0.0.0 --port 8080
```

### Docker 部署

```bash
docker build -t ecommerce-backend .
docker run -e DB_PASSWORD=your_pw -p 8080:8080 ecommerce-backend
```

## 專案結構

```
backend/
├── main.py                 # FastAPI 應用主程式
├── database.py             # PostgreSQL 連線管理
├── requirements.txt        # 依賴套件
├── Dockerfile              # 容器化配置
└── routers/               # 模組化路由
    ├── products.py        # 商品相關 API
    ├── users.py           # 使用者認證 API
    ├── cart.py            # 購物車 API
    ├── orders.py          # 訂單 API
    ├── coupons.py         # 優惠券 API
    ├── comments.py        # 商品留言 API
    ├── wishlist.py        # 收藏 API
    ├── dashboard.py       # 後台總覽
    ├── admin_users.py     # 使用者後台管理
    └── admin_coupons.py   # 優惠券後台管理
```

## 環境變數

| 變數 | 說明 |
|------|------|
| `DATABASE_URL` | PostgreSQL 連線字串（部署時使用） |
| `DB_PASSWORD` | 本機資料庫密碼 |
| `BACKEND_BASE_URL` | API 後端 Base URL（用於圖片 URL） |

## 技術亮點

### 1. 交易與鎖定
- 訂單建立時使用 `FOR UPDATE` 鎖定商品行確保庫存一致性
- 完整的 commit/rollback 機制防止資料不一致

### 2. 多圖上傳管理
- 商品支援多张圖片上傳與排序
- 動態構建完整 URL（本地或 CDN）

### 3. 複雜的優惠券邏輯
- 支援固定折扣與百分比折扣
- 類別限制、消費門檻、使用次數限制
- 使用者/Email 層級可使用檢查

