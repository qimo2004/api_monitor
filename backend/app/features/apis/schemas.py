"""接口管理 Pydantic 模型：接口创建/更新/响应/状态概览 / 手动巡检"""
from datetime import datetime
from pydantic import BaseModel


class ApiCreate(BaseModel):
    name: str
    url: str
    method: str = "GET"
    headers: str | None = None
    body: str | None = None
    timeout: int = 5000
    expected_status: int = 200
    expected_response_time: int = 1000
    check_interval: int = 300
    enabled: bool = True
    group_name: str | None = None
    tags: str | None = None
    body_type: str = "json"


class ApiUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    method: str | None = None
    headers: str | None = None
    body: str | None = None
    timeout: int | None = None
    expected_status: int | None = None
    expected_response_time: int | None = None
    check_interval: int | None = None
    enabled: bool | None = None
    group_name: str | None = None
    tags: str | None = None
    body_type: str | None = None


class ApiResponse(BaseModel):
    id: int
    name: str
    url: str
    method: str
    headers: str | None = None
    body: str | None = None
    timeout: int
    expected_status: int
    expected_response_time: int
    check_interval: int
    enabled: bool
    group_name: str | None = None
    tags: str | None = None
    body_type: str | None = None
    last_status: str | None = None
    last_response_time_ms: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ApiStatusOverview(BaseModel):
    total: int
    healthy: int
    warning: int
    down: int


class ApiBatchImport(BaseModel):
    """批量导入接口：包含名称、URL、方法、分组、请求头、请求体、请求体类型"""
    name: str
    url: str
    method: str = "GET"
    group_name: str | None = None
    headers: str | None = None
    body: str | None = None
    body_type: str = "json"


class ApiBatchImportResponse(BaseModel):
    """批量导入结果"""
    imported: int
    items: list[ApiResponse]


class ApiBatchCheckInterval(BaseModel):
    """批量设置巡检间隔"""
    ids: list[int]
    check_interval: int


class ApiBatchEnabled(BaseModel):
    """批量启用/禁用"""
    ids: list[int]
    enabled: bool


class ApiBatchDelete(BaseModel):
    """批量删除"""
    ids: list[int]


class ApiAuthUpdate(BaseModel):
    """接口授权更新"""
    user_ids: list[int]


class CheckLogResponse(BaseModel):
    id: int
    api_id: int
    api_name: str | None = None
    status: str
    http_status: int | None = None
    response_time_ms: int | None = None
    response_size: int | None = None
    response_summary: str | None = None
    error_message: str | None = None
    check_time: datetime
    request_url: str | None = None
    request_method: str | None = None
    request_body: str | None = None

    model_config = {"from_attributes": True}


class ManualCheckResponse(BaseModel):
    """手动巡检响应：包含本次巡检结果和是否触发告警"""
    check_log: CheckLogResponse
    alert_created: bool
    alert_message: str | None = None


class ManualCheckRequest(BaseModel):
    """手动巡检自定义参数"""
    method: str = "GET"
    url: str | None = None
    headers: str | None = None
    body: str | None = None
    body_type: str = "json"
    timeout: int = 5000
