"""
Flask应用启动入口
"""
import os
import logging
import logging.handlers
import sys
from pathlib import Path

# 尽早加载 .env，以便 LOG_LEVEL 等可配置
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / '.env')
except ImportError:
    pass

# 加载配置以获取日志级别
# 优先级：环境变量 LOG_LEVEL > settings.json flask.log_level > 默认 INFO
try:
    from config.loader import get_config as get_config_loader
    config_loader = get_config_loader()
    config_dict = config_loader.load_config()
    # 从 settings.json 读取日志级别
    flask_config = config_dict.get('flask', {})
    default_log_level = flask_config.get('log_level', 'INFO')
except Exception:
    # 如果配置加载失败，使用默认值
    default_log_level = 'INFO'

# 日志级别：优先级 环境变量 > settings.json > 默认值
# 可通过以下方式设置：
# 1. 环境变量: LOG_LEVEL=DEBUG python run.py
# 2. .env 文件: LOG_LEVEL=DEBUG
# 3. settings.json: "flask": { "log_level": "DEBUG" }
_log_level = os.environ.get('LOG_LEVEL', default_log_level).upper()

# 配置日志，输出到控制台和文件
# 创建 logs 目录
logs_dir = Path(__file__).parent / 'logs'
logs_dir.mkdir(exist_ok=True)

# 日志文件路径
log_file = logs_dir / 'app.log'

# 创建格式化器
formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s [%(name)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# 创建处理器
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)

file_handler = logging.handlers.RotatingFileHandler(
    log_file,
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5,  # 保留5个备份
    encoding='utf-8'
)
file_handler.setFormatter(formatter)

# 配置根日志记录器
logging.basicConfig(
    level=getattr(logging, _log_level, logging.INFO),
    handlers=[console_handler, file_handler],
    force=True
)

print(f"日志文件: {log_file.absolute()}")

from app import create_app
from config.flask import get_config

# 获取配置
config = get_config()

# 创建应用
app = create_app(config)


def _should_enable_debug() -> bool:
    """P0-3 安全判定：仅 development 环境 + 显式 FLASK_DEBUG=1 才允许调试器。"""
    return os.environ.get('FLASK_ENV') == 'development' and os.environ.get('FLASK_DEBUG') == '1'


if __name__ == '__main__':
    # 从环境变量获取端口，默认5000
    port = int(os.environ.get('PORT', 5001))
    debug = _should_enable_debug()  # 安全硬约束 (P0-3)：调试器=RCE，禁止配置文件隐式开启

    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug,
        use_reloader=debug
    )

