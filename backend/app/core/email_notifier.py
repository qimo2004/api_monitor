"""邮件通知模块：发送告警通知和告警解决通知"""
import logging
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.models import User, Api, Alert

logger = logging.getLogger(__name__)


def _send_email(to_addrs: list[str], subject: str, html_body: str):
    """底层 SMTP 发送函数，配置为空时静默跳过"""
    if not settings.SMTP_HOST or not settings.SMTP_USER:
        logger.info(f"[邮件通知] 跳过发送（未配置SMTP）: {subject}")
        return False
    try:
        msg = MIMEText(html_body, "html", "utf-8")
        msg["Subject"] = Header(subject, "utf-8")
        msg["From"] = settings.SMTP_FROM or settings.SMTP_USER
        msg["To"] = ", ".join(to_addrs)
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as s:
            s.starttls()
            s.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            s.send_message(msg)
        logger.info(f"[邮件通知] 已发送: {subject} → {to_addrs}")
        return True
    except Exception as e:
        logger.error(f"[邮件通知] 发送失败: {e}")
        return False


def _get_notify_users(db: Session, api: Api) -> list[User]:
    """获取需要接收该接口告警通知的用户（admin + 被授权的 operator）"""
    from app.models.models import ApiAuthorization
    admin_users = db.query(User).filter(
        User.role == "admin",
        User.email.isnot(None),
        User.email != "",
        User.enabled == 1,
    ).all()

    auth_records = db.query(ApiAuthorization).filter(
        ApiAuthorization.api_id == api.id,
    ).all()
    auth_user_ids = [r.user_id for r in auth_records]

    operator_users = db.query(User).filter(
        User.id.in_(auth_user_ids) if auth_user_ids else False,
        User.role == "operator",
        User.email.isnot(None),
        User.email != "",
        User.enabled == 1,
    ).all()

    seen = set()
    result = []
    for u in admin_users + operator_users:
        if u.id not in seen and u.email:
            seen.add(u.id)
            result.append(u)
    return result


def _build_alert_html(alert: Alert, api: Api, alert_type_label: str) -> str:
    """构建告警通知 HTML"""
    from datetime import datetime, timezone, timedelta
    cst = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: 'Microsoft YaHei', Arial, sans-serif; background:#f4f4f4; padding:20px;">
<div style="max-width:600px; margin:0 auto; background:#fff; border-radius:8px; box-shadow:0 2px 8px rgba(0,0,0,0.1); overflow:hidden;">
<div style="background:#ff4d4f; color:#fff; padding:16px 24px; font-size:18px; font-weight:bold;">
  ⚠ 接口告警通知
</div>
<div style="padding:24px;">
  <p style="font-size:14px; color:#666;">发送时间：{cst}</p>
  <table style="width:100%; border-collapse:collapse; margin-top:12px;">
    <tr><td style="padding:8px 12px; background:#fafafa; font-weight:bold; width:100px; border:1px solid #e8e8e8;">告警类型</td>
        <td style="padding:8px 12px; border:1px solid #e8e8e8;"><span style="color:#ff4d4f;font-weight:bold;">{alert_type_label}</span></td></tr>
    <tr><td style="padding:8px 12px; background:#fafafa; font-weight:bold; border:1px solid #e8e8e8;">接口名称</td>
        <td style="padding:8px 12px; border:1px solid #e8e8e8;">{api.name}</td></tr>
    <tr><td style="padding:8px 12px; background:#fafafa; font-weight:bold; border:1px solid #e8e8e8;">接口URL</td>
        <td style="padding:8px 12px; border:1px solid #e8e8e8; word-break:break-all;">{api.url}</td></tr>
    <tr><td style="padding:8px 12px; background:#fafafa; font-weight:bold; border:1px solid #e8e8e8;">告警消息</td>
        <td style="padding:8px 12px; border:1px solid #e8e8e8;">{alert.message}</td></tr>
    <tr><td style="padding:8px 12px; background:#fafafa; font-weight:bold; border:1px solid #e8e8e8;">告警时间</td>
        <td style="padding:8px 12px; border:1px solid #e8e8e8;">{alert.created_at.strftime("%Y-%m-%d %H:%M:%S") if alert.created_at else "-"}</td></tr>
  </table>
  <p style="margin-top:16px; font-size:13px; color:#999;">请尽快登录系统进行处理。</p>
</div>
<div style="background:#fafafa; padding:12px 24px; text-align:center; font-size:12px; color:#bbb;">
  企业接口巡检与稳定性监控系统 · 自动发送
</div>
</div>
</body>
</html>"""


def _build_resolve_html(alert: Alert, api: Api, resolver: str) -> str:
    """构建告警解决通知 HTML"""
    from datetime import datetime, timezone, timedelta
    cst = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")
    alert_type_labels = {
        "response_timeout": "响应超时",
        "status_code_error": "状态码异常",
        "consecutive_failure": "连续失败",
    }
    alert_type_label = alert_type_labels.get(alert.alert_type, alert.alert_type)
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: 'Microsoft YaHei', Arial, sans-serif; background:#f4f4f4; padding:20px;">
<div style="max-width:600px; margin:0 auto; background:#fff; border-radius:8px; box-shadow:0 2px 8px rgba(0,0,0,0.1); overflow:hidden;">
<div style="background:#52c41a; color:#fff; padding:16px 24px; font-size:18px; font-weight:bold;">
  ✅ 告警已解决
</div>
<div style="padding:24px;">
  <p style="font-size:14px; color:#666;">发送时间：{cst}</p>
  <table style="width:100%; border-collapse:collapse; margin-top:12px;">
    <tr><td style="padding:8px 12px; background:#fafafa; font-weight:bold; width:100px; border:1px solid #e8e8e8;">告警类型</td>
        <td style="padding:8px 12px; border:1px solid #e8e8e8;">{alert_type_label}</td></tr>
    <tr><td style="padding:8px 12px; background:#fafafa; font-weight:bold; border:1px solid #e8e8e8;">接口名称</td>
        <td style="padding:8px 12px; border:1px solid #e8e8e8;">{api.name}</td></tr>
    <tr><td style="padding:8px 12px; background:#fafafa; font-weight:bold; border:1px solid #e8e8e8;">接口URL</td>
        <td style="padding:8px 12px; border:1px solid #e8e8e8; word-break:break-all;">{api.url}</td></tr>
    <tr><td style="padding:8px 12px; background:#fafafa; font-weight:bold; border:1px solid #e8e8e8;">告警消息</td>
        <td style="padding:8px 12px; border:1px solid #e8e8e8;">{alert.message}</td></tr>
    <tr><td style="padding:8px 12px; background:#fafafa; font-weight:bold; border:1px solid #e8e8e8;">创建时间</td>
        <td style="padding:8px 12px; border:1px solid #e8e8e8;">{alert.created_at.strftime("%Y-%m-%d %H:%M:%S") if alert.created_at else "-"}</td></tr>
    <tr><td style="padding:8px 12px; background:#fafafa; font-weight:bold; border:1px solid #e8e8e8;">已解决</td>
        <td style="padding:8px 12px; border:1px solid #e8e8e8;">由 {resolver} 确认解决</td></tr>
  </table>
</div>
<div style="background:#fafafa; padding:12px 24px; text-align:center; font-size:12px; color:#bbb;">
  企业接口巡检与稳定性监控系统 · 自动发送
</div>
</div>
</body>
</html>"""


def notify_alert(db: Session, alert: Alert, api: Api):
    """发送告警通知邮件给管理员和授权运维"""
    alert_type_labels = {
        "response_timeout": "响应超时",
        "status_code_error": "状态码异常",
        "consecutive_failure": "连续失败",
    }
    alert_type_label = alert_type_labels.get(alert.alert_type, alert.alert_type)
    users = _get_notify_users(db, api)
    if not users:
        return
    to_addrs = [u.email for u in users if u.email]
    if not to_addrs:
        return
    subject = f"[告警] {alert_type_label} - {api.name}"
    html = _build_alert_html(alert, api, alert_type_label)
    _send_email(to_addrs, subject, html)


def notify_resolve(db: Session, alert: Alert, api: Api, resolver: str):
    """发送告警解决通知邮件给管理员和授权运维"""
    users = _get_notify_users(db, api)
    if not users:
        return
    to_addrs = [u.email for u in users if u.email]
    if not to_addrs:
        return
    alert_type_labels = {
        "response_timeout": "响应超时",
        "status_code_error": "状态码异常",
        "consecutive_failure": "连续失败",
    }
    alert_type_label = alert_type_labels.get(alert.alert_type, alert.alert_type)
    subject = f"[已解决] {alert_type_label} - {api.name}"
    html = _build_resolve_html(alert, api, resolver)
    _send_email(to_addrs, subject, html)
