"""用户模块：注册、登录、退出。"""
import re

from flask import (Blueprint, flash, redirect, render_template, request, session,
                   url_for)

from ..extensions import db
from ..models import Category, User

auth_bp = Blueprint("auth", __name__)

USERNAME_RE = re.compile(r"^[A-Za-z0-9_\u4e00-\u9fa5]{3,20}$")


def _safe_next(target: str | None) -> str:
    """只允许跳回本站相对路径，防止 open redirect。"""
    if not target or not target.startswith("/") or target.startswith("//"):
        return url_for("main.index")
    return target


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("main.index"))

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm") or ""
        nickname = (request.form.get("nickname") or "").strip() or None

        if not USERNAME_RE.match(username):
            flash("用户名需为 3~20 位的字母、数字、下划线或中文", "danger")
        elif len(password) < 6:
            flash("密码至少 6 位", "danger")
        elif password != confirm:
            flash("两次输入的密码不一致", "danger")
        elif db.session.scalar(db.select(User).where(User.username == username)):
            flash("该用户名已被注册", "danger")
        else:
            user = User(username=username, nickname=nickname)
            user.set_password(password)
            db.session.add(user)
            db.session.flush()          # 拿到 user.id

            # 首次注册时把系统预置分类复制一份给自己
            presets = db.session.scalars(
                db.select(Category).where(Category.user_id == 0)
            ).all()
            for preset in presets:
                db.session.add(Category(
                    user_id=user.id,
                    name=preset.name,
                    type=preset.type,
                    is_system=False,
                    sort_order=preset.sort_order,
                ))
            db.session.commit()
            flash("注册成功，请登录", "success")
            return redirect(url_for("auth.login"))

    return render_template("auth/register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("main.index"))

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        user = db.session.scalar(db.select(User).where(User.username == username))

        if user is None or not user.check_password(password):
            # 不区分"用户不存在"和"密码错误"，避免暴露账号是否存在
            flash("用户名或密码错误", "danger")
        else:
            session.clear()
            session["user_id"] = user.id
            session["username"] = user.username
            flash(f"欢迎回来，{user.display_name}", "success")
            return redirect(_safe_next(request.args.get("next")))

    return render_template("auth/login.html")


@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("已退出登录", "info")
    return redirect(url_for("main.index"))
