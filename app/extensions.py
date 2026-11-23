"""扩展对象集中在这里创建，避免循环导入。"""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
