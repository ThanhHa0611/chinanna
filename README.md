# Phong Van

Hệ thống web full-stack với ReactJS (frontend) và Python Flask (backend), kết nối MongoDB Atlas.

## Cấu trúc dự án

```
Phong_van/
├── backend/          # Python Flask
│   ├── app.py
│   ├── requirements.txt
│   └── .env
└── frontend/         # React + Vite
    ├── src/
    │   ├── pages/    # Home, Login, Register
    │   ├── components/
    │   ├── context/
    │   └── services/
    └── package.json
```

## Yêu cầu

- Python 3.10+
- Node.js 18+ và npm

## Chạy nhanh (Backend + Frontend)

### Windows (PowerShell / CMD) — khuyên dùng

```powershell
.\start.bat
```

Hoặc double-click file `start.bat` trong thư mục dự án. Script mở 2 cửa sổ: backend và frontend.

### Mac / Linux / Git Bash

```bash
bash start.sh
```

## Chạy Backend

### Windows (PowerShell)

Nếu gặp lỗi *"禁止运行脚本"* khi chạy `venv\Scripts\activate`, **không cần activate** — dùng trực tiếp:

```powershell
cd backend
python -m venv venv
.\venv\Scripts\pip.exe install -r requirements.txt
.\venv\Scripts\python.exe app.py
```

Hoặc sửa quyền chạy script (chỉ cần làm 1 lần):

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
venv\Scripts\activate
```

Hoặc dùng **Command Prompt (cmd)** thay vì PowerShell:

```cmd
cd backend
venv\Scripts\activate.bat
pip install -r requirements.txt
python app.py
```

API docs: http://127.0.0.1:8000/api/health

## Chạy Frontend

**Lưu ý:** Cần cài [Node.js](https://nodejs.org/) trước (máy bạn hiện chưa có Node.js).

```bash
cd frontend
npm install
npm run dev
```

Truy cập: http://localhost:5173

## API Endpoints

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| GET | `/api/health` | Kiểm tra backend |
| POST | `/api/auth/register` | Đăng ký tài khoản |
| POST | `/api/auth/login` | Đăng nhập |
| GET | `/api/auth/me` | Lấy thông tin user (cần token) |
| POST | `/api/auth/logout` | Đăng xuất |

## Lưu ý bảo mật

- File `.env` chứa thông tin MongoDB — **không commit lên Git**
- Đổi `SECRET_KEY` trong production
- Cài Node.js nếu chưa có: https://nodejs.org/

## MongoDB Atlas

1. Vào **Network Access** trên MongoDB Atlas → thêm IP `0.0.0.0/0` (cho phép mọi IP khi dev)
2. Kiểm tra kết nối: `GET http://127.0.0.1:8000/api/health` — trường `database` phải là `"connected"`
3. Nếu gặp lỗi SSL với Python 3.14, thử dùng Python 3.12 hoặc 3.11
