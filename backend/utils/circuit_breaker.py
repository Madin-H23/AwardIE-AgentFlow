"""熔断器（P1-10 / 设计 AI 层 §6：Closed→Open→Half-Open）。

- 仅网络/服务类失败（Timeout/Connection/5xx）计数；4xx 参数错与业务异常不计
- 连续 fail_threshold 次失败 -> Open（cooldown 秒）；Half-Open 探活成功×success_threshold 复位
- 线程安全；进程级单例（按 name 注册）
"""
import logging
import threading
import time

logger = logging.getLogger(__name__)


class CircuitBreaker:
    _registry = {}
    _lock = threading.Lock()

    def __init__(self, name: str, fail_threshold: int = 5, window: float = 60.0,
                 cooldown: float = 60.0, success_threshold: int = 2):
        self.name = name
        self.fail_threshold = fail_threshold
        self.window = window
        self.cooldown = cooldown
        self.success_threshold = success_threshold
        self._state = "closed"          # closed / open / half_open
        self._fails = []
        self._half_ok = 0
        self._opened_at = 0.0
        self._mutex = threading.Lock()

    # ---------- 状态 ----------
    @property
    def state(self) -> str:
        with self._mutex:
            self._normalize()
            return self._state

    def _normalize(self):
        """open 冷却期过 -> half_open（惰性转换；供 state 读取与记录函数共用）。"""
        if self._state == "open" and time.time() - self._opened_at >= self.cooldown:
            self._state = "half_open"

    def remaining(self) -> int:
        with self._mutex:
            if self._state == "open":
                return max(0, int(self.cooldown - (time.time() - self._opened_at)))
            return 0

    # ---------- 记录 ----------
    def _prune(self):
        now = time.time()
        self._fails = [t for t in self._fails if now - t <= self.window]

    def record_success(self):
        with self._mutex:
            self._normalize()          # open 冷却过 -> half_open（半开计数从正确起点累计）
            if self._state == "half_open":
                self._half_ok += 1
                if self._half_ok >= self.success_threshold:
                    self._state = "closed"
                    self._fails = []
                    self._half_ok = 0
                    logger.info("[breaker] %s 恢复 closed", self.name)
            else:
                self._fails = []          # closed 态成功清失败窗口；半开计数只在复位时清

    def record_failure(self):
        with self._mutex:
            self._normalize()
            self._prune()
            if self._state == "half_open":
                self._open()
            else:
                self._fails.append(time.time())
                if len(self._fails) >= self.fail_threshold:
                    self._open()

    def _open(self):
        self._state = "open"
        self._opened_at = time.time()
        self._half_ok = 0
        logger.warning("[breaker] %s 熔断开启（cooldown=%ss）", self.name, self.cooldown)

    # ---------- 守卫上下文 ----------
    def guard(self):
        """with breaker.guard(): 调用外部服务。失败需调用方标记 record_failure。"""
        if self.state == "open":
            from backend.utils.app_error import BreakerOpenError
            raise BreakerOpenError(retry_after=self.remaining())
        return self

    # ---------- 注册表（进程级单例） ----------
    @classmethod
    def get(cls, name: str, **kwargs) -> "CircuitBreaker":
        with cls._lock:
            if name not in cls._registry:
                cls._registry[name] = cls(name, **kwargs)
            return cls._registry[name]


# 便捷：判定某异常是否属于"应计数"的网络/服务类失败
def is_service_failure(exc: Exception) -> bool:
    import requests
    if isinstance(exc, (requests.Timeout, requests.ConnectionError)):
        return True
    if isinstance(exc, requests.HTTPError):
        return exc.response is not None and exc.response.status_code >= 500
    return False
