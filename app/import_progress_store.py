"""
批量导入进度存储：与请求生命周期解耦，供上传请求写入、进度接口读取。
解决 Cookie Session 在长请求未结束前无法被其他请求读到的问题。
"""
import threading
import time

_store = {}
_lock = threading.Lock()

# 完成后保留时长（秒），超时清理避免内存堆积
_COMPLETED_TTL = 300


def _default_progress():
    return {
        'total': 0,
        'current': 0,
        'current_file': '',
        'current_step': '',
        'status': 'idle',
        'uploaded_count': 0,
        'stats': {
            'award': {'valid': 0, 'invalid': 0},
            'patent': {'valid': 0, 'invalid': 0},
            'software': {'valid': 0, 'invalid': 0},
            'innovation': {'valid': 0, 'invalid': 0},
            'other': {'valid': 0, 'invalid': 0}
        },
        'errors': []
    }


def set_progress(task_id: str, data: dict) -> None:
    """设置某任务的完整进度（覆盖）。"""
    with _lock:
        data = dict(data)
        data['_updated_at'] = time.time()
        _store[task_id] = data


def update_progress(task_id: str, **kwargs) -> None:
    """更新某任务进度（部分字段）。"""
    with _lock:
        if task_id not in _store:
            _store[task_id] = _default_progress()
        _store[task_id].update(kwargs)
        _store[task_id]['_updated_at'] = time.time()


def get_progress(task_id: str) -> dict | None:
    """读取某任务进度；若不存在或已过期则返回 None。"""
    with _lock:
        if task_id not in _store:
            return None
        entry = _store[task_id].copy()
    # 不对外暴露内部字段
    entry.pop('_updated_at', None)
    # 完成后超时清理
    if entry.get('status') == 'completed':
        with _lock:
            t = _store[task_id].get('_updated_at', 0)
            if time.time() - t > _COMPLETED_TTL:
                _store.pop(task_id, None)
    return entry


def get_progress_or_idle(task_id: str) -> dict:
    """读取进度；无 task_id 或不存在时返回 idle 结构。"""
    if not (task_id or '').strip():
        return _default_progress()
    out = get_progress((task_id or '').strip())
    return out if out is not None else _default_progress()
