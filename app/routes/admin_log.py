"""admin_log 蓝图：日志管理 API（阶段六 L4，日志系统设计 §5）。

18 接口：四源查询（audit/system/review/app）+ 分析看板 5 + 指标/告警/计划 + SSE 实时流。
鉴权统一 @require_role_api_json('admin')；响应统一 {trace_id, code, message, data}。
HTML 页面（/admin/logs）随 L5 前端落地。
"""
import json
import time

from flask import Blueprint, Response, jsonify, request, stream_with_context

from app.auth import require_role_api_json

bp = Blueprint('admin_log', __name__)


@bp.route('/logs')
@require_role_api_json('admin')
def index():
    """日志管理页面（阶段六 L5，控制台新体系首个页面）。"""
    from flask import render_template
    return render_template('admin/logs/console_logs.html')


def _ok(data=None, message="ok"):
    from flask import current_app
    return jsonify({"trace_id": current_app._current_trace_id(),
                    "code": 0, "message": message, "data": data})


def _int_arg(name, default):
    try:
        return int(request.args.get(name, default))
    except (TypeError, ValueError):
        return default


# ==================== 查询类 ====================

@bp.route('/api/logs/audit')
@require_role_api_json('admin')
def query_audit():
    from backend.services.log_query_service import LogQueryService
    r = LogQueryService.query_audit_logs(
        page=_int_arg('page', 1), per_page=_int_arg('per_page', 50),
        action_type=request.args.get('action_type', type=int),
        operator_role=request.args.get('operator_role', type=int),
        achievement_id=request.args.get('achievement_id', type=int),
        trace_id=request.args.get('trace_id') or None,
        start_date=request.args.get('start_date') or None,
        end_date=request.args.get('end_date') or None)
    return _ok(r)


@bp.route('/api/logs/system')
@require_role_api_json('admin')
def query_system():
    from backend.services.log_query_service import LogQueryService
    r = LogQueryService.query_system_events(
        page=_int_arg('page', 1), per_page=_int_arg('per_page', 50),
        category=request.args.get('category') or None,
        level=request.args.get('level') or None,
        trace_id=request.args.get('trace_id') or None,
        start_date=request.args.get('start_date') or None,
        end_date=request.args.get('end_date') or None)
    return _ok(r)


@bp.route('/api/logs/review')
@require_role_api_json('admin')
def query_review():
    from backend.services.log_query_service import LogQueryService
    r = LogQueryService.query_review_logs(
        page=_int_arg('page', 1), per_page=_int_arg('per_page', 50),
        action_type=request.args.get('action_type') or None,
        reviewer_id=request.args.get('reviewer_id', type=int),
        submitter_id=request.args.get('submitter_id', type=int),
        start_date=request.args.get('start_date') or None,
        end_date=request.args.get('end_date') or None)
    return _ok(r)


@bp.route('/api/logs/app')
@require_role_api_json('admin')
def query_app_log():
    from backend.services.log_file_reader import LogFileReader
    rows = LogFileReader.search(
        keyword=request.args.get('keyword') or None,
        level=request.args.get('level') or None,
        limit=_int_arg('limit', 500),
        start_time=request.args.get('start_time') or None,
        end_time=request.args.get('end_time') or None)
    return _ok({"items": rows, "total": len(rows)})


@bp.route('/api/logs/app/tail')
@require_role_api_json('admin')
def tail_app_log():
    from backend.services.log_file_reader import LogFileReader
    rows = LogFileReader.tail(lines=_int_arg('lines', 100))
    return _ok({"items": rows, "total": len(rows)})


# ==================== 分析类 ====================

@bp.route('/api/logs/analysis/actions')
@require_role_api_json('admin')
def analysis_actions():
    from backend.services.log_analyzer import LogAnalyzer
    return _ok(LogAnalyzer.action_distribution(
        start_date=request.args.get('start_date') or None,
        end_date=request.args.get('end_date') or None))


@bp.route('/api/logs/analysis/errors')
@require_role_api_json('admin')
def analysis_errors():
    from backend.services.log_analyzer import LogAnalyzer
    return _ok(LogAnalyzer.error_trend(days=_int_arg('days', 7)))


@bp.route('/api/logs/analysis/bottleneck')
@require_role_api_json('admin')
def analysis_bottleneck():
    from backend.services.log_analyzer import LogAnalyzer
    return _ok(LogAnalyzer.review_bottleneck())


@bp.route('/api/logs/analysis/activity')
@require_role_api_json('admin')
def analysis_activity():
    from backend.services.log_analyzer import LogAnalyzer
    return _ok(LogAnalyzer.user_activity(top_n=_int_arg('top_n', 10)))


@bp.route('/api/logs/analysis/ai-health')
@require_role_api_json('admin')
def analysis_ai_health():
    from backend.services.log_analyzer import LogAnalyzer
    return _ok({"ai_health": LogAnalyzer.ai_health(),
                "audit_write": LogAnalyzer.audit_write_health()})


@bp.route('/api/logs/metrics')
@require_role_api_json('admin')
def metrics_snapshot():
    from backend.services.metrics_snapshot import collect
    return _ok(collect())


@bp.route('/api/logs/daily-report')
@require_role_api_json('admin')
def daily_report():
    from backend.services.plan_generator import daily_report as _dr
    return _ok(_dr())


# ==================== 告警与计划 ====================

@bp.route('/api/logs/alerts')
@require_role_api_json('admin')
def current_alerts():
    from backend.services.alert_engine import evaluate
    alerts = evaluate()
    return _ok({"items": alerts, "total": len(alerts)})


@bp.route('/api/logs/alerts/history')
@require_role_api_json('admin')
def alert_history():
    from backend.services.alert_engine import get_recent_alerts
    rows = get_recent_alerts(days=_int_arg('days', 7))
    return _ok({"items": rows, "total": len(rows)})


@bp.route('/api/logs/plan')
@require_role_api_json('admin')
def plan_list():
    from backend.services.plan_generator import generate
    plans = generate()
    return _ok({"items": plans, "total": len(plans)})


@bp.route('/api/logs/plan/<plan_id>/acknowledge', methods=['POST'])
@require_role_api_json('admin')
def plan_acknowledge(plan_id):
    from backend.services.plan_generator import generate, transition
    plans = [p for p in generate() if p["id"] == plan_id]
    if not plans:
        return _ok(None, message=f"计划项不存在或已流转: {plan_id}")
    p = plans[0]
    if p["status"] in ("resolved", "ignored"):
        # 幂等处理：已结束流转的计划重复确认不再抛 500
        return _ok(p, message=f"计划已处于 {p['status']} 状态，无需确认")
    transition(p, "acknowledged")
    return _ok(p)


@bp.route('/api/logs/plan/<plan_id>/resolve', methods=['POST'])
@require_role_api_json('admin')
def plan_resolve(plan_id):
    from backend.services.plan_generator import generate, transition
    plans = [p for p in generate() if p["id"] == plan_id]
    if not plans:
        return _ok(None, message=f"计划项不存在或已流转: {plan_id}")
    p = plans[0]
    if p["status"] in ("resolved",):
        return _ok(p, message="计划已解决")
    if p["status"] == "ignored":
        return _ok(p, message="计划已忽略，7 天后重评估")
    transition(p, "acknowledged")
    transition(p, "resolved")
    return _ok(p)


# ==================== SSE 实时流 ====================

_SSE_CONN = {}   # user -> 当前连接数（进程内；多 worker 场景随 Redis 迁移统一，R-014 同源）


@bp.route('/api/logs/stream')
@require_role_api_json('admin')
def stream():
    """SSE 实时日志流：source=app（文件增量）/audit/system（DB 轮询）。

    协议：open → log* → ping(30s)；每管理员并发 ≤2，超限 429。
    """
    from flask import session
    user = str(session.get('user_id', 'anon'))
    if _SSE_CONN.get(user, 0) >= 2:
        return jsonify({"code": 4029, "message": "SSE 并发连接超限（≤2）"}), 429

    source = request.args.get('source', 'app')
    level = request.args.get('level') or None
    keyword = request.args.get('keyword') or None

    _SSE_CONN[user] = _SSE_CONN.get(user, 0) + 1

    def gen():
        try:
            yield f"event: open\ndata: {json.dumps({'source': source, 'level': level, 'keyword': keyword})}\n\n"
            last_id = 0
            last_ping = time.time()
            from backend.services.log_file_reader import LogFileReader, parse_line
            from backend.services.log_query_service import LogQueryService
            # app 文件用非阻塞 readline 增量（只推新增行）：
            # 旧实现 LogFileReader.stream 是阻塞生成器——source=all 时先 next() 卡在 app 等待，
            # audit/system 新事件推不出（实时流只有"已连接"）。非阻塞后可每轮交替轮询全部源。
            app_f = None
            if source in ("app", "all"):
                _p = LogFileReader._path()
                if _p.exists():
                    app_f = open(_p, "r", encoding="utf-8", errors="replace")
                    app_f.seek(0, 2)
            while True:
                sent = False
                if app_f:
                    line = app_f.readline()
                    while line:
                        parsed = parse_line(line)
                        if parsed and (not level or parsed.get("level") == level) and (
                                not keyword or keyword.lower() in (parsed.get("msg") or "").lower()):
                            yield f"event: log\ndata: {json.dumps({'source': 'app', **parsed}, ensure_ascii=False)}\n\n"
                            sent = True
                        line = app_f.readline()
                if source in ("audit", "system", "all"):
                    srcs = ["audit", "system"] if source == "all" else [source]
                    for src in srcs:
                        fn = {"audit": "query_audit_logs", "system": "query_system_events"}[src]
                        r = getattr(LogQueryService, fn)(page=1, per_page=20)
                        new = [it for it in r["items"] if it.get("id", 0) > last_id]
                        if new:
                            last_id = max(it.get("id", 0) for it in new)
                            for it in new:
                                yield f"event: log\ndata: {json.dumps({'source': src, **it}, ensure_ascii=False, default=str)}\n\n"
                            sent = True
                if not sent and time.time() - last_ping >= 30:
                    yield f"event: ping\ndata: {json.dumps({'ts': int(time.time())})}\n\n"
                    last_ping = time.time()
                time.sleep(1 if sent else 0.5)
        finally:
            if 'app_f' in locals() and app_f:
                app_f.close()
            _SSE_CONN[user] = max(0, _SSE_CONN.get(user, 0) - 1)

    resp = Response(stream_with_context(gen()), mimetype="text/event-stream")
    resp.headers['Cache-Control'] = 'no-cache'
    resp.headers['X-Accel-Buffering'] = 'no'
    return resp
