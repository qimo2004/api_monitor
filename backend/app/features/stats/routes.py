"""统计分析路由：仪表盘、SLA统计、排行榜、报表导出
- GET /api/dashboard           仪表盘概览
- GET /api/apis/{id}/stats     SLA统计
- GET /api/top-slow            最慢接口TOP N
- GET /api/top-unstable        最不稳定接口TOP N
- GET /api/reports/export      导出报表 (admin)
"""
from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
from app.core.config import get_db
from app.core.deps import get_current_user, require_role
from app.models.models import User, Api
from app.features.stats.service import StatsService
from app.features.stats.schemas import CompareRequest

router = APIRouter(prefix="/api", tags=["统计报表"])


@router.post("/apis/stats/compare", response_model=dict)
def compare_apis(data: CompareRequest, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """获取多个接口的对比统计数据（含日趋势）"""
    svc = StatsService(db)
    items = svc.get_compare_stats(data.api_ids, data.days)
    return {"items": items, "total": len(items)}


@router.get("/dashboard", response_model=dict)
def get_dashboard(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """获取仪表盘概览数据：总接口数、健康分布、今日巡检、待处理告警、最近5条日志"""
    svc = StatsService(db)
    return svc.get_dashboard(current_user=current_user)


@router.get("/apis/{api_id}/stats", response_model=dict)
def get_api_stats(api_id: int, days: int = Query(7, ge=1, le=365), db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """获取单接口SLA统计：成功率、平均响应时间、SLA达标率、日趋势"""
    svc = StatsService(db)
    return svc.get_daily_stats(api_id, days)


@router.get("/apis/stats/all", response_model=dict)
def get_all_apis_stats(days: int = Query(7, ge=1, le=365), db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """获取所有接口的统计概览"""
    svc = StatsService(db)
    items = svc.get_all_apis_stats(days)
    return {"items": items, "total": len(items)}


@router.get("/top-slow", response_model=list)
def get_top_slow(limit: int = Query(10, ge=1, le=50), db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """最慢接口TOP N（按最近7天平均响应时间降序）"""
    svc = StatsService(db)
    return svc.get_top_slow(limit)


@router.get("/top-unstable", response_model=list)
def get_top_unstable(limit: int = Query(10, ge=1, le=50), db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """最不稳定接口TOP N（按最近7天成功率升序）"""
    svc = StatsService(db)
    return svc.get_top_unstable(limit)


@router.get("/reports/export")
def export_report(
    api_id: Optional[int] = Query(None),
    days: int = Query(7, ge=1, le=365),
    export_format: str = Query("csv", pattern="^(csv|pdf)$"),
    db: Session = Depends(get_db),
    _: User = Depends(require_role(["admin"])),
):
    """导出报表 (admin only)：export_format 支持 csv/pdf，默认 csv"""
    svc = StatsService(db)
    daily_stats = []
    if api_id:
        data = svc.get_daily_stats(api_id, days)
        api_obj = db.query(Api).filter(Api.id == api_id).first()
        api_name = api_obj.name if api_obj else "未知"
        daily_stats = data.get("daily_stats", [])
    else:
        apis = db.query(Api).filter(Api.enabled == 1).all()
        data = {"apis": [{"id": a.id, "name": a.name, **svc.get_daily_stats(a.id, days)} for a in apis]}
        api_name = "全部接口"

    if export_format == "csv":
        import csv, io
        output = io.StringIO()
        writer = csv.writer(output)

        if daily_stats:
            writer.writerow(["日期", "成功率(%)", "平均响应时间(ms)", "SLA达标率(%)"])
            for d in daily_stats:
                writer.writerow([d.get("date", ""), d.get("success_rate", ""), d.get("avg_response_time", ""), ""])
        else:
            writer.writerow(["接口名称", "成功率(%)", "平均响应时间(ms)", "SLA达标率(%)"])
            for a in data.get("apis", []):
                writer.writerow([a.get("name", ""), a.get("success_rate", ""), a.get("avg_response_time", ""), ""])

        return PlainTextResponse(output.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=report.csv"})

    # PDF 导出（使用 fpdf2，完整 CJK 支持）
    try:
        from fpdf import FPDF
        import os

        # ── 查找中文字体 ──
        cn_font_path = None
        for fp in [
            r"C:\Windows\Fonts\simhei.ttf",
            r"C:\Windows\Fonts\simsun.ttc",
            r"C:\Windows\Fonts\simsunb.ttf",
            r"C:\Windows\Fonts\msyh.ttc",
        ]:
            if os.path.exists(fp):
                cn_font_path = fp
                break

        # ── 获取排行榜数据 ──
        top_slow = svc.get_top_slow(10)
        top_unstable = svc.get_top_unstable(10)

        class PDF(FPDF):
            pass

        pdf = PDF(orientation="P", unit="mm", format="A4")
        pdf.set_auto_page_break(auto=True, margin=20)
        pdf.add_page()

        # 注册中文字体
        font_name = "Helvetica"
        if cn_font_path:
            try:
                pdf.add_font("CJK", "", cn_font_path, uni=True)
                font_name = "CJK"
            except Exception:
                pass

        # ── fpdf2 颜色辅助（使用 0-255 整数） ──
        def fill_clr(pdf, r, g, b):
            pdf.set_fill_color(r, g, b)
        def draw_clr(pdf, r, g, b):
            pdf.set_draw_color(r, g, b)
        def text_clr(pdf, r, g, b):
            pdf.set_text_color(r, g, b)

        page_w = 210  # A4 width in mm
        margin = 20
        content_w = page_w - 2 * margin

        # ═══ 标题 ═══
        pdf.set_font(font_name, "", 18)
        pdf.cell(0, 10, "API巡检稳定性报表", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

        pdf.set_font(font_name, "", 9)
        pdf.cell(0, 6, f"接口: {api_name}  |  统计周期: 最近{days}天  |  导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}", align="L", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

        # ═══ 综合指标 ═══
        if data.get("success_rate") is not None:
            pdf.set_font(font_name, "", 10)
            pdf.cell(0, 7, f"综合成功率: {data['success_rate']}%  |  平均响应时间: {data['avg_response_time']}ms  |  SLA达标率: {data['sla_compliance']}%",
                     align="L", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(4)

        # ═══ 数据表 ═══
        table_data = []
        if daily_stats:
            table_data = [["日期", "成功率(%)", "平均响应时间(ms)"]]
            for d in daily_stats:
                table_data.append([str(d.get("date", "")), str(d.get("success_rate", "")), str(d.get("avg_response_time", ""))])
        elif data.get("apis"):
            table_data = [["接口名称", "成功率(%)", "平均响应时间(ms)"]]
            for a in data["apis"]:
                table_data.append([str(a.get("name", "")), str(a.get("success_rate", "")), str(a.get("avg_response_time", ""))])

        if table_data:
            col_w = [70, 45, 45]  # mm
            pdf.set_font(font_name, "", 9)
            for ri, row in enumerate(table_data):
                for ci, cell in enumerate(row):
                    if ri == 0:
                        pdf.set_fill_color(24, 144, 255)  # 表头蓝色
                        pdf.set_text_color(255, 255, 255)
                    else:
                        pdf.set_fill_color(242, 242, 242) if ri % 2 == 0 else pdf.set_fill_color(255, 255, 255)
                        pdf.set_text_color(0, 0, 0)
                    pdf.cell(col_w[ci], 7, str(cell), border=1, align="C", fill=True)
                pdf.ln()

        pdf.ln(5)

        # ── 响应时间趋势图（折线图） ──
        if daily_stats and len(daily_stats) > 0:
            values = [d.get("avg_response_time", 0) or 0 for d in daily_stats]
            labels = [str(d.get("date", ""))[-5:] for d in daily_stats]
            max_val = max(values) * 1.2 or 100

            chart_x = margin + 8
            chart_y = pdf.get_y()
            chart_w = content_w - 16
            chart_h = 75
            plot_area_h = chart_h - 18  # 留出X轴标签空间
            y0 = pdf.get_y() + 7

            # 标题
            pdf.set_font(font_name, "", 10)
            pdf.cell(0, 6, "响应时间趋势图", align="C", new_x="LMARGIN", new_y="NEXT")

            # 背景
            pdf.set_fill_color(250, 250, 250)
            pdf.rect(chart_x, y0, chart_w, chart_h, style="F")
            pdf.set_draw_color(230, 230, 230)

            # Y轴网格（共4条水平线）
            n_grid = 4
            for i in range(n_grid):
                gy = y0 + chart_h - 10 - (i / (n_grid - 1)) * plot_area_h
                val = int(max_val / (n_grid - 1) * i)
                pdf.set_font(font_name, "", 7)
                pdf.set_text_color(153, 153, 153)
                pdf.text(chart_x - 3, gy - 1.5, str(val))
                pdf.set_draw_color(230, 230, 230)
                pdf.line(chart_x + 2, gy, chart_x + chart_w - 2, gy)

            # X轴标签
            n_labels = len(labels)
            for i, lbl in enumerate(labels):
                if n_labels <= 8 or i % max(1, n_labels // 6) == 0:
                    x = chart_x + 2 + (i / max(n_labels - 1, 1)) * (chart_w - 4)
                    pdf.set_font(font_name, "", 7)
                    pdf.set_text_color(153, 153, 153)
                    pdf.text(x - 5, y0 + chart_h - 4, lbl)

            # 折线 + 数据点
            pdf.set_line_width(0.5)
            points_x = []
            points_y_list = []
            denom = max(n_labels - 1, 1)

            for i, v in enumerate(values):
                x = chart_x + 2 + (i / denom) * (chart_w - 4)
                y = y0 + chart_h - 10 - (v / max_val if max_val > 0 else 0) * plot_area_h
                points_x.append(x)
                points_y_list.append(y)

                if i > 0:
                    pdf.set_draw_color(24, 144, 255)
                    pdf.line(points_x[i - 1], points_y_list[i - 1], x, y)

                # 数据点圆
                pdf.set_fill_color(24, 144, 255)
                pdf.circle(x, y, 1.4, style="F")
                pdf.set_draw_color(255, 255, 255)
                pdf.set_line_width(0.3)
                pdf.circle(x, y, 0.8, style="D")  # 白色内点增强视觉效果
                pdf.set_line_width(0.5)

            # 如果只有1个数据点，画一条水平虚线表示当前值
            if n_labels == 1 and len(points_y_list) == 1:
                y = points_y_list[0]
                pdf.set_draw_color(24, 144, 255)
                pdf.set_line_width(0.3)
                for dx in range(0, int(chart_w - 4), 5):
                    x1 = chart_x + 2 + dx
                    x2 = min(x1 + 2, chart_x + chart_w - 2)
                    if x2 > x1:
                        pdf.line(x1, y, x2, y)

            pdf.set_y(y0 + chart_h + 6)
            pdf.set_text_color(0, 0, 0)

        # ── 成功率趋势图（柱状图） ──
        if daily_stats and len(daily_stats) > 0:
            values = [d.get("success_rate", 0) or 0 for d in daily_stats]
            labels = [str(d.get("date", ""))[-5:] for d in daily_stats]
            max_val = 100

            chart_x = margin + 8
            chart_y = pdf.get_y()
            chart_w = content_w - 16
            chart_h = 75
            plot_area_h = chart_h - 18
            y0 = pdf.get_y() + 7

            pdf.set_font(font_name, "", 10)
            pdf.cell(0, 6, "成功率趋势图", align="C", new_x="LMARGIN", new_y="NEXT")

            pdf.set_fill_color(250, 250, 250)
            pdf.rect(chart_x, y0, chart_w, chart_h, style="F")
            pdf.set_draw_color(230, 230, 230)

            # Y轴网格
            n_grid = 4
            for i in range(n_grid):
                gy = y0 + chart_h - 10 - (i / (n_grid - 1)) * plot_area_h
                val = int(max_val / (n_grid - 1) * i)
                pdf.set_font(font_name, "", 7)
                pdf.set_text_color(153, 153, 153)
                pdf.text(chart_x - 3, gy - 1.5, str(val))
                pdf.set_draw_color(230, 230, 230)
                pdf.line(chart_x + 2, gy, chart_x + chart_w - 2, gy)

            # 柱状图
            n_bars = len(values)
            bar_w = max(4, (chart_w - 4) / n_bars * 0.55) if n_bars > 0 else 4
            gap = (chart_w - 4) / n_bars if n_bars > 0 else chart_w
            for i, v in enumerate(values):
                x = chart_x + 2 + i * gap + (gap - bar_w) / 2
                bar_h = (v / max_val) * plot_area_h
                y = y0 + chart_h - 10 - bar_h
                if v >= 90:
                    pdf.set_fill_color(82, 196, 26)
                elif v >= 70:
                    pdf.set_fill_color(250, 173, 20)
                else:
                    pdf.set_fill_color(255, 77, 79)
                pdf.rect(x, y, bar_w, bar_h, style="F")
                # X轴标签
                if n_bars <= 8 or i % max(1, n_bars // 6) == 0:
                    pdf.set_font(font_name, "", 7)
                    pdf.set_text_color(153, 153, 153)
                    pdf.text(x - 2, y0 + chart_h - 4, labels[i])
                # 柱顶数值
                pdf.set_font(font_name, "", 6)
                pdf.set_text_color(102, 102, 102)
                pdf.text(x - 1, y - 2.5, f"{v}%")

            pdf.set_y(y0 + chart_h + 6)
            pdf.set_text_color(0, 0, 0)

        # ═══ 分页：排行榜 ═══
        if top_slow or top_unstable:
            pdf.add_page()

        # 排行榜：固定列宽（CJK 字体下用定宽，保证结构一致）
        name_w = 65    # 名称列 (mm)
        val_w = 18     # 数值列 (mm)
        bar_max = content_w - name_w - val_w  # 柱状图最大宽度 (mm)
        row_h = 6.5    # 行高（含空隙）
        bar_h = 4      # 条的高度（<行高 → 条之间留空隙）

        # 最慢接口TOP10
        if top_slow:
            pdf.set_font(font_name, "", 11)
            pdf.cell(0, 8, "最慢接口排行 TOP10", align="C", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(3)

            max_val = max(item.get("avg_response_time", 0) or 1 for item in top_slow) * 1.2
            # X轴参考刻度
            ref_y = pdf.get_y()
            pdf.set_font(font_name, "", 6)
            pdf.set_text_color(180, 180, 180)
            pdf.set_draw_color(200, 200, 200)
            for pct in [0, 25, 50, 75, 100]:
                v = int(max_val * pct / 100)
                x = pdf.l_margin + name_w + (pct / 100) * bar_max
                pdf.text(x - 3, ref_y, str(v))
                pdf.line(x, ref_y + 1, x, ref_y + 2)
            pdf.ln(5)

            pdf.set_font(font_name, "", 7)
            for i, item in enumerate(top_slow):
                val = item.get("avg_response_time", 0) or 0
                bar_w = (val / max_val) * bar_max
                name = (item.get("name", "") or "")[:18]
                pdf.set_text_color(0, 0, 0)

                pdf.cell(name_w, row_h, f" {i+1}. {name}", align="L", new_x="RIGHT")
                x = pdf.get_x()
                bar_y = pdf.get_y() + (row_h - bar_h) / 2
                if val >= 1000:
                    pdf.set_fill_color(255, 77, 79)
                elif val >= 500:
                    pdf.set_fill_color(250, 173, 20)
                else:
                    pdf.set_fill_color(24, 144, 255)
                pdf.rect(x, bar_y, bar_w, bar_h, style="F")
                pdf.set_x(x + bar_w)
                pdf.cell(val_w, row_h, f"{val}ms", align="L",
                         new_x="LMARGIN", new_y="NEXT")

        pdf.ln(3)

        # 最不稳定接口TOP10
        if top_unstable:
            pdf.set_font(font_name, "", 11)
            pdf.cell(0, 8, "最不稳定接口排行 TOP10", align="C", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(3)

            # X轴参考刻度
            ref_y = pdf.get_y()
            pdf.set_font(font_name, "", 6)
            pdf.set_text_color(180, 180, 180)
            pdf.set_draw_color(200, 200, 200)
            for pct in [0, 25, 50, 75, 100]:
                x = pdf.l_margin + name_w + (pct / 100) * bar_max
                pdf.text(x - 3, ref_y, f"{pct}%")
                pdf.line(x, ref_y + 1, x, ref_y + 2)
            pdf.ln(5)

            pdf.set_font(font_name, "", 7)
            for i, item in enumerate(top_unstable):
                val = item.get("success_rate", 0) or 0
                bar_w = (val / 100) * bar_max
                name = (item.get("name", "") or "")[:18]
                pdf.set_text_color(0, 0, 0)

                pdf.cell(name_w, row_h, f" {i+1}. {name}", align="L", new_x="RIGHT")
                x = pdf.get_x()
                bar_y = pdf.get_y() + (row_h - bar_h) / 2
                if val < 70:
                    pdf.set_fill_color(255, 77, 79)
                elif val < 90:
                    pdf.set_fill_color(250, 173, 20)
                else:
                    pdf.set_fill_color(82, 196, 26)
                pdf.rect(x, bar_y, bar_w, bar_h, style="F")
                pdf.set_x(x + bar_w)
                pdf.cell(val_w, row_h, f"{val}%", align="L",
                         new_x="LMARGIN", new_y="NEXT")

        pdf_bytes = bytes(pdf.output())
        return Response(content=pdf_bytes, media_type="application/pdf",
                        headers={"Content-Disposition": "attachment; filename=report.pdf"})
    except ImportError:
        return {"message": "PDF 导出需要安装 fpdf2: pip install fpdf2", "data": data}
