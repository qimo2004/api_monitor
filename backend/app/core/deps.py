"""依赖注入模块：导出 get_current_user 和 require_role，供路由层直接导入"""
from app.core.security import get_current_user, require_role

__all__ = ["get_current_user", "require_role"]
