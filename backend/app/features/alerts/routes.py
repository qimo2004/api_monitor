"""告警管理路由：告警查询、告警处理
- GET  /api/alerts             告警列表（筛选/分页）
- POST /api/alerts/{id}/resolve 解决告警 (operator/admin)
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from typing import Optional
from datetime import timezone, timedelta
from app.core.config import get_db
from app.core.deps import get_current_user, require_role
from app.models.models import User
from app.features.alerts.service import AlertService
from app.core.logger import log_op, get_client_ip

router = APIRouter(prefix="/api", tags=["告警管理"])

CST = timezone(timedelta(hours=8))  # 东八区


@router.get("/alerts/today-count", response_model=dict)
def today_alert_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取今日新增告警总数（不受筛选条件影响）"""
    svc = AlertService(db)
    count = svc.get_today_count(current_user=current_user)
    return {"count": count}


@router.get("/alerts", response_model=dict)
def list_alerts(
    status: Optional[str] = Query(None, description="筛选: pending/resolved"),
    alert_type: Optional[str] = Query(None, description="筛选: consecutive_failure/response_timeout/status_code_error"),
    api_id: Optional[int] = Query(None, description="按接口筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """查询告警列表：支持按状态/类型/接口筛选、分页，联表返回 api_name"""
    svc = AlertService(db)
    items, total = svc.get_alerts(status, alert_type, api_id, page, page_size, current_user=current_user)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/alerts/{alert_id}/resolve", response_model=dict)
def resolve_alert(
    alert_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["operator", "admin"])),
):
    """确认/解决告警 (operator/admin)"""
    svc = AlertService(db)
    alert = svc.resolve_alert(alert_id, resolver=current_user.username)
    if not alert:
        raise HTTPException(status_code=404, detail="告警不存在或已解决")
    # 写操作审计日志 (文件)
    api_info = f"[{alert.api.method} {alert.api.url}]" if alert.api else ""
    log_op(current_user.username, "resolve", "alert", alert.id,
           f"解决告警-{alert.alert_type}{api_info}",
           ip=get_client_ip(request))
    return {"message": "告警已解决", "id": alert.id, "status": alert.status,
            "resolved_at": alert.resolved_at.replace(tzinfo=timezone.utc).astimezone(CST).isoformat() if alert.resolved_at else None}
