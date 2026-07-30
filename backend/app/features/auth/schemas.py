"""用户认证 Pydantic 模型：登录/用户管理请求和响应"""
from datetime import datetime
from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    user: "UserResponse"


class UserCreate(BaseModel):
    username: str
    password: str
    display_name: str
    role: str = "viewer"
    email: str | None = None
    enabled: bool = True


class UserUpdate(BaseModel):
    display_name: str | None = None
    password: str | None = None
    role: str | None = None
    email: str | None = None
    enabled: bool | None = None


class UserResponse(BaseModel):
    id: int
    username: str
    display_name: str
    role: str
    email: str | None = None
    enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
