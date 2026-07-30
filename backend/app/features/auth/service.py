"""用户认证服务：登录验证、用户CRUD管理
- authenticate: 校验用户名密码，返回 User 或 None
- login: 登录成功返回 JWT Token + 用户信息
- create_user / update_user / delete_user: admin 用户管理
"""
import logging
from sqlalchemy.orm import Session
from app.models.models import User
from app.core.security import hash_password, verify_password, create_access_token

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self, db: Session):
        self.db = db

    def authenticate(self, username: str, password: str) -> User | None:
        """校验用户名密码，成功返回 User 对象，失败返回 None"""
        user = self.db.query(User).filter(User.username == username, User.enabled == 1).first()
        if user:
            result = verify_password(password, user.password_hash)
            logger.info(f"authenticate[{username}]: verify_password={result}, hash_prefix={user.password_hash[:20] if user.password_hash else 'None'}...")
            if result:
                return user
        else:
            logger.info(f"authenticate[{username}]: user not found or disabled")
        return None

    def login(self, username: str, password: str) -> dict | None:
        """用户登录：校验 → 生成Token → 返回 {token, user}"""
        user = self.authenticate(username, password)
        if not user:
            return None
        token = create_access_token({"sub": str(user.id), "role": user.role})
        logger.info(f"用户登录: {username}({user.role})")
        return {
            "token": token,
            "user": {
                "id": user.id,
                "username": user.username,
                "display_name": user.display_name,
                "role": user.role,
                "email": user.email,
                "enabled": bool(user.enabled),
                "created_at": user.created_at,
                "updated_at": user.updated_at,
            },
        }

    def get_users(self, page: int = 1, page_size: int = 20) -> tuple[list, int]:
        """分页获取用户列表"""
        q = self.db.query(User)
        total = q.count()
        users = q.order_by(User.id).offset((page - 1) * page_size).limit(page_size).all()
        return users, total

    def create_user(self, data: dict) -> User:
        """创建新用户"""
        user = User(
            username=data["username"],
            password_hash=hash_password(data["password"]),
            display_name=data["display_name"],
            role=data.get("role", "viewer"),
            email=data.get("email"),
            enabled=data.get("enabled", True),
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update_user(self, user_id: int, data: dict) -> User | None:
        """更新用户信息（部分更新）、包括修改密码"""
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return None
        logger.info(f"update_user[{user_id}]: incoming data keys={list(data.keys())}")
        for key, val in data.items():
            if key == "password" and val:
                logger.info(f"update_user[{user_id}]: hashing new password (len={len(val)})")
                setattr(user, "password_hash", hash_password(val))
            elif key != "password" and val is not None:
                setattr(user, key, val)
        self.db.commit()
        self.db.refresh(user)
        logger.info(f"update_user[{user_id}]: commit ok, username={user.username}")
        return user

    def delete_user(self, user_id: int) -> bool:
        """删除用户"""
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return False
        self.db.delete(user)
        self.db.commit()
        return True
