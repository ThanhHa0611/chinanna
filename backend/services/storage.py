"""Lớp lưu trữ file thống nhất cho local disk và Amazon S3.

- Để trống ``S3_BUCKET`` (env)  => lưu trên đĩa local dưới ``UPLOAD_ROOT`` (như cũ).
- Đặt ``S3_BUCKET``             => lưu trên Amazon S3 (bền vững khi redeploy / nhiều instance).

Mọi nơi trong code chỉ làm việc với một ``key`` dạng chuỗi (ví dụ
``"<user_id>/<doc_id>/<stored_name>"``) — tương ứng đường dẫn tương đối cũ
``UPLOAD_ROOT / user_id / doc_id / stored_name``. Nhờ vậy dữ liệu đã lưu trên
đĩa vẫn ánh xạ 1-1 sang key trên S3.
"""

from __future__ import annotations

import io
import os
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path

from config import AWS_REGION, S3_BUCKET, S3_PREFIX, UPLOAD_ROOT

_s3_client = None


def use_s3() -> bool:
    return bool(S3_BUCKET)


def _s3():
    global _s3_client
    if _s3_client is None:
        import boto3

        _s3_client = boto3.client("s3", region_name=AWS_REGION or None)
    return _s3_client


def storage_key(*parts) -> str:
    """Ghép các phần thành một key chuẩn (dùng dấu ``/``), bỏ phần rỗng."""
    cleaned = []
    for part in parts:
        text = str(part).replace("\\", "/").strip("/")
        if text:
            cleaned.append(text)
    return "/".join(cleaned)


def _full_key(key: str) -> str:
    prefix = (S3_PREFIX or "").strip("/")
    key = key.strip("/")
    return f"{prefix}/{key}" if prefix else key


def _local_path(key: str) -> Path:
    return UPLOAD_ROOT / key.strip("/")


def save_fileobj(key: str, fileobj, content_type: str = "") -> None:
    """Lưu một file-like object (ví dụ werkzeug FileStorage) vào ``key``."""
    try:
        fileobj.seek(0)
    except Exception:
        pass
    if use_s3():
        extra = {"ContentType": content_type} if content_type else {}
        _s3().upload_fileobj(fileobj, S3_BUCKET, _full_key(key), ExtraArgs=extra)
        return
    path = _local_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fileobj.seek(0)
    except Exception:
        pass
    with open(path, "wb") as dest:
        shutil.copyfileobj(fileobj, dest)


def save_bytes(key: str, data: bytes, content_type: str = "") -> None:
    save_fileobj(key, io.BytesIO(data), content_type)


def read_bytes(key: str) -> bytes | None:
    """Đọc toàn bộ nội dung ``key``; trả về ``None`` nếu không tồn tại."""
    if use_s3():
        try:
            obj = _s3().get_object(Bucket=S3_BUCKET, Key=_full_key(key))
            return obj["Body"].read()
        except Exception:
            return None
    path = _local_path(key)
    if not path.is_file():
        return None
    return path.read_bytes()


def exists(key: str) -> bool:
    if use_s3():
        try:
            _s3().head_object(Bucket=S3_BUCKET, Key=_full_key(key))
            return True
        except Exception:
            return False
    return _local_path(key).is_file()


def delete(key: str) -> None:
    """Xóa ``key`` nếu có; không báo lỗi nếu không tồn tại."""
    if use_s3():
        try:
            _s3().delete_object(Bucket=S3_BUCKET, Key=_full_key(key))
        except Exception:
            pass
        return
    path = _local_path(key)
    if path.is_file():
        try:
            path.unlink()
        except OSError:
            pass


def delete_prefix(prefix: str) -> None:
    """Xóa mọi file có key bắt đầu bằng ``prefix`` (vd. toàn bộ file của 1 mentee)."""
    prefix = prefix.strip("/")
    if not prefix:
        return
    if use_s3():
        try:
            client = _s3()
            token = None
            while True:
                kwargs = {"Bucket": S3_BUCKET, "Prefix": _full_key(prefix) + "/"}
                if token:
                    kwargs["ContinuationToken"] = token
                resp = client.list_objects_v2(**kwargs)
                objects = [{"Key": obj["Key"]} for obj in resp.get("Contents", [])]
                if objects:
                    client.delete_objects(Bucket=S3_BUCKET, Delete={"Objects": objects})
                if not resp.get("IsTruncated"):
                    break
                token = resp.get("NextContinuationToken")
        except Exception:
            pass
        return
    path = _local_path(prefix)
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)


@contextmanager
def local_path(key: str):
    """Cung cấp một đường dẫn file cục bộ thực sự cho ``key``.

    Dùng cho code cần một ``Path`` trên đĩa (vd. ``document_processing``).
    Ở chế độ S3, file được tải về một file tạm và tự xóa sau khi dùng.
    Yield ``None`` nếu key không tồn tại.
    """
    if use_s3():
        data = read_bytes(key)
        if data is None:
            yield None
            return
        suffix = Path(key).suffix
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        try:
            tmp.write(data)
            tmp.flush()
            tmp.close()
            yield Path(tmp.name)
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass
        return
    path = _local_path(key)
    yield path if path.is_file() else None
