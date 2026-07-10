"""
文件管理器异常定义

严格异常处理，无降级方案
"""


class FileManagerError(Exception):
    """文件管理器基础异常"""
    pass


class ConfigurationError(FileManagerError):
    """配置错误 - 配置文件缺失或格式错误"""
    pass


class SessionNotFoundError(FileManagerError):
    """会话不存在"""
    pass


class FileNotFoundError(FileManagerError):
    """文件不存在"""
    pass


class InvalidFileTypeError(FileManagerError):
    """不支持的文件类型"""
    pass


class OperationFailedError(FileManagerError):
    """操作失败 - 文件移动、创建等失败"""
    pass