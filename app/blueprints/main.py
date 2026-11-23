"""首页：未登录显示欢迎页，已登录显示本月概览。"""
from datetime import date

from flask import Blueprint, render_template, session
from sqlalchemy import func

from ..extensions import db
from ..models import Record
from ..utils import month_range

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    if not session.get("user_id"):
        return render_template("index.html")

    today = date.today()
    month = today.strftime("%Y-%m")
    start, end = month_range(month)
    uid = session["user_id"]

    def total(kind: str):
        return db.session.scalar(
            db.select(func.coalesce(func.sum(Record.amount), 0)).where(
                Record.user_id == uid,
                Record.type == kind,
                Record.record_date >= start,
                Record.record_date < end,
            )
        ) or 0

    income, expense = total("income"), total("expense")
    recent = db.session.scalars(
        db.select(Record)
        .where(Record.user_id == uid)
        .order_by(Record.record_date.desc(), Record.id.desc())
        .limit(8)
    ).all()

    return render_template(
        "dashboard.html",
        month=month,
        income=income,
        expense=expense,
        balance=income - expense,
        recent=recent,
        today=today,
    )
