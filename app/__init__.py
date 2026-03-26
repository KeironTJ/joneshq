import os

from flask import Flask 
from config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager 
from flask_socketio import SocketIO
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


db = SQLAlchemy()
migrate = Migrate()
login = LoginManager()
login.login_view = 'auth.login'


def _parse_socket_origins():
    origins = os.getenv('SOCKETIO_ALLOWED_ORIGINS')
    if origins:
        return [origin.strip() for origin in origins.split(',') if origin.strip()]
    return [
        'https://joneshq.co.uk',
        'https://www.joneshq.co.uk',
        'http://localhost',
        'http://127.0.0.1:5000',
    ]


socketio = SocketIO(cors_allowed_origins=_parse_socket_origins(), async_mode="eventlet")
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],
    storage_uri=os.getenv('RATELIMIT_STORAGE_URI', 'memory://')
)


def create_app(config_class=Config):
    app = Flask(__name__)
    
    flask_env = os.getenv('FLASK_ENV', 'production')
    if flask_env == 'development':
        app.config.from_object('config.DevelopmentConfig')
    else:
        app.config.from_object('config.ProductionConfig')

    # Debugging to confirm correct config is loaded without leaking credentials
    masked_uri = app.config['SQLALCHEMY_DATABASE_URI']
    if masked_uri and '@' in masked_uri:
        masked_uri = masked_uri.split('@', 1)[-1]
    print(f"FLASK_ENV: {flask_env}")
    print(f"Database backend: {masked_uri}")


    db.init_app(app)
    migrate.init_app(app, db)
    login.init_app(app)
    app.config.setdefault('RATELIMIT_HEADERS_ENABLED', True)
    limiter.init_app(app)
    socketio.init_app(app, async_mode="eventlet")


    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp)

    from app.admin import bp as admin_bp
    app.register_blueprint(admin_bp)

    from app.main import bp as main_bp
    app.register_blueprint(main_bp)

    from app.activity_planner import bp as activity_planner_bp
    app.register_blueprint(activity_planner_bp)

    from app.chat import bp as chat_bp
    app.register_blueprint(chat_bp)

    from app.meal_planner import bp as meal_planner_bp
    app.register_blueprint(meal_planner_bp)

    from app.family_manager import bp as family_manager_bp
    app.register_blueprint(family_manager_bp)

    from app.rewards import bp as rewards_bp
    app.register_blueprint(rewards_bp)

    from app.health import bp as health_bp
    app.register_blueprint(health_bp)

    @app.context_processor
    def inject_site_banners():
        from app.models import SiteBanner
        banners = SiteBanner.query.filter_by(is_active=True).order_by(SiteBanner.created_at.desc()).all()
        return dict(site_banners=banners)

    return app
    
from app import models
from app.sockets import socketio
