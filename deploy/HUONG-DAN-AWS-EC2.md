# Deploy backend chinanna lên AWS EC2 (free tier 12 tháng) + HTTPS miễn phí

Mục tiêu: backend Flask chạy 24/7 trên **EC2 t3.micro** (nhanh, không ngủ như Render), file lưu **S3**, DB giữ **MongoDB Atlas**, có **HTTPS** để frontend Vercel gọi được.

> ⚠️ **Bắt buộc có HTTPS.** Frontend trên Vercel chạy `https://`. Trình duyệt **chặn** trang https gọi backend `http://` (mixed content). Guide này dùng **DuckDNS (subdomain free) + Let's Encrypt (cert free)** để có https không tốn tiền.

> 💰 EC2 t3.micro free 750 giờ/tháng trong **12 tháng đầu** (đủ chạy 1 máy 24/7). Sau đó ~7–8 USD/tháng. Elastic IP miễn phí *khi đang gắn vào máy đang chạy*.

---

## Bước 0 — Chuẩn bị trước
- Đã làm **S3 bucket + IAM** theo [HUONG-DAN-AWS-S3.md](HUONG-DAN-AWS-S3.md) (ở đây ta gắn IAM **role** vào EC2 nên không cần access key).
- MongoDB Atlas: Network Access mở `0.0.0.0/0` (hoặc thêm Elastic IP ở Bước 3).
- Chuỗi `MONGODB_URL`, `SECRET_KEY` sẵn sàng.

---

## Bước 1 — Tạo IAM role cho EC2 (để truy cập S3 không cần key)
1. **IAM → Roles → Create role** → Trusted entity = **AWS service** → **EC2**.
2. Attach policy `chinanna-s3-rw` (đã tạo ở guide S3).
3. Tên role: `chinanna-ec2-role` → Create.

## Bước 2 — Launch EC2 instance
1. **EC2 → Launch instance**.
2. **Name**: `chinanna-api`.
3. **AMI**: **Ubuntu Server 24.04 LTS** (có sẵn Python 3.12).
4. **Instance type**: **t3.micro** (nhãn *Free tier eligible*).
5. **Key pair**: tạo mới (tải file `.pem` về để SSH).
6. **Network settings → Edit → Security group**, thêm 3 rule inbound:
   - SSH (22) — Source: **My IP** (chỉ IP của bạn).
   - HTTP (80) — Source: Anywhere `0.0.0.0/0`.
   - HTTPS (443) — Source: Anywhere `0.0.0.0/0`.
7. **Advanced → IAM instance profile**: chọn `chinanna-ec2-role`.
8. Launch.

## Bước 3 — Elastic IP (IP cố định, khỏi đổi khi reboot)
1. **EC2 → Elastic IPs → Allocate** → **Associate** với instance `chinanna-api`.
2. Ghi lại IP này (vd `13.212.x.x`). Thêm nó vào Atlas Network Access nếu không dùng `0.0.0.0/0`.

## Bước 4 — DuckDNS: subdomain free trỏ về Elastic IP
1. Vào https://www.duckdns.org → đăng nhập (Google/GitHub).
2. Tạo subdomain, vd `chinanna` → được `chinanna.duckdns.org`.
3. Ô **current ip**: điền **Elastic IP** ở Bước 3 → **update ip**.

## Bước 5 — SSH vào máy & cài môi trường
```bash
chmod 400 chinanna-api.pem
ssh -i chinanna-api.pem ubuntu@chinanna.duckdns.org

# trên máy EC2:
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3.12 python3.12-venv python3-pip git nginx
```

## Bước 6 — Lấy code & cài dependency
```bash
cd ~
git clone <URL_REPO> chinanna        # hoặc git clone repo của bạn
cd chinanna/backend
python3.12 -m venv venv
. venv/bin/activate
pip install -r requirements.txt      # đã gồm boto3, gunicorn
```

## Bước 7 — Tạo file `.env`
```bash
nano ~/chinanna/backend/.env
```
Dán (thay giá trị thật):
```bash
MONGODB_URL=mongodb+srv://user:pass@cluster0.xxx.mongodb.net/
DATABASE_NAME=phong_van
SECRET_KEY=<chuoi-bi-mat-dai-ngau-nhien>
ACCESS_TOKEN_EXPIRE_MINUTES=60

# S3 — KHÔNG cần AWS key vì đã gắn IAM role ở Bước 1
S3_BUCKET=chinanna-uploads
S3_PREFIX=uploads
AWS_REGION=ap-southeast-1

# URL công khai của chính backend (dùng trong link email, serve file)
BACKEND_PUBLIC_URL=https://chinanna.duckdns.org

# Cho phép frontend gọi (CORS). *.vercel.app đã tự cho phép sẵn,
# thêm domain tùy chỉnh nếu có:
# CORS_ORIGINS=https://chinanna-frontend.vercel.app

# Email/Google… copy từ cấu hình Render cũ nếu có
```
Tạo SECRET_KEY ngẫu nhiên: `python3 -c "import secrets; print(secrets.token_hex(32))"`

Seed admin (chạy 1 lần):
```bash
. venv/bin/activate && python seed_admin.py
```

## Bước 8 — Chạy bằng gunicorn qua systemd
```bash
sudo cp ~/chinanna/deploy/aws-ec2/chinanna-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now chinanna-api
sudo systemctl status chinanna-api      # phải thấy active (running)
```
Nếu lỗi, xem log: `journalctl -u chinanna-api -n 50 --no-pager`.

## Bước 9 — nginx reverse proxy
```bash
sudo cp ~/chinanna/deploy/aws-ec2/nginx-chinanna.conf /etc/nginx/sites-available/chinanna
# đảm bảo server_name = chinanna.duckdns.org trong file
sudo ln -s /etc/nginx/sites-available/chinanna /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl restart nginx
```
Test HTTP: mở `http://chinanna.duckdns.org/api/health` (hoặc route health của app) → phải có phản hồi.

## Bước 10 — Bật HTTPS (Let's Encrypt, free, tự gia hạn)
```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d chinanna.duckdns.org
```
Chọn redirect HTTP→HTTPS khi được hỏi. Certbot tự sửa file nginx thêm khối `443` và tự gia hạn (cron/systemd timer).

Xong: `https://chinanna.duckdns.org` đã có SSL. Test lại `/api/health` bằng https.

## Bước 11 — Trỏ frontend sang backend mới
Frontend (do chủ repo deploy trên Vercel) cần đổi biến API base URL sang `https://chinanna.duckdns.org` rồi redeploy. Tìm biến kiểu `VITE_API_URL` / `VITE_API_BASE` trong Vercel Project Settings → Environment Variables của cả 3 frontend.

---

## Cập nhật code về sau
```bash
cd ~/chinanna && git pull
cd backend && . venv/bin/activate && pip install -r requirements.txt
sudo systemctl restart chinanna-api
```

## Kiểm tra cuối
1. Đăng nhập mentee trên frontend Vercel → không lỗi CORS/mixed-content.
2. Upload 1 giấy tờ → object xuất hiện trong S3 bucket.
3. Mentor mở lại file đó → xem được (đọc từ S3).
4. Backend không "ngủ" — phản hồi nhanh mọi lúc.

## Ghi chú bảo mật
- Backend đứng sau nginx: `get_client_ip` đọc `X-Forwarded-For`. Nếu cần chống giả mạo IP chặt hơn (liên quan auto-login), cấu hình tin cậy đúng số hop proxy. Xem mục C2 trong đánh giá bảo mật.
- Đừng mở port 8000 ra ngoài (chỉ nghe `127.0.0.1`); chỉ 80/443 qua nginx.
- Giữ `.env` chỉ đọc bởi user `ubuntu`: `chmod 600 ~/chinanna/backend/.env`.
