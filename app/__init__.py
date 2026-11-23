"""应用工厂：Flask 2.3+ 推荐的 create_app 模式。"""
from flask import Flask

from .config import Config
from .extensions import db
from .utils import format_money


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    db.init_app(app)

    from .blueprints.auth import auth_bp
    from .blueprints.main import main_bp
    from .blueprints.records import records_bp
    from .blueprints.stats import stats_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(records_bp, url_prefix="/records")
    app.register_blueprint(stats_bp, url_prefix="/stats")

    app.jinja_env.filters["money"] = format_money

    return app
