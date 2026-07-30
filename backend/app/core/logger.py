"""操作审计日志工具：写入 logs/operation.log（共享 op_logger）"""
import json
import datetime
import logging
from fastapi import Request

op_logger = logging.getLogger("operation")


def now_cst() -> str:
    """返回 Asia/Shanghai (UTC+8) 当前时间的 ISO 格式字符串"""
    return datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=8))
    ).isoformat()


def get_client_ip(request: Request) -> str:
    """从请求中提取客户端真实 IP（优先 X-Forwarded-For）"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host or ""
    return ""


def log_op(user: str, action: str, target_type: str, target_id: int,
           detail: str, ip: str = ""):
    """标准化写入操作审计日志（自动填充本地时间戳）"""
    op_logger.info(json.dumps({
        "timestamp": now_cst(),
        "user": user, "ip": ip,
        "action": action,
        "target_type": target_type, "target_id": target_id,
        "detail": detail,
    }, ensure_ascii=False))
