"""chat_stream 分片流式回归（_answer_pieces）：auto/tools 答案分片段下发，拼接必须与原文一致。"""
import pytest

from app.routes.chat import _answer_pieces


def test_pieces_中文混合拼接还原():
    t = "根据知识库，A类赛事包括：1. 一带一路暨金砖国家技能发展与技术创新大赛（国家级，A类）"
    pieces = _answer_pieces(t)
    assert len(pieces) > 1                # 确实被分片
    assert "".join(pieces) == t           # 无丢失无增字


def test_pieces_英文含空格拼接还原():
    t = "The quick brown fox jumps over the lazy dog 混合 测试"
    assert "".join(_answer_pieces(t)) == t


def test_pieces_短文本单片():
    t = "好的"
    assert _answer_pieces(t) == [t]


def test_pieces_空串与None():
    assert _answer_pieces("") == [""]
    assert _answer_pieces(None) == []


def test_pieces_自定义块大小():
    t = "一二三四五六七八九十"
    pieces = _answer_pieces(t, size=3)
    assert "".join(pieces) == t
    assert pieces == ["一二三", "四五六", "七八九", "十"]
