"""告警服务：检测并创建告警、查询告警列表、解决告警
- check_and_alert: 巡检后自动检测是否需要告警
- get_alerts: 分页查询告警列表
- resolve_alert: 确认/解决告警
"""
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models.models import Alert, CheckLog
from app.core.logger import log_op
from app.core.email_notifier import notify_alert, notify_resolve

logger = logging.getLogger(__name__)

CST = timezone(timedelta(hours=8))  # 东八区


class NotificationChannel:
    """告警通知渠道基类（可扩展对接钉钉/企业微信/邮件等）"""

    @staticmethod
    def send(title: str, message: str):
        """
        发送通知。当前实现：写入操作审计日志。
        扩展方式：子类重写此方法，如 DingTalkChannel.send(title, message)
        """
        log_op("system", "notify", "alert", 0, f"[{title}] {message}")
        logger.warning(f"[通知] {title}: {message}")


class AlertService:
    def __init__(self, db: Session):
        self.db = db

    def check_and_alert(self, api_id: int) -> str | None:
        """
        巡检后检测是否触发告警，返回告警消息或None。
        告警类型：
        - response_timeout: 最新日志响应时间 > api.timeout
        - status_code_error: HTTP状态码 != 期望值 (仅当 status=failure)
        - consecutive_failure: 最近3条日志全部 failure
        告警聚合：同类型未解决的告警不重复创建
        恢复通知：接口从故障恢复到正常时，自动解决告警并通知
        """
        from app.models.models import Api
        api = self.db.query(Api).filter(Api.id == api_id).first()
        if not api:
            return None

        latest_log = self.db.query(CheckLog).filter(
            CheckLog.api_id == api_id
        ).order_by(desc(CheckLog.check_time)).first()
        if not latest_log:
            return None

        # 先检查是否需要触发新告警
        alert_msg = self._check_alerts(api, latest_log)
        if alert_msg:
            NotificationChannel.send("新告警", alert_msg)
            return alert_msg

        # 没有新告警 → 检测恢复通知
        if latest_log.status == "success":
            self._check_recovery(api)

        return None

    def _check_alerts(self, api, latest_log) -> str | None:
        """检测三种告警类型，返回告警消息或None，新告警时发送邮件"""
        api_id = api.id

        # 1. 响应超时告警
        if latest_log.response_time_ms and latest_log.response_time_ms > api.timeout:
            existing = self.db.query(Alert).filter(
                Alert.api_id == api_id,
                Alert.alert_type == "response_timeout",
                Alert.status == "pending",
            ).first()
            if not existing:
                msg = f"响应超时告警: {api.name} 响应时间{latest_log.response_time_ms}ms > 阈值{api.timeout}ms"
                alert = Alert(api_id=api_id, alert_type="response_timeout", message=msg)
                self.db.add(alert)
                self.db.commit()
                self.db.refresh(alert)
                logger.warning(msg)
                notify_alert(self.db, alert, api)
                return msg

        # 2. 状态码异常告警
        if latest_log.status == "failure" and latest_log.http_status:
            existing = self.db.query(Alert).filter(
                Alert.api_id == api_id,
                Alert.alert_type == "status_code_error",
                Alert.status == "pending",
            ).first()
            if not existing:
                msg = f"状态码异常告警: {api.name} 返回状态码 {latest_log.http_status}"
                alert = Alert(api_id=api_id, alert_type="status_code_error", message=msg)
                self.db.add(alert)
                self.db.commit()
                self.db.refresh(alert)
                logger.warning(msg)
                notify_alert(self.db, alert, api)
                return msg

        # 3. 连续失败告警
        recent_logs = self.db.query(CheckLog).filter(
            CheckLog.api_id == api_id
        ).order_by(desc(CheckLog.check_time)).limit(3).all()
        if len(recent_logs) >= 3 and all(log.status == "failure" for log in recent_logs):
            existing = self.db.query(Alert).filter(
                Alert.api_id == api_id,
                Alert.alert_type == "consecutive_failure",
                Alert.status == "pending",
            ).first()
            if not existing:
                msg = f"连续失败告警: {api.name} 连续{len(recent_logs)}次巡检失败"
                alert = Alert(api_id=api_id, alert_type="consecutive_failure", message=msg)
                self.db.add(alert)
                self.db.commit()
                self.db.refresh(alert)
                logger.warning(msg)
                notify_alert(self.db, alert, api)
                return msg

        return None

    def _check_recovery(self, api):
        """检测恢复通知：如果存在 pending 告警且最新巡检成功，自动解决并发送恢复通知"""
        pending_alerts = self.db.query(Alert).filter(
            Alert.api_id == api.id,
            Alert.status == "pending",
        ).all()

        if pending_alerts:
            now = datetime.now(timezone.utc)
            for alert in pending_alerts:
                alert.status = "resolved"
                alert.resolved_at = now
            self.db.commit()

            types = ", ".join(a.alert_type for a in pending_alerts)
            msg = f"恢复通知: {api.name} 已恢复正常（此前告警: {types}）"
            logger.info(msg)
            NotificationChannel.send("恢复通知", msg)

            # 自动恢复时发送邮件通知
            for alert in pending_alerts:
                self.db.refresh(alert)
                notify_resolve(self.db, alert, api, "系统（自动恢复）")

    def check_escalation(self):
        """告警升级：持续未解决的告警超过阈值(ALERT_ESCALATION_HOURS)时升级通知"""
        from app.core.config import settings
        from app.models.models import Api

        cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.ALERT_ESCALATION_HOURS)
        old_pending = self.db.query(Alert).join(Api, Alert.api_id == Api.id).filter(
            Alert.status == "pending",
            Alert.created_at < cutoff,
        ).all()

        for alert in old_pending:
            msg = f"告警升级: {alert.api.name if alert.api else '未知接口'} 的「{alert.alert_type}」告警已持续超过{settings.ALERT_ESCALATION_HOURS}小时未解决"
            logger.warning(msg)
            NotificationChannel.send("告警升级", msg)

    def get_alerts(self, status: str | None = None, alert_type: str | None = None,
                   api_id: int | None = None, page: int = 1, page_size: int = 20,
                   current_user=None) -> tuple[list[dict], int]:
        """分页查询告警列表，联表返回 api_name。运维角色只查看授权接口的告警"""
        from app.models.models import ApiAuthorization
        q = self.db.query(Alert)
        if status:
            q = q.filter(Alert.status == status)
        if alert_type:
            q = q.filter(Alert.alert_type == alert_type)
        if api_id:
            q = q.filter(Alert.api_id == api_id)

        # 运维角色只查看授权接口的告警
        if current_user and current_user.role == "operator":
            auth_ids = [
                r[0] for r in self.db.query(ApiAuthorization.api_id).filter(
                    ApiAuthorization.user_id == current_user.id
                ).all()
            ]
            if auth_ids:
                q = q.filter(Alert.api_id.in_(auth_ids))
            else:
                # 没有授权任何接口，返回空
                return [], 0

        total = q.count()
        alerts = q.order_by(desc(Alert.created_at)).offset((page - 1) * page_size).limit(page_size).all()

        items = []
        for a in alerts:
            items.append({
                "id": a.id,
                "api_id": a.api_id,
                "api_name": a.api.name if a.api else None,
                "alert_type": a.alert_type,
                "message": a.message,
                "status": a.status,
                "created_at": a.created_at.replace(tzinfo=timezone.utc).astimezone(CST).isoformat(),
                "resolved_at": a.resolved_at.replace(tzinfo=timezone.utc).astimezone(CST).isoformat() if a.resolved_at else None,
            })
        return items, total

    def resolve_alert(self, alert_id: int, resolver: str = "") -> Alert | None:
        """解决告警：设 status=resolved，记录解决时间，发送邮件通知"""
        alert = self.db.query(Alert).filter(Alert.id == alert_id).first()
        if alert and alert.status == "pending":
            alert.status = "resolved"
            alert.resolved_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(alert)
            # 发送解决通知邮件
            if alert.api and resolver:
                notify_resolve(self.db, alert, alert.api, resolver)
        return alert
