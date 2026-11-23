"""登录 demo 账号，把三张图的数据打出来，快速核对聚合是否正确。"""
import json
import os
import sys
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener

BASE = os.getenv("BASE_URL", "http://127.0.0.1:5000")
opener = build_opener(HTTPCookieProcessor())
opener.open(Request(BASE + "/auth/login",
                    data=urlencode({"username": "demo", "password": "123456"}).encode()))
for path in ["/stats/api/summary", "/stats/api/pie", "/stats/api/bar?months=6",
             "/stats/api/line"]:
    with opener.open(BASE + path) as resp:
        data = json.loads(resp.read().decode())
    body = data["data"]
    if isinstance(body, dict) and "values" in body:
        body = {"天数": len(body["days"]), "有支出的天数": sum(1 for v in body["values"] if v > 0),
                "合计": round(sum(body["values"]), 2)}
    elif isinstance(body, list):
        body = {"分类数": len(body), "合计": round(sum(x["value"] for x in body), 2),
                "明细": body[:3]}
    elif isinstance(body, dict) and "months" in body:
        body = {"月份": body["months"], "收入合计": round(sum(body["income"]), 2),
                "支出合计": round(sum(body["expense"]), 2)}
    print(path, "->", json.dumps(body, ensure_ascii=False))
