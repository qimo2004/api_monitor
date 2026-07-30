"""统计分析 Pydantic 模型"""
from pydantic import BaseModel


class CompareRequest(BaseModel):
    api_ids: list[int]
    days: int = 7
