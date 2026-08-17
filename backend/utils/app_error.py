"""统一异常契约（T4 / 设计 API §1.4 / CR-9）。

业务侧只抛异常、不自行 jsonify 错误（P2-8 根治的执行机制）；
全局 errorhandler（app/__init__.py 注册）翻译为统一包装 {trace_id, code, message, data}。
错误码段位见设计 API §1.2：3xxx=业务状态机。
"""


class AppError(Exception):
    """业务异常基类：code 为业务错误码（API §1.2），http_status 为响应码。"""

    code = 5002
    http_status = 500

    def __init__(self, message: str = "", *, code=None, http_status=None):
        super().__init__(message or self.__class__.__name__)
        self.message = message or self.__class__.__name__
        if code is not None:
            self.code = code
        if http_status is not None:
            self.http_status = http_status


class StateConflictError(AppError):
    """乐观锁/状态机并发冲突（version 不符，另一操作已变更）。"""
    code = 3001
    http_status = 409


class NotSubmittableError(AppError):
    """非 submit 状态不可审核（P1-14 状态机守卫）。"""
    code = 3002
    http_status = 409


class DuplicateEntryError(AppError):
    """重复入库（唯一索引护栏拦截，P0-9）。"""
    code = 3003
    http_status = 409


class RejectWithoutEditError(AppError):
    """驳回后未修改不可重交（API §1.2 3004）。"""
    code = 3004
    http_status = 409


class FileTypeDenied(AppError):
    code = 2002
    http_status = 415


class FileTooLarge(AppError):
    code = 2003
    http_status = 413


class BreakerOpenError(AppError):
    """熔断开启中（响应应附 Retry-After，由 handler 统一注入）。"""
    code = 4003
    http_status = 503
    retry_after = 60

    def __init__(self, message="服务暂时不可用（熔断保护中）", retry_after=60):
        super().__init__(message)
        self.retry_after = retry_after


# 业务异常 -> 错误码映射表（设计 API §1.4；新增异常在此登记）
__all__ = ["AppError", "StateConflictError", "NotSubmittableError", "DuplicateEntryError",
           "RejectWithoutEditError", "FileTypeDenied", "FileTooLarge", "BreakerOpenError"]
