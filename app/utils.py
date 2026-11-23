"""通用工具：登录校验装饰器、金额与日期处理。"""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from functools import wraps

from flask import flash, jsonify, redirect, request, session, url_for


def login_required(view):
    """未登录跳登录页；Ajax 请求返回 401 JSON。"""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            wants_json = (
                request.path.startswith("/api")
                or request.path.startswith("/stats/api")
                or request.headers.get("X-Requested-With") == "XMLHttpRequest"
            )
            if wants_json:
                return jsonify({"code": 401, "msg": "请先登录"}), 401
            flash("请先登录后再访问该页面", "warning")
            return redirect(url_for("auth.login", next=request.full_path))
        return view(*args, **kwargs)
    return wrapped


def parse_amount(raw: str) -> Decimal:
    """把表单里的金额转成 Decimal，非法输入抛 ValueError。"""
    if raw is None or str(raw).strip() == "":
        raise ValueError("金额不能为空")
    try:
        value = Decimal(str(raw).strip())
    except InvalidOperation as exc:
        raise ValueError("金额必须是数字") from exc
    if value < 0:
        raise ValueError("金额不能为负数")
    if value > Decimal("99999999.99"):
        raise ValueError("金额超出允许范围")
    return value.quantize(Decimal("0.01"))


def parse_date(raw: str) -> date:
    """解析 YYYY-MM-DD，非法输入抛 ValueError。"""
    if not raw:
        raise ValueError("日期不能为空")
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("日期格式应为 YYYY-MM-DD") from exc


def parse_month(raw: str) -> str:
    """校验并返回 'YYYY-MM'，非法抛 ValueError。"""
    if not raw:
        raise ValueError("月份不能为空")
    try:
        datetime.strptime(raw, "%Y-%m")
    except ValueError as exc:
        raise ValueError("月份格式应为 YYYY-MM") from exc
    return raw


def month_range(month: str) -> tuple[date, date]:
    """传入 'YYYY-MM'，返回该月 [第一天, 下月第一天) 的日期区间。"""
    year, mon = (int(part) for part in month.split("-"))
    start = date(year, mon, 1)
    end = date(year + (mon == 12), 1 if mon == 12 else mon + 1, 1)
    return start, end


def format_money(value) -> str:
    """Jinja 过滤器：1234.5 -> '1,234.50'。"""
    if value is None:
        return "0.00"
    return f"{Decimal(str(value)):,.2f}"
