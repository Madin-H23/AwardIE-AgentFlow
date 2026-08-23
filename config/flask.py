"""
Flask应用配置文件
"""
import os
from pathlib import Path

# 项目根目录（config/ 的父目录）
# 注意：这里使用相对路径是为了初始化ConfigLoader，ConfigLoader会从配置文件读取所有路径
BASE_DIR = Path(__file__).parent.parent

# 尝试导入 dotenv 加载环境变量
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass  # dotenv 不可用时忽略

def _get_paths_from_config():
    """从配置文件获取路径（延迟加载，避免循环依赖）"""
    try:
        from .loader import get_config_loader
        config_loader = get_config_loader()
        return {
            'database_path': config_loader.get_path("database", "competitions_db"),
            'files_dir': config_loader.get_path("files"),
            'max_content_length_mb': config_loader.load_config().get('flask', {}).get('max_content_length_mb', 50),
        }
    except Exception:
        # 降级方案：如果配置加载失败，使用相对路径和默认值
        return {
            'database_path': BASE_DIR / 'database' / 'competitions.db',
            'files_dir': BASE_DIR / 'files',
            'max_content_length_mb': 50,
        }

# 从配置文件加载路径
_paths = _get_paths_from_config()

_WEAK_SECRET_MARKERS = ('dev-secret', 'change-in-production', 'for-agent', 'secret-key', '123456')


def _is_weak_secret_key(key: str) -> bool:
    """P1-3：可预测签名密钥=可伪造任意用户 session。弱 key 判定（过短/含已知占位词）。"""
    if not key or len(key) < 32:
        return True
    lowered = key.lower()
    return any(marker in lowered for marker in _WEAK_SECRET_MARKERS)


def validate_secret_key(key) -> None:
    """启动期校验：生产环境弱 SECRET_KEY 直接拒绝启动（fail-fast，防带病上线）。

    Dev/Test 环境允许弱 key（本地便利），但会打告警日志。
    Raises:
        RuntimeError: 弱密钥且环境为生产
    """
    import logging
    env = os.environ.get('FLASK_ENV', '')
    key = key or ''
    if _is_weak_secret_key(key):
        if env == 'production':
            raise RuntimeError(
                "SECRET_KEY 不安全（过短或含占位词）。"
                "请执行 python -c \"import secrets;print(secrets.token_hex(32))\" 生成后写入 .env 的 SECRET_KEY"
            )
        logging.getLogger(__name__).warning("SECRET_KEY 为弱值（仅开发/测试可容忍），生产将拒绝启动")


class Config:
    """基础配置"""
    # Flask配置
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'

    # Session配置
    SESSION_COOKIE_NAME = 'competition_session'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    # 开发环境设置为False，生产环境需要HTTPS并设置为True
    SESSION_COOKIE_SECURE = False
    # Session永久化，有效期31天
    PERMANENT_SESSION_LIFETIME = 2678400  # 31天（秒）

    # 数据库路径（从配置文件读取，不允许硬编码）
    DATABASE_PATH = _paths['database_path']

    # 文件存储路径（从配置文件读取，不允许硬编码）
    FILES_DIR = _paths['files_dir']

    # 上传文件配置（从配置文件读取，单位：MB，转换为字节）
    MAX_CONTENT_LENGTH = _paths['max_content_length_mb'] * 1024 * 1024

    # 模板和静态文件自动重载（开发环境）
    TEMPLATES_AUTO_RELOAD = True

class DevelopmentConfig(Config):
    """开发环境配置"""
    DEBUG = True
    TESTING = False

class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True  # 生产环境需要HTTPS

class TestingConfig(Config):
    """测试环境配置"""
    DEBUG = True
    TESTING = True
    # 数据库及路径均从配置文件读取，与 Config 一致（使用 _paths）
    # 如需测试库，请在 config/settings.json 的 database 中配置 test_competitions_db 并在此选用
    pass

# 根据配置或环境变量选择配置
config_map = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

def get_config():
    """获取配置类。优先从 config/settings.json 的 flask.env 读取，否则用 FLASK_ENV。"""
    env = None
    try:
        from .loader import get_config_loader as get_loader
        cfg = get_loader().load_config()
        env = (cfg.get('flask') or {}).get('env')
    except Exception:
        pass
    if not env:
        env = os.environ.get('FLASK_ENV', 'default')
    cls = config_map.get(env, DevelopmentConfig)
    # P1-3：生产环境弱 SECRET_KEY 拒绝启动（fail-fast）
    if cls is ProductionConfig:
        validate_secret_key(getattr(cls, 'SECRET_KEY', ''))
    return cls
