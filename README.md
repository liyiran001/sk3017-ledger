课程设计选题：题目三-个人记账本（收支管理 + 图表统计）

# SK3017 课程设计 · 个人记账本

基于 Flask + MySQL + ECharts 的个人记账 Web 应用：记录收支、按月份/分类/类型组合筛选、三张图表统计、月度预算提醒、CSV 导出。

> 选题路线：**路线 B（题库选题 + AI Coding）**　题目三《个人记账本（收支管理 + 图表统计）》

## 功能清单

| 模块 | 功能 | 状态 |
|---|---|---|
| 用户 | 注册（自动获得 13 个预置分类）、登录、退出，密码 scrypt 哈希存储 | ✅ |
| 记账 | 新增、编辑、删除条目（分类/金额/日期/备注），二次确认删除 | ✅ |
| 筛选 | 按月份 + 收支类型 + 分类组合筛选，分页，服务端 SQL 过滤 | ✅ |
| 统计 | 当月支出分类占比饼图 | ✅ |
| 统计 | 近 6 个月收支并列柱状图 | ✅ |
| 统计 | 当月每日支出折线图 | ✅ |
| 加分 | 月度预算设置，支出达 80% 黄色提醒、超 100% 红色告警 | ✅ |
| 加分 | 导出 CSV（UTF-8 BOM，Excel 打开不乱码） | ✅ |

三张图表随月份筛选联动刷新；没有数据的月份/日期由后端补 0，不会白屏或错位。

## 技术栈

- 后端：Flask 3.1 + Flask-SQLAlchemy 3.1 + PyMySQL，应用工厂 + 蓝图分层
- 数据库：MySQL 8.0（utf8mb4 / InnoDB），4 张表，3 个复合索引
- 前端：Jinja2 模板 + Bootstrap 5.3 + ECharts 5.5（均已下载到 `static/vendor/`，**断网也能演示**）
- 运行环境：Python 3.12

## 目录结构

```
sk3017-ledger/
├── app/
│   ├── __init__.py          # create_app 工厂
│   ├── config.py            # 配置（全部走 .env / 环境变量）
│   ├── extensions.py        # db 单例，避免循环导入
│   ├── models.py            # User / Category / Record / Budget
│   ├── utils.py             # 登录装饰器、金额/日期/月份解析
│   ├── blueprints/          # auth / main / records / stats
│   ├── templates/           # base + 各页面
│   └── static/              # css、js（stats.js）、vendor（bootstrap、echarts）
├── database/
│   ├── schema.sql           # 建库建表 + 13 条预置分类
│   └── seed.py              # 演示数据：demo 账号 + 近 3 个月 69 条记录
├── scripts/
│   ├── smoke_test.py        # 端到端冒烟测试（25 项断言）
│   └── check_charts.py      # 打印四个统计接口结果，核对聚合
├── docs/
│   ├── 数据库设计.md         # ER 图 + 表结构 + 统计 SQL + 设计取舍
│   ├── DEVELOPMENT_LOG.md
│   ├── DEBUG_LOG.md
│   ├── AI协作记录.md
│   ├── 课程设计报告.docx     # 按模板填写的报告源文件
│   └── 课程设计报告.pdf      # 导出的提交版（14 页）
├── screenshots/
├── requirements.txt
└── README.md
```

## 运行说明

### 1. 准备 Python 环境

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 初始化数据库

确保本地 MySQL 8.0 已启动（默认 3306 端口）：

```bash
mysql -u root -p < database/schema.sql
```

脚本会重建 `ledger_db`、创建 4 张表并写入 13 条系统预置分类。

### 3. 配置环境变量

复制 `.env.example` 为 `.env`，改成自己的数据库密码：

```
DATABASE_URL=mysql+pymysql://root:你的密码@127.0.0.1:3306/ledger_db?charset=utf8mb4
SECRET_KEY=随便一段随机字符串
```

> `.env` 已在 `.gitignore` 中排除，不会提交到仓库。

### 4. 生成演示数据（可选但推荐）

```bash
python database/seed.py            # 已有数据会跳过
python database/seed.py --force    # 清空 demo 的记录后重建
```

生成内容：`demo` 账号 + 近 3 个月 69 条记录 + 当月预算 3000 元。

### 5. 启动

```bash
python run.py
```

浏览器打开 http://127.0.0.1:5000

### 6. 测试账号

| 用户名 | 密码 | 说明 |
|---|---|---|
| demo | 123456 | 预置 69 条演示数据，含当月预算 3000 元（预算使用率约 89%，可看到黄色接近提醒） |
| 自行注册 | — | 注册后自动获得 13 个分类，从零开始记账 |

### 7. 自测

服务启动后另开一个终端：

```bash
python scripts/smoke_test.py                       # 默认 http://127.0.0.1:5000
BASE_URL=http://127.0.0.1:5001 python scripts/smoke_test.py   # 换端口
python scripts/check_charts.py                     # 打印统计接口的聚合结果
```

冒烟测试覆盖：未登录跳转、注册、登录、密码错误、新增、非法金额/日期、列表筛选、四个统计接口、预算保存、CSV BOM、404 越权、退出，共 25 项断言。

## 安全与健壮性说明

- 密码只存 `werkzeug` 的 scrypt 哈希，不存明文；登录失败统一提示，不暴露账号是否存在。
- 所有记录查询都带 `user_id = 当前登录用户`，取单条记录时二次校验归属，改 URL 里的 id 越不了权。
- 金额用 `Decimal` 处理并量化到两位，避免浮点误差；入库前校验非负与上限。
- 记录的分类类型以数据库里的分类为准，不信任前端传值。
- 数据库连接 `pool_pre_ping=True`，避免 MySQL 闲置断连导致第一个请求 500。
- 月份、分页、`months` 等参数全部做边界处理，非法输入返回 400 或兜底为本月，不会 500。

## 开发进度

- [x] M0 环境与数据库骨架
- [x] M1 用户模块
- [x] M2 记账核心 CRUD + 筛选 + CSV
- [x] M3 统计三图（饼图/柱状图/折线图）
- [x] M4 预算提醒
- [x] M5 报告填写并导出 PDF（14 页）、5 张功能截图、三份日志
- [ ] 仓库推送与报告封面个人信息（需本人操作）

详细过程见 [docs/DEVELOPMENT_LOG.md](docs/DEVELOPMENT_LOG.md)，踩坑记录见 [docs/DEBUG_LOG.md](docs/DEBUG_LOG.md)。
