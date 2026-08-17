"""P0-3 回归测试：调试器（Werkzeug debugger = RCE）不得被隐式开启。

修复前：FLASK_ENV=development 或 config.DEBUG 任一为真即开 debug → 生产误配即裸奔。
修复后：仅 FLASK_ENV=development 且显式 FLASK_DEBUG=1 才开。
用 AST 从 run.py 提取 _should_enable_debug 真实源码执行（避免 import 触发 create_app 副作用）。
"""
import ast
import os
import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_debug_fn():
    src = (PROJECT_ROOT / 'run.py').read_text(encoding='utf-8')
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == '_should_enable_debug':
            mod = ast.Module(body=[node], type_ignores=[])
            ns = {'os': os}
            exec(compile(mod, 'run.py', 'exec'), ns)
            return ns['_should_enable_debug']
    raise AssertionError('run.py 中未找到 _should_enable_debug 函数')


def _debug_flag_with(env: dict) -> bool:
    fn = _load_debug_fn()
    saved = {k: os.environ.get(k) for k in ('FLASK_ENV', 'FLASK_DEBUG')}
    try:
        for k, v in env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        return fn()
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_no_implicit_or_in_debug_gate():
    """判定逻辑禁止出现 or（防退化为'任一条件即开'）。"""
    src = (PROJECT_ROOT / 'run.py').read_text(encoding='utf-8')
    m = re.search(r'def _should_enable_debug\(\).*?return ([^\n]+)', src, re.S)
    assert m, '未找到 _should_enable_debug 的 return'
    assert ' or ' not in m.group(1), f'debug 判定出现 or（可能回退为隐式开启）: {m.group(1)}'


@pytest.mark.parametrize("env,expected", [
    ({}, False),                                          # 默认（生产）：关
    ({'FLASK_ENV': 'production'}, False),                 # 生产 env：关
    ({'FLASK_ENV': 'development'}, False),                # 仅 dev env（修复前会误开！）：关
    ({'FLASK_DEBUG': '1'}, False),                        # 仅显式 debug 但非 dev env：关
    ({'FLASK_ENV': 'development', 'FLASK_DEBUG': '1'}, True),  # 双条件显式开启：开
])
def test_debug_disabled_by_default(env, expected):
    assert _debug_flag_with(env) is expected


def test_settings_default_env_is_production():
    """settings.json 默认 env 必须为 production（防误配回退）。
    用项目 ConfigLoader 的正规注释剥离器（简陋正则会误删字符串内 URL 的 //）。"""
    import sys
    sys.path.insert(0, str(PROJECT_ROOT))
    from config.loader import ConfigLoader
    assert ConfigLoader().load_config()['flask']['env'] == 'production'
