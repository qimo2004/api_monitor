"""FastAPI 应用入口：创建应用实例、注册路由、配置定时巡检调度与数据归档
- 启动时自动建表（Base.metadata.create_all）
- APScheduler 定时全量巡检（每60秒检查一次）
- APScheduler 定时数据归档（每月1号凌晨2点，保留最近90天数据）
- 操作日志写入 logs/operation.log（按日轮转）
"""
import logging
import logging.handlers
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from app.core.config import engine, SessionLocal
from app.models import Base
from app.api.router import router
from app.features.apis.service import CheckService
from app.features.alerts.service import AlertService
from app.core.logger import op_logger

# ---------- 操作审计日志配置（按日轮转，写入 logs/operation.log） ----------
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

op_logger.setLevel(logging.INFO)
op_handler = logging.handlers.TimedRotatingFileHandler(
    os.path.join(LOG_DIR, "operation.log"), when="midnight", interval=1, backupCount=90, encoding="utf-8",
)
op_handler.setFormatter(logging.Formatter("%(message)s"))
op_logger.addHandler(op_handler)
op_logger.propagate = False

# ---------- 定时调度 ----------
scheduler = AsyncIOScheduler()


async def scheduled_check():
    """定时全量巡检任务：遍历所有启用接口，距上次巡检时间 ≥ check_interval 才执行"""
    db = SessionLocal()
    try:
        from app.models.models import Api, CheckLog
        from sqlalchemy import desc
        import datetime

        apis = db.query(Api).filter(Api.enabled == 1).all()
        now = datetime.datetime.now()
        check_svc = CheckService(db)
        alert_svc = AlertService(db)

        for api in apis:
            last_log = db.query(CheckLog).filter(
                CheckLog.api_id == api.id
            ).order_by(desc(CheckLog.check_time)).first()

            if last_log:
                elapsed = (now - last_log.check_time).total_seconds()
                if elapsed < api.check_interval:
                    continue

            log = await check_svc.check_api(api)
            alert_svc.check_and_alert(api.id)

        # 每轮巡检后检查告警升级
        alert_svc.check_escalation()
    except Exception as e:
        logging.getLogger(__name__).error(f"定时巡检异常: {e}")
    finally:
        db.close()


def run_data_archive():
    """数据归档任务：将超过保留期(90天)的巡检日志和已解决告警迁移到归档表后删除"""
    import datetime
    from app.models.models import CheckLog, Alert, CheckLogArchive, AlertArchive

    db = SessionLocal()
    logger = logging.getLogger(__name__)
    try:
        cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=90)

        # 1. 归档巡检日志（超过90天的）
        old_logs = db.query(CheckLog).filter(CheckLog.check_time < cutoff).all()
        archived_log_count = 0
        for log in old_logs:
            archive = CheckLogArchive(
                api_id=log.api_id,
                status=log.status,
                http_status=log.http_status,
                response_time_ms=log.response_time_ms,
                response_size=log.response_size,
                response_summary=log.response_summary,
                error_message=log.error_message,
                check_time=log.check_time,
            )
            db.add(archive)
            db.delete(log)
            archived_log_count += 1
        if archived_log_count > 0:
            db.commit()
            logger.info(f"归档完成：巡检日志 {archived_log_count} 条已迁移到 check_logs_archive")
        else:
            logger.info("归档检查：无超过90天的巡检日志需要归档")

        # 2. 归档已解决的告警（超过90天的）
        old_alerts = db.query(Alert).filter(
            Alert.status == "resolved",
            Alert.resolved_at < cutoff,
        ).all()
        archived_alert_count = 0
        for alert in old_alerts:
            archive = AlertArchive(
                api_id=alert.api_id,
                alert_type=alert.alert_type,
                message=alert.message,
                status=alert.status,
                created_at=alert.created_at,
                resolved_at=alert.resolved_at,
            )
            db.add(archive)
            db.delete(alert)
            archived_alert_count += 1
        if archived_alert_count > 0:
            db.commit()
            logger.info(f"归档完成：已解决告警 {archived_alert_count} 条已迁移到 alerts_archive")
        else:
            logger.info("归档检查：无超过90天的已解决告警需要归档")

    except Exception as e:
        db.rollback()
        logger.error(f"数据归档异常: {e}")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时建表 + 启动调度器；关闭时停止调度器"""
    Base.metadata.create_all(bind=engine)
    scheduler.add_job(
        scheduled_check,
        trigger=IntervalTrigger(seconds=60),
        id="check_all_apis",
        name="全量接口巡检（每60秒）",
        replace_existing=True,
    )
    scheduler.add_job(
        run_data_archive,
        trigger=CronTrigger(day=1, hour=2, minute=0),
        id="data_archive",
        name="数据归档（每月1号凌晨2点）",
        replace_existing=True,
    )
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


# ---------- FastAPI 应用 ----------
app = FastAPI(
    title="企业接口巡检与稳定性监控系统",
    description="定时调用接口、状态记录、异常告警、稳定性报表",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
def root():
    return {"service": "企业接口巡检与稳定性监控系统", "version": "1.0.0", "docs": "/docs"}
