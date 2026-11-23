# 个人记账本 Debug 日志

> 每条记四件事：**现象（怎么错的）→ 根因（为什么错）→ 解决（改了什么）→ 预防（下次怎么不踩）**。
> 标准：下次遇到同样报错的人（包括三个月后的自己）照着做就能脱困。

## BUG-001 ｜ 10-28 ｜ 列表页 500：MySQL 1140 only_full_group_by

- **现象**：访问 `/records/` 整页 500，报错栈最后一行是
  `pymysql.err.OperationalError: (1140, "In aggregated query without GROUP BY, expression #1 of SELECT list contains nonaggregated column 'ledger_db.records.type'...")`，
  出错 SQL 是 `SELECT records.type, coalesce(sum(records.amount), 0) FROM records WHERE ...`。
- **根因**：我想做"本月收入合计 + 本月支出合计"两行结果，SQL 里 `SELECT type, SUM(amount)` 却没有 `GROUP BY type`。
  这在旧版 MySQL（或把 `sql_mode` 里的 `ONLY_FULL_GROUP_BY` 关掉）能跑，会随手返回一个不确定的 `type` 值；
  MySQL 5.7 以后默认开启 `ONLY_FULL_GROUP_BY`，直接拒绝执行。**关 sql_mode 是掩盖问题，不是解决**。
- **解决**：补上 `.group_by(Record.type)`，并把重复调用的 `month_range(month)` 提到循环外只算一次：
  ```python
  start, end = month_range(month)
  sums = db.session.execute(
      db.select(Record.type, func.coalesce(func.sum(Record.amount), 0))
      .where(Record.user_id == uid, Record.record_date >= start, Record.record_date < end)
      .group_by(Record.type)
  ).all()
  ```
- **预防**：`SELECT` 里只要出现聚合函数，其余非聚合列必须出现在 `GROUP BY` 里——写 SQL 时先问一句"这些列的粒度是什么"。
  另外，写聚合查询前先在 Navicat / mysql 命令行里把 SQL 单独跑一遍，别等页面 500 才发现。

## BUG-002 ｜ 10-28 ｜ 未登录访问 `/records/` 返回一坨 JSON，而不是登录页

- **现象**：浏览器直接打开 `http://127.0.0.1:5000/records/`，页面显示 `{"code":401,"msg":"请先登录"}`；但浏览器地址栏并没有跳到登录页。
- **根因**：`login_required` 装饰器第一版用"路径前缀"判断是不是 Ajax：
  ```python
  if request.path.startswith(("/records", "/stats", "/api")):
      return jsonify(...), 401
  ```
  可 `/records/` 既是 Ajax 数据接口的父路径，也是**页面的地址**。按路径判断，页面请求也被当成了接口请求。
- **解决**：改成按"请求想要什么"判断，而不是按路径：
  ```python
  wants_json = (request.path.startswith("/api")
                or request.path.startswith("/stats/api")
                or request.headers.get("X-Requested-With") == "XMLHttpRequest")
  ```
  页面请求继续 302 跳转并带 `next`，接口请求才返回 401。
- **预防**：区分"页面路由"和"数据接口"不要靠 URL 前缀猜，要么用显式的 header（`X-Requested-With` / `Accept`），要么把接口统一归到 `/api` 前缀下。

## BUG-003 ｜ 10-28 ｜ 批量写文件时第二个文件只剩半行

- **现象**：一条命令里用两个 heredoc 写 `records.py` 和 `stats.py`，命令结束后 `stats.py` 只有 51 行、末尾停在
  `month = _month_or_c` 这种半个单词上，Python 直接语法错误；bash 还提示
  `warning: here-document at line 207 delimited by end-of-file`。
- **根因**：不是 heredoc 语法错，是**单次命令太长被截断**，后半段根本没送到 shell，heredoc 永远等不到结束符。
- **解决**：拆成一条命令只写一个文件（每个文件 100~200 行），写完立刻 `wc -l` + `tail` 确认行数和结尾正常。
- **预防**：大文件分块写、每次都验长度；`here-document ... delimited by end-of-file` 这个警告基本等于"内容没写完"，看到就先检查文件完整性，别急着改代码。

## BUG-004 ｜ 10-28 ｜ curl 传中文昵称，注册表单被判定为空

- **现象**：用 `curl -d "username=wangwu&password=123456&confirm=123456&nickname=王五"` 注册，
  返回 200 + 提示"用户名需为 3~20 位的字母、数字、下划线或中文"，但 `wangwu` 明明是合法用户名；页面回填的 `value` 也是空的。
- **根因**：`-d` 把 UTF-8 原始字节直接塞进请求体，没有做 URL 编码。表单解析拿到的是畸形数据，整个 form 解析结果为空，
  于是 `request.form.get("username")` 是 `None`，`.strip()` 后是空串 → 正则不通过。
  **浏览器永远会对表单字段做 URL 编码，所以这不是应用 bug，是我测试方法错了。**
- **解决**：测试改用 `--data-urlencode`（或 Python 的 `urlencode`），中文昵称注册立刻 302 成功。
- **预防**：用 curl 测带非 ASCII 的表单，一律 `--data-urlencode`；排查"字段明明是合法的却被判非法"时，**先把服务端收到的值打印出来**，
  确认是"值错了"还是"校验错了"，别急着改正则。

## BUG-005 ｜ 10-28 ｜ 冒烟测试硬编码 category_id 导致"新增记账"必然失败

- **现象**：`scripts/smoke_test.py` 里写死 `"category_id": "11"`，第一次跑 `[4] 新增记账 FAIL got 200`，
  紧接着列表、筛选、统计全挂——因为根本没新增成功。
- **根因**：分类是注册时从预置模板复制给每个用户的，`id` 是自增值。第一个用户拿到 14~26，第二个用户拿到 27~39……
  **写死的 11 在别人的账号下要么不存在、要么属于别人**，被"分类归属校验"拦下，页面 flash "请选择有效的分类" 后 200 回表单。
- **解决**：测试先 `GET /records/new`，用正则从下拉框里取出真实 `category_id` 再提交。
- **预防**：测试数据不要依赖数据库自增 id；凡是"每个用户一份"的数据（分类、标签、看板列），测试里都要先查再用。
  另外"POST 返回 200"通常等于"校验没过、原样回显表单"，只有 302 才代表写成功——断言时盯状态码比盯页面文字快。

## BUG-006 ｜ 10-28 ｜ 演示数据全生成了未来月份，柱状图只显示一根柱子

- **现象**：柱状图"近 6 个月收支对比"里只有 2026-10 有柱子，左边 5 个月全空；但种子脚本明明写了"生成近 3 个月数据"。
- **根因**：`PER_MONTH_COUNT = {0: 22, 1: 20, 2: 18}` 的 key 我写成了 **0/1/2**，
  而 `month_start(offset)` 的语义是 **0=当月、-1=上月**，于是 `month_start(1)` 落在 **11 月**、`month_start(2)` 落在 **12 月**——
  数据全跑到未来了。柱状图只查 `record_date >= 6 个月前`，未来的 11/12 月自然被排除，看起来像"只生成了一个月"。
- **解决**：把 key 改成 `{0: 22, -1: 20, -2: 18}`，并重新 `--force` 生成。核对：
  `SELECT DATE_FORMAT(record_date,'%Y-%m'), COUNT(*) FROM records GROUP BY 1` 得到 2026-08/09/10 三个月。
- **预防**：凡是"相对当前时间"的偏移量，**先写一行注释把正负号定死**，再用一条 SQL 抽查结果区间的 max/min 日期；
  图表"少数据"时先查数据在不在、在哪个区间，别急着改前端聚合逻辑。

## BUG-007 ｜ 10-28 ｜ 数据库总数和页面数字对不上（35.50 的差额）

- **现象**：用 mysql 命令行查 `SELECT SUM(amount) FROM records WHERE type='expense'` 得到当月支出 2712.51，
  但页面 `/stats/api/summary` 显示 2677.01，差 35.50。
- **根因**：命令行那条 SQL **没有加 `user_id` 过滤**，把冒烟测试脚本注册的临时账号（smoke_xxx）记的那笔 35.50 也算进去了。
  页面接口是按当前登录用户隔离查询的，所以两边天然差这一笔。**数据没错，是我的核对方法错了。**
- **解决**：核对时带上用户条件：
  `SELECT SUM(amount) FROM records WHERE user_id=(SELECT id FROM users WHERE username='demo') AND ...`，两边立刻一致。
- **预防**：多用户系统的任何"对数"动作，都要把用户条件写进 SQL；看到差异先怀疑统计口径不一致，再怀疑代码。

## 复盘小结

这轮一共 7 条，可以分为四类：

1. **SQL 的正确性**（BUG-001）：聚合查询的 `GROUP BY`、以及"能跑但结果不确定"的写法，是最容易在 MySQL 8 上翻车的地方。
   下一阶段要养成"聚合 SQL 先在命令行单独验证，再写进代码"的习惯。
2. **Web 语义的边界**（BUG-002、BUG-004）：页面请求 vs 接口请求、原始字节 vs URL 编码——都属于"框架没做错，是我对协议的理解不到位"。
   这类问题不会报 500，只会表现为"看起来正常的错误行为"，最难靠报错栈发现。
3. **测试与工具本身也会错**（BUG-003、BUG-005）：把测试脚本当成代码来审，别默认"测试失败就是被测代码的错"。
4. **核对方法也会错**（BUG-006、BUG-007）：造数据的时间区间算错、对数时漏了用户条件，都会让人误判"功能坏了"。
   下一步改进：把"造数 → 抽查区间 → 对数"写成固定三步，别凭感觉看一眼图表就下结论。
   下一步改进：把冒烟测试接进一个一键脚本（起服务 → 跑测试 → 出报告），避免每次手工贴 BASE_URL。
