"""
抽取模块异常定义

定义了模块中使用的所有异常类，以及面向用户的错误文案映射。
"""


# ==================== 基础异常 ====================

class ExtractError(Exception):
    """抽取模块基础异常"""
    pass


class ExtractorError(ExtractError):
    """抽取器异常"""
    pass


class TemplateError(ExtractError):
    """模板异常"""
    pass


# ==================== LLM相关异常 ====================

class LLMError(ExtractError):
    """LLM调用异常"""

    def __init__(self, message: str):
        super().__init__(f"LLM错误: {message}")


# ==================== 面向用户的错误文案 ====================

# 费用/限流类错误统一提示（OCR、LLM 共用）
USER_MESSAGE_QUOTA = "OCR/LLM 费用不足，无法处理"

# 压缩/OCR 无法解析时的统一提示（页面预览可能正常，仅为解析库不兼容）
USER_MESSAGE_BROKEN_IMAGE = "图片在压缩或OCR阶段无法解析（格式与当前解析库不兼容），页面预览可能正常，可尝试重新导出或更换图片。"


def user_facing_message(exc: Exception) -> str:
    """
    将异常转为面向用户的简短提示，便于在 other 类型和文件解析结果中展示。

    - 429、频率限制、quota、费用、余额等 -> USER_MESSAGE_QUOTA
    - broken PNG、broken image、chunk 等 -> USER_MESSAGE_BROKEN_IMAGE
    - 其他 -> 异常信息或默认提示
    """
    if exc is None:
        return "服务暂时不可用，请稍后重试"
    s = str(exc).lower()
    if any(k in s for k in ("429", "频率限制", "quota", "费用不足", "余额不足", "rate limit")):
        return USER_MESSAGE_QUOTA
    if any(k in s for k in ("broken png", "broken image", "图片文件已损坏", "chunk b'")):
        return USER_MESSAGE_BROKEN_IMAGE
    return str(exc).strip() or "服务暂时不可用，请稍后重试"
