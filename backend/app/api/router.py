"""路由聚合器：从 features 导入所有子路由"""
from fastapi import APIRouter
from app.features.apis.routes import router as api_router
from app.features.alerts.routes import router as alert_router
from app.features.stats.routes import router as stats_router
from app.features.auth.routes import router as auth_router
from app.features.logs.routes import router as logs_router

router = APIRouter()
router.include_router(api_router)
router.include_router(alert_router)
router.include_router(stats_router)
router.include_router(auth_router)
router.include_router(logs_router)
