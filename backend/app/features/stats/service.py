"""统计分析服务：接口SLA统计、概览仪表盘、最慢/最不稳定排行榜
- get_daily_stats: 单接口日统计（从CheckLog实时计算）
- get_dashboard: 仪表盘概览数据
- get_top_slow: 最慢接口TOP N（从CheckLog实时计算）
- get_top_unstable: 最不稳定接口TOP N（从CheckLog实时计算）
"""
from datetime import date, timedelta, datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from app.models.models import Api, CheckLog, Alert
from app.features.apis.service import CheckService


class StatsService:
    def __init__(self, db: Session):
        self.db = db

    def get_daily_stats(self, api_id: int, days: int = 7) -> dict:
        """从 CheckLog 实时计算单接口SLA统计：成功率、平均响应时间、SLA达标率、日趋势"""
        cutoff = date.today() - timedelta(days=days)
        cutoff_dt = datetime.combine(cutoff, datetime.min.time())

        # 获取接口的期望响应时间作为 SLA 超时阈值
        api = self.db.query(Api.expected_response_time).filter(Api.id == api_id).first()
        sla_timeout_threshold = api[0] if api else 1000

        # 按日期分组聚合
        rows = self.db.query(
            func.date(CheckLog.check_time).label("log_date"),
            func.count(CheckLog.id).label("total"),
            func.sum(case((CheckLog.status == "success", 1), else_=0)).label("success"),
            func.sum(case((CheckLog.status == "failure", 1), else_=0)).label("failed"),
            func.avg(CheckLog.response_time_ms).label("avg_time"),
            func.sum(case((CheckLog.response_time_ms > sla_timeout_threshold, 1), else_=0)).label("timeout_count"),
        ).filter(
            CheckLog.api_id == api_id,
            CheckLog.check_time >= cutoff_dt,
        ).group_by(
            func.date(CheckLog.check_time)
        ).order_by("log_date").all()

        total_checks = sum(r.total for r in rows)
        total_success = sum(r.success for r in rows)
        success_rate = round(total_success / total_checks * 100, 2) if total_checks else 0
        avg_time_all = round(sum(r.avg_time or 0 for r in rows) / len(rows)) if rows else 0

        # SLA 达标率：每日平均响应时间 <= 期望响应时间的天数比例
        sla_ok_days = sum(1 for r in rows if r.success > 0 and (r.avg_time or 0) <= sla_timeout_threshold)
        sla_compliance = round(sla_ok_days / len(rows) * 100, 2) if rows else 0

        daily = [{
            "date": str(r.log_date),
            "success_rate": round(r.success / r.total * 100, 2) if r.total else 0,
            "avg_response_time": round(r.avg_time) if r.avg_time else 0,
        } for r in rows]

        return {
            "success_rate": success_rate,
            "avg_response_time": avg_time_all,
            "sla_compliance": sla_compliance,
            "daily_stats": daily,
        }

    def get_compare_stats(self, api_ids: list[int], days: int = 7) -> list[dict]:
        """获取多个接口的对比统计数据（含日趋势）"""
        apis = self.db.query(Api).filter(Api.id.in_(api_ids), Api.enabled == 1).all()
        result = []
        for api in apis:
            data = self.get_daily_stats(api.id, days)
            result.append({
                "api_id": api.id,
                "name": api.name,
                "method": api.method,
                "url": api.url,
                "group_name": api.group_name,
                "success_rate": data["success_rate"],
                "avg_response_time": data["avg_response_time"],
                "sla_compliance": data["sla_compliance"],
                "daily_stats": data.get("daily_stats", []),
            })
        return result

    def get_all_apis_stats(self, days: int = 7) -> list[dict]:
        """获取所有已启用接口的统计概览（成功率、平均响应时间、SLA达标率）"""
        apis = self.db.query(Api).filter(Api.enabled == 1).all()
        result = []
        for api in apis:
            data = self.get_daily_stats(api.id, days)
            result.append({
                "api_id": api.id,
                "name": api.name,
                "method": api.method,
                "url": api.url,
                "group_name": api.group_name,
                "success_rate": data["success_rate"],
                "avg_response_time": data["avg_response_time"],
                "sla_compliance": data["sla_compliance"],
            })
        return result

    def get_dashboard(self, current_user=None) -> dict:
        """获取仪表盘概览数据"""
        # 运维角色只统计被授权的接口
        from app.models.models import ApiAuthorization, User
        auth_api_ids = None
        if current_user and current_user.role == "operator":
            auth_api_ids = [
                r[0] for r in self.db.query(ApiAuthorization.api_id).filter(
                    ApiAuthorization.user_id == current_user.id
                ).all()
            ]
            if not auth_api_ids:
                # 没有授权任何接口，返回空数据
                return {
                    "total_apis": 0, "healthy_count": 0, "warning_count": 0,
                    "down_count": 0, "disabled_count": 0,
                    "today_checks": 0, "today_failures": 0,
                    "pending_alerts": 0, "recent_logs": [],
                }

        total_apis_query = self.db.query(Api)
        if auth_api_ids is not None:
            total_apis_query = total_apis_query.filter(Api.id.in_(auth_api_ids))
        total_apis = total_apis_query.count()
        check_svc = CheckService(self.db)

        healthy = warning = down = disabled = 0
        api_query = self.db.query(Api)
        if auth_api_ids is not None:
            api_query = api_query.filter(Api.id.in_(auth_api_ids))
        for api in api_query.all():
            if not api.enabled:
                disabled += 1
                continue
            status = check_svc.get_api_status(api)
            if status == "healthy":
                healthy += 1
            elif status == "warning":
                warning += 1
            elif status == "down":
                down += 1

        today_str = date.today().isoformat()
        check_query = self.db.query(CheckLog).filter(func.date(CheckLog.check_time) == today_str)
        if auth_api_ids is not None:
            check_query = check_query.filter(CheckLog.api_id.in_(auth_api_ids))
        today_checks = check_query.count()

        fail_query = self.db.query(CheckLog).filter(
            func.date(CheckLog.check_time) == today_str,
            CheckLog.status == "failure",
        )
        if auth_api_ids is not None:
            fail_query = fail_query.filter(CheckLog.api_id.in_(auth_api_ids))
        today_failures = fail_query.count()

        alert_query = self.db.query(Alert).filter(Alert.status == "pending")
        if auth_api_ids is not None:
            alert_query = alert_query.filter(Alert.api_id.in_(auth_api_ids))
        pending_alerts = alert_query.count()

        recent_query = self.db.query(CheckLog)
        if auth_api_ids is not None:
            recent_query = recent_query.filter(CheckLog.api_id.in_(auth_api_ids))
        recent_logs = recent_query.order_by(desc(CheckLog.check_time)).limit(5).all()
        recent = [{
            "id": l.id,
            "api_name": l.api.name if l.api else None,
            "status": l.status,
            "response_time_ms": l.response_time_ms,
            "check_time": l.check_time.isoformat(),
        } for l in recent_logs]

        return {
            "total_apis": total_apis,
            "healthy_count": healthy,
            "warning_count": warning,
            "down_count": down,
            "disabled_count": disabled,
            "today_checks": today_checks,
            "today_failures": today_failures,
            "pending_alerts": pending_alerts,
            "recent_logs": recent,
        }

    def get_top_slow(self, limit: int = 10) -> list[dict]:
        """从 CheckLog 实时计算最近7天平均响应时间最慢的接口 TOP N"""
        cutoff = datetime.combine(date.today() - timedelta(days=7), datetime.min.time())
        rows = self.db.query(
            CheckLog.api_id,
            func.avg(CheckLog.response_time_ms).label("avg_time"),
        ).filter(
            CheckLog.check_time >= cutoff
        ).group_by(CheckLog.api_id).order_by(
            desc("avg_time")
        ).limit(limit).all()

        result = []
        for i, row in enumerate(rows):
            api = self.db.query(Api).filter(Api.id == row.api_id).first()
            result.append({
                "rank": i + 1,
                "api_id": row.api_id,
                "name": api.name if api else "未知",
                "avg_response_time": round(row.avg_time, 1) if row.avg_time else 0,
            })
        return result

    def get_top_unstable(self, limit: int = 10) -> list[dict]:
        """从 CheckLog 实时计算最近7天成功率最低的接口 TOP N"""
        cutoff = datetime.combine(date.today() - timedelta(days=7), datetime.min.time())
        rows = self.db.query(
            CheckLog.api_id,
            func.count(CheckLog.id).label("total"),
            func.sum(case((CheckLog.status == "success", 1), else_=0)).label("success"),
        ).filter(
            CheckLog.check_time >= cutoff
        ).group_by(CheckLog.api_id).order_by(
            (func.sum(case((CheckLog.status == "success", 1), else_=0)) / func.count(CheckLog.id)).asc()
        ).limit(limit).all()

        result = []
        for i, row in enumerate(rows):
            api = self.db.query(Api).filter(Api.id == row.api_id).first()
            success_rate = round(row.success / row.total * 100, 2) if row.total else 0
            result.append({
                "rank": i + 1,
                "api_id": row.api_id,
                "name": api.name if api else "未知",
                "success_rate": success_rate,
            })
        return result


def case(whens, else_=None):
    """SQLAlchemy CASE 表达式辅助函数"""
    from sqlalchemy import case as sa_case
    return sa_case(whens, else_=else_)
