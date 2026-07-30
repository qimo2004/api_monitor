"""用户认证路由：登录/登出、用户管理
- POST /api/auth/login         用户登录
- POST /api/auth/logout        退出登录
- GET  /api/auth/me            获取当前用户信息
- GET  /api/users              用户列表 (admin)
- POST /api/users              创建用户 (admin)
- PUT  /api/users/{id}         编辑用户 (admin)
- DELETE /api/users/{id}       删除用户 (admin)
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from app.core.config import get_db
from app.core.deps import get_current_user, require_role
from app.models.models import User
from app.features.auth.schemas import LoginRequest, LoginResponse, UserCreate, UserUpdate, UserResponse
from app.features.auth.service import AuthService
from app.core.logger import log_op, get_client_ip
from fastapi.responses import Response
router = APIRouter(prefix="/api", tags=["用户认证"])


@router.post("/auth/login", response_model=LoginResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    """用户登录：用户名密码校验 → 返回 JWT Token + 用户信息"""
    svc = AuthService(db)
    result = svc.login(data.username, data.password)
    if not result:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return result


@router.post("/auth/logout")
def logout(current_user: User = Depends(get_current_user)):
    """退出登录：客户端清除 Token（服务端无状态 JWT）"""
    return {"message": "已退出登录"}


@router.get("/auth/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """获取当前登录用户信息"""
    return current_user


@router.get("/users", response_model=dict)
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=1000),
    db: Session = Depends(get_db),
    _: User = Depends(require_role(["admin"])),
):
    """用户列表（分页，仅 admin）"""
    svc = AuthService(db)
    users, total = svc.get_users(page, page_size)
    return {"items": [UserResponse.model_validate(u) for u in users], "total": total, "page": page, "page_size": page_size}


@router.post("/users", response_model=UserResponse)
def create_user(data: UserCreate, request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_role(["admin"]))):
    """新增用户 (admin)"""
    svc = AuthService(db)
    # 检查用户名是否已存在
    existing = db.query(User).filter(User.username == data.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")
    user = svc.create_user(data.model_dump())
    log_op(current_user.username, "create", "user", user.id,
           f"新增用户-{user.username}({user.role})",
           ip=get_client_ip(request))
    return UserResponse.model_validate(user)


@router.put("/users/{user_id}", response_model=UserResponse)
def update_user(user_id: int, data: UserUpdate, request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_role(["admin"]))):
    """编辑用户信息 (admin)"""
    svc = AuthService(db)
    user = svc.update_user(user_id, data.model_dump(exclude_unset=True))
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    changed = [f"{k}={v}" for k, v in data.model_dump(exclude_unset=True).items()]
    log_op(current_user.username, "update", "user", user_id,
           f"编辑用户-{user.username}: {', '.join(changed)}",
           ip=get_client_ip(request))
    return UserResponse.model_validate(user)

@router.delete("/users/{user_id}")
def delete_user(user_id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_role(["admin"]))):
    """删除用户 (admin)"""
    svc = AuthService(db)
    user = db.query(User).filter(User.id == user_id).first()
    username = user.username if user else f"id={user_id}"
    if not svc.delete_user(user_id):
        raise HTTPException(status_code=404, detail="用户不存在")
    log_op(current_user.username, "delete", "user", user_id,
           f"删除用户-{username}",
           ip=get_client_ip(request))
    return {"message": "删除成功"}
