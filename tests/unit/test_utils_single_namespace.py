"""T73 验收：app.utils 双命名空间消除——_managers 全局仅一份。"""
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

PROBE_CODE = """
import sys
sys.path.insert(0, r"{root}")
import app.utils as pkg
from app.utils import _core
assert "app.utils_module" not in sys.modules, "双命名空间仍存在"
assert not hasattr(pkg, "_managers"), "包层不应再持有 _managers 副本"
pkg.reset_runtime_caches()
assert isinstance(_core._managers, dict)
print("OK")
""".format(root=str(PROJECT_ROOT))


def test_no_second_namespace_and_single_managers():
    """独立进程验证：sys.modules 无 app.utils_module；包层不持缓存副本。"""
    r = subprocess.run([sys.executable, "-c", PROBE_CODE],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-1500:]
    assert "OK" in r.stdout


def test_reexport_names_available():
    from app.utils import (get_app_context_instance, get_app_config,
                           calculate_file_hash, reset_runtime_caches,
                           get_user_route_url)
    assert callable(get_app_context_instance)
    assert callable(get_app_config)
    assert callable(calculate_file_hash)
    assert callable(reset_runtime_caches)
    assert callable(get_user_route_url)
