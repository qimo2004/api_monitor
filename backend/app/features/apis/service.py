"""巡检引擎服务：执行接口巡检、获取接口实时状态
- check_api: 单接口巡检，发送HTTP请求并记录结果（含重试机制）
- check_all: 全量巡检所有启用接口（支持并发控制）
- get_api_status: 判定接口健康状态(healthy/warning/down)
"""
import json
import asyncio
import httpx
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models.models import Api, CheckLog
from app.core.config import settings


class CheckService:
    MAX_RETRIES = 3  # 最大重试次数
    _semaphore: asyncio.Semaphore | None = None

    @classmethod
    def _get_semaphore(cls) -> asyncio.Semaphore:
        """全局共享并发信号量（基于配置的 MAX_CONCURRENT_CHECKS）"""
        if cls._semaphore is None:
            cls._semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_CHECKS)
        return cls._semaphore

    def __init__(self, db: Session):
        self.db = db

    async def check_api(self, api: Api) -> CheckLog:
        """
        执行单接口巡检（含重试机制）。
        1. 解析 headers/body (JSON字符串)
        2. 用 httpx.AsyncClient 发送请求，失败时最多重试MAX_RETRIES次
        3. 记录响应时间/状态码/body大小/摘要
        4. 异常时记录 error_message
        5. 返回 CheckLog 对象
        """
        headers = json.loads(api.headers) if api.headers else {}
        body = json.loads(api.body) if api.body else None
        start = datetime.now()
        log = CheckLog(api_id=api.id, check_time=start)

        async with self._get_semaphore():
            last_exception = None
            for attempt in range(1, self.MAX_RETRIES + 1):
                try:
                    async with httpx.AsyncClient(timeout=api.timeout / 1000.0) as client:
                        if api.method.upper() == "GET":
                            resp = await client.get(api.url, headers=headers)
                        elif api.method.upper() == "POST":
                            if api.body_type == "data":
                                resp = await client.post(api.url, headers=headers, data=body)
                            else:
                                resp = await client.post(api.url, headers=headers, json=body)
                        elif api.method.upper() == "PUT":
                            if api.body_type == "data":
                                resp = await client.put(api.url, headers=headers, data=body)
                            else:
                                resp = await client.put(api.url, headers=headers, json=body)
                        elif api.method.upper() == "PATCH":
                            if api.body_type == "data":
                                resp = await client.patch(api.url, headers=headers, data=body)
                            else:
                                resp = await client.patch(api.url, headers=headers, json=body)
                        elif api.method.upper() == "DELETE":
                            resp = await client.delete(api.url, headers=headers)
                        else:
                            resp = await client.get(api.url, headers=headers)

                    elapsed = (datetime.now() - start).total_seconds() * 1000
                    log.http_status = resp.status_code
                    log.response_time_ms = int(elapsed)
                    log.response_size = len(resp.content)
                    log.response_summary = resp.text if resp.text else None
                    log.status = "success" if resp.status_code == api.expected_status else "failure"
                    if log.status == "failure":
                        log.error_message = f"状态码异常: 期望{api.expected_status}, 实际{resp.status_code}"
                    break  # 成功则跳出重试循环

                except (httpx.TimeoutException, httpx.RequestError) as e:
                    last_exception = e
                    if attempt < self.MAX_RETRIES:
                        wait = attempt * 2  # 递增等待：2s, 4s, 6s
                        await asyncio.sleep(wait)
                    continue

        if last_exception:
            log.status = "failure"
            if isinstance(last_exception, httpx.TimeoutException):
                log.error_message = f"请求超时(>{api.timeout / 1000}s)，已重试{self.MAX_RETRIES}次"
                log.response_time_ms = api.timeout
            else:
                log.error_message = f"{str(last_exception)}，已重试{self.MAX_RETRIES}次"

        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    async def custom_check_api(self, api: Api, method: str = None, req_url: str = None,
                                headers: str = None, body: str = None,
                                body_type: str = "json", timeout: int = None) -> CheckLog:
        """
        自定义单接口巡检（手动测试用）。
        参数与 check_api 相同，但 method/url/headers/body/body_type/timeout 可覆盖 Api 模型中的值。
        """
        actual_method = (method or api.method).upper()
        actual_url = req_url or api.url
        actual_headers = json.loads(headers) if headers else (json.loads(api.headers) if api.headers else {})
        actual_body = json.loads(body) if body else (json.loads(api.body) if api.body else None)
        actual_body_type = body_type or api.body_type or "json"
        actual_timeout = (timeout or api.timeout) / 1000.0
        start = datetime.now()
        log = CheckLog(api_id=api.id, check_time=start)

        async with self._get_semaphore():
            last_exception = None
            for attempt in range(1, self.MAX_RETRIES + 1):
                try:
                    async with httpx.AsyncClient(timeout=actual_timeout) as client:
                        if actual_method == "GET":
                            resp = await client.get(actual_url, headers=actual_headers)
                        elif actual_method == "POST":
                            if actual_body_type == "data":
                                resp = await client.post(actual_url, headers=actual_headers, data=actual_body)
                            else:
                                resp = await client.post(actual_url, headers=actual_headers, json=actual_body)
                        elif actual_method == "PUT":
                            if actual_body_type == "data":
                                resp = await client.put(actual_url, headers=actual_headers, data=actual_body)
                            else:
                                resp = await client.put(actual_url, headers=actual_headers, json=actual_body)
                        elif actual_method == "PATCH":
                            if actual_body_type == "data":
                                resp = await client.patch(actual_url, headers=actual_headers, data=actual_body)
                            else:
                                resp = await client.patch(actual_url, headers=actual_headers, json=actual_body)
                        elif actual_method == "DELETE":
                            resp = await client.delete(actual_url, headers=actual_headers)
                        else:
                            resp = await client.get(actual_url, headers=actual_headers)

                    elapsed = (datetime.now() - start).total_seconds() * 1000
                    log.http_status = resp.status_code
                    log.response_time_ms = int(elapsed)
                    log.response_size = len(resp.content)
                    log.response_summary = resp.text if resp.text else None
                    log.status = "success" if resp.status_code == api.expected_status else "failure"
                    if log.status == "failure":
                        log.error_message = f"状态码异常: 期望{api.expected_status}, 实际{resp.status_code}"
                    break
                except (httpx.TimeoutException, httpx.RequestError) as e:
                    last_exception = e
                    if attempt < self.MAX_RETRIES:
                        wait = attempt * 2
                        await asyncio.sleep(wait)
                    continue

        if last_exception:
            log.status = "failure"
            if isinstance(last_exception, httpx.TimeoutException):
                log.error_message = f"请求超时(>{actual_timeout}s)，已重试{self.MAX_RETRIES}次"
                log.response_time_ms = int(actual_timeout * 1000)
            else:
                log.error_message = f"{str(last_exception)}，已重试{self.MAX_RETRIES}次"

        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    async def check_all(self) -> list[CheckLog]:
        """全量巡检所有启用(enabled=1)的接口，返回本次巡检日志列表"""
        apis = self.db.query(Api).filter(Api.enabled == 1).all()
        logs = []
        for api in apis:
            log = await self.check_api(api)
            logs.append(log)
        return logs

    def get_api_status(self, api: Api) -> str:
        """根据最近一条巡检日志判定接口健康状态: healthy/down"""
        last_log = self.db.query(CheckLog).filter(
            CheckLog.api_id == api.id
        ).order_by(desc(CheckLog.check_time)).first()
        if last_log is None:
            return "unknown"
        if last_log.status == "success":
            return "healthy"
        return "down"
