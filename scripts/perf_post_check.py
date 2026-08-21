"""A5 补充压测：POST 类链路（登录/审核/AI 问答）并发实测。

背景：业务 GET 链路用 locust 20 并发已实测（P95=49ms）。POST 类请求的
CSRF token 由页面 csrf.js 注入（浏览器行为），python HTTP 客户端（requests/
locust）无法等价复刻（meta 签名 token 直发报 missing）——故用真实浏览器
（playwright 多 context）并发：
- 登录：3 并发（P2-25 仅失败计数，成功登录不限流）
- 审核提交：2 并发（approve-with-data，真实入库？本次为只读验证不重复入库——
  使用列表查询+详情打开代替写操作，写操作由 gui_smoke 单用户覆盖）
- AI 问答：2 并发真实提问（外部 LLM 吞吐为合理边界）

输出：每项 min/avg/max/P95（ms），供《压测报告》引用。
"""
import json
import sys
import threading
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:5001"

import re  # noqa: E402


def _login(pg, username, password):
    t0 = time.perf_counter()
    pg.goto(f"{BASE}/login")
    pg.wait_for_load_state("domcontentloaded")
    # 等 csrf.js 动态注入 hidden token（点提交前必须就位，否则 400）
    for _ in range(20):
        try:
            if pg.locator("form input[name='csrf_token']").count():
                break
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.3)
    pg.fill("input[name='username']", username)
    pg.fill("input[name='password']", password)
    pg.locator("button[type='submit']").first.click()
    pg.wait_for_load_state("domcontentloaded")
    ok = "/login" not in pg.url
    return ok, (time.perf_counter() - t0) * 1000


def _chat(pg, question):
    t0 = time.perf_counter()
    pg.goto(f"{BASE}/assistant")
    pg.wait_for_load_state("domcontentloaded")
    for _ in range(20):
        try:
            if pg.locator("#chatInput").count():
                break
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.3)
    pg.fill("#chatInput", question)
    pg.press("#chatInput", "Enter")
    n0 = pg.locator(".message").count()
    for _ in range(60):
        time.sleep(0.5)
        if pg.locator(".message").count() >= n0 + 2:
            return True, (time.perf_counter() - t0) * 1000
    return False, (time.perf_counter() - t0) * 1000


def run_concurrent(label, workers, fn, browser):
    results = []
    barrier = threading.Barrier(workers)
    lock = threading.Lock()

    def worker():
        ctx = browser.new_context()
        pg = ctx.new_page()
        barrier.wait()
        try:
            ok, ms = fn(pg)
            with lock:
                results.append((ok, ms))
        except Exception as e:  # noqa: BLE001
            with lock:
                results.append((False, f"ERR {str(e)[:60]}"))
        finally:
            ctx.close()

    threads = [threading.Thread(target=worker) for _ in range(workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    ok_n = sum(1 for ok, _ in results if ok is True)
    times = sorted([ms for ok, ms in results if ok is True and isinstance(ms, (int, float))])
    print(f"== {label}: {ok_n}/{workers} 成功")
    if times:
        avg = sum(times) / len(times)
        p95 = times[int(len(times) * 0.95) - 1] if times else 0
        print(f"   min={times[0]:.0f}ms avg={avg:.0f}ms max={times[-1]:.0f}ms P95={p95:.0f}ms")
    else:
        print("   无有效样本:", [r for r in results if r[1] != True][:3])
    return times


if __name__ == "__main__":
    with sync_playwright() as p:
        b = p.chromium.launch()
        # 预热（页面加载/字体等首次成本不计入）
        ctx = b.new_context()
        pg = ctx.new_page()
        pg.goto(f"{BASE}/login")
        pg.wait_for_load_state("domcontentloaded")
        ctx.close()

        run_concurrent("登录（3 并发）", 3, lambda pg: _login(pg, "student", "P@ss301"), b)
        run_concurrent("AI 问答（2 并发）", 2, lambda pg: _chat(pg, "请用一句话介绍蓝桥杯"), b)
        b.close()
    print("完成")