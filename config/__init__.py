"""
配置模块

统一管理所有配置文件
"""

from .flask import Config, DevelopmentConfig, ProductionConfig, TestingConfig, get_config
from .loader import ConfigLoader, get_config as get_loader

__all__ = [
    'Config',
    'DevelopmentConfig',
    'ProductionConfig',
    'TestingConfig',
    'get_config',
    'ConfigLoader',
    'get_loader',
]
