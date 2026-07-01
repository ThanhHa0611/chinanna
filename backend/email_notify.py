import logging

import os

import smtplib

from email.mime.multipart import MIMEMultipart

from email.mime.text import MIMEText



logger = logging.getLogger(__name__)



SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()

SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))

SMTP_USER = os.getenv("SMTP_USER", "").strip()

SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "").strip().replace(" ", "")

ADMIN_NOTIFY_EMAIL = os.getenv("ADMIN_NOTIFY_EMAIL", os.getenv("SUPER_ADMIN_EMAIL", "")).strip().lower()

MENTOR_ADMIN_URL = os.getenv("MENTOR_ADMIN_URL", "http://localhost:5174/access-requests").strip()


def mentor_snooze_links_html(snooze_urls: list[dict] | None) -> str:
    if not snooze_urls:
        return ""
    links = " · ".join(
        f'<a href="{item["url"]}" style="color:#666;text-decoration:underline;">{item["label"]}</a>'
        for item in snooze_urls
    )
    return (
        f'<p style="font-size:0.85rem;color:#666;margin-top:0.75rem;">'
        f"Nhắc lại sau: {links}</p>"
    )


def mentor_snooze_links_text(snooze_urls: list[dict] | None) -> str:
    if not snooze_urls:
        return ""
    links = "\n".join(f"Nhắc lại sau {item['label']}: {item['url']}" for item in snooze_urls)
    return f"\n{links}\n"

def smtp_configured() -> bool:

    return bool(SMTP_USER and SMTP_PASSWORD)



def send_password_reset_otp_email(
    *,
    to_email: str,
    otp: str,
    account_label: str,
    expire_minutes: int,
) -> bool:
    subject = f"[{account_label}] Mã OTP đặt lại mật khẩu"
    text_body = (
        f"Bạn vừa yêu cầu đặt lại mật khẩu trên hệ thống {account_label}.\n\n"
        f"Mã OTP: {otp}\n"
        f"Mã có hiệu lực trong {expire_minutes} phút.\n\n"
        "Nếu bạn không yêu cầu, hãy bỏ qua email này.\n\n"
        "— Hệ thống Phong Van"
    )
    html_body = f"""
    <div style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 480px;">
      <h2 style="color: #eb2233; margin-top: 0;">Đặt lại mật khẩu</h2>
      <p>Bạn vừa yêu cầu đặt lại mật khẩu trên <strong>{account_label}</strong>.</p>
      <p style="font-size: 1.75rem; letter-spacing: 0.35rem; font-weight: 700; color: #111;">
        {otp}
      </p>
      <p style="color: #666;">Mã có hiệu lực trong <strong>{expire_minutes} phút</strong>.</p>
      <p style="color: #888; font-size: 0.9rem;">Nếu bạn không yêu cầu, hãy bỏ qua email này.</p>
    </div>
    """
    return send_email(
        to_email=to_email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
    )






def send_email(*, to_email: str, subject: str, text_body: str, html_body: str | None = None) -> bool:

    if not smtp_configured():

        logger.warning("SMTP chua cau hinh — bo qua gui email toi %s", to_email)

        return False



    message = MIMEMultipart("alternative")

    message["Subject"] = subject

    message["From"] = SMTP_USER

    message["To"] = to_email

    message.attach(MIMEText(text_body, "plain", "utf-8"))

    if html_body:

        message.attach(MIMEText(html_body, "html", "utf-8"))



    try:

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as server:

            server.starttls()

            server.login(SMTP_USER, SMTP_PASSWORD)

            server.sendmail(SMTP_USER, [to_email], message.as_string())

        return True

    except Exception:

        logger.exception("Gui email that bai toi %s", to_email)

        return False





def send_l1_mentee_request_email(
    *,
    to_email: str,
    subject: str,
    title: str,
    description: str,
    details: list[tuple[str, str]],
    approve_url: str = "",
    reject_url: str = "",
    admin_page_url: str = "",
) -> bool:
    rows_text = "\n".join(f"{label}: {value}" for label, value in details)
    text_body = (
        f"{title}\n\n"
        f"{description}\n\n"
        f"{rows_text}\n\n"
        + (f"Dong y: {approve_url}\n" if approve_url else "")
        + (f"Tu choi: {reject_url}\n" if reject_url else "")
        + (f"Mo app mentor: {admin_page_url}\n" if admin_page_url else "")
        + "\n— He thong Phong Van"
    )

    detail_rows = "".join(
        f"<tr><td style='padding:4px 12px 4px 0;'><strong>{label}</strong></td>"
        f"<td>{value or '—'}</td></tr>"
        for label, value in details
    )
    action_buttons = ""
    if approve_url and reject_url:
        action_buttons = f"""
      <p style="margin-top: 1.25rem; display: flex; gap: 0.75rem; flex-wrap: wrap;">
        <a href="{approve_url}"
           style="background:#059669;color:#fff;padding:12px 18px;text-decoration:none;border-radius:8px;font-weight:600;">
          ✓ Đồng ý
        </a>
        <a href="{reject_url}"
           style="background:#eb2233;color:#fff;padding:12px 18px;text-decoration:none;border-radius:8px;font-weight:600;">
          ✕ Từ chối
        </a>
      </p>
      <p style="font-size: 0.85rem; color: #666; margin-top: 0.75rem;">
        Bấm trực tiếp trong email — link có hiệu lực 7 ngày, dùng một lần.
      </p>
        """

    html_body = f"""
    <div style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
      <h2 style="color: #eb2233;">{title}</h2>
      <p>{description}</p>
      <table style="border-collapse: collapse;">{detail_rows}</table>
      {action_buttons}
      <p style="margin-top: 1.25rem;">
        <a href="{admin_page_url}" style="color:#eb2233;font-weight:600;">Mở app mentor</a>
      </p>
    </div>
    """
    return send_email(
        to_email=to_email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
    )


def send_admin_access_request_email(

    *,

    applicant_email: str,

    applicant_username: str,

    applicant_name: str,

    mentor_name: str,

    requested_at: str,

    approve_url: str = "",

    reject_url: str = "",

    admin_page_url: str = "",

) -> bool:

    admin_page_url = admin_page_url or MENTOR_ADMIN_URL

    subject = "[Mentor Trơn Tru] Yêu cầu đăng ký mentor mới"

    text_body = (

        "Có yêu cầu đăng ký tài khoản mentor mới trên hệ thống Mentor Trơn Tru.\n\n"

        f"Email: {applicant_email}\n"

        f"Tên đăng nhập: {applicant_username}\n"

        f"Họ tên: {applicant_name or '—'}\n"

        f"Mentor phụ trách: {mentor_name}\n"

        f"Thời gian: {requested_at}\n\n"

    )

    if approve_url and reject_url:

        text_body += (

            f"Duyệt ngay: {approve_url}\n"

            f"Từ chối: {reject_url}\n\n"

        )

    text_body += f"Hoặc mở trang quản lý: {admin_page_url}\n\n— Hệ thống Phong Van"



    action_buttons = ""

    if approve_url and reject_url:

        action_buttons = f"""

      <p style="margin-top: 1.25rem; display: flex; gap: 0.75rem; flex-wrap: wrap;">

        <a href="{approve_url}"

           style="background:#059669;color:#fff;padding:12px 18px;text-decoration:none;border-radius:8px;font-weight:600;">

          ✓ Duyệt

        </a>

        <a href="{reject_url}"

           style="background:#eb2233;color:#fff;padding:12px 18px;text-decoration:none;border-radius:8px;font-weight:600;">

          ✕ Từ chối

        </a>

      </p>

      <p style="font-size: 0.85rem; color: #666; margin-top: 0.75rem;">

        Bấm trực tiếp trong email — link có hiệu lực 7 ngày, dùng một lần.

      </p>

        """



    html_body = f"""

    <div style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">

      <h2 style="color: #eb2233;">Yêu cầu đăng ký mentor mới</h2>

      <p>Có tài khoản mentor mới đang chờ phê duyệt:</p>

      <table style="border-collapse: collapse;">

        <tr><td style="padding: 4px 12px 4px 0;"><strong>Email</strong></td><td>{applicant_email}</td></tr>

        <tr><td style="padding: 4px 12px 4px 0;"><strong>Tên đăng nhập</strong></td><td>{applicant_username}</td></tr>

        <tr><td style="padding: 4px 12px 4px 0;"><strong>Họ tên</strong></td><td>{applicant_name or '—'}</td></tr>

        <tr><td style="padding: 4px 12px 4px 0;"><strong>Mentor phụ trách</strong></td><td>{mentor_name}</td></tr>

        <tr><td style="padding: 4px 12px 4px 0;"><strong>Thời gian</strong></td><td>{requested_at}</td></tr>

      </table>

      {action_buttons}

      <p style="margin-top: 1.25rem;">

        <a href="{admin_page_url}" style="color:#eb2233;font-weight:600;">

          Mở trang quản lý mentor

        </a>

      </p>

    </div>

    """

    return send_email(

        to_email=ADMIN_NOTIFY_EMAIL,

        subject=subject,

        text_body=text_body,

        html_body=html_body,

    )


def send_mentee_document_upload_email(
    *,
    to_email: str,
    mentee_name: str,
    mentee_email: str,
    mentor_name: str,
    document_label: str,
    mentee_page_url: str = "",
    view_url: str = "",
    confirm_url: str = "",
    snooze_urls: list[dict] | None = None,
) -> bool:
    mentee_page_url = mentee_page_url or os.getenv(
        "MENTOR_MENTEES_URL", "http://localhost:5174/mentees"
    ).strip()
    subject = "[Mentor Trơn Tru] Mentee upload giấy tờ mới"
    action_lines = []
    if view_url:
        action_lines.append(f"Xem giấy tờ (PDF): {view_url}")
    if confirm_url:
        action_lines.append(f"Xác nhận đã xử lí: {confirm_url}")
    action_lines.append(f"Mở app mentor: {mentee_page_url}")
    text_body = (
        "Có giấy tờ apply mới cần xem trên hệ thống Mentor Trơn Tru.\n\n"
        f"Mentee: {mentee_name}\n"
        f"Email mentee: {mentee_email}\n"
        f"Mentor phụ trách: {mentor_name}\n"
        f"Giấy tờ: {document_label}\n\n"
        + "\n".join(action_lines)
        + mentor_snooze_links_text(snooze_urls)
        + "\n— Hệ thống Phong Van"
    )
    view_btn = (
        f'<a href="{view_url}" style="display:inline-block;margin:0.5rem 0.75rem 0.5rem 0;padding:0.65rem 1rem;background:#eb2233;color:#fff;text-decoration:none;border-radius:8px;font-weight:600;">Xem giấy tờ</a>'
        if view_url
        else ""
    )
    confirm_btn = (
        f'<a href="{confirm_url}" style="display:inline-block;margin:0.5rem 0;padding:0.65rem 1rem;background:#059669;color:#fff;text-decoration:none;border-radius:8px;font-weight:600;">Đã xử lí</a>'
        if confirm_url
        else ""
    )
    html_body = f"""
    <div style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
      <h2 style="color: #eb2233;">Mentee upload giấy tờ mới</h2>
      <p>Có giấy tờ apply mới cần mentor xem:</p>
      <table style="border-collapse: collapse;">
        <tr><td style="padding: 4px 12px 4px 0;"><strong>Mentee</strong></td><td>{mentee_name}</td></tr>
        <tr><td style="padding: 4px 12px 4px 0;"><strong>Email</strong></td><td>{mentee_email}</td></tr>
        <tr><td style="padding: 4px 12px 4px 0;"><strong>Mentor</strong></td><td>{mentor_name}</td></tr>
        <tr><td style="padding: 4px 12px 4px 0;"><strong>Giấy tờ</strong></td><td>{document_label}</td></tr>
      </table>
      <p style="margin-top: 1.25rem;">{view_btn}{confirm_btn}</p>
      {mentor_snooze_links_html(snooze_urls)}
      <p style="margin-top: 0.75rem;">
        <a href="{mentee_page_url}" style="color:#eb2233;font-weight:600;">Mở trang quản lý mentor</a>
      </p>
    </div>
    """
    return send_email(
        to_email=to_email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
    )


def send_mentor_inbox_activity_email(
    *,
    to_email: str,
    title: str,
    description: str,
    mentee_name: str,
    mentee_email: str,
    view_url: str = "",
    confirm_url: str = "",
    snooze_urls: list[dict] | None = None,
) -> bool:
    subject = f"[Mentor Trơn Tru] {title}"
    text_body = (
        "Có cập nhật mới từ mentee trên hệ thống Mentor Trơn Tru.\n\n"
        f"Mentee: {mentee_name}\n"
        f"Email: {mentee_email}\n"
        f"Nội dung: {description}\n\n"
        + (f"Xem chi tiết: {view_url}\n" if view_url else "")
        + (f"Xác nhận đã xử lí: {confirm_url}\n" if confirm_url else "")
        + mentor_snooze_links_text(snooze_urls)
        + "\n— Hệ thống Phong Van"
    )
    view_btn = (
        f'<a href="{view_url}" style="display:inline-block;margin:0.5rem 0.75rem 0.5rem 0;padding:0.65rem 1rem;background:#eb2233;color:#fff;text-decoration:none;border-radius:8px;font-weight:600;">Xem</a>'
        if view_url
        else ""
    )
    confirm_btn = (
        f'<a href="{confirm_url}" style="display:inline-block;margin:0.5rem 0;padding:0.65rem 1rem;background:#059669;color:#fff;text-decoration:none;border-radius:8px;font-weight:600;">Đã xử lí</a>'
        if confirm_url
        else ""
    )
    html_body = f"""
    <div style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
      <h2 style="color: #eb2233;">{title}</h2>
      <p><strong>{mentee_name}</strong> ({mentee_email})</p>
      <p style="background:#f9f9f9;padding:1rem;border-radius:8px;white-space:pre-wrap;">{description}</p>
      <p style="margin-top:1rem;">{view_btn}{confirm_btn}</p>
      {mentor_snooze_links_html(snooze_urls)}
    </div>
    """
    return send_email(
        to_email=to_email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
    )


def send_mentee_activity_email(
    *,
    to_email: str,
    mentee_name: str,
    title: str,
    description: str,
    mentor_name: str = "",
    view_url: str = "",
    profile_url: str = "",
) -> bool:
    profile_url = profile_url or os.getenv("MENTEE_PROFILE_URL", "http://localhost:5173/profile").strip()
    subject = f"[Trơn Tru] {title}"
    text_body = (
        "Có cập nhật mới từ mentor trên hệ thống Trơn Tru.\n\n"
        f"Mentee: {mentee_name}\n"
        f"Mentor: {mentor_name or 'Mentor'}\n"
        f"{description}\n\n"
        + (f"Xem chi tiết: {view_url}\n" if view_url else "")
        + f"Mở hồ sơ: {profile_url}\n\n— Hệ thống Phong Van"
    )
    view_btn = (
        f'<a href="{view_url}" style="display:inline-block;margin-top:1rem;padding:0.65rem 1rem;background:#eb2233;color:#fff;text-decoration:none;border-radius:8px;font-weight:600;">Xem</a>'
        if view_url
        else ""
    )
    html_body = f"""
    <div style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
      <h2 style="color: #eb2233;">{title}</h2>
      <p>Mentor: {mentor_name or 'Mentor'}</p>
      <p style="background:#f9f9f9;padding:1rem;border-radius:8px;white-space:pre-wrap;">{description}</p>
      {view_btn}
      <p style="margin-top:1rem;"><a href="{profile_url}" style="color:#eb2233;font-weight:600;">Mở hồ sơ</a></p>
    </div>
    """
    return send_email(
        to_email=to_email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
    )


def send_mentee_mentor_document_upload_email(
    *,
    to_email: str,
    mentee_name: str,
    mentor_name: str,
    document_label: str,
    profile_url: str = "",
    view_url: str = "",
) -> bool:
    profile_url = profile_url or os.getenv("MENTEE_PROFILE_URL", "http://localhost:5173/profile").strip()
    subject = "[Trơn Tru] Mentor đã tải lên giấy tờ cho bạn"
    text_body = (
        "Mentor đã tải lên giấy tờ apply trên hệ thống Trơn Tru.\n\n"
        f"Mentee: {mentee_name}\n"
        f"Mentor: {mentor_name}\n"
        f"Giấy tờ: {document_label}\n\n"
        + (f"Xem giấy tờ: {view_url}\n" if view_url else "")
        + f"Mở hồ sơ: {profile_url}\n\n— Hệ thống Phong Van"
    )
    view_btn = (
        f'<a href="{view_url}" style="display:inline-block;margin-top:1rem;padding:0.65rem 1rem;background:#eb2233;color:#fff;text-decoration:none;border-radius:8px;font-weight:600;">Xem giấy tờ</a>'
        if view_url
        else ""
    )
    html_body = f"""
    <div style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
      <h2 style="color: #eb2233;">Mentor đã tải lên giấy tờ</h2>
      <p>Mentor đã tải lên giấy tờ apply cho bạn:</p>
      <table style="border-collapse: collapse;">
        <tr><td style="padding: 4px 12px 4px 0;"><strong>Mentor</strong></td><td>{mentor_name}</td></tr>
        <tr><td style="padding: 4px 12px 4px 0;"><strong>Giấy tờ</strong></td><td>{document_label}</td></tr>
      </table>
      {view_btn}
      <p style="margin-top: 1rem;">
        <a href="{profile_url}" style="color:#eb2233;font-weight:600;">Mở hồ sơ giấy tờ</a>
      </p>
    </div>
    """
    return send_email(
        to_email=to_email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
    )


def send_mentee_document_feedback_email(
    *,
    to_email: str,
    mentee_name: str,
    document_label: str,
    mentor_status: str,
    mentor_note: str,
    profile_url: str = "",
    view_url: str = "",
) -> bool:
    profile_url = profile_url or os.getenv("MENTEE_PROFILE_URL", "http://localhost:5173/profile").strip()
    subject = "[Trơn Tru] Mentor đã phản hồi giấy tờ của bạn"
    text_body = (
        "Mentor đã phản hồi giấy tờ apply trên hệ thống Trơn Tru.\n\n"
        f"Mentee: {mentee_name}\n"
        f"Giấy tờ: {document_label}\n"
        f"Trạng thái: {mentor_status}\n"
        f"Nhận xét: {mentor_note}\n\n"
        + (f"Xem giấy tờ: {view_url}\n" if view_url else "")
        + f"Mở hồ sơ: {profile_url}\n\n— Hệ thống Phong Van"
    )
    view_btn = (
        f'<a href="{view_url}" style="display:inline-block;margin-top:1rem;padding:0.65rem 1rem;background:#eb2233;color:#fff;text-decoration:none;border-radius:8px;font-weight:600;">Xem giấy tờ</a>'
        if view_url
        else ""
    )
    html_body = f"""
    <div style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
      <h2 style="color: #eb2233;">Mentor đã phản hồi giấy tờ</h2>
      <p>Mentor đã gửi nhận xét về giấy tờ apply của bạn:</p>
      <table style="border-collapse: collapse;">
        <tr><td style="padding: 4px 12px 4px 0;"><strong>Giấy tờ</strong></td><td>{document_label}</td></tr>
        <tr><td style="padding: 4px 12px 4px 0;"><strong>Trạng thái</strong></td><td>{mentor_status}</td></tr>
        <tr><td style="padding: 4px 12px 4px 0; vertical-align:top;"><strong>Nhận xét</strong></td><td>{mentor_note}</td></tr>
      </table>
      {view_btn}
      <p style="margin-top: 1rem;">
        <a href="{profile_url}" style="color:#eb2233;font-weight:600;">Mở hồ sơ giấy tờ</a>
      </p>
    </div>
    """
    return send_email(
        to_email=to_email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
    )


def send_mentee_activity_digest_email(
    *,
    to_email: str,
    mentee_name: str,
    activity_names: list[str],
    profile_url: str = "",
) -> bool:
    profile_url = profile_url or os.getenv("MENTEE_PROFILE_URL", "http://localhost:5173/profile").strip()
    count = len(activity_names)
    if count == 0:
        return False

    intro = f"Mentor cập nhật {count} hoạt động ngoại khóa, hãy tham gia ngay nhé"
    subject = f"[Trơn Tru] {intro}"
    numbered_lines = [f"{index}. {name}" for index, name in enumerate(activity_names, start=1)]
    list_text = "\n".join(numbered_lines)
    text_body = (
        f"{intro}\n\n"
        f"{list_text}\n\n"
        f"Mở hồ sơ: {profile_url}\n\n— Hệ thống Phong Van"
    )
    list_html = "".join(
        f"<li style=\"margin:0.35rem 0;\">{index}. {name}</li>"
        for index, name in enumerate(activity_names, start=1)
    )
    html_body = f"""
    <div style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
      <h2 style="color: #eb2233; margin-top: 0;">{intro}</h2>
      <ol style="padding-left: 1.25rem; margin: 1rem 0;">
        {list_html}
      </ol>
      <p style="margin-top: 1.25rem;">
        <a href="{profile_url}" style="color:#eb2233;font-weight:600;">Xem hoạt động ngoại khóa</a>
      </p>
    </div>
    """
    return send_email(
        to_email=to_email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
    )


def send_mentor_inbox_digest_email(
    *,
    to_email: str,
    item_lines: list[str],
    admin_url: str = "",
) -> bool:
    admin_url = admin_url or os.getenv("MENTOR_ADMIN_URL", "http://localhost:5174/").strip()
    count = len(item_lines)
    if count == 0:
        return False

    intro = f"Bạn có {count} việc chưa xử lí:"
    subject = f"[Mentor Trơn Tru] {intro}"
    numbered_lines = [f"{index}. {line}" for index, line in enumerate(item_lines, start=1)]
    list_text = "\n".join(numbered_lines)
    text_body = (
        f"{intro}\n\n"
        f"{list_text}\n\n"
        f"Mở trang mentor: {admin_url}\n\n— Hệ thống Phong Van"
    )
    list_html = "".join(
        f'<li style="margin:0.35rem 0;">{index}. {line}</li>'
        for index, line in enumerate(item_lines, start=1)
    )
    html_body = f"""
    <div style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
      <h2 style="color: #eb2233; margin-top: 0;">{intro}</h2>
      <ol style="padding-left: 1.25rem; margin: 1rem 0;">
        {list_html}
      </ol>
      <p style="margin-top: 1.25rem;">
        <a href="{admin_url}" style="color:#eb2233;font-weight:600;">Mở trang quản lý mentor</a>
      </p>
    </div>
    """
    return send_email(
        to_email=to_email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
    )


def send_mentee_login_anomaly_email(
    *,
    to_email: str,
    mentee_name: str,
    mentee_email: str,
    mentor_name: str,
    unique_ip_count: int,
    unique_device_count: int,
    mentee_page_url: str = "",
) -> bool:
    mentee_page_url = mentee_page_url or os.getenv(
        "MENTOR_MENTEES_URL",
        "http://localhost:5174/mentees",
    ).strip()
    subject = "[Mentor Trơn Tru] Cảnh báo: mentee đăng nhập nhiều thiết bị/IP"
    text_body = (
        "Phát hiện mentee đăng nhập từ nhiều thiết bị hoặc nhiều IP.\n\n"
        f"Mentee: {mentee_name}\n"
        f"Email: {mentee_email}\n"
        f"Mentor: {mentor_name or '—'}\n"
        f"Số IP: {unique_ip_count}\n"
        f"Số thiết bị: {unique_device_count}\n\n"
        f"Xem tại: {mentee_page_url}\n\n— Hệ thống Phong Van"
    )
    html_body = f"""
    <div style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
      <h2 style="color: #eb2233;">Cảnh báo đăng nhập mentee</h2>
      <p>Mentee có từ 2 IP hoặc 2 thiết bị đăng nhập khác nhau:</p>
      <table style="border-collapse: collapse;">
        <tr><td style="padding: 4px 12px 4px 0;"><strong>Mentee</strong></td><td>{mentee_name}</td></tr>
        <tr><td style="padding: 4px 12px 4px 0;"><strong>Email</strong></td><td>{mentee_email}</td></tr>
        <tr><td style="padding: 4px 12px 4px 0;"><strong>Mentor</strong></td><td>{mentor_name or '—'}</td></tr>
        <tr><td style="padding: 4px 12px 4px 0;"><strong>Số IP</strong></td><td>{unique_ip_count}</td></tr>
        <tr><td style="padding: 4px 12px 4px 0;"><strong>Số thiết bị</strong></td><td>{unique_device_count}</td></tr>
      </table>
      <p style="margin-top: 1.25rem;">
        <a href="{mentee_page_url}" style="color:#eb2233;font-weight:600;">Mở trang quản lý mentee</a>
      </p>
    </div>
    """
    return send_email(
        to_email=to_email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
    )


def send_mentee_feedback_to_mentor_email(
    *,
    to_email: str,
    mentee_name: str,
    mentee_email: str,
    mentor_name: str,
    content_preview: str,
    view_url: str = "",
    confirm_url: str = "",
    mentee_page_url: str = "",
    snooze_urls: list[dict] | None = None,
) -> bool:
    mentee_page_url = mentee_page_url or os.getenv(
        "MENTOR_MENTEES_URL", "http://localhost:5174/mentees"
    ).strip()
    subject = "[Mentor Trơn Tru] Mentee gửi phản hồi mới"
    text_body = (
        "Mentee gửi phản hồi mới trên hệ thống Mentor Trơn Tru.\n\n"
        f"Mentee: {mentee_name}\n"
        f"Email: {mentee_email}\n"
        f"Mentor: {mentor_name}\n\n"
        f"Nội dung: {content_preview}\n\n"
        + (f"Xem chi tiết: {view_url}\n" if view_url else "")
        + (f"Xác nhận đã xử lí: {confirm_url}\n" if confirm_url else "")
        + f"Mở app: {mentee_page_url}\n"
        + mentor_snooze_links_text(snooze_urls)
        + "\n— Hệ thống Phong Van"
    )
    view_btn = (
        f'<a href="{view_url}" style="display:inline-block;margin:0.5rem 0.75rem 0.5rem 0;padding:0.65rem 1rem;background:#eb2233;color:#fff;text-decoration:none;border-radius:8px;font-weight:600;">Xem phản hồi</a>'
        if view_url
        else ""
    )
    confirm_btn = (
        f'<a href="{confirm_url}" style="display:inline-block;margin:0.5rem 0;padding:0.65rem 1rem;background:#059669;color:#fff;text-decoration:none;border-radius:8px;font-weight:600;">Đã xử lí</a>'
        if confirm_url
        else ""
    )
    html_body = f"""
    <div style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
      <h2 style="color: #eb2233;">Mentee gửi phản hồi mới</h2>
      <p><strong>{mentee_name}</strong> ({mentee_email})</p>
      <p style="background:#f9f9f9;padding:1rem;border-radius:8px;white-space:pre-wrap;">{content_preview}</p>
      <p style="margin-top: 1rem;">{view_btn}{confirm_btn}</p>
      {mentor_snooze_links_html(snooze_urls)}
      <p><a href="{mentee_page_url}" style="color:#eb2233;font-weight:600;">Mở trang mentor</a></p>
    </div>
    """
    return send_email(
        to_email=to_email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
    )


def send_inbox_reminder_email(
    *,
    to_email: str,
    title: str,
    description: str,
    mentee_name: str,
    view_url: str = "",
    confirm_url: str = "",
    snooze_urls: list[dict] | None = None,
) -> bool:
    subject = f"[Mentor Trơn Tru] Nhắc nhở: {title}"
    text_body = (
        "Bạn còn việc chưa xử lí trên hệ thống Mentor Trơn Tru.\n\n"
        f"Mentee: {mentee_name}\n"
        f"Việc: {title}\n"
        f"{description}\n\n"
        + (f"Xem: {view_url}\n" if view_url else "")
        + (f"Xác nhận đã xử lí: {confirm_url}\n" if confirm_url else "")
        + mentor_snooze_links_text(snooze_urls)
        + "\n— Hệ thống Phong Van"
    )
    snooze_html = mentor_snooze_links_html(snooze_urls)
    html_body = f"""
    <div style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
      <h2 style="color: #eb2233;">Nhắc nhở công việc chưa xử lí</h2>
      <p><strong>{title}</strong></p>
      <p>Mentee: {mentee_name}</p>
      <p>{description}</p>
      <p style="margin-top:1rem;">
        {f'<a href="{view_url}" style="margin-right:0.75rem;color:#eb2233;font-weight:600;">Xem</a>' if view_url else ''}
        {f'<a href="{confirm_url}" style="color:#059669;font-weight:600;">Đã xử lí</a>' if confirm_url else ''}
      </p>
      {snooze_html}
    </div>
    """
    return send_email(
        to_email=to_email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
    )


def send_daily_inbox_summary_email(
    *,
    to_email: str,
    date_label: str,
    items: list[dict],
) -> bool:
    subject = f"[Mentor Trơn Tru] Tổng hợp Trơn Tru ngày {date_label}"
    lines_text = []
    rows_html = []
    for item in items:
        summary = item.get("summary_line") or item.get("title") or item.get("description") or ""
        lines_text.append(summary)
        view_url = item.get("view_url") or ""
        confirm_url = item.get("confirm_url") or ""
        state = item.get("display_state") or "new"
        row_bg = "#f3f4f6" if state == "viewed" else "#ffffff"
        state_label = {
            "viewed": "Đã xem · chưa xử lí",
            "new": "Chưa xem",
            "done": "Đã xử lí",
        }.get(state, "")
        snooze_html = mentor_snooze_links_html(item.get("snooze_urls"))
        rows_html.append(
            f"""
            <tr style="background:{row_bg};">
              <td style="padding:12px 10px;border-bottom:1px solid #e5e7eb;vertical-align:top;">
                <div style="font-size:0.95rem;color:#111;">{summary}</div>
                <div style="font-size:0.78rem;color:#6b7280;margin-top:4px;">{state_label}</div>
                <div style="margin-top:8px;">
                  {f'<a href="{view_url}" style="display:inline-block;margin-right:8px;padding:6px 12px;background:#eb2233;color:#fff;text-decoration:none;border-radius:6px;font-size:0.82rem;font-weight:600;">Xem</a>' if view_url else ''}
                  {f'<a href="{confirm_url}" style="display:inline-block;padding:6px 12px;background:#059669;color:#fff;text-decoration:none;border-radius:6px;font-size:0.82rem;font-weight:600;">Đã xử lí</a>' if confirm_url else ''}
                </div>
                {snooze_html}
              </td>
            </tr>
            """
        )

    text_body = (
        f"Tổng hợp Trơn Tru ngày {date_label}\n\n"
        + "\n".join(f"• {line}" for line in lines_text)
        + "\n\n— Hệ thống Phong Van"
    )
    html_body = f"""
    <div style="font-family:Arial,sans-serif;line-height:1.6;color:#333;max-width:640px;">
      <h2 style="color:#eb2233;margin-top:0;">Tổng hợp Trơn Tru ngày {date_label}</h2>
      <p style="color:#666;font-size:0.9rem;">Các việc mentee cần mentor xử lí (màu xám = đã xem, chưa xử lí):</p>
      <table style="width:100%;border-collapse:collapse;border:1px solid #e5e7eb;border-radius:8px;overflow:hidden;">
        {''.join(rows_html)}
      </table>
    </div>
    """
    return send_email(
        to_email=to_email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
    )

