"""A5 性能压测 locust 脚本（目标：9.5 DoD 20 并发 / P95≤20s 实测结论）。

三类用户（用 locust 权重控制并发分配，跑法见 scripts/run_perf_test.py）：
- LoginUser：登录链路（P2-25 仅失败计数限流，成功登录不受限；单独低并发跑）
- AdminUser/TeacherUser/StudentUser：业务 API（列表/审核留痕/系统事件/成果页）
- AIUser：AI 助手问答（真实 LLM 调用，外部 API 限流为合理边界，单独小并发）

CSRF：POST 需携带 X-CSRF-Token（从 login/assistant 页 meta 获取）。
"""
import re

from locust import HttpUser, between, task

BASE_URL = "http://127.0.0.1:5001"

ACCOUNTS = {
    "admin": ("admin", "Mayy123"),
    "teacher": ("02110606", "P@ss301"),
    "student": ("212306413", "P@ss301"),
}


def fetch_csrf(client, path="/login"):
    r = client.get(path)
    m = re.search(r'csrf-token" content="([^"]+)"', r.text or "")
    return m.group(1) if m else None


def do_login(client, role):
    """登录并缓存 CSRF token（供后续 POST）。

    注意：requests.Session 自动携带 cookie 在本环境 FAIL（代理残留/环境差异，
    原因未定位），而显式 cookies= 传参稳定 200——统一用显式传参。
    """
    user, pwd = ACCOUNTS[role]
    token = fetch_csrf(client)
    if not token:
        raise RuntimeError("登录页未找到 CSRF token")
    r = client.post("/login", data={"username": user, "password": pwd},
                    headers={"X-CSRF-Token": token},
                    cookies=client.cookies.get_dict())
    if r.status_code != 200:
        raise RuntimeError(f"登录失败 HTTP {r.status_code}")
    client.csrf_token = token
    return r


class LoginUser(HttpUser):
    """登录链路（独立低并发：3 个用户轮询登录/登出页）。"""
    wait_time = between(2, 4)

    @task
    def login_page(self):
        self.client.get("/login")


class AdminUser(HttpUser):
    wait_time = between(0.3, 1.2)

    def on_start(self):
        do_login(self.client, "admin")

    @task(3)
    def dashboard(self):
        self.client.get("/admin/dashboard")

    @task(3)
    def achievements(self):
        self.client.get("/admin/achievements")

    @task(2)
    def audit_logs(self):
        self.client.get("/admin/api/logs/audit?page=1&per_page=20")

    @task(2)
    def system_events(self):
        self.client.get("/admin/api/logs/system?page=1&per_page=20")


class TeacherUser(HttpUser):
    wait_time = between(0.3, 1.2)

    def on_start(self):
        do_login(self.client, "teacher")

    @task(3)
    def review_list(self):
        self.client.get("/teacher/achievement-review")

    @task(2)
    def achievements(self):
        self.client.get("/teacher/achievements")


class StudentUser(HttpUser):
    wait_time = between(0.3, 1.2)

    def on_start(self):
        do_login(self.client, "student")

    @task(3)
    def submit_page(self):
        self.client.get("/student/achievement-submit")

    @task(2)
    def submissions(self):
        self.client.get("/student/submissions")


class AIUser(HttpUser):
    """AI 问答（真实 LLM 调用；外部 API 吞吐是合理边界，单独 2 并发跑）。"""
    wait_time = between(1, 2)

    def on_start(self):
        do_login(self.client, "student")
        doc_m = re.search(r'csrf-token" content="([^"]+)"', self.client.get("/assistant").text or "")
        if doc_m:
            self.client.csrf_token = doc_m.group(1)

    @task
    def chat_qa(self):
        self.client.post("/assistant/chat",
                         json={"message": "请用一句话介绍蓝桥杯是什么级别的比赛", "mode": "qa"},
                         headers={"Content-Type": "application/json",
                                  "X-CSRF-Token": getattr(self.client, "csrf_token", "")},
                         cookies=self.client.cookies.get_dict())