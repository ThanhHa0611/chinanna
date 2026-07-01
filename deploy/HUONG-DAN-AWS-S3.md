# Hướng dẫn lưu file trên AWS S3 + deploy backend (free tier)

Backend giờ hỗ trợ 2 chế độ lưu file, tự chọn theo biến môi trường:

| Chế độ | Điều kiện | Ghi chú |
|--------|-----------|---------|
| **Local disk** (như cũ) | `S3_BUCKET` để trống | File nằm trong `backend/uploads/`. Mất khi redeploy trên Render/Heroku (đĩa ephemeral). |
| **Amazon S3** | Đặt `S3_BUCKET` | File bền vững, dùng được cho nhiều instance. |

Code không đổi hành vi khi chưa cấu hình S3 — bạn có thể bật S3 bất cứ lúc nào chỉ bằng cách thêm env var.

---

## Phần 1 — Tạo S3 bucket

1. Vào **AWS Console → S3 → Create bucket**.
2. **Bucket name**: ví dụ `chinanna-uploads` (tên phải là duy nhất toàn cầu).
3. **Region**: chọn gần VN nhất, ví dụ `ap-southeast-1` (Singapore). Ghi nhớ region này.
4. **Block Public Access**: **GIỮ BẬT TẤT CẢ** (file riêng tư — backend tự phục vụ qua endpoint có xác thực, không cho public đọc trực tiếp).
5. Các mục khác để mặc định → **Create bucket**.

> Free tier: S3 miễn phí 5GB lưu trữ + 20.000 GET + 2.000 PUT mỗi tháng, trong 12 tháng đầu.

---

## Phần 2 — Tạo IAM user + policy (least-privilege)

Backend cần quyền đọc/ghi/xóa **chỉ trong bucket này**.

1. **AWS Console → IAM → Policies → Create policy → tab JSON**, dán (đổi `chinanna-uploads` thành tên bucket của bạn):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ChinannaBucketRW",
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
      "Resource": "arn:aws:s3:::chinanna-uploads/*"
    },
    {
      "Sid": "ChinannaBucketList",
      "Effect": "Allow",
      "Action": ["s3:ListBucket"],
      "Resource": "arn:aws:s3:::chinanna-uploads"
    }
  ]
}
```

2. Đặt tên policy: `chinanna-s3-rw` → **Create policy**.
3. **IAM → Users → Create user** → tên `chinanna-backend` → **KHÔNG** cần "console access".
4. **Attach policy** vừa tạo (`chinanna-s3-rw`) → tạo user.
5. Vào user → tab **Security credentials → Create access key** → chọn "Application running outside AWS" → lưu lại **Access key ID** và **Secret access key** (secret chỉ hiện 1 lần).

> Nếu sau này chạy backend trên **EC2/ECS**, nên gắn **IAM role** cho máy thay vì dùng access key (an toàn hơn, không cần lưu secret). Khi có IAM role thì bỏ 2 biến `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`.

---

## Phần 3 — Cấu hình biến môi trường backend

Thêm vào `.env` (local) hoặc phần Environment của nền tảng deploy:

```bash
S3_BUCKET=chinanna-uploads
S3_PREFIX=uploads              # thư mục con trong bucket (tùy chọn)
AWS_REGION=ap-southeast-1
AWS_ACCESS_KEY_ID=AKIA...      # bỏ nếu dùng IAM role
AWS_SECRET_ACCESS_KEY=...      # bỏ nếu dùng IAM role
```

Cài thêm dependency (đã có trong `requirements.txt`):

```bash
pip install -r backend/requirements.txt   # đã gồm boto3
```

Khởi động lại backend. Từ giờ mọi upload (giấy tờ apply, kê khai cá nhân) sẽ lưu lên S3 với key `uploads/<mentee_id>/<doc_id>/<stored_name>`.

---

## Phần 4 — Chuyển file cũ đang nằm ở local lên S3 (nếu có)

Nếu `backend/uploads/` đang có dữ liệu thật cần giữ:

```bash
# cài AWS CLI, rồi:
aws s3 sync backend/uploads/ s3://chinanna-uploads/uploads/ --region ap-southeast-1
```

Key trên S3 giữ đúng cấu trúc `uploads/<mentee_id>/<doc_id>/<stored_name>` nên backend đọc lại được ngay.

---

## Phần 5 — Deploy backend (free tier)

MongoDB: **giữ MongoDB Atlas M0** (free vĩnh viễn). Chỉ cần vào Atlas → Network Access → cho phép IP của server (hoặc `0.0.0.0/0` nếu chấp nhận, kém an toàn hơn).

**Backend chạy trên AWS EC2 t3.micro** (free 12 tháng, nhanh, không ngủ như Render):
xem hướng dẫn chi tiết từng bước — gồm Elastic IP, DuckDNS + HTTPS miễn phí,
systemd, nginx, gắn IAM role cho S3 — tại **[HUONG-DAN-AWS-EC2.md](HUONG-DAN-AWS-EC2.md)**.

---

## Kiểm tra nhanh sau khi bật S3
1. Đăng nhập mentee → upload 1 giấy tờ → kiểm tra object xuất hiện trong bucket (S3 Console).
2. Mở lại file đó ở giao diện mentor → phải xem được (backend đọc từ S3).
3. Xóa mentee (nếu test) → toàn bộ key `uploads/<mentee_id>/…` bị xóa khỏi bucket.

Nếu lỗi `AccessDenied`: kiểm tra ARN trong policy khớp tên bucket và có cả 2 statement (object `/*` và bucket-level cho `ListBucket`).
