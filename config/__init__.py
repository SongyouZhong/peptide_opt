"""
配置模块
统一配置入口，支持 YAML 配置文件和环境变量覆盖
"""

from pathlib import Path

# 项目根目录
ROOT = Path(__file__).resolve().parent.parent

# 导出设置访问器
from .settings import (
    get_settings, 
    get, 
    reload_settings,
    server,
    cors,
    database,
    storage,
    task_processor,
    logging_config,
)

# 兼容性导出
from . import database_config

# 设置日志系统
def setup_logging(level=None):
    """设置日志系统，level 默认从 settings.yaml 读取"""
    from .logging_config import setup_logging as _setup_logging
    if level is None:
        level = logging_config.level
    log_file = logging_config.file
    return _setup_logging(level, log_file)


def get_module_logger(module_name):
    """获取模块日志器"""
    from .logging_config import get_module_logger as _get_module_logger
    return _get_module_logger(module_name)


__all__ = [
    'ROOT',
    'setup_logging',
    'get_module_logger',
    'get_settings',
    'get',
    'reload_settings',
    # 配置对象
    'server',
    'cors',
    'database',
    'storage',
    'task_processor',
    'logging_config',
    # 兼容性模块
    'database_config',
]
