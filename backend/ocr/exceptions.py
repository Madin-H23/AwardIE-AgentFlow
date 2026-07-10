"""
OCR模块自定义异常类
"""


class OCRError(Exception):
    """OCR模块基础异常"""
    pass


class OCRConfigError(OCRError):
    """配置错误"""
    pass


class OCRAPIServiceError(OCRError):
    """OCR API调用失败"""
    pass


class OCRFileNotFoundError(OCRError):
    """文件不存在"""
    pass


class OCRFileFormatError(OCRError):
    """文件格式不支持"""
    pass


class OCRCacheError(OCRError):
    """缓存操作失败"""
    pass


class OCRImageProcessingError(OCRError):
    """图片处理失败"""
    pass


class OCRTimeoutError(OCRError):
    """OCR请求超时"""
    pass
