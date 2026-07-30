"""告警管理 Pydantic 模型：告警响应"""
from datetime import datetime
from pydantic import BaseModel


class AlertResponse(BaseModel):
    id: int
    api_id: int
    api_name: str | None = None
    alert_type: str
    message: str
    status: str
    created_at: datetime
    resolved_at: datetime | None = None

    model_config = {"from_attributes": True}
