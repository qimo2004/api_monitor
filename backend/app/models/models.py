"""数据模型定义：5张表的 ORM 映射，含字段注释、外键关系、索引
- Api: 接口配置表
- CheckLog: 巡检日志表
- Alert: 告警记录表
- User: 用户表
- ApiAuthorization: 接口授权表
"""
import datetime
from sqlalchemy import String, Text, Integer, SmallInteger, \
    DateTime, ForeignKey, Index
from sqlalchemy.orm import DeclarativeBase, relationship, Mapped, mapped_column
from sqlalchemy.sql import func as sqlfunc


class Base(DeclarativeBase):
    pass


class Api(Base):
    """接口配置表：存储需监控的 API 信息和检测策略"""
    __tablename__ = "apis"

    __table_args__ = (
        Index("idx_api_enabled", "enabled"),
        Index("idx_api_group", "group_name"),
        {"comment": "接口配置表"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="接口ID")
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="接口名称")
    url: Mapped[str] = mapped_column(String(500), nullable=False, comment="接口URL")
    method: Mapped[str] = mapped_column(String(10), nullable=False, comment="HTTP请求方法")
    headers: Mapped[str | None] = mapped_column(Text, nullable=True, comment="请求头(JSON格式)")
    body: Mapped[str | None] = mapped_column(Text, nullable=True, comment="请求体(JSON格式)")
    timeout: Mapped[int] = mapped_column(Integer, nullable=False, default=5000, comment="超时时间(毫秒)")
    expected_status: Mapped[int] = mapped_column(Integer, nullable=False, default=200, comment="期望状态码")
    expected_response_time: Mapped[int] = mapped_column(Integer, nullable=False, default=1000, comment="期望响应时间(毫秒)")
    check_interval: Mapped[int] = mapped_column(Integer, nullable=False, default=300, comment="巡检间隔(秒)")
    enabled: Mapped[bool] = mapped_column(SmallInteger, nullable=False, default=1, comment="是否启用: 1启用 0禁用")
    group_name: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="业务分组")
    tags: Mapped[str | None] = mapped_column(Text, nullable=True, comment="标签(JSON数组)")
    body_type: Mapped[str | None] = mapped_column(String(10), nullable=True, default="json", comment="请求体类型: json/data")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=sqlfunc.now(), comment="创建时间")
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=sqlfunc.now(), onupdate=sqlfunc.now(), comment="更新时间")

    check_logs: Mapped[list["CheckLog"]] = relationship(back_populates="api", cascade="all, delete-orphan")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="api", cascade="all, delete-orphan")


class CheckLog(Base):
    """巡检日志表：记录每次巡检的详细结果"""
    __tablename__ = "check_logs"

    __table_args__ = (
        Index("idx_cl_api_id", "api_id"),
        Index("idx_cl_status", "status"),
        Index("idx_cl_check_time", "check_time"),
        {"comment": "巡检日志表"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="日志ID")
    api_id: Mapped[int] = mapped_column(Integer, ForeignKey("apis.id", ondelete="CASCADE"), nullable=False, comment="关联接口ID")
    status: Mapped[str] = mapped_column(String(20), nullable=False, comment="状态: success/failure")
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="HTTP响应状态码")
    response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="响应时间(毫秒)")
    response_size: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="响应体大小(字节)")
    response_summary: Mapped[str | None] = mapped_column(Text, nullable=True, comment="响应内容摘要")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, comment="错误信息(仅失败时)")
    check_time: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=sqlfunc.now(), comment="巡检时间")

    api: Mapped["Api"] = relationship(back_populates="check_logs")


class Alert(Base):
    """告警记录表：记录触发的告警及处理状态"""
    __tablename__ = "alerts"

    __table_args__ = (
        Index("idx_al_api_id", "api_id"),
        Index("idx_al_type", "alert_type"),
        Index("idx_al_status", "status"),
        Index("idx_al_created_at", "created_at"),
        {"comment": "告警记录表"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="告警ID")
    api_id: Mapped[int] = mapped_column(Integer, ForeignKey("apis.id", ondelete="CASCADE"), nullable=False, comment="关联接口ID")
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False, comment="告警类型: consecutive_failure/response_timeout/status_code_error")
    message: Mapped[str] = mapped_column(String(500), nullable=False, comment="告警消息")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", comment="状态: pending/resolved")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=sqlfunc.now(), comment="创建时间")
    resolved_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True, comment="解决时间")

    api: Mapped["Api"] = relationship(back_populates="alerts")


class User(Base):
    """用户表：存储登录用户信息、角色权限、密码哈希"""
    __tablename__ = "users"

    __table_args__ = (
        Index("idx_user_username", "username", unique=True),
        {"comment": "用户表"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="用户ID")
    username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, comment="用户名")
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False, comment="密码哈希(bcrypt)")
    display_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="显示名称")
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="viewer", comment="角色: admin/operator/viewer")
    email: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="邮箱")
    enabled: Mapped[bool] = mapped_column(SmallInteger, nullable=False, default=1, comment="是否启用")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=sqlfunc.now(), comment="创建时间")
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=sqlfunc.now(), onupdate=sqlfunc.now(), comment="更新时间")


class ApiAuthorization(Base):
    """接口授权表：admin 将接口授权给 operator"""
    __tablename__ = "api_authorizations"

    __table_args__ = (
        Index("idx_auth_api_user", "api_id", "user_id", unique=True),
        Index("idx_auth_user_id", "user_id"),
        {"comment": "接口授权表"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="授权ID")
    api_id: Mapped[int] = mapped_column(Integer, ForeignKey("apis.id", ondelete="CASCADE"), nullable=False, comment="接口ID")
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="用户ID")

    api: Mapped["Api"] = relationship()
    user: Mapped["User"] = relationship()


class CheckLogArchive(Base):
    """巡检日志归档表：存储超过保留期的历史巡检日志"""
    __tablename__ = "check_logs_archive"

    __table_args__ = (
        Index("idx_cla_api_id", "api_id"),
        Index("idx_cla_check_time", "check_time"),
        {"comment": "巡检日志归档表"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="日志ID")
    api_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="关联接口ID")
    status: Mapped[str] = mapped_column(String(20), nullable=False, comment="状态: success/failure")
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="HTTP响应状态码")
    response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="响应时间(毫秒)")
    response_size: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="响应体大小(字节)")
    response_summary: Mapped[str | None] = mapped_column(Text, nullable=True, comment="响应内容摘要")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, comment="错误信息(仅失败时)")
    check_time: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, comment="巡检时间")
    archived_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=sqlfunc.now(), comment="归档时间")


class AlertArchive(Base):
    """告警记录归档表：存储超过保留期的已解决告警"""
    __tablename__ = "alerts_archive"

    __table_args__ = (
        Index("idx_ala_api_id", "api_id"),
        Index("idx_ala_created_at", "created_at"),
        {"comment": "告警记录归档表"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="告警ID")
    api_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="关联接口ID")
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False, comment="告警类型")
    message: Mapped[str] = mapped_column(String(500), nullable=False, comment="告警消息")
    status: Mapped[str] = mapped_column(String(20), nullable=False, comment="状态: resolved")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, comment="创建时间")
    resolved_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True, comment="解决时间")
    archived_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=sqlfunc.now(), comment="归档时间")
