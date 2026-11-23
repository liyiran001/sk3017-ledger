r"""测试数据脚本：生成一个 demo 账号 + 近 3 个月 50+ 条记账记录 + 当月预算。

用法（在项目根目录执行）：
    .venv\Scripts\python.exe database/seed.py            # 已有数据则跳过
    .venv\Scripts\python.exe database/seed.py --force    # 清空 demo 的数据重新生成

依赖 schema.sql 已经执行过（库表和预置分类存在）。
"""
import random
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app                      # noqa: E402
from app.extensions import db                   # noqa: E402
from app.models import Budget, Category, Record, User  # noqa: E402

DEMO_USERNAME = "demo"
DEMO_PASSWORD = "123456"
RANDOM_SEED = 20261028          # 固定种子，保证每次生成的测试数据一样

# (分类名, 金额下限, 金额上限, 该分类的备选备注)
EXPENSE_PLAN = [
    ("餐饮", 12, 45, ["午饭", "食堂", "外卖", "早饭", "聚餐"]),
    ("交通", 3, 30, ["地铁", "公交", "打车", "共享单车"]),
    ("学习", 20, 200, ["教材", "网课", "打印资料", "文具"]),
    ("娱乐", 15, 120, ["电影", "游戏", "演唱会门票", "KTV"]),
    ("购物", 30, 300, ["日用品", "衣服", "数码配件"]),
]
INCOME_PLAN = [("工资", 6000, 8000, "月薪"), ("兼职", 200, 800, "周末兼职"),
               ("红包", 50, 300, "家里人给的")]

# 每月大致记多少笔（≥50 条总量，覆盖最近 3 个月）。key 是相对当月的偏移：0 当月，-1 上月，-2 上上月
PER_MONTH_COUNT = {0: 22, -1: 20, -2: 18}


def ensure_demo_user() -> User:
    user = db.session.scalar(db.select(User).where(User.username == DEMO_USERNAME))
    if user:
        return user
    user = User(username=DEMO_USERNAME, nickname="演示账号")
    user.set_password(DEMO_PASSWORD)
    db.session.add(user)
    db.session.flush()

    presets = db.session.scalars(db.select(Category).where(Category.user_id == 0)).all()
    for preset in presets:
        db.session.add(Category(user_id=user.id, name=preset.name, type=preset.type,
                                is_system=False, sort_order=preset.sort_order))
    db.session.commit()
    print(f"已创建演示账号 {DEMO_USERNAME}/{DEMO_PASSWORD}")
    return user


def month_start(offset: int) -> date:
    """offset=0 当月，-1 上个月……"""
    today = date.today()
    y, m = today.year, today.month + offset
    while m <= 0:
        y, m = y - 1, m + 12
    return date(y, m, 1)


def generate_records(user: User, force: bool) -> int:
    existing = db.session.scalar(
        db.select(db.func.count(Record.id)).where(Record.user_id == user.id))
    if existing and not force:
        print(f"demo 账号已有 {existing} 条记录，跳过生成（加 --force 可重建）")
        return 0
    if force:
        db.session.execute(db.delete(Record).where(Record.user_id == user.id))
        db.session.execute(db.delete(Budget).where(Budget.user_id == user.id))
        db.session.commit()
        print("已清空 demo 的历史记录")

    cats = db.session.scalars(db.select(Category).where(Category.user_id == user.id)).all()
    by_name = {c.name: c for c in cats}
    rng = random.Random(RANDOM_SEED)
    created = 0

    for offset, count in PER_MONTH_COUNT.items():
        start = month_start(offset)
        # 当月只生成到今天为止，避免出现"未来日期"的账
        if offset == 0:
            last_day = date.today().day
        else:
            import calendar
            last_day = calendar.monthrange(start.year, start.month)[1]

        for _ in range(count):
            name, low, high, remarks = rng.choice(EXPENSE_PLAN)
            day = rng.randint(1, last_day)
            amount = Decimal(rng.randint(int(low * 100), int(high * 100))) / 100
            db.session.add(Record(
                user_id=user.id, category_id=by_name[name].id, type="expense",
                amount=amount, record_date=start.replace(day=day),
                remark=rng.choice(remarks)))
            created += 1

        # 房租每月固定一笔，避免随机出多笔不真实
        db.session.add(Record(
            user_id=user.id, category_id=by_name["住房"].id, type="expense",
            amount=Decimal("1200.00"), record_date=start.replace(day=5), remark="房租"))
        created += 1

        # 每月 10 号固定发工资，另外随机一笔兼职/红包
        db.session.add(Record(
            user_id=user.id, category_id=by_name["工资"].id, type="income",
            amount=Decimal(rng.randint(650000, 750000)) / 100,
            record_date=start.replace(day=10), remark="月薪"))
        created += 1
        name, low, high, remark = rng.choice(INCOME_PLAN[1:])
        db.session.add(Record(
            user_id=user.id, category_id=by_name[name].id, type="income",
            amount=Decimal(rng.randint(int(low * 100), int(high * 100))) / 100,
            record_date=start.replace(day=rng.randint(1, last_day)), remark=remark))
        created += 1

    # 当月预算 3000 元（用于演示"接近/超出预算"提醒）
    db.session.add(Budget(user_id=user.id, month=date.today().strftime("%Y-%m"),
                          amount=Decimal("3000.00")))
    db.session.commit()
    print(f"已生成 {created} 条记录 + 当月预算 3000 元")
    return created


def main() -> None:
    force = "--force" in sys.argv
    app = create_app()
    with app.app_context():
        user = ensure_demo_user()
        generate_records(user, force)
        total = db.session.scalar(
            db.select(db.func.count(Record.id)).where(Record.user_id == user.id))
        print(f"demo 账号当前共 {total} 条记录")


if __name__ == "__main__":
    main()
