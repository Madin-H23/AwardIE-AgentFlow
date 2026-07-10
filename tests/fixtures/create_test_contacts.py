#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
创建教师通讯录测试数据文件

生成测试用的Excel文件(.xlsx格式)，包含:
- 3个已有教师数据（用于测试更新功能）
- 2个新教师数据（用于测试插入功能）

Usage:
    python tests/fixtures/create_test_contacts.py

Output:
    tests/fixtures/test_contacts.xlsx
"""

from pathlib import Path
import pandas as pd


def create_test_contacts(output_path: str = None) -> str:
    """
    创建教师通讯录测试Excel文件

    Args:
        output_path: 输出文件路径，默认为 tests/fixtures/test_contacts.xlsx

    Returns:
        实际创建的文件绝对路径
    """
    # 确定输出路径
    if output_path is None:
        script_dir = Path(__file__).parent
        output_path = script_dir / "test_contacts.xlsx"
    else:
        output_path = Path(output_path)

    # 创建测试数据（模拟双列布局）
    data = [
        ['教师通讯录', '', '', '', '', '', '', '', '', ''],
        ['', '', '', '', '', '', '', '', '', ''],
        ['职务', '姓名', '工号', '电话', '备注', '职务', '姓名', '工号', '电话', '备注'],
        # 已有教师 - 需要更新
        ['主任', '马云莺', '02114818', '13950308256', '讲师', '', '', '', '', ''],
        ['辅导员', '阴爱英', '02112675', '18050406269', '副教授', '', '', '', '', ''],
        ['辅导员', '陈欣', '02104010', '18006927966', '讲师', '', '', '', '', ''],
        # 新教师 - 需要插入
        ['教授', '张三', '99991001', '13800000001', '教授', '', '', '', '', ''],
        ['讲师', '李四', '99991002', '13800000002', '讲师', '', '', '', '', ''],
    ]

    df = pd.DataFrame(data)

    # 确保输出目录存在
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 保存为.xlsx格式（使用openpyxl引擎，原生支持UTF-8）
    df.to_excel(
        output_path,
        index=False,
        header=False,
        sheet_name='教师通讯录',
        engine='openpyxl'
    )

    return str(output_path.resolve())


if __name__ == "__main__":
    try:
        result_path = create_test_contacts()
        print(f"测试文件创建完成: {result_path}")
    except Exception as e:
        print(f"错误: 无法创建测试文件: {e}")
        import sys
        sys.exit(1)
