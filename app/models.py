"""数据模型：与 database/schema.sql 一一对应。"""
from datetime import date, datetime
from decimal import Decimal

from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(32), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    nickname = db.Column(db.String(32))
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)

    records = db.relationship("Record", back_populates="user", lazy="dynamic",
                              cascade="all, delete-orphan")
    categories = db.relationship("Category", back_populates="user", lazy="dynamic")

    def set_password(self, raw: str) -> None:
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw: str) -> bool:
        return check_password_hash(self.password_hash, raw)

    @property
    def display_name(self) -> str:
        return self.nickname or self.username

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User {self.username}>"


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    name = db.Column(db.String(32), nullable=False)
    type = db.Column(db.Enum("income", "expense", name="record_type"), nullable=False)
    is_system = db.Column(db.Boolean, default=False, nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)

    user = db.relationship("User", back_populates="categories")
    records = db.relationship("Record", back_populates="category", lazy="dynamic")

    __table_args__ = (
        db.UniqueConstraint("user_id", "name", "type", name="uk_user_name_type"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Category {self.name}>"


class Record(db.Model):
    __tablename__ = "records"

    id = db.Column(db.BigInteger, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False, index=True)
    type = db.Column(db.Enum("income", "expense", name="record_type"), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    record_date = db.Column(db.Date, nullable=False, index=True)
    remark = db.Column(db.String(255), nullable=False, default="")
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)

    user = db.relationship("User", back_populates="records")
    category = db.relationship("Category", back_populates="records")

    __table_args__ = (
        db.Index("idx_user_date", "user_id", "record_date"),
        db.Index("idx_user_type_date", "user_id", "type", "record_date"),
        db.CheckConstraint("amount >= 0", name="chk_record_amount"),
    )

    @property
    def amount_yuan(self) -> Decimal:
        return Decimal(self.amount).quantize(Decimal("0.01"))

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Record {self.record_date} {self.amount}>"


class Budget(db.Model):
    __tablename__ = "budgets"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    month = db.Column(db.String(7), nullable=False)          # 'YYYY-MM'
    amount = db.Column(db.Numeric(10, 2), nullable=False)

    __table_args__ = (
        db.UniqueConstraint("user_id", "month", name="uk_user_month"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Budget {self.month} {self.amount}>"
