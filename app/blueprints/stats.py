"""统计模块：三张图表的聚合接口 + 月度预算。"""
import calendar
from datetime import date
from decimal import Decimal

from flask import Blueprint, jsonify, render_template, request, session
from sqlalchemy import func

from ..extensions import db
from ..models import Budget, Category, Record
from ..utils import login_required, month_range, parse_amount, parse_month

stats_bp = Blueprint("stats", __name__)


def _uid() -> int:
    return session["user_id"]


def _month_or_current() -> str:
    return parse_month(request.args.get("month") or date.today().strftime("%Y-%m"))


def _sum_by_type(start, end) -> dict:
    rows = db.session.execute(
        db.select(Record.type, func.coalesce(func.sum(Record.amount), 0))
        .where(Record.user_id == _uid(),
               Record.record_date >= start,
               Record.record_date < end)
        .group_by(Record.type)
    ).all()
    totals = {"income": Decimal("0.00"), "expense": Decimal("0.00")}
    for kind, total in rows:
        totals[kind] = Decimal(total or 0)
    return totals


@stats_bp.route("/")
@login_required
def index():
    return render_template("stats.html", month=date.today().strftime("%Y-%m"))


@stats_bp.route("/api/summary")
@login_required
def api_summary():
    """本月收支汇总 + 预算使用率（页面顶部指标卡）。"""
    try:
        month = _month_or_current()
    except ValueError as exc:
        return jsonify({"code": 400, "msg": str(exc)}), 400

    start, end = month_range(month)
    totals = _sum_by_type(start, end)
    budget = db.session.scalar(
        db.select(Budget.amount).where(Budget.user_id == _uid(), Budget.month == month))

    spent = float(totals["expense"])
    percent = None
    if budget and float(budget) > 0:
        percent = round(spent / float(budget) * 100, 1)

    return jsonify({"code": 0, "data": {
        "month": month,
        "income": float(totals["income"]),
        "expense": spent,
        "balance": float(totals["income"] - totals["expense"]),
        "budget": float(budget) if budget else None,
        "budget_percent": percent,
    }})


@stats_bp.route("/api/pie")
@login_required
def api_pie():
    """当月支出按分类占比。"""
    try:
        month = _month_or_current()
    except ValueError as exc:
        return jsonify({"code": 400, "msg": str(exc)}), 400

    start, end = month_range(month)
    rows = db.session.execute(
        db.select(Category.name, func.sum(Record.amount).label("total"))
        .join(Record, Record.category_id == Category.id)
        .where(Record.user_id == _uid(),
               Record.type == "expense",
               Record.record_date >= start,
               Record.record_date < end)
        .group_by(Category.id, Category.name)
        .order_by(func.sum(Record.amount).desc())
    ).all()

    return jsonify({"code": 0,
                    "data": [{"name": name, "value": float(total)} for name, total in rows]})


@stats_bp.route("/api/bar")
@login_required
def api_bar():
    """近 N 个月收支并列对比；没有数据的月份补 0，保证 x 轴连续。"""
    months = request.args.get("months", 6, type=int) or 6
    months = min(max(months, 3), 12)          # 防御：只允许 3~12 个月

    today = date.today()
    y, m = today.year, today.month - (months - 1)
    while m <= 0:
        y, m = y - 1, m + 12
    start = date(y, m, 1)

    rows = db.session.execute(
        db.select(func.year(Record.record_date).label("y"),
                  func.month(Record.record_date).label("m"),
                  Record.type,
                  func.coalesce(func.sum(Record.amount), 0).label("total"))
        .where(Record.user_id == _uid(), Record.record_date >= start)
        .group_by("y", "m", Record.type)
    ).all()

    bucket: dict[str, dict[str, float]] = {}
    for ry, rm, kind, total in rows:
        key = f"{ry:04d}-{rm:02d}"
        bucket.setdefault(key, {"income": 0.0, "expense": 0.0})[kind] = float(total)

    axis: list[str] = []
    cy, cm = y, m
    for _ in range(months):
        axis.append(f"{cy:04d}-{cm:02d}")
        cy, cm = (cy + 1, 1) if cm == 12 else (cy, cm + 1)

    return jsonify({"code": 0, "data": {
        "months": axis,
        "income": [bucket.get(k, {}).get("income", 0.0) for k in axis],
        "expense": [bucket.get(k, {}).get("expense", 0.0) for k in axis],
    }})


@stats_bp.route("/api/line")
@login_required
def api_line():
    """当月每日支出；没记账的日期补 0，天数按实际月份计算。"""
    try:
        month = _month_or_current()
    except ValueError as exc:
        return jsonify({"code": 400, "msg": str(exc)}), 400

    start, end = month_range(month)
    days_in_month = calendar.monthrange(start.year, start.month)[1]

    rows = db.session.execute(
        db.select(func.day(Record.record_date).label("d"),
                  func.coalesce(func.sum(Record.amount), 0).label("total"))
        .where(Record.user_id == _uid(),
               Record.type == "expense",
               Record.record_date >= start,
               Record.record_date < end)
        .group_by("d")
    ).all()

    by_day = {int(day): float(total) for day, total in rows}
    return jsonify({"code": 0, "data": {
        "days": [f"{day}日" for day in range(1, days_in_month + 1)],
        "values": [by_day.get(day, 0.0) for day in range(1, days_in_month + 1)],
    }})


@stats_bp.route("/api/budget", methods=["GET", "POST"])
@login_required
def api_budget():
    """查询/设置某月预算（加分项）。"""
    if request.method == "GET":
        try:
            month = _month_or_current()
        except ValueError as exc:
            return jsonify({"code": 400, "msg": str(exc)}), 400
        amount = db.session.scalar(
            db.select(Budget.amount).where(Budget.user_id == _uid(), Budget.month == month))
        return jsonify({"code": 0, "data": {"month": month,
                                            "amount": float(amount) if amount else None}})

    payload = request.get_json(silent=True) or {}
    try:
        month = parse_month(payload.get("month") or "")
        amount = parse_amount(payload.get("amount"))
    except ValueError as exc:
        return jsonify({"code": 400, "msg": str(exc)}), 400

    budget = db.session.scalar(
        db.select(Budget).where(Budget.user_id == _uid(), Budget.month == month))
    if budget:
        budget.amount = amount
    else:
        db.session.add(Budget(user_id=_uid(), month=month, amount=amount))
    db.session.commit()
    return jsonify({"code": 0, "msg": "预算已保存",
                    "data": {"month": month, "amount": float(amount)}})
