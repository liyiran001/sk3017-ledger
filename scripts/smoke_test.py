"""端到端冒烟测试：对着已启动的服务跑一遍主流程。

用法：
    1. 另开一个终端启动服务：python run.py
    2. 运行：python scripts/smoke_test.py
可选环境变量：BASE_URL（默认 http://127.0.0.1:5000）
"""
import json
import os
import re
import sys
import uuid
from datetime import date
from urllib.parse import urlencode
from urllib.request import (HTTPCookieProcessor, HTTPRedirectHandler, Request,
                            build_opener)
from urllib.error import HTTPError

BASE = os.getenv("BASE_URL", "http://127.0.0.1:5000")


class NoRedirect(HTTPRedirectHandler):
    """冒烟测试要断言状态码本身，不能让 urllib 自动跟随 302。"""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


opener = build_opener(HTTPCookieProcessor(), NoRedirect())

passed, failed = 0, 0


def check(name, cond, extra=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name} {extra}")


def get(path, expect=200):
    try:
        with opener.open(BASE + path, timeout=10) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")


def post(path, data, expect=302):
    body = urlencode(data).encode()
    req = Request(BASE + path, data=body,
                  headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with opener.open(req, timeout=10) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")


def post_json(path, payload):
    req = Request(BASE + path, data=json.dumps(payload).encode(),
                  headers={"Content-Type": "application/json"})
    with opener.open(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def main():
    username = "smoke_" + uuid.uuid4().hex[:8]
    print(f"测试账号：{username}")

    print("\n[1] 未登录访问受保护页面")
    status, _ = get("/records/")
    check("未登录访问 /records/ 返回 302 跳登录页", status == 302, f"got {status}")

    print("\n[2] 注册 / 登录")
    status, body = post("/auth/register", {
        "username": username, "password": "123456",
        "confirm": "123456", "nickname": "冒烟测试"})
    check("注册成功（302 跳转登录）", status == 302, f"got {status}")
    status, _ = post("/auth/login", {"username": username, "password": "wrong"})
    check("密码错误被拒绝", status == 200, f"got {status}")
    status, _ = post("/auth/login", {"username": username, "password": "123456"})
    check("登录成功", status == 302, f"got {status}")

    print("\n[3] 首页概览")
    status, body = get("/")
    check("首页渲染概览", status == 200 and "概览" in body)

    print("\n[4] 新增记账")
    today = date.today().isoformat()
    # 分类 id 从表单页解析，不硬编码（每个用户的分类 id 都不一样）
    status, page = get("/records/new")
    m = re.search(r'<option value="(\d+)"', page)
    check("记账表单能拿到分类下拉", bool(m))
    cat_id = m.group(1)
    status, body = post("/records/new", {
        "category_id": cat_id, "amount": "35.50", "record_date": today, "remark": "午饭"})
    check("新增记录成功", status == 302, f"got {status}")

    print("\n[5] 非法输入校验")
    status, body = post("/records/new", {
        "category_id": cat_id, "amount": "-5", "record_date": today, "remark": "负数"})
    check("负数金额被拒绝", "金额不能为负数" in body or status == 200)
    status, body = post("/records/new", {
        "category_id": cat_id, "amount": "abc", "record_date": today})
    check("非数字金额被拒绝", "金额必须是数字" in body)
    status, body = post("/records/new", {
        "category_id": cat_id, "amount": "10", "record_date": "2026-13-45"})
    check("非法日期被拒绝", "日期格式" in body)

    print("\n[6] 列表与筛选")
    status, body = get("/records/")
    check("列表显示刚录入的记录", "午饭" in body)
    status, body = get("/records/?month=2020-01")
    check("空月份显示空状态", "没有记录" in body)
    status, body = get("/records/?page=-1")
    check("非法分页参数不报错", status == 200)
    status, body = get("/records/?month=abc")
    check("非法月份被兜底处理", status == 200)

    print("\n[7] 统计接口")
    for path, min_len in [("/stats/api/pie", 0), ("/stats/api/bar?months=6", 1),
                          ("/stats/api/line", 1), ("/stats/api/summary", 1)]:
        status, body = get(path)
        ok = status == 200 and '"code":0' in body.replace('"code": 0', '"code":0')
        check(f"{path} 返回正常", ok, f"status={status}")

    status, body = get("/stats/api/bar?months=999")
    check("months 越界被夹到合法范围", status == 200)

    print("\n[8] 预算设置")
    payload = post_json("/stats/api/budget", {"month": date.today().strftime("%Y-%m"),
                                              "amount": "1000"})
    check("预算保存成功", payload.get("code") == 0, str(payload))
    status, body = get("/stats/api/summary")
    check("汇总里带上预算使用率", "budget_percent" in body)

    print("\n[9] CSV 导出")
    status, body = get("/records/export")
    check("导出带 UTF-8 BOM", body.startswith("\ufeff"), repr(body[:5]))
    check("CSV 含表头", "日期,类型,分类,金额,备注" in body)

    print("\n[10] 越权访问")
    status, body = get("/records/999999/edit")
    check("访问不存在的记录返回 404", status == 404, f"got {status}")

    print("\n[11] 退出登录")
    status, _ = get("/auth/logout")
    check("退出后访问 /records/ 返回 302", status == 302, f"got {status}")

    print(f"\n结果：{passed} 通过 / {failed} 失败")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
