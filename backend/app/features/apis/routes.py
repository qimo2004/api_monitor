"""接口管理路由：接口CRUD、手动巡检、状态概览
- GET  /api/apis               接口列表（搜索/筛选/分页/联表返回最近一次状态）
- GET  /api/apis/status        状态概览
- GET  /api/apis/{id}          接口详情
- POST /api/apis               新增接口 (admin)
- PUT  /api/apis/{id}          编辑接口 (admin)
- DELETE /api/apis/{id}        删除接口 (admin)
- POST /api/apis/{id}/check    手动巡检 (operator/admin)
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from typing import Optional
from app.core.config import get_db
from app.core.deps import get_current_user, require_role
from app.models.models import Api, User, CheckLog, ApiAuthorization
from app.features.apis.schemas import ApiCreate, ApiUpdate, ApiResponse, ApiStatusOverview, ApiBatchImport, ApiBatchImportResponse, ApiBatchCheckInterval, ApiBatchEnabled, ApiBatchDelete, ApiAuthUpdate, CheckLogResponse, ManualCheckResponse, ManualCheckRequest
from app.features.apis.service import CheckService
from app.features.alerts.service import AlertService
from app.core.logger import log_op, get_client_ip

router = APIRouter(prefix="/api", tags=["接口管理"])


@router.get("/apis/authorizations", response_model=dict)
def get_authorizations(
    db: Session = Depends(get_db),
    _: User = Depends(require_role(["admin"])),
):
    """获取所有接口的授权信息 (admin)"""
    from app.models.models import ApiAuthorization
    auths = db.query(ApiAuthorization).all()
    result: dict[int, list[int]] = {}
    for a in auths:
        result.setdefault(a.api_id, []).append(a.user_id)
    return result


@router.put("/apis/{api_id}/authorizations", response_model=dict)
def update_authorizations(
    api_id: int,
    data: ApiAuthUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin"])),
):
    """设置接口的授权用户列表 (admin)：全量替换"""
    from app.models.models import ApiAuthorization
    api = db.query(Api).filter(Api.id == api_id).first()
    if not api:
        raise HTTPException(status_code=404, detail="接口不存在")
    # 删除旧授权
    db.query(ApiAuthorization).filter(ApiAuthorization.api_id == api_id).delete()
    # 添加新授权
    for uid in data.user_ids:
        db.add(ApiAuthorization(api_id=api_id, user_id=uid))
    db.commit()
    log_op(current_user.username, "authorize", "api", api_id,
           f"授权接口-{api.name}[{api.method} {api.url}]: userIds={data.user_ids}",
           ip=get_client_ip(request))
    return {"message": "授权已更新"}


@router.get("/users/{user_id}/authorized-apis", response_model=dict)
def get_user_authorized_apis(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(["admin"])),
):
    """获取指定用户的授权接口列表 (admin)"""
    rows = db.query(ApiAuthorization, Api).join(Api, ApiAuthorization.api_id == Api.id).filter(
        ApiAuthorization.user_id == user_id
    ).order_by(desc(ApiAuthorization.id)).all()

    items = []
    for auth, api in rows:
        from app.features.apis.service import CheckService
        status = CheckService(db).get_api_status(api)
        items.append({
            "id": auth.id,
            "api_id": api.id,
            "name": api.name,
            "url": api.url,
            "method": api.method,
            "group_name": api.group_name,
            "enabled": api.enabled,
            "status": status,
        })
    return {"items": items, "user_id": user_id}


@router.post("/authorizations/batch-delete", response_model=dict)
def batch_delete_authorizations(
    data: dict,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin"])),
):
    """批量删除授权记录 (admin)"""
    ids = data.get("ids", [])
    if not ids:
        raise HTTPException(status_code=400, detail="请选择要删除的授权记录")
    deleted = db.query(ApiAuthorization).filter(ApiAuthorization.id.in_(ids)).delete(synchronize_session=False)
    db.commit()
    log_op(current_user.username, "unauthorize", "authorization", 0,
           f"批量取消授权: 删除{deleted}条授权记录，ids={ids}",
           ip=get_client_ip(request))
    return {"message": f"已取消 {deleted} 条授权", "deleted": deleted}


@router.get("/apis/status", response_model=ApiStatusOverview)
def get_status_overview(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """获取所有接口实时状态概览（健康/故障数量）"""
    check_svc = CheckService(db)
    apis = db.query(Api).filter(Api.enabled == 1).all()
    healthy = down = 0
    for api in apis:
        s = check_svc.get_api_status(api)
        if s == "healthy": healthy += 1
        elif s == "down": down += 1
    return ApiStatusOverview(total=len(apis), healthy=healthy, warning=0, down=down)


@router.get("/apis", response_model=dict)
def list_apis(
    search: Optional[str] = Query(None, description="名称模糊搜索"),
    group_name: Optional[str] = Query(None, description="分组筛选"),
    enabled: Optional[int] = Query(None, description="启用状态: 1/0"),
    tag: Optional[str] = Query(None, description="标签筛选"),
    health: Optional[str] = Query(None, description="健康状态筛选: healthy/warning/down"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取接口列表：支持名称模糊搜索、分组筛选、标签筛选、启用状态筛选、健康状态筛选、分页，每条返回最近一次巡检状态"""
    q = db.query(Api)

    # operator 角色仅查看被授权的接口
    if current_user.role == "operator":
        auth_ids = [r[0] for r in db.query(ApiAuthorization.api_id).filter(
            ApiAuthorization.user_id == current_user.id
        ).all()]
        if auth_ids:
            q = q.filter(Api.id.in_(auth_ids))
        else:
            # 没有授权任何接口，返回空
            return {"items": [], "total": 0, "page": page, "page_size": page_size}

    if search:
        q = q.filter(Api.name.contains(search))
    if group_name:
        q = q.filter(Api.group_name == group_name)
    if enabled is not None:
        q = q.filter(Api.enabled == enabled)
    if tag:
        q = q.filter(Api.tags.contains(tag))

    # 健康状态筛选：匹配 CheckService.get_api_status() 的判定逻辑
    # - healthy: status=success
    # - down:    status=failure
    # 健康筛选只针对已启用的接口（与仪表盘统计一致）
    if health:
        q = q.filter(Api.enabled == 1)
        latest_log_ids = db.query(
            func.max(CheckLog.id).label("max_id")
        ).group_by(CheckLog.api_id).subquery()
        latest_logs = db.query(CheckLog).filter(
            CheckLog.id.in_(latest_log_ids)
        ).subquery()

        if health == "down":
            q = q.join(latest_logs, Api.id == latest_logs.c.api_id).filter(
                latest_logs.c.status == "failure"
            )
        elif health == "healthy":
            q = q.join(latest_logs, Api.id == latest_logs.c.api_id).filter(
                latest_logs.c.status == "success"
            )

    total = q.count()
    apis = q.order_by(desc(Api.id)).offset((page - 1) * page_size).limit(page_size).all()

    items = []
    for api in apis:
        last_log = db.query(CheckLog).filter(
            CheckLog.api_id == api.id
        ).order_by(desc(CheckLog.check_time)).first()
        items.append({
            "id": api.id,
            "name": api.name,
            "url": api.url,
            "method": api.method,
            "headers": api.headers,
            "body": api.body,
            "timeout": api.timeout,
            "expected_status": api.expected_status,
            "expected_response_time": api.expected_response_time,
            "check_interval": api.check_interval,
            "enabled": bool(api.enabled),
            "group_name": api.group_name,
            "tags": api.tags,
            "last_status": last_log.status if last_log else None,
            "last_response_time_ms": last_log.response_time_ms if last_log else None,
            "created_at": api.created_at.isoformat(),
            "updated_at": api.updated_at.isoformat(),
        })

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/apis/{api_id}", response_model=ApiResponse)
def get_api(api_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """获取单个接口详情"""
    api = db.query(Api).filter(Api.id == api_id).first()
    if not api:
        raise HTTPException(status_code=404, detail="接口不存在")
    last_log = db.query(CheckLog).filter(CheckLog.api_id == api_id).order_by(desc(CheckLog.check_time)).first()
    resp = ApiResponse(
        id=api.id, name=api.name, url=api.url, method=api.method,
        headers=api.headers, body=api.body, timeout=api.timeout,
        expected_status=api.expected_status, expected_response_time=api.expected_response_time,
        check_interval=api.check_interval, enabled=bool(api.enabled),
        group_name=api.group_name, tags=api.tags,
        last_status=last_log.status if last_log else None,
        last_response_time_ms=last_log.response_time_ms if last_log else None,
        created_at=api.created_at, updated_at=api.updated_at,
    )
    return resp


@router.post("/apis", response_model=ApiResponse)
def create_api(data: ApiCreate, request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_role(["admin"]))):
    """新增接口配置 (admin)"""
    api = Api(**data.model_dump())
    db.add(api)
    db.commit()
    db.refresh(api)
    log_op(current_user.username, "create", "api", api.id,
           f"新增接口-{api.name}[{api.method} {api.url}]",
           ip=get_client_ip(request))
    return ApiResponse(
        id=api.id, name=api.name, url=api.url, method=api.method,
        headers=api.headers, body=api.body, timeout=api.timeout,
        expected_status=api.expected_status, expected_response_time=api.expected_response_time,
        check_interval=api.check_interval, enabled=bool(api.enabled),
        group_name=api.group_name, tags=api.tags,
        created_at=api.created_at, updated_at=api.updated_at,
    )


@router.post("/apis/batch", response_model=ApiBatchImportResponse)
def batch_create_apis(data: list[ApiBatchImport], request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_role(["admin"]))):
    """批量导入接口 (admin)：导入名称、URL、方法、分组、请求头、请求体、请求体类型，其余用默认值"""
    created = []
    for item in data:
        if not item.name or not item.url:
            continue
        api = Api(
            name=item.name, url=item.url, method=item.method, group_name=item.group_name,
            headers=item.headers, body=item.body, body_type=item.body_type,
        )
        db.add(api)
        db.flush()
        created.append(api)
        log_op(current_user.username, "batch_create", "api", api.id,
               f"批量导入接口-{api.name}({api.url})",
               ip=get_client_ip(request))
    db.commit()
    for api in created:
        db.refresh(api)
    items = [ApiResponse(
        id=api.id, name=api.name, url=api.url, method=api.method,
        headers=api.headers, body=api.body, timeout=api.timeout,
        expected_status=api.expected_status, expected_response_time=api.expected_response_time,
        check_interval=api.check_interval, enabled=bool(api.enabled),
        group_name=api.group_name, tags=api.tags,
        created_at=api.created_at, updated_at=api.updated_at,
    ) for api in created]
    return ApiBatchImportResponse(imported=len(items), items=items)


@router.put("/apis/batch/check-interval", response_model=dict)
def batch_update_check_interval(
    data: ApiBatchCheckInterval,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin"])),
):
    """批量设置接口巡检间隔 (admin)"""
    apis = db.query(Api).filter(Api.id.in_(data.ids)).all()
    if not apis:
        raise HTTPException(status_code=404, detail="未找到指定接口")
    updated_names = []
    for api in apis:
        api.check_interval = data.check_interval
        updated_names.append(api.name)
    db.commit()
    log_op(current_user.username, "batch_update", "api", 0,
           f"批量设置巡检间隔-{data.check_interval}s: {', '.join(updated_names)}",
           ip=get_client_ip(request))
    return {"message": f"已更新 {len(apis)} 个接口的巡检间隔", "updated": len(apis)}


@router.put("/apis/batch/enabled", response_model=dict)
def batch_update_enabled(
    data: ApiBatchEnabled,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin"])),
):
    """批量启用/禁用接口 (admin)"""
    apis = db.query(Api).filter(Api.id.in_(data.ids)).all()
    if not apis:
        raise HTTPException(status_code=404, detail="未找到指定接口")
    updated_names = []
    for api in apis:
        api.enabled = 1 if data.enabled else 0
        updated_names.append(api.name)
    db.commit()
    action = "启用" if data.enabled else "禁用"
    log_op(current_user.username, "batch_update", "api", 0,
           f"批量{action}接口: {', '.join(updated_names)}",
           ip=get_client_ip(request))
    return {"message": f"已{action} {len(apis)} 个接口", "updated": len(apis)}


@router.post("/apis/batch/delete", response_model=dict)
def batch_delete_apis(
    data: ApiBatchDelete,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin"])),
):
    """批量删除接口 (admin)"""
    apis = db.query(Api).filter(Api.id.in_(data.ids)).all()
    if not apis:
        raise HTTPException(status_code=404, detail="未找到指定接口")
    deleted_names = [api.name for api in apis]
    for api in apis:
        db.delete(api)
    db.commit()
    log_op(current_user.username, "batch_delete", "api", 0,
           f"批量删除接口: {', '.join(deleted_names)}",
           ip=get_client_ip(request))
    return {"message": f"已删除 {len(apis)} 个接口", "deleted": len(apis)}


@router.put("/apis/{api_id}", response_model=ApiResponse)
def update_api(api_id: int, data: ApiUpdate, request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_role(["admin"]))):
    """编辑接口配置（部分更新）(admin)"""
    api = db.query(Api).filter(Api.id == api_id).first()
    if not api:
        raise HTTPException(status_code=404, detail="接口不存在")
    changed_fields = [f"{k}={v}" for k, v in data.model_dump(exclude_unset=True).items()]
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(api, key, val)
    db.commit()
    db.refresh(api)
    log_op(current_user.username, "update", "api", api.id,
           f"编辑接口-{api.name}[{api.method} {api.url}]: {', '.join(changed_fields)}",
           ip=get_client_ip(request))
    last_log = db.query(CheckLog).filter(CheckLog.api_id == api_id).order_by(desc(CheckLog.check_time)).first()
    return ApiResponse(
        id=api.id, name=api.name, url=api.url, method=api.method,
        headers=api.headers, body=api.body, timeout=api.timeout,
        expected_status=api.expected_status, expected_response_time=api.expected_response_time,
        check_interval=api.check_interval, enabled=bool(api.enabled),
        group_name=api.group_name, tags=api.tags,
        last_status=last_log.status if last_log else None,
        last_response_time_ms=last_log.response_time_ms if last_log else None,
        created_at=api.created_at, updated_at=api.updated_at,
    )


@router.delete("/apis/{api_id}")
def delete_api(api_id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_role(["admin"]))):
    """删除接口配置及关联日志/告警/统计 (admin)"""
    api = db.query(Api).filter(Api.id == api_id).first()
    if not api:
        raise HTTPException(status_code=404, detail="接口不存在")
    api_name = api.name
    api_url = api.url
    db.delete(api)
    db.commit()
    log_op(current_user.username, "delete", "api", api_id,
           f"删除接口-{api_name}({api_url})",
           ip=get_client_ip(request))
    return {"message": "删除成功"}


@router.post("/apis/{api_id}/check", response_model=ManualCheckResponse)
async def manual_check(
    api_id: int,
    request: Request,
    custom: ManualCheckRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["operator", "admin"]))
):
    """手动触发一次巡检 (operator/admin)。可传入自定义请求参数覆盖接口配置"""
    api = db.query(Api).filter(Api.id == api_id).first()
    if not api:
        raise HTTPException(status_code=404, detail="接口不存在")

    check_svc = CheckService(db)
    alert_svc = AlertService(db)

    if custom:
        log = await check_svc.custom_check_api(
            api, method=custom.method, req_url=custom.url,
            headers=custom.headers, body=custom.body,
            body_type=custom.body_type, timeout=custom.timeout,
        )
    else:
        log = await check_svc.check_api(api)

    alert_msg = alert_svc.check_and_alert(api_id)

    log_resp = CheckLogResponse(
        id=log.id, api_id=log.api_id, api_name=api.name,
        status=log.status, http_status=log.http_status,
        response_time_ms=log.response_time_ms, response_size=log.response_size,
        response_summary=log.response_summary, error_message=log.error_message,
        check_time=log.check_time,
    )
    log_op(current_user.username, "check", "api", api.id,
           f"手动巡检-{api.name}[{api.method} {api.url}]: {log.status}({log.response_time_ms}ms)",
           ip=get_client_ip(request))
    return ManualCheckResponse(
        check_log=log_resp,
        alert_created=alert_msg is not None,
        alert_message=alert_msg,
    )
