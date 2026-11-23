-- ============================================================
-- SK3017 课程设计 · 题目三 个人记账本（收支管理 + 图表统计）
-- 数据库建库脚本 schema.sql
-- MySQL 8.0 / utf8mb4
-- 执行方式: mysql -u root -p < database/schema.sql
-- ============================================================

DROP DATABASE IF EXISTS ledger_db;
CREATE DATABASE ledger_db DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE ledger_db;

-- ------------------------------------------------------------
-- 1. 用户表
-- ------------------------------------------------------------
CREATE TABLE users (
    id            INT UNSIGNED AUTO_INCREMENT COMMENT '用户主键',
    username      VARCHAR(32)  NOT NULL                COMMENT '登录名',
    password_hash VARCHAR(255) NOT NULL                COMMENT '密码哈希(werkzeug pbkdf2)',
    nickname      VARCHAR(32)  DEFAULT NULL            COMMENT '昵称',
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '注册时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';

-- ------------------------------------------------------------
-- 2. 分类表
--    系统预置分类 is_system=1, user_id 为 0 表示全局预置；
--    用户自定义分类 is_system=0, 归属自己的 user_id。
-- ------------------------------------------------------------
CREATE TABLE categories (
    id         INT UNSIGNED AUTO_INCREMENT COMMENT '分类主键',
    user_id    INT UNSIGNED NOT NULL           COMMENT '归属用户(预置分类为 0)',
    name       VARCHAR(32)  NOT NULL           COMMENT '分类名称',
    type       ENUM('income','expense') NOT NULL COMMENT '收支类型',
    is_system  TINYINT(1)   NOT NULL DEFAULT 0 COMMENT '1=系统预置 0=用户自定义',
    sort_order INT          NOT NULL DEFAULT 0 COMMENT '排序',
    created_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_user_name_type (user_id, name, type),
    KEY idx_user_type (user_id, type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='收支分类表';

-- ------------------------------------------------------------
-- 3. 记账条目表（核心业务表）
-- ------------------------------------------------------------
CREATE TABLE records (
    id          BIGINT UNSIGNED AUTO_INCREMENT COMMENT '条目主键',
    user_id     INT UNSIGNED  NOT NULL           COMMENT '所属用户',
    category_id INT UNSIGNED  NOT NULL           COMMENT '分类',
    type        ENUM('income','expense') NOT NULL COMMENT '收支类型(冗余,便于聚合)',
    amount      DECIMAL(10,2) NOT NULL           COMMENT '金额(元,两位小数)',
    record_date DATE          NOT NULL           COMMENT '记账日期',
    remark      VARCHAR(255)  NOT NULL DEFAULT '' COMMENT '备注',
    created_at  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_user_date (user_id, record_date),
    KEY idx_user_type_date (user_id, type, record_date),
    KEY idx_user_category (user_id, category_id),
    CONSTRAINT fk_record_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_record_category FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE RESTRICT,
    CONSTRAINT chk_record_amount CHECK (amount >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='记账条目表';

-- ------------------------------------------------------------
-- 4. 月度预算表（加分项）
-- ------------------------------------------------------------
CREATE TABLE budgets (
    id         INT UNSIGNED AUTO_INCREMENT COMMENT '预算主键',
    user_id    INT UNSIGNED  NOT NULL COMMENT '所属用户',
    month      CHAR(7)       NOT NULL COMMENT '月份 格式 YYYY-MM',
    amount     DECIMAL(10,2) NOT NULL COMMENT '该月总预算',
    created_at DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_user_month (user_id, month),
    CONSTRAINT fk_budget_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='月度预算表';

-- ------------------------------------------------------------
-- 5. 系统预置分类（user_id=0 为全局模板，首次登录时复制给用户）
-- ------------------------------------------------------------
INSERT INTO categories (user_id, name, type, is_system, sort_order) VALUES
(0, '餐饮', 'expense', 1, 10),
(0, '交通', 'expense', 1, 20),
(0, '学习', 'expense', 1, 30),
(0, '娱乐', 'expense', 1, 40),
(0, '购物', 'expense', 1, 50),
(0, '住房', 'expense', 1, 60),
(0, '医疗', 'expense', 1, 70),
(0, '其他支出', 'expense', 1, 90),
(0, '工资', 'income', 1, 10),
(0, '奖学金', 'income', 1, 20),
(0, '兼职', 'income', 1, 30),
(0, '红包', 'income', 1, 40),
(0, '其他收入', 'income', 1, 90);
