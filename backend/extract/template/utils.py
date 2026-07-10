"""模板模块公共工具函数"""
import re


def clean_text(text: str) -> str:
    """
    清理文本，去除标点符号和特殊字符

    用于关键词匹配和相似度计算前的文本预处理。

    Args:
        text: 原始文本

    Returns:
        清理后的文本

    清理规则:
        - 去除 OCR 识别产生的无关标点符号
        - 去除空格、换行符、制表符
        - 去除其他常见标点符号
    """
    if not text:
        return ""

    # 去除常见的 OCR 识别产生的无关标点符号
    text = re.sub(r'[|\•●○■□★☆♦♢♠♣♥♤♡♧♩♪♫♬♭♮♯♰♱♲♳♴♵♶♷♸♹♺♻♼♽♾♿⚀⚁⚂⚃⚄⚅░▒▓█▄▀■□▪▫◼◻◾◽▴▾▸▂]', '', text)

    # 去除空格和换行
    text = text.replace(" ", "").replace("\n", "").replace("\r", "").replace("\t", "")

    # 去除其他常见标点
    text = re.sub(r'[…―—－‐‑‒–—―＿_]', '', text)

    return text
