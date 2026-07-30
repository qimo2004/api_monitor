"""种子数据脚本：为5张表写入测试数据，支持三种数据库连接方式"""
from datetime import datetime, timezone, date, timedelta
from app.core.config import engine, SessionLocal
from app.models import Base
from app.models.models import User, Api, CheckLog, Alert, ApiStatsDaily
from app.core.security import hash_password


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # 清除已有数据
        db.query(ApiStatsDaily).delete()
        db.query(Alert).delete()
        db.query(CheckLog).delete()
        db.query(Api).delete()
        db.query(User).delete()
        db.commit()

        # 1. 用户
        users = [
            User(username="admin", password_hash=hash_password("admin123"), display_name="管理员", role="admin", email="admin@example.com"),
            User(username="operator", password_hash=hash_password("oper123"), display_name="运维张三", role="operator", email="zhangsan@example.com"),
            User(username="viewer", password_hash=hash_password("view123"), display_name="观察者李四", role="viewer", email="lisi@example.com"),
        ]
        db.add_all(users)
        db.commit()

        # 2. 接口
        apis = [
            # 用户指定的公开测试API
            Api(name="JSONPlaceholder 文章列表", url="https://jsonplaceholder.typicode.com/posts", method="GET", timeout=5000, group_name="公开API", tags='["测试","JSON"]'),
            Api(name="JSONPlaceholder 用户列表", url="https://jsonplaceholder.typicode.com/users", method="GET", timeout=5000, group_name="公开API", tags='["测试","JSON"]'),
            Api(name="JSONPlaceholder 评论列表", url="https://jsonplaceholder.typicode.com/comments", method="GET", timeout=5000, group_name="公开API", tags='["测试","JSON"]'),
            Api(name="DummyJSON 产品列表", url="https://dummyjson.com/products", method="GET", timeout=5000, group_name="公开API", tags='["测试","DummyJSON"]'),
            Api(name="DummyJSON 模拟登录", url="https://dummyjson.com/auth/login", method="POST", headers='{"Content-Type":"application/json"}', body='{"username":"emilys","password":"emilyspass"}', body_type="json", timeout=5000, group_name="公开API", tags='["测试","认证"]'),
            Api(name="ReqRes 用户列表", url="https://reqres.in/api/users?page=2", method="GET", timeout=5000, group_name="公开API", tags='["测试"]'),
            Api(name="ReqRes 注册", url="https://reqres.in/api/register", method="POST", headers='{"Content-Type":"application/json","x-api-key":"reqres-free-v1"}', body='{"email":"eve.holt@reqres.in","password":"pistol"}', body_type="json", timeout=5000, group_name="公开API", tags='["测试","认证"]'),
            Api(name="RandomUser 生成", url="https://randomuser.me/api/", method="GET", timeout=5000, group_name="公开API", tags='["测试"]'),
            Api(name="测试端点-健康检查", url="https://jsonplaceholder.typicode.com/posts/1", method="GET", timeout=5000, group_name="测试端点", tags='["监控"]'),
            Api(name="测试端点-用户数据", url="https://jsonplaceholder.typicode.com/users", method="GET", timeout=5000, group_name="测试端点", tags='["监控"]'),
            Api(name="测试端点-慢响应检测", url="https://randomuser.me/api/", method="GET", timeout=10000, expected_response_time=1000, group_name="测试端点", tags='["监控","慢响应"]'),
            Api(name="测试端点-错误模拟", url="https://jsonplaceholder.typicode.com/invalid-path", method="GET", timeout=5000, group_name="测试端点", tags='["监控","错误测试"]'),
            Api(name="测试端点-POST提交", url="https://jsonplaceholder.typicode.com/posts", method="POST", headers='{"Content-Type":"application/json"}', body='{"title":"test","userId":1}', body_type="json", timeout=5000, expected_status=201, group_name="测试端点", tags='["监控"]'),
            # 内部模拟端点（使用稳定公开API）
            Api(name="模拟支付-查询订单", url="https://jsonplaceholder.typicode.com/comments", method="GET", timeout=5000, group_name="支付系统", tags='["核心"]'),
            Api(name="模拟用户-登录", url="https://jsonplaceholder.typicode.com/posts", method="POST", headers='{"Content-Type":"application/json"}', body='{"title":"login","userId":1}', body_type="json", timeout=5000, expected_status=201, group_name="用户服务", tags='["核心"]'),
            Api(name="模拟数据-报表", url="https://jsonplaceholder.typicode.com/albums", method="GET", timeout=5000, group_name="数据服务", tags='["核心"]'),
            Api(name="已禁用-旧接口", url="https://jsonplaceholder.typicode.com/todos", method="GET", timeout=5000, enabled=0, group_name="已废弃", tags='["废弃"]'),
        ]
        db.add_all(apis)
        db.commit()

        # 3. 巡检日志 (每个接口2~4条)
        now = datetime.now(timezone.utc)
        # 给某些特定接口加入失败记录
        failure_apis = {"模拟支付-查询订单", "DummyJSON 模拟登录", "ReqRes 注册"}
        logs = []
        for i, api in enumerate(apis):
            if not api.enabled:
                continue
            log_count = 2 + (i % 3)
            for j in range(log_count):
                is_success = not (api.name in failure_apis and j == 1)
                logs.append(CheckLog(
                    api_id=api.id,
                    status="success" if is_success else "failure",
                    http_status=200 if is_success else 503,
                    response_time_ms=150 + i * 50 + j * 20,
                    response_size=512 + i * 100,
                    error_message=None if is_success else "Service Unavailable",
                    check_time=now - timedelta(minutes=j * 5),
                ))
        db.add_all(logs)
        db.commit()

        # 4. 告警 (通过名称查找对应的 api_id)
        api_map = {a.name: a.id for a in apis}
        alerts = [
            Alert(api_id=api_map.get("模拟支付-查询订单"), alert_type="response_timeout", message="模拟支付-查询订单响应超时(3000ms)", status="pending"),
            Alert(api_id=api_map.get("模拟用户-登录"), alert_type="consecutive_failure", message="模拟用户-登录连续2次巡检失败", status="pending"),
            Alert(api_id=api_map.get("测试端点-慢响应检测"), alert_type="response_timeout", message="测试端点-慢响应检测响应超时", status="pending"),
            Alert(api_id=api_map.get("测试端点-错误模拟"), alert_type="status_code_error", message="测试端点-错误模拟返回异常状态码", status="pending"),
            Alert(api_id=api_map.get("DummyJSON 模拟登录"), alert_type="response_timeout", message="DummyJSON 模拟登录响应超时", status="resolved", resolved_at=now - timedelta(hours=2)),
            Alert(api_id=api_map.get("ReqRes 注册"), alert_type="status_code_error", message="ReqRes 注册返回状态码异常", status="resolved", resolved_at=now - timedelta(hours=1)),
        ]
        db.add_all(alerts)
        db.commit()

        # 5. 日统计
        today = date.today()
        stats = []
        for i, api in enumerate(apis):
            if not api.enabled:
                continue
            for d in range(7):
                day = today - timedelta(days=d)
                total = 100 + i * 10
                failed = i % 3
                stats.append(ApiStatsDaily(
                    api_id=api.id,
                    date=day,
                    total_checks=total,
                    success_count=total - failed,
                    failed_count=failed,
                    timeout_count=i % 4,
                    avg_response_time=150 + i * 30,
                    max_response_time=300 + i * 50,
                    min_response_time=100 + i * 20,
                ))
        db.add_all(stats)
        db.commit()

        print("✅ 种子数据写入成功！")
        print(f"  - users: {len(users)} 条")
        print(f"  - apis: {len(apis)} 条")
        print(f"  - check_logs: {len(logs)} 条")
        print(f"  - alerts: {len(alerts)} 条")
        print(f"  - api_stats_daily: {len(stats)} 条")
    except Exception as e:
        db.rollback()
        print(f"❌ 写入失败: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
