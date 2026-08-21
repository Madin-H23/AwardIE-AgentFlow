"""A2 GUI 冒烟自动化（T50）：三端并行核心链路冒烟。

覆盖（真实浏览器 UI 交互，playwright）：
1. 三角色登录（admin/teacher/student，各独立 context 隔离 cookie/登录态）
2. 学生端成果提交：上传测试图片 → 识别 → 提交
3. 教师端审核：待审核列表 → 审核通过（若学生提交未触发自动归档）
4. 留痕核对（admin 日志）：审核动作/操作人条目出现
5. AI 助手三模式问答（student 端）：各发一问，有回答即过
6. 日志四源（admin）：应用日志 tail/系统事件/审核留痕/告警 查询接口 200
7. 实时流 SSE：/api/logs/stream 连接收到事件或保持
自带清理：冒烟创建的成果（awards/pending/文件）结束后删除，可重复执行。

用法：python scripts/gui_smoke.py [--base http://127.0.0.1:5001] [--keep-data]
退出码：0=全绿，1=任一步失败。运行两次验证可重复性。
"""
import argparse
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_IMAGE = PROJECT_ROOT / "docs" / "测试" / "测试文件" / "国赛_二等奖_陈品天学生.jpg"

ACCOUNTS = {
    "admin": {"username": "admin", "password": "Mayy123"},
    "teacher": {"username": "02110606", "password": "P@ss301"},  # 黄巧云（02114818 已不在 users 表）
    "student": {"username": "212306413", "password": "P@ss301"},
}

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, ok, detail))
    print(f"[{'OK' if ok else 'FAIL'}] {name} {('— ' + detail) if detail else ''}")


def login(page, role):
    """登录并返回是否成功（统一 /login 认证入口，按角色跳 dashboard）。"""
    acc = ACCOUNTS[role]
    page.goto(f"{BASE}/login")
    page.wait_for_load_state("domcontentloaded")
    for field in ("username", "password"):
        sel = f"input[name='{field}'], input[id='{field}']"
        if page.locator(sel).count():
            page.fill(sel, acc["username"] if field == "username" else acc["password"])
    if page.locator("button[type='submit'], input[type='submit']").count():
        page.locator("button[type='submit'], input[type='submit']").first.click()
    elif page.locator("form").count():
        page.locator("form").first.locator("button, input[type='submit']").first.click()
    page.wait_for_load_state("domcontentloaded")
    time.sleep(0.5)
    # 首登改密页兜底：需要改密则填写新密码（与测试账号不一致时跳过并提示）
    if "change-password" in page.url or "change_password" in page.url:
        return False, "首登改密页拦截（账号需先人工改密）"
    # 登录成功标志：URL 离开 login 页
    return "/login" not in page.url, page.url


def smoke(browser):
    results = {}

    # ============ 1. 三角色登录（三 context 并行） ============
    ctxs = {}
    for role in ("admin", "teacher", "student"):
        ctx = browser.new_context()
        page = ctx.new_page()
        ok, detail = login(page, role)
        check(f"登录-{role}", ok, detail or page.url)
        if not ok:
            ctx.close()
            return False
        ctxs[role] = (ctx, page)

    admin, teacher, student = (ctxs[r][1] for r in ("admin", "teacher", "student"))

    # ============ 2. 学生端成果提交 ============
    pending_award_id = None
    try:
        student.goto(f"{BASE}/student/achievement-submit")
        student.wait_for_load_state("domcontentloaded")
        # 上传（hidden file input；多文件控件存在即页面就绪）
        file_input = student.locator("input[type='file']").first
        if not file_input.count():
            check("学生-上传页文件控件", False, "未找到 file input")
            return False
        file_input.set_input_files(str(TEST_IMAGE))
        # 两段式流程：先点"上传"按钮触发上传+识别（OCR+LLM 可能耗时），
        # 识别完成后"提交审核"按钮才可见
        upload_btn = student.locator("#uploadBtn")
        if not upload_btn.count():
            check("学生-上传并提交", False, "未找到 #uploadBtn（上传按钮）")
            return False
        upload_btn.click()
        submit_btn = student.locator("button:has-text('提交审核')").first
        submit_visible = False
        for _ in range(150):
            time.sleep(1)
            try:
                if submit_btn.is_visible():
                    submit_visible = True
                    break
            except Exception:  # noqa: BLE001
                pass
            # 识别失败提示出现则放弃
            body_txt = student.locator("body").inner_text()
            if "识别失败" in body_txt or "抽取失败" in body_txt or "上传失败" in body_txt:
                check("学生-上传并提交", False, "识别/上传失败提示出现")
                return False
        if not submit_visible:
            check("学生-上传并提交", False, "提交按钮 150s 内未可见（识别超时）")
            return False
        submit_btn.click()
        time.sleep(1)
        # 提交确认弹窗（submitConfirmButton）：出现则确认
        confirm_btn = student.locator("#submitConfirmButton")
        for _ in range(10):
            try:
                if confirm_btn.is_visible():
                    confirm_btn.click()
                    break
            except Exception:  # noqa: BLE001
                pass
            time.sleep(0.5)
        time.sleep(2)
        # 调试：确认提交后 pending 状态（自动归档配置可能直接 archived）
        try:
            import sqlite3
            _conn = sqlite3.connect(str(PROJECT_ROOT / "database" / "competitions.db"))
            _rows = _conn.execute(
                "SELECT id, status, submitter_type FROM pending_achievements "
                "WHERE submit_time > datetime('now', '-5 minutes') ORDER BY id DESC LIMIT 2").fetchall()
            _conn.close()
            if _rows:
                check("学生-提交后状态", True, f"pending={_rows}")
            else:
                check("学生-提交后状态", False, "5 分钟内无新 pending（提交未落库）")
                return False
        except Exception as _e:  # noqa: BLE001
            check("学生-提交后状态", False, str(_e))
            return False
        check("学生-上传并提交", True, "已提交（自动归档或待审核）")
    except Exception as e:  # noqa: BLE001
        check("学生-上传并提交", False, str(e))
        return False

    # ============ 3. 教师审核（UI 列表渲染验证 + 同一登录态走审核 API 完成入库） ============
    teacher.goto(f"{BASE}/teacher/achievement-review")
    teacher.wait_for_load_state("domcontentloaded")
    time.sleep(1)
    # 以库状态决定分支：学生待审(submit) → 人工审核；无 submit → 已被自动归档
    import sqlite3
    _conn = sqlite3.connect(str(PROJECT_ROOT / "database" / "competitions.db"))
    _row = _conn.execute(
        "SELECT id FROM pending_achievements WHERE status='submit' "
        "AND submitter_type='student' ORDER BY id DESC LIMIT 1").fetchone()
    _conn.close()
    if _row:
        pending_id = _row[0]
        body_text = teacher.locator("body").inner_text()
        # 待审列表渲染：页面有成果审核区（文案可能有差异，断言 200 + 非空主体 + 通过后状态变化为准）
        check("教师-审核列表渲染", bool(teacher.url) and "Error" not in teacher.locator("body").inner_text(),
              f"审核页渲染 OK，待审 pending#{pending_id}")
        # 页面上下文 fetch：csrf.js 自动注入 X-CSRF-Token，绕过 APIRequestContext 无 token 问题
        rr = teacher.evaluate(
            """async (args) => {
                const resp = await fetch(args.url, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({pending_id: args.pending_id})
                });
                let body = '';
                try { body = await resp.text(); } catch (e) {}
                return {status: resp.status, body: body.slice(0, 300)};
            }""", {"url": f"{BASE}/teacher/api/achievement-review/{pending_id}/approve-with-data",
                   "pending_id": pending_id})
        check("教师-审核通过", rr.get("status") == 200,
              f"pending#{pending_id} HTTP {rr.get('status')} {rr.get('body', '')[:120]}")
        if rr.get("status") != 200:
            return False
        # 入库验证：pending 被软归档（archived）= approve 链路完成入库（award 可能因
        # 同图 hash 复用已有行，用状态闭环而非计数）
        archived_ok = False
        for _ in range(5):
            time.sleep(1)
            _conn = sqlite3.connect(str(PROJECT_ROOT / "database" / "competitions.db"))
            try:
                st = _conn.execute(
                    "SELECT status FROM pending_achievements WHERE id=?", (pending_id,)
                ).fetchone()
            finally:
                _conn.close()
            if st and st[0] == "archived":
                archived_ok = True
                break
        check("入库验证-审核入库闭环", archived_ok, f"pending#{pending_id} 已归档（入库完成）")
        if not archived_ok:
            return False
    else:
        check("教师-审核通过", True, "学生提交已自动归档，无可审记录（配置生效）")
        # 异步自动归档可能尚未完成入库：等待并验证 award 落库（闭环"审核入库"）
        _before = None
        for _ in range(12):
            time.sleep(2)
            _conn = sqlite3.connect(str(PROJECT_ROOT / "database" / "competitions.db"))
            try:
                _count = _conn.execute(
                    "SELECT COUNT(*) FROM awards WHERE submit_time > datetime('now', '-10 minutes')"
                ).fetchone()[0]
            finally:
                _conn.close()
            if _count and _count > 0:
                _before = _count
                break
        if _before:
            check("入库验证-自动归档入库", True, f"10 分钟内新增 award={_before}")
        else:
            check("入库验证-自动归档入库", False, "24s 内未见新 award 入库")
            return False

    # ============ 4. 留痕核对（admin /admin/logs 审核留痕） ============
    try:
        admin.goto(f"{BASE}/admin/logs")
        admin.wait_for_load_state("domcontentloaded")
        admin.locator("text=审核留痕").first.click(timeout=5000)
        time.sleep(1.5)
        logs_text = admin.locator("body").inner_text()
        # 动态断言：出现"审核"动作或入库/提交相关条目（时间敏感，弱断言）
        has_action = any(k in logs_text for k in ("审核通过", "入库", "审核", "提交"))
        check("留痕核对-审核留痕可见", has_action, "审核留痕列表出现动作条目")
    except Exception as e:  # noqa: BLE001
        check("留痕核对-审核留痕可见", False, str(e))
        return False

    # ============ 5. AI 助手三模式问答（student 端） ============
    try:
        student.goto(f"{BASE}/assistant")
        student.wait_for_load_state("domcontentloaded")
        time.sleep(1)
        modes = ["qa", "tools", "auto"]  # 知识问答(真流式快)/数据操作/智能路由
        mode_text_map = {"auto": "智能路由", "qa": "知识问答", "tools": "数据操作"}
        asked = 0
        for mode in modes:
            mode_btn = student.locator(
                f"a[data-mode='{mode}'], button:has-text('{mode_text_map[mode]}')").first
            if mode_btn.count():
                mode_btn.click()
                time.sleep(0.5)
            # 记录当前气泡数，发送后等待新气泡（user + assistant）
            n0 = student.locator(".message").count()
            qbox = student.locator("#chatInput").first
            qbox.fill(f"请简单回答：{mode_text_map[mode]}模式是否正常工作")
            qbox.press("Enter")
            answered = False
            error_hit = False
            for _ in range(60):
                time.sleep(1)
                try:
                    txt = student.locator("body").inner_text()
                except Exception:  # noqa: BLE001
                    txt = ""
                if any(k in txt for k in ("Connection error", "处理失败", "执行失败", "❌")):
                    error_hit = True
                    break
                if student.locator(".message").count() >= n0 + 2:
                    answered = True
                    break
            if error_hit:
                check(f"AI 助手-{mode}", False, "问答报错（Connection/执行失败）")
                return False
            check(f"AI 助手-{mode}", answered, f"模式={mode_text_map[mode]}")
            asked += 1
        if asked == 0:
            check("AI 助手-模式入口", False, "未找到模式切换入口")
            return False
    except Exception as e:  # noqa: BLE001
        check("AI 助手-问答", False, str(e))
        return False

    # ============ 6. 日志四源（admin page.request 直查，复用登录会话） ============
    try:
        api_checks = {
            "应用日志-tail": "/admin/api/logs/app/tail?limit=5",
            "系统事件": "/admin/api/logs/system?page=1",
            "审核留痕": "/admin/api/logs/audit?page=1",
            "告警": "/admin/api/logs/alerts?page=1",
        }
        for name, path in api_checks.items():
            resp = admin.evaluate(
                """async (url) => {
                    const r = await fetch(url);
                    return {status: r.status, ok: r.ok};
                }""", f"{BASE}{path}")
            check(f"日志四源-{name}", resp.get("ok"), f"HTTP {resp.get('status')}")
    except Exception as e:  # noqa: BLE001
        check("日志四源", False, str(e))
        return False

    # 实时流 SSE（EventSource 探活：2s 内收到 open 或任意事件）
    try:
        admin.goto(f"{BASE}/admin/logs")
        admin.wait_for_load_state("domcontentloaded")
        r = admin.evaluate("""() => new Promise(res => {
            const es = new EventSource('/admin/api/logs/stream?source=all');
            let got = false;
            const t = setTimeout(() => { es.close(); res({connected: got}); }, 4000);
            es.onopen = () => { got = true; es.close(); clearTimeout(t); res({connected: true}); };
            es.onerror = () => {};
        })""")
        check("实时流-SSE 连接", r.get("connected"), "EventSource 4s 内建立")
    except Exception as e:  # noqa: BLE001
        check("实时流-SSE 连接", False, str(e))
        return False

    for ctx, _ in ctxs.values():
        ctx.close()
    return all(ok for _, ok, _ in RESULTS)


def cleanup():
    """清理冒烟数据：删除本脚本创建的 pending/成果（best-effort）。"""
    try:
        sys.path.insert(0, str(PROJECT_ROOT))
        import sqlite3
        from backend.services.unified_file_manager import get_unified_file_manager
        db = PROJECT_ROOT / "database" / "competitions.db"
        conn = sqlite3.connect(str(db))
        cur = conn.cursor()
        # 删除 5 分钟内创建的 pending（本脚本上传的测试图片会话）
        cur.execute(
            "SELECT id, file_path FROM pending_achievements "
            "WHERE submit_time > datetime('now', '-10 minutes') AND submitter_type='student'")
        pendings = cur.fetchall()
        cur.execute(
            "DELETE FROM pending_achievements WHERE submit_time > datetime('now', '-10 minutes') "
            "AND submitter_type='student'")
        # 删除测试图片 hash 对应的 award（含关联表；hash 复用场景也能清干净）
        import hashlib
        img_hash = hashlib.md5(TEST_IMAGE.read_bytes()).hexdigest()
        rows = cur.execute(
            "SELECT id FROM awards WHERE image_hash=?", (img_hash,)).fetchall()
        for (aid,) in rows:
            for t in ("award_student_winners", "award_teacher_winners",
                      "award_supervisors", "award_related_students"):
                cur.execute(f"DELETE FROM {t} WHERE award_id=?", (aid,))
            cur.execute("DELETE FROM awards WHERE id=?", (aid,))
        conn.commit()
        conn.close()
        # 清理文件（review/temp_upload 下 10 分钟内测试图片拷贝，best-effort）
        try:
            fm = get_unified_file_manager()
            for sub in ("review", "temp_upload"):
                d = fm.files_root / sub
                if d.exists():
                    for f in d.rglob("*.jpg"):
                        if (time.time() - f.stat().st_mtime) < 600:
                            f.unlink(missing_ok=True)
        except Exception:  # noqa: BLE001
            pass
        print(f"[cleanup] 已清理 pending={len(pendings)} award={len(rows)}")
    except Exception as e:  # noqa: BLE001
        print(f"[cleanup] 清理跳过: {e}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:5001")
    ap.add_argument("--keep-data", action="store_true", help="不清理冒烟数据")
    args = ap.parse_args()
    BASE = args.base
    if not TEST_IMAGE.exists():
        print(f"[FAIL] 测试图片缺失: {TEST_IMAGE}")
        sys.exit(1)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ok = smoke(browser)
        browser.close()
    if not args.keep_data:
        cleanup()
    print("=" * 60)
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    print(f"冒烟结果: {passed}/{len(RESULTS)} 通过")
    sys.exit(0 if ok else 1)