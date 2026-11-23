"""记账条目模块：列表/筛选、新增、编辑、删除、导出 CSV。"""
import csv
import io
from datetime import date

from flask import (Blueprint, Response, abort, flash, redirect, render_template,
                   request, session, url_for)
from sqlalchemy import func

from ..extensions import db
from ..models import Category, Record
from ..utils import login_required, month_range, parse_amount, parse_date

records_bp = Blueprint("records", __name__)


def _current_user_id() -> int:
    return session["user_id"]


def _user_categories(kind: str | None = None):
    stmt = db.select(Category).where(Category.user_id == _current_user_id())
    if kind in ("income", "expense"):
        stmt = stmt.where(Category.type == kind)
    return db.session.scalars(stmt.order_by(Category.type, Category.sort_order, Category.id)).all()


def _get_own_record(record_id: int) -> Record:
    """按 id 取记录，并强制校验归属，防止改 URL 越权操作别人的账。"""
    record = db.session.get(Record, record_id)
    if record is None or record.user_id != _current_user_id():
        abort(404)
    return record


def _filtered_stmt(month: str | None, category_id: int | None, kind: str | None):
    stmt = db.select(Record).where(Record.user_id == _current_user_id())
    if month:
        start, end = month_range(month)
        stmt = stmt.where(Record.record_date >= start, Record.record_date < end)
    if category_id:
        stmt = stmt.where(Record.category_id == category_id)
    if kind in ("income", "expense"):
        stmt = stmt.where(Record.type == kind)
    return stmt


@records_bp.route("/")
@login_required
def index():
    month = request.args.get("month") or date.today().strftime("%Y-%m")
    kind = request.args.get("type") or ""
    category_id = request.args.get("category_id", type=int)
    page = max(request.args.get("page", 1, type=int) or 1, 1)  # 防负数/0

    try:
        month_range(month)
    except ValueError:
        flash("月份格式不正确，已回到本月", "warning")
        month = date.today().strftime("%Y-%m")

    stmt = _filtered_stmt(month, category_id, kind).order_by(
        Record.record_date.desc(), Record.id.desc())

    pagination = db.paginate(stmt, page=page, per_page=15, error_out=False)

    # 当前月份的收入/支出合计（必须 GROUP BY，否则 MySQL only_full_group_by 会报 1140）
    start, end = month_range(month)
    sums = db.session.execute(
        db.select(Record.type, func.coalesce(func.sum(Record.amount), 0))
        .where(Record.user_id == _current_user_id(),
               Record.record_date >= start,
               Record.record_date < end)
        .group_by(Record.type)
    ).all()
    totals = {"income": 0, "expense": 0}
    for kind_name, total in sums:
        totals[kind_name] = total

    return render_template(
        "records/list.html",
        records=pagination.items,
        pagination=pagination,
        month=month,
        kind=kind,
        category_id=category_id,
        categories=_user_categories(),
        totals=totals,
    )


@records_bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    categories = _user_categories()
    if request.method == "POST":
        try:
            category_id = int(request.form.get("category_id") or 0)
            category = db.session.get(Category, category_id)
            if category is None or category.user_id != _current_user_id():
                raise ValueError("请选择有效的分类")
            amount = parse_amount(request.form.get("amount"))
            record_date = parse_date(request.form.get("record_date"))
        except ValueError as exc:
            flash(str(exc), "danger")
        else:
            record = Record(
                user_id=_current_user_id(),
                category_id=category.id,
                type=category.type,          # 类型以分类为准，不信任前端传值
                amount=amount,
                record_date=record_date,
                remark=(request.form.get("remark") or "").strip()[:255],
            )
            db.session.add(record)
            db.session.commit()
            flash("已记一笔", "success")
            return redirect(url_for("records.index"))

    return render_template(
        "records/form.html",
        categories=categories,
        record=None,
        today=date.today().isoformat(),
    )


@records_bp.route("/<int:record_id>/edit", methods=["GET", "POST"])
@login_required
def edit(record_id: int):
    record = _get_own_record(record_id)
    categories = _user_categories()

    if request.method == "POST":
        try:
            category_id = int(request.form.get("category_id") or 0)
            category = db.session.get(Category, category_id)
            if category is None or category.user_id != _current_user_id():
                raise ValueError("请选择有效的分类")
            record.amount = parse_amount(request.form.get("amount"))
            record.record_date = parse_date(request.form.get("record_date"))
            record.category_id = category.id
            record.type = category.type
            record.remark = (request.form.get("remark") or "").strip()[:255]
        except ValueError as exc:
            flash(str(exc), "danger")
        else:
            db.session.commit()
            flash("修改已保存", "success")
            return redirect(url_for("records.index"))

    return render_template(
        "records/form.html",
        categories=categories,
        record=record,
        today=date.today().isoformat(),
    )


@records_bp.route("/<int:record_id>/delete", methods=["POST"])
@login_required
def delete(record_id: int):
    record = _get_own_record(record_id)
    db.session.delete(record)
    db.session.commit()
    flash("已删除该条目", "info")
    return redirect(request.referrer or url_for("records.index"))


@records_bp.route("/export")
@login_required
def export_csv():
    month = request.args.get("month") or date.today().strftime("%Y-%m")
    kind = request.args.get("type") or ""
    category_id = request.args.get("category_id", type=int)

    try:
        month_range(month)
    except ValueError:
        abort(400, description="月份格式不正确")

    rows = db.session.scalars(
        _filtered_stmt(month, category_id, kind).order_by(Record.record_date, Record.id)
    ).all()

    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(["日期", "类型", "分类", "金额", "备注"])
    for row in rows:
        writer.writerow([
            row.record_date.isoformat(),
            "收入" if row.type == "income" else "支出",
            row.category.name,
            f"{row.amount:.2f}",
            row.remark,
        ])

    # BOM 让 Excel 双击打开不乱码
    payload = "\ufeff" + buffer.getvalue()
    filename = f"ledger-{month}.csv"
    return Response(
        payload,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
