# Code Wiki — 企业接口巡检与稳定性监控系统

> 本文档基于实际源码分析生成，覆盖项目整体架构、主要模块职责、关键类与函数说明、依赖关系以及项目运行方式。
> 版本：v1.0 / 最后更新：2026-07-31

---

## 目录

1. [项目概述](#1-项目概述)
2. [项目整体架构](#2-项目整体架构)
3. [技术栈与依赖关系](#3-技术栈与依赖关系)
4. [后端模块详解](#4-后端模块详解)
5. [前端模块详解](#5-前端模块详解)
6. [数据模型与 ER 关系](#6-数据模型与-er-关系)
7. [关键业务流程](#7-关键业务流程)
8. [项目运行方式](#8-项目运行方式)
9. [配置说明](#9-配置说明)
10. [附录：实际代码与文档差异说明](#10-附录实际代码与文档差异说明)

---

## 1. 项目概述

本项目是一个轻量级的**企业接口巡检与稳定性监控系统**，采用前后端分离架构，实现对核心 API 接口的自动化监控、异常告警和稳定性分析。

- **后端**：FastAPI + SQLAlchemy 2.0 + SQLite，按 feature 模块组织代码，APScheduler 驱动定时巡检。
- **前端**：React 19 + TypeScript + Ant Design + Vite，Zustand 做轻量状态管理，ECharts 做可视化。

核心能力：接口 CRUD、定时/手动巡检、巡检日志查询、自动告警与邮件通知、告警升级/恢复、仪表盘概览、SLA 统计与报表导出（CSV/PDF）、用户认证与角色权限（admin/operator/viewer）、接口授权、操作审计日志。

---

## 2. 项目整体架构

### 2.1 目录结构

```
day_20/
├── backend/                        # 后端（FastAPI + SQLAlchemy + SQLite）
│   ├── app/
│   │   ├── main.py                 # 应用入口：FastAPI 实例、CORS、APScheduler 定时巡检、日志轮转
│   │   ├── api/
│   │   │   └── router.py           # 路由聚合器：汇总各 feature 子路由
│   │   ├── core/                   # 核心基础设施层
│   │   │   ├── config.py           # 配置管理（pydantic-settings）+ DB 引擎 + get_db 依赖
│   │   │   ├── security.py         # JWT 生成/校验、bcrypt 密码哈希、get_current_user/require_role
│   │   │   ├── deps.py             # 依赖注入统一导出
│   │   │   ├── logger.py           # 操作审计日志工具（写入 logs/operation.log）
│   │   │   └── email_notifier.py   # SMTP 邮件通知（告警/恢复）
│   │   ├── features/               # 按业务功能划分的模块（路由+服务+模型）
│   │   │   ├── auth/               # 用户认证与用户管理
│   │   │   ├── apis/               # 接口管理 + 巡检引擎 + 授权
│   │   │   ├── logs/               # 巡检日志查询 + 审计日志下载
│   │   │   ├── alerts/             # 告警管理（检测/聚合/恢复/升级）
│   │   │   └── stats/              # 统计分析 + 仪表盘 + 报表导出
│   │   ├── models/
│   │   │   ├── models.py           # 5 张表的 ORM 定义
│   │   │   └── __init__.py         # 统一导出 Base 与模型类
│   │   ├── schemas/                # （预留目录）
│   │   ├── services/               # （预留目录）
│   │   └── __init__.py
│   ├── requirements.txt            # Python 依赖清单
│   └── seed.py                     # 种子数据脚本（写入测试数据）
├── frontend/                       # 前端（React + Ant Design + Vite）
│   ├── src/
│   │   ├── main.tsx                # 应用入口（createRoot）
│   │   ├── App.tsx                 # 路由配置（React Router v7）
│   │   ├── features/               # 按业务功能划分
│   │   │   ├── auth/               # 登录页 + 状态(store) + API 封装
│   │   │   ├── apis/               # 接口管理页 + API 封装
│   │   │   ├── logs/               # 巡检日志页 + API 封装
│   │   │   ├── alerts/             # 告警管理页 + 铃铛 + 状态 + API
│   │   │   ├── stats/              # 统计报表页 + API 封装
│   │   │   ├── dashboard/          # 仪表盘页
│   │   │   └── users/              # 用户管理 + 用户授权接口页 + API
│   │   └── shared/                 # 共享层
│   │       ├── client.ts           # Axios 实例（自动附 Token + 401 拦截）
│   │       ├── Layout.tsx          # 整体布局（侧栏+顶栏+内容+底部）
│   │       ├── AuthGuard.tsx       # 路由守卫（无 Token → /login）
│   │       └── sound.ts            # 告警提示音（Web Audio API）
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   └── tsconfig*.json
├── docs/                           # 文档目录
│   ├── 项目需求.md
│   ├── 系统功能说明.md
│   └── CodeWiki.md                 # 本文档
└── .gitignore
```

### 2.2 系统架构图

```
┌─────────────────────────────────────────────────────────────┐
│                 前端界面（React SPA · Vite）                  │
│  Login / Dashboard / ApiList / LogList / AlertList /         │
│  Reports / UserManage / UserAuthApis                         │
│  AuthGuard(路由守卫) · Zustand(状态) · Ant Design · ECharts   │
│  NotificationBell(铃铛+音效) · Axios Client(自动附 Token)     │
└───────────────────────┬─────────────────────────────────────┘
                        │ HTTP (Authorization: Bearer <JWT>)
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI 后端 (app/main.py)                │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  api/router.py 聚合 5 个 feature 子路由              │   │
│  │  auth · apis · logs · alerts · stats                 │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌──────────┐  │
│  │ 巡检引擎    │ │ 告警服务   │ │ 统计分析    │ │ 认证鉴权 │  │
│  │ CheckService│ │AlertService│ │StatsService│ │ JWT+角色 │  │
│  └────────────┘ └────────────┘ └────────────┘ └──────────┘  │
│  APScheduler(每60s全量巡检) · 操作审计日志(按日轮转)          │
│  core: config / security / deps / logger / email_notifier    │
│  SQLAlchemy ORM (数据访问层)                                  │
└───────────────────────┬─────────────────────────────────────┘
                        │
           ┌────────────┴────────────┐
           ▼                         ▼
    ┌──────────────┐          ┌──────────────┐
    │  SQLite      │          │  外部 API     │
    │ (5 张表)     │          │ (httpx 巡检)  │
    └──────────────┘          └──────────────┘
```

### 2.3 分层职责

| 层次 | 位置 | 职责 |
|------|------|------|
| 路由层 | `features/*/routes.py` | 接收 HTTP 请求、参数校验、调用 Service、写审计日志、返回响应 |
| 服务层 | `features/*/service.py` | 核心业务逻辑（巡检、告警判定、统计聚合、用户管理） |
| 模型层 | `models/models.py` | ORM 定义，与数据库表一一映射 |
| 核心层 | `core/` | 配置、安全(JWT/密码)、依赖注入、日志、邮件等基础设施 |
| 表现层 | `frontend/src/features/*` | 页面组件 + API 封装 + 局部状态 |
| 共享层 | `frontend/src/shared/` | Axios 实例、布局、路由守卫、声音工具 |

---

## 3. 技术栈与依赖关系

### 3.1 后端依赖（[requirements.txt](file:///f:/day_20/backend/requirements.txt)）

| 依赖 | 版本 | 用途 |
|------|------|------|
| fastapi | 0.115.0 | Web 框架（异步、自动生成 OpenAPI 文档） |
| uvicorn[standard] | 0.30.0 | ASGI 服务器 |
| sqlalchemy | 2.0.35 | ORM（声明式映射 2.0 风格） |
| httpx | 0.27.0 | 异步 HTTP 客户端（巡检目标接口） |
| apscheduler | 3.10.4 | 定时任务调度（全量巡检） |
| python-jose[cryptography] | 3.3.0 | JWT 生成与校验 |
| passlib[bcrypt] / bcrypt | 1.7.4 / 4.0.1 | 密码 bcrypt 哈希 |
| pydantic / pydantic-settings | 2.9.0 / 2.5.0 | 数据校验与配置管理 |
| aiosqlite | 0.20.0 | SQLite 异步驱动（声明，当前 engine 为同步） |
| python-multipart | 0.0.9 | 表单解析 |
| reportlab | 4.2.0 | 声明的 PDF 库（**注意**：实际代码使用 fpdf2，见附录） |

### 3.2 前端依赖（[package.json](file:///f:/day_20/frontend/package.json)）

| 依赖 | 用途 |
|------|------|
| react / react-dom 19 | UI 框架 |
| react-router-dom 7 | 前端路由 |
| antd 6 + @ant-design/icons | 企业级 UI 组件库 |
| axios | HTTP 客户端 |
| zustand | 轻量状态管理 |
| echarts + echarts-for-react | 图表可视化 |
| dayjs | 日期处理 |
| xlsx | Excel 导入/导出（SheetJS） |
| vite 8 + @vitejs/plugin-react + typescript 6 | 构建与类型 |

### 3.3 模块间依赖关系

**后端依赖图（关键调用关系）：**

```
main.py
  ├─→ core.config (engine/SessionLocal)
  ├─→ models (Base.metadata.create_all 建表)
  ├─→ api.router (聚合路由)
  │     ├─→ features.apis.routes
  │     ├─→ features.alerts.routes
  │     ├─→ features.stats.routes
  │     ├─→ features.auth.routes
  │     └─→ features.logs.routes
  ├─→ features.apis.service.CheckService (定时巡检)
  └─→ features.alerts.service.AlertService (告警检测/升级)

features.apis.service.CheckService
  └─→ models.Api / CheckLog, core.config.settings

features.alerts.service.AlertService
  ├─→ models.Alert / CheckLog / Api / ApiAuthorization
  ├─→ core.logger.log_op (NotificationChannel 写审计)
  └─→ core.email_notifier.notify_alert / notify_resolve

features.stats.service.StatsService
  ├─→ models.Api / CheckLog / Alert / ApiAuthorization
  └─→ features.apis.service.CheckService (复用 get_api_status)

features.auth.service.AuthService
  ├─→ models.User
  └─→ core.security (hash_password / verify_password / create_access_token)

所有 routes → core.deps (get_current_user / require_role) → core.security → models.User
所有 routes → core.config.get_db (DB 会话注入)
所有写操作 routes → core.logger.log_op (审计日志)
```

**前端依赖图：**

```
main.tsx → App.tsx (路由)
App.tsx → AuthGuard → shared.Layout (Outlet 渲染子路由)
           └→ features.* 各页面组件

所有 features/*/api.ts → shared/client.ts (Axios 实例)
shared/client.ts → localStorage (Token) → 后端 http://localhost:8000
shared.Layout → features.alerts.NotificationBell → shared.sound
features.* 页面 → 各自 api.ts + 可选 store.ts (Zustand)
```

---

## 4. 后端模块详解

### 4.1 应用入口 — [app/main.py](file:///f:/day_20/backend/app/main.py)

创建 FastAPI 应用实例，承担三项核心职责：

| 职责 | 实现要点 |
|------|----------|
| 自动建表 | `lifespan` 启动时执行 `Base.metadata.create_all(bind=engine)` |
| 定时巡检 | `AsyncIOScheduler` + `IntervalTrigger(seconds=60)` 注册 `scheduled_check` 任务 |
| 审计日志 | `TimedRotatingFileHandler` 按日轮转写入 `logs/operation.log`，保留 90 天 |
| CORS | 允许 `localhost:3000/5173/127.0.0.1:3000` 跨域 |

**关键函数：**

- `scheduled_check()` — 定时全量巡检任务。遍历所有 `enabled==1` 的接口，距上次巡检时间 `< check_interval` 则跳过；调用 `CheckService.check_api()` 执行巡检，再调用 `AlertService.check_and_alert()` 检测告警；每轮结束后调用 `check_escalation()` 检查告警升级。
- `lifespan(app)` — 异步上下文管理器，启动时建表+启动调度器，关闭时停止调度器。

### 4.2 核心层 — [core/](file:///f:/day_20/backend/app/core)

#### [config.py](file:///f:/day_20/backend/app/core/config.py)
- `Settings(BaseSettings)` — 从 `.env` 加载配置：`DATABASE_URL`（默认 SQLite）、`SECRET_KEY`、`ALGORITHM`(HS256)、`ACCESS_TOKEN_EXPIRE_MINUTES`(1440=24h)、`MAX_CONCURRENT_CHECKS`(20)、`ALERT_ESCALATION_HOURS`(2)、SMTP 系列。
- `engine` / `SessionLocal` — SQLAlchemy 引擎与会话工厂（SQLite 时附加 `check_same_thread=False`）。
- `get_db()` — FastAPI 依赖注入，提供 DB 会话并自动关闭。

#### [security.py](file:///f:/day_20/backend/app/core/security.py)
- `hash_password(password)` / `verify_password(plain, hashed)` — bcrypt 哈希与校验。
- `create_access_token(data)` — 生成 JWT（sub=用户ID，含 role，24h 过期）。
- `get_current_user(credentials, db)` — 依赖注入：解析 Bearer Token → 返回 `User` 对象；无/无效 Token 返回 401；用户禁用也返回 401。
- `require_role(required_roles)` — 角色鉴权工厂函数，返回依赖检查器，角色不符返回 403。

#### [deps.py](file:///f:/day_20/backend/app/core/deps.py)
统一导出 `get_current_user` 与 `require_role`，供路由层导入。

#### [logger.py](file:///f:/day_20/backend/app/core/logger.py)
- `op_logger` — 名为 `"operation"` 的 logger，写入审计日志文件。
- `now_cst()` — 返回东八区（UTC+8）ISO 时间字符串。
- `get_client_ip(request)` — 提取客户端 IP（优先 `X-Forwarded-For`）。
- `log_op(user, action, target_type, target_id, detail, ip)` — 标准化写入一条 JSON 审计日志。

#### [email_notifier.py](file:///f:/day_20/backend/app/core/email_notifier.py)
- `_send_email(to_addrs, subject, html_body)` — SMTP 底层发送；未配置 SMTP 时静默跳过。
- `_get_notify_users(db, api)` — 获取通知用户（admin + 被授权的 operator，需有邮箱且启用）。
- `_build_alert_html()` / `_build_resolve_html()` — 构建告警/恢复通知 HTML 邮件。
- `notify_alert(db, alert, api)` — 发送新告警邮件。
- `notify_resolve(db, alert, api, resolver)` — 发送告警解决邮件。

### 4.3 路由聚合 — [api/router.py](file:///f:/day_20/backend/app/api/router.py)

创建顶层 `APIRouter`，按顺序 include 五个 feature 子路由：`apis`、`alerts`、`stats`、`auth`、`logs`。由 `main.py` 通过 `app.include_router(router)` 注册。

### 4.4 数据模型 — [models/models.py](file:///f:/day_20/backend/app/models/models.py)

定义 5 张表（详见第 6 节）：

| 模型类 | 表名 | 说明 |
|--------|------|------|
| `Api` | `apis` | 接口配置表 |
| `CheckLog` | `check_logs` | 巡检日志表 |
| `Alert` | `alerts` | 告警记录表 |
| `User` | `users` | 用户表 |
| `ApiAuthorization` | `api_authorizations` | 接口授权关联表 |

[models/\_\_init\_\_.py](file:///f:/day_20/backend/app/models/__init__.py) 统一导出 `Base, Api, CheckLog, Alert, User, ApiAuthorization`。

### 4.5 Feature 模块

每个 feature 模块遵循 **routes.py（路由）+ service.py（服务）+ schemas.py（Pydantic 模型）** 的三层结构。

---

#### 4.5.1 接口管理模块 — [features/apis/](file:///f:/day_20/backend/app/features/apis)

**[routes.py](file:///f:/day_20/backend/app/features/apis/routes.py)** — 前缀 `/api`，tag「接口管理」。负责接口 CRUD、批量操作、手动巡检、接口授权。

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | `/api/apis` | 认证用户 | 接口列表（搜索/分组/标签/启用/健康筛选/分页；operator 仅见授权接口；联表返回最近一次状态） |
| GET | `/api/apis/status` | 认证用户 | 健康状态概览（healthy/down 计数） |
| GET | `/api/apis/{api_id}` | 认证用户 | 接口详情 |
| POST | `/api/apis` | admin | 新增接口 |
| POST | `/api/apis/batch` | admin | 批量导入接口（仅 name/url/method/group_name） |
| PUT | `/api/apis/{api_id}` | admin | 编辑接口（部分更新） |
| PUT | `/api/apis/batch/check-interval` | admin | 批量设置巡检间隔 |
| PUT | `/api/apis/batch/enabled` | admin | 批量启用/禁用 |
| POST | `/api/apis/batch/delete` | admin | 批量删除 |
| DELETE | `/api/apis/{api_id}` | admin | 删除接口（级联删除日志/告警/统计） |
| POST | `/api/apis/{api_id}/check` | operator/admin | 手动巡检（可传自定义参数覆盖配置） |
| GET | `/api/apis/authorizations` | admin | 获取所有接口授权映射 |
| PUT | `/api/apis/{api_id}/authorizations` | admin | 设置接口授权用户（全量替换） |
| GET | `/api/users/{user_id}/authorized-apis` | admin | 获取用户授权接口列表 |
| POST | `/api/authorizations/batch-delete` | admin | 批量删除授权记录 |

**[service.py](file:///f:/day_20/backend/app/features/apis/service.py)** — `CheckService` 巡检引擎：

- `MAX_RETRIES = 3` — 最大重试次数；`_get_semaphore()` — 基于 `MAX_CONCURRENT_CHECKS` 的全局并发信号量。
- `check_api(api)` — **单接口巡检核心方法**。解析 headers/body(JSON 字符串)→`httpx.AsyncClient` 发请求（GET/POST/PUT/PATCH/DELETE，POST/PUT/PATCH 按 `body_type` 选 json/data）→记录响应时间/状态码/body 大小/摘要→状态码等于 `expected_status` 为 success 否则 failure→失败时递增等待重试（2s/4s/6s）→异常记 error_message→写入 CheckLog 并返回。
- `custom_check_api(api, ...)` — 手动测试用，参数可覆盖 Api 配置（method/url/headers/body/body_type/timeout）。
- `check_all()` — 全量巡检所有启用接口。
- `get_api_status(api)` — 根据最近一条日志判定健康状态：`success→healthy`、`failure→down`、无日志→`unknown`。

**[schemas.py](file:///f:/day_20/backend/app/features/apis/schemas.py)** — 定义 `ApiCreate`、`ApiUpdate`、`ApiResponse`、`ApiStatusOverview`、`ApiBatchImport`、`ApiBatchImportResponse`、`ApiBatchCheckInterval`、`ApiBatchEnabled`、`ApiBatchDelete`、`ApiAuthUpdate`、`CheckLogResponse`、`ManualCheckRequest`、`ManualCheckResponse` 等 Pydantic 模型。

---

#### 4.5.2 巡检日志模块 — [features/logs/](file:///f:/day_20/backend/app/features/logs)

**[routes.py](file:///f:/day_20/backend/app/features/logs/routes.py)** — 前缀 `/api`，tag「日志查询」。

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | `/api/logs` | 认证用户 | 分页查询巡检日志（按接口/状态/时间范围筛选；operator 仅见授权接口） |
| GET | `/api/logs/download` | admin | 下载操作审计日志文件（可指定 date） |
| GET | `/api/logs/{log_id}` | 认证用户 | 单条日志详情（含请求 URL/方法/请求体） |

**[service.py](file:///f:/day_20/backend/app/features/logs/service.py)** — `LogService.get_logs(...)` 分页查询，operator 角色过滤授权接口，联表返回 `api_name` 与 `request_method`。

---

#### 4.5.3 告警管理模块 — [features/alerts/](file:///f:/day_20/backend/app/features/alerts)

**[routes.py](file:///f:/day_20/backend/app/features/alerts/routes.py)** — 前缀 `/api`，tag「告警管理」。

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | `/api/alerts` | 认证用户 | 告警列表（状态/类型/接口筛选/分页；operator 仅见授权接口） |
| GET | `/api/alerts/pending-count` | 认证用户 | 待处理告警总数 |
| GET | `/api/alerts/today-count` | 认证用户 | 今日新增告警总数 |
| POST | `/api/alerts/{alert_id}/resolve` | operator/admin | 解决告警（写审计+发邮件） |

**[service.py](file:///f:/day_20/backend/app/features/alerts/service.py)** — `AlertService` + `NotificationChannel`：

- `NotificationChannel.send(title, message)` — 通知渠道基类，当前实现为写操作审计日志 + logger.warning。可扩展子类对接钉钉/企业微信。
- `AlertService.check_and_alert(api_id)` — 巡检后检测告警，返回告警消息或 None。先 `_check_alerts` 检测新告警；无新告警且最新日志成功时 `_check_recovery` 检测恢复。
- `_check_alerts(api, latest_log)` — 检测三类告警（**告警聚合**：同类型 pending 不重复创建；新告警时发邮件）：
  1. `response_timeout`：响应时间 > `api.timeout`
  2. `status_code_error`：status=failure 且有 http_status
  3. `consecutive_failure`：最近 3 条日志全部 failure
- `_check_recovery(api)` — 存在 pending 告警且最新巡检成功 → 自动解决并发恢复通知邮件。
- `check_escalation()` — 告警升级：pending 且 `created_at` 超过 `ALERT_ESCALATION_HOURS` 的告警发升级通知。
- `get_alerts(...)` / `get_today_count(...)` / `get_pending_count(...)` — 查询方法，operator 角色过滤授权接口。
- `resolve_alert(alert_id, resolver)` — 手动解决告警，记录解决时间并发邮件。

---

#### 4.5.4 统计分析模块 — [features/stats/](file:///f:/day_20/backend/app/features/stats)

**[routes.py](file:///f:/day_20/backend/app/features/stats/routes.py)** — 前缀 `/api`，tag「统计报表」。

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | `/api/dashboard` | 认证用户 | 仪表盘概览（总数/健康分布/今日巡检/待处理告警/最近5条日志） |
| GET | `/api/apis/{api_id}/stats` | 认证用户 | 单接口 SLA 统计（成功率/平均响应时间/SLA达标率/日趋势） |
| GET | `/api/apis/stats/all` | 认证用户 | 所有接口统计概览 |
| POST | `/api/apis/stats/compare` | 认证用户 | 多接口对比统计 |
| GET | `/api/top-slow` | 认证用户 | 最慢接口 TOP N（7天平均响应时间降序） |
| GET | `/api/top-unstable` | 认证用户 | 最不稳定接口 TOP N（7天成功率升序） |
| GET | `/api/reports/export` | admin | 导出报表（csv/pdf，默认 csv） |

**[service.py](file:///f:/day_20/backend/app/features/stats/service.py)** — `StatsService`：

- `get_daily_stats(api_id, days)` — 从 `CheckLog` **实时计算**单接口 SLA（按日期分组聚合：成功率、平均响应时间、SLA 达标率=每日平均响应时间≤期望响应时间的天数比例、日趋势）。> 注：模块底部定义了 `case()` 辅助函数包装 SQLAlchemy 的 `case` 表达式。
- `get_compare_stats(api_ids, days)` — 多接口对比统计。
- `get_all_apis_stats(days)` — 所有启用接口统计概览。
- `get_dashboard(current_user)` — 仪表盘数据（operator 过滤授权接口；统计 healthy/warning/down/disabled、今日巡检/失败、待处理告警、最近5条日志）。
- `get_top_slow(limit)` / `get_top_unstable(limit)` — 从 CheckLog 实时计算排行榜。

**报表导出**（`export_report` 路由内联实现）：
- CSV：用 `csv.writer` 生成。
- PDF：使用 **fpdf2**（`from fpdf import FPDF`），自动查找系统中文字体（simhei/simsun/msyh），绘制数据表、响应时间折线图、成功率柱状图、最慢/最不稳定 TOP10 排行榜。

---

#### 4.5.5 用户认证模块 — [features/auth/](file:///f:/day_20/backend/app/features/auth)

**[routes.py](file:///f:/day_20/backend/app/features/auth/routes.py)** — 前缀 `/api`，tag「用户认证」。

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| POST | `/api/auth/login` | 公开 | 登录（用户名+密码 → JWT Token + 用户信息） |
| POST | `/api/auth/logout` | 认证用户 | 退出登录（无状态 JWT，客户端清 Token） |
| GET | `/api/auth/me` | 认证用户 | 获取当前用户信息 |
| GET | `/api/users` | admin | 用户列表（分页） |
| POST | `/api/users` | admin | 新增用户 |
| PUT | `/api/users/{user_id}` | admin | 编辑用户（含改密码） |
| DELETE | `/api/users/{user_id}` | admin | 删除用户 |

**[service.py](file:///f:/day_20/backend/app/features/auth/service.py)** — `AuthService`：
- `authenticate(username, password)` — 校验用户名密码（用户需 enabled=1），返回 User 或 None。
- `login(username, password)` — 校验通过生成 Token（sub=用户ID, role）返回 `{token, user}`。
- `get_users(page, page_size)` / `create_user(data)` / `update_user(user_id, data)` / `delete_user(user_id)` — 用户 CRUD；`update_user` 中 `password` 字段单独哈希处理。

**[schemas.py](file:///f:/day_20/backend/app/features/auth/schemas.py)** — `LoginRequest`、`LoginResponse`、`UserCreate`、`UserUpdate`、`UserResponse`。

### 4.6 种子数据 — [seed.py](file:///f:/day_20/backend/seed.py)

`seed()` 函数：建表后清空数据，写入测试数据（3 个用户 admin/operator/viewer、17 个接口、巡检日志、6 条告警、7天日统计）。运行方式见第 8 节。

---

## 5. 前端模块详解

### 5.1 入口与路由

- [main.tsx](file:///f:/day_20/frontend/src/main.tsx) — `createRoot` 挂载 `<App />`（StrictMode）。
- [App.tsx](file:///f:/day_20/frontend/src/App.tsx) — `BrowserRouter` + `Routes` 配置：
  - `/login` → Login
  - `/` → `AuthGuard` 包裹 `AppLayout`（嵌套路由 Outlet）
    - `index` → 重定向 `/dashboard`
    - `/dashboard`、`/apis`、`/logs`、`/alerts`、`/reports`、`/users`、`/users/:userId/auth-apis`
  - `*` → 重定向 `/dashboard`

### 5.2 共享层 — [shared/](file:///f:/day_20/frontend/src/shared)

| 文件 | 职责 |
|------|------|
| [client.ts](file:///f:/day_20/frontend/src/shared/client.ts) | Axios 实例，`baseURL=http://localhost:8000`；请求拦截器自动附加 `Authorization: Bearer <token>`；响应拦截器 401 时清 Token 并跳转 `/login` |
| [AuthGuard.tsx](file:///f:/day_20/frontend/src/shared/AuthGuard.tsx) | 路由守卫，无 token 时 `<Navigate to="/login">` 并记录来源页 |
| [Layout.tsx](file:///f:/day_20/frontend/src/shared/Layout.tsx) | 整体布局：PC 端 Sider 侧栏 + Header（NotificationBell + 声音开关 + 用户下拉菜单）+ Content(Outlet) + Footer；移动端 Drawer 抽屉菜单；非 admin 隐藏「用户管理」菜单；admin 下拉菜单含「下载审计日志」 |
| [sound.ts](file:///f:/day_20/frontend/src/shared/sound.ts) | Web Audio API 生成提示音（无需音频文件）；`isSoundEnabled`/`setSoundEnabled` 用 localStorage 持久化开关；`playAlertSound` 播放两段 800→1000→1200Hz 的 sine 波提示音 |

### 5.3 Feature 模块

每个 feature 含页面组件（`.tsx`）+ API 封装（`api.ts`），部分含状态管理（`store.ts`，Zustand）。

| 模块 | 关键文件 | 说明 |
|------|----------|------|
| auth | [Login.tsx](file:///f:/day_20/frontend/src/features/auth/Login.tsx)、[api.ts](file:///f:/day_20/frontend/src/features/auth/api.ts)、[store.ts](file:///f:/day_20/frontend/src/features/auth/store.ts) | 登录表单（用户名+密码+记住我）；登录成功后 admin→仪表盘、operator→接口管理；`useAuthStore` 管理 token/user（localStorage 持久化），提供 `isAuthenticated`/`hasRole` |
| apis | [ApiList.tsx](file:///f:/day_20/frontend/src/features/apis/ApiList.tsx)、[api.ts](file:///f:/day_20/frontend/src/features/apis/api.ts) | 接口管理页（CRUD 抽屉表单 + 批量操作 + Excel 导入/模版下载 + 手动巡检）；`apiApi` 封装全部接口管理 API |
| logs | [LogList.tsx](file:///f:/day_20/frontend/src/features/logs/LogList.tsx)、[api.ts](file:///f:/day_20/frontend/src/features/logs/api.ts) | 巡检日志页（筛选 + 分页 + 详情抽屉）；`logApi` 封装日志查询 |
| alerts | [AlertList.tsx](file:///f:/day_20/frontend/src/features/alerts/AlertList.tsx)、[NotificationBell.tsx](file:///f:/day_20/frontend/src/features/alerts/NotificationBell.tsx)、[api.ts](file:///f:/day_20/frontend/src/features/alerts/api.ts)、[store.ts](file:///f:/day_20/frontend/src/features/alerts/store.ts) | 告警管理页（筛选 + 解决操作 + URL 参数 `?api_id=` 自动筛选）；`NotificationBell` 头部铃铛：轮询待处理告警、检测新告警播放音效、页面标题闪烁「⚠ 有新告警」、获焦清除闪烁；`useAlertStore` 管理 pendingCount |
| stats | [Reports.tsx](file:///f:/day_20/frontend/src/features/stats/Reports.tsx)、[api.ts](file:///f:/day_20/frontend/src/features/stats/api.ts) | 统计报表页（接口选择 + SLA 卡片 + 日趋势图 + TOP10 排行 + 导出）；`statsApi` 封装仪表盘/统计/排行/导出 |
| dashboard | [Dashboard.tsx](file:///f:/day_20/frontend/src/features/dashboard/Dashboard.tsx) | 仪表盘页（统计卡片 + ECharts 饼图/折线图 + 最近日志）；数据通过 `statsApi` 获取 |
| users | [UserManage.tsx](file:///f:/day_20/frontend/src/features/users/UserManage.tsx)、[UserAuthApis.tsx](file:///f:/day_20/frontend/src/features/users/UserAuthApis.tsx)、[api.ts](file:///f:/day_20/frontend/src/features/users/api.ts) | 用户管理页（CRUD + 点击跳转授权接口）；用户授权接口页（查看/批量删除授权） |

### 5.4 前端路由总览

| 路径 | 页面 | 权限 |
|------|------|------|
| `/login` | 登录页 | 公开 |
| `/dashboard` | 仪表盘 | 认证用户 |
| `/apis` | 接口管理 | 认证用户（operator 仅见授权接口） |
| `/logs` | 巡检日志 | 认证用户 |
| `/alerts` | 告警管理 | 认证用户 |
| `/reports` | 统计报表 | 认证用户（导出仅 admin） |
| `/users` | 用户管理 | admin |
| `/users/:userId/auth-apis` | 用户授权接口 | admin |

---

## 6. 数据模型与 ER 关系

### 6.1 表结构概览（[models.py](file:///f:/day_20/backend/app/models/models.py)）

共 5 张表，均使用 SQLAlchemy 2.0 声明式映射（`DeclarativeBase` + `Mapped` + `mapped_column`）。

| 表名 | 模型 | 关键字段 | 关系 |
|------|------|----------|------|
| `apis` | `Api` | name, url, method, headers, body, **body_type**(json/data), timeout, expected_status, expected_response_time, check_interval, enabled, group_name, tags | 1→N CheckLog / Alert（cascade delete） |
| `check_logs` | `CheckLog` | api_id(FK CASCADE), status, http_status, response_time_ms, response_size, response_summary, error_message, check_time | N→1 Api |
| `alerts` | `Alert` | api_id(FK CASCADE), alert_type, message, status(pending/resolved), created_at, resolved_at | N→1 Api |
| `users` | `User` | username(unique), password_hash, display_name, role(admin/operator/viewer), email, enabled | — |
| `api_authorizations` | `ApiAuthorization` | api_id(FK CASCADE), user_id(FK CASCADE) | N→1 Api, N→1 User |

### 6.2 ER 关系图

```
┌──────────────┐        ┌──────────────────┐        ┌─────────────────────┐
│    users     │        │      apis        │        │    check_logs       │
│  (用户表)    │        │  (接口配置表)    │  1  N  │   (巡检日志表)      │
├──────────────┤        ├──────────────────┤◄───────┤                     │
│ id PK        │        │ id PK            │        │ api_id FK→apis.id   │
│ username     │        │ name/url/method  │        │ status/http_status  │
│ password_hash│        │ timeout          │        │ response_time_ms    │
│ role         │        │ expected_status  │        │ check_time          │
│ email/enabled│        │ check_interval   │        └─────────────────────┘
└──────┬───────┘        │ enabled          │
       │                │ group_name/tags  │
       │ 1              │ body_type        │
       │                └────┬─────────────┘
       │                     │ 1
       │              ┌──────┴──┐
       │              ▼ N
       │      ┌──────────────┐
       │      │   alerts     │
       │      │ (告警记录)   │
       │      │ api_id FK    │
       │      │ alert_type   │
       │      │ status       │
       │      └──────────────┘
       │
       └─N─┐
           ▼
   ┌──────────────────────┐
   │ api_authorizations   │  (接口授权关联表)
   │ api_id FK→apis.id    │
   │ user_id FK→users.id  │
   │ (api_id,user_id)uniq │
   └──────────────────────┘
```

### 6.3 外键与级联

| 子表 | 外键字段 | 主表 | 级联 |
|------|----------|------|------|
| check_logs | api_id | apis | CASCADE |
| alerts | api_id | apis | CASCADE |
| api_authorizations | api_id / user_id | apis / users | CASCADE |

---

## 7. 关键业务流程

### 7.1 定时巡检流程

```
APScheduler 每 60s 触发 scheduled_check()
  │
  ├─ 查询所有 enabled==1 的接口
  │
  └─ 对每个接口：
       ├─ 查最近一条 CheckLog，若距上次巡检 < check_interval → 跳过
       └─ CheckService.check_api(api)
            ├─ 解析 headers/body（JSON 字符串）
            ├─ asyncio.Semaphore 并发控制（MAX_CONCURRENT_CHECKS=20）
            ├─ httpx.AsyncClient 发请求（失败重试 3 次，间隔 2s/4s/6s）
            ├─ 判定 status：HTTP 状态码 == expected_status ? success : failure
            ├─ 写入 CheckLog（响应时间/状态码/body大小/摘要/error_message）
            └─ AlertService.check_and_alert(api.id)
                 ├─ _check_alerts：响应超时 / 状态码异常 / 连续3次失败
                 │    └─ 同类型 pending 不重复创建 → 新建 Alert + 发邮件
                 └─ 若无新告警且最新成功 → _check_recovery：自动解决 pending 告警 + 发恢复邮件
  │
  └─ 每轮结束：AlertService.check_escalation() 检查告警升级（>2h 未解决）
```

### 7.2 认证与鉴权流程

```
登录：POST /api/auth/login {username, password}
  └─ AuthService.authenticate → verify_password(bcrypt)
       └─ create_access_token({sub:user.id, role}) → 返回 {token, user}

后续请求：前端 Axios 自动附加 Authorization: Bearer <token>
  └─ get_current_user(credentials, db)
       ├─ jwt.decode → 取 sub → 查 User（需 enabled）
       └─ require_role(["admin"]) → 角色不符返回 403

前端 401 拦截：清 localStorage token/user → 跳转 /login
```

### 7.3 告警处理流程

```
告警产生：巡检触发 → 写入 Alert(status=pending) + 邮件通知 + 审计日志
   │
   ├─ 自动恢复：接口恢复成功 → _check_recovery 自动 resolve + 恢复邮件
   ├─ 手动解决：POST /api/alerts/{id}/resolve → resolve_alert + 邮件 + 审计日志
   └─ 告警升级：pending 超过 ALERT_ESCALATION_HOURS(2h) → check_escalation 升级通知

前端联动：
   NotificationBell 轮询待处理告警 → 检测新告警 → playAlertSound + 标题闪烁
   用户解决告警 → pendingCount 实时减少
```

### 7.4 角色权限矩阵

| 操作 | admin | operator | viewer |
|------|:---:|:---:|:---:|
| 仪表盘/接口列表/日志/告警/报表查看 | ✓ | ✓（仅授权接口） | ✓ |
| 接口 CRUD / 批量操作 / 授权 | ✓ | ✗ | ✗ |
| 手动巡检 | ✓ | ✓ | ✗ |
| 解决告警 | ✓ | ✓ | ✗ |
| 报表导出 / 审计日志下载 | ✓ | ✗ | ✗ |
| 用户管理 | ✓ | ✗ | ✗ |

---

## 8. 项目运行方式

### 8.1 环境准备

- **Python** ≥ 3.10（后端）
- **Node.js** ≥ 18（前端）
- 数据库默认使用 SQLite（零配置，自动生成 `api_monitor.db`）；可在 `.env` 中改 `DATABASE_URL` 切换 PostgreSQL/MySQL

### 8.2 后端启动

```bash
# 1. 进入后端目录
cd backend

# 2. 安装依赖
pip install -r requirements.txt
# 注意：PDF 导出实际依赖 fpdf2，如需 PDF 报表请额外安装
pip install fpdf2

# 3. （可选）写入种子测试数据
python seed.py

# 4. 启动服务（默认 8000 端口）
uvicorn app.main:app --reload --port 8000
```

启动后访问：
- API 服务：`http://localhost:8000`
- Swagger 文档：`http://localhost:8000/docs`
- 根路由：`GET /` 返回服务信息

> 应用启动时会自动建表（`Base.metadata.create_all`）并启动 APScheduler 定时巡检（每 60 秒）。

### 8.3 前端启动

```bash
# 1. 进入前端目录
cd frontend

# 2. 安装依赖
npm install

# 3. 启动开发服务器（默认 5173 端口）
npm run dev

# 4. 生产构建
npm run build      # tsc -b && vite build
npm run preview    # 预览构建产物
```

启动后访问：`http://localhost:5173`

> 前端 Axios `baseURL` 直连 `http://localhost:8000`（见 [client.ts](file:///f:/day_20/frontend/src/shared/client.ts)），后端 CORS 已放行 5173 端口。

### 8.4 默认账号（种子数据）

| 用户名 | 密码 | 角色 |
|--------|------|------|
| admin | admin123 | admin（管理员） |
| operator | oper123 | operator（运维） |
| viewer | view123 | viewer（观察者） |

### 8.5 服务重启约定

> **重要**：本项目需要重启服务时，必须**前端与后端统一全部重启**，不得只重启其中一端。

---

## 9. 配置说明

### 9.1 后端配置（[core/config.py](file:///f:/day_20/backend/app/core/config.py) + `backend/.env`）

通过 `pydantic-settings` 的 `Settings` 类加载，`.env` 文件优先级高于默认值。

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `DATABASE_URL` | `sqlite:///./api_monitor.db` | 数据库连接串 |
| `SECRET_KEY` | `your-secret-key-change-in-production` | JWT 签名密钥（生产需修改） |
| `ALGORITHM` | `HS256` | JWT 算法 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 1440 | Token 有效期（24 小时） |
| `MAX_CONCURRENT_CHECKS` | 20 | 最大并发巡检数 |
| `ALERT_ESCALATION_HOURS` | 2 | 告警升级阈值（小时） |
| `SMTP_HOST` / `SMTP_PORT` | "" / 587 | SMTP 邮件服务器 |
| `SMTP_USER` / `SMTP_PASSWORD` | "" | SMTP 账号/授权码 |
| `SMTP_FROM` | "" | 发件人地址 |

`.env` 示例（被 `.gitignore` 忽略，需自行创建）：

```env
DATABASE_URL=sqlite:///./api_monitor.db
SECRET_KEY=your-secret-key-change-in-production
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=your_email@example.com
SMTP_PASSWORD=your_auth_code
SMTP_FROM=your_email@example.com
```

### 9.2 前端配置

- [vite.config.ts](file:///f:/day_20/frontend/vite.config.ts) — 仅启用 `@vitejs/plugin-react` 插件，无自定义代理（API 直连 8000 端口）。
- [tsconfig.json](file:///f:/day_20/frontend/tsconfig.json) — TypeScript 配置（含 `tsconfig.app.json` / `tsconfig.node.json`）。

### 9.3 关键文件清单

| 文件 | 说明 |
|------|------|
| [backend/app/main.py](file:///f:/day_20/backend/app/main.py) | FastAPI 入口、调度器、日志轮转 |
| [backend/app/api/router.py](file:///f:/day_20/backend/app/api/router.py) | 路由聚合 |
| [backend/app/core/config.py](file:///f:/day_20/backend/app/core/config.py) | 配置与 DB 引擎 |
| [backend/app/core/security.py](file:///f:/day_20/backend/app/core/security.py) | JWT/密码/鉴权 |
| [backend/app/core/logger.py](file:///f:/day_20/backend/app/core/logger.py) | 审计日志 |
| [backend/app/core/email_notifier.py](file:///f:/day_20/backend/app/core/email_notifier.py) | 邮件通知 |
| [backend/app/models/models.py](file:///f:/day_20/backend/app/models/models.py) | 5 张表 ORM |
| [backend/app/features/apis/service.py](file:///f:/day_20/backend/app/features/apis/service.py) | 巡检引擎 |
| [backend/app/features/alerts/service.py](file:///f:/day_20/backend/app/features/alerts/service.py) | 告警服务 |
| [backend/app/features/stats/service.py](file:///f:/day_20/backend/app/features/stats/service.py) | 统计服务 |
| [backend/app/features/auth/service.py](file:///f:/day_20/backend/app/features/auth/service.py) | 认证服务 |
| [backend/seed.py](file:///f:/day_20/backend/seed.py) | 种子数据脚本 |
| [frontend/src/App.tsx](file:///f:/day_20/frontend/src/App.tsx) | 前端路由 |
| [frontend/src/shared/client.ts](file:///f:/day_20/frontend/src/shared/client.ts) | Axios 实例 |
| [frontend/src/shared/Layout.tsx](file:///f:/day_20/frontend/src/shared/Layout.tsx) | 整体布局 |
| [frontend/src/shared/AuthGuard.tsx](file:///f:/day_20/frontend/src/shared/AuthGuard.tsx) | 路由守卫 |
| [frontend/src/shared/sound.ts](file:///f:/day_20/frontend/src/shared/sound.ts) | 提示音工具 |

---

## 10. 附录：实现细节说明

> 以下为代码实现中需要特别注意的若干细节，`项目需求.md` 与 `系统功能说明.md` 已据此同步对齐：

1. **数据模型**：定义 **5 张表**（`Api` / `CheckLog` / `Alert` / `User` / `ApiAuthorization`）；`Api` 表含 `body_type` 字段（`json`/`data`），决定 POST/PUT/PATCH 请求体发送方式（`json=` 或 `data=`）。
2. **PDF 导出依赖**：PDF 导出使用 **fpdf2**（`from fpdf import FPDF`），已在 [requirements.txt](file:///f:/day_20/backend/requirements.txt) 中声明为 `fpdf2>=2.7.0`。
3. **巡检日志模块位置**：巡检日志路由独立位于 [features/logs/](file:///f:/day_20/backend/app/features/logs)（`LogService` + `/api/logs` 端点），与接口管理模块 `features/apis` 分离。
4. **健康状态**：`CheckService.get_api_status()` 仅返回 `healthy`/`down`/`unknown`（无 `warning`），仪表盘统计中 `warning_count` 恒为 0，保留该字段仅为前端兼容。
5. **统计计算方式**：`StatsService` 从 `CheckLog` **实时计算**统计指标（成功率、平均响应时间、SLA 达标率、日趋势、TOP N 排行），不使用预聚合表，无需日终批处理任务。
6. **数据库驱动**：`requirements.txt` 含 `aiosqlite`，但 `engine` 使用同步 `create_engine`（`SessionLocal` 为同步会话）；巡检的异步性体现在 `httpx.AsyncClient` 与 FastAPI 异步路由上。
7. **告警规则**：`AlertService._check_alerts` 当前实现三类告警（`response_timeout` / `status_code_error` / `consecutive_failure`），同类 pending 告警不重复创建；接口恢复成功时自动解决 pending 告警。
