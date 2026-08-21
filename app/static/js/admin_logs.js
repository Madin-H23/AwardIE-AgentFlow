/* admin_logs.js —— L5 日志管理页交互（对接 L4 admin_log 蓝图 19 接口）
 * Tab1 日志查看：三源分页查询 + SSE 实时流（断线自动重连提示）
 * Tab2 分析看板：生命体征带 + 6 ECharts（配色读 CSS token，随主题重绘）
 * Tab3 行动计划：列表 + acknowledge/resolve 流转
 */
(function () {
  'use strict';

  // 动作中文标签（与 backend audit_logger.ACTION_LABELS 对齐）
  var ACTION_LABELS = { 1: '提交', 2: 'AI 审核', 3: 'AI 通过', 4: 'AI 驳回', 5: '教师复核',
                        6: '审核通过', 7: '驳回打回', 8: '入库', 9: '修改字段', 10: '删除/放弃',
                        11: '撤回', 12: '成果删除' };
  function actionLabel(k) { return ACTION_LABELS[k] || ('动作' + k); }
  /* 成果编号阶段语义：动作8=入库后(awards.id)→'成果#'；其余作用于待审(pending.id)→'待审成果#' */
  function entityTag(type, id) { return (type === 8 || type === 12 ? '成果#' : '待审成果#') + id; }

  /* ---------- 工具 ---------- */
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function api(url, opts) {
    return fetch(url, Object.assign({ headers: { 'X-CSRF-Token': csrfToken() } }, opts || {}))
      .then(function (r) { return r.json(); })
      .then(function (body) {
        if (body && body.code === 0) return body.data;
        throw new Error((body && body.message) || '请求失败');
      });
  }
  function csrfToken() {
    var m = document.querySelector('meta[name="csrf-token"]');
    return m ? m.content : '';
  }
  function cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || '#666';
  }
  function setVital(id, value, sub, dotState) {
    var v = document.getElementById('vital-' + id + '-value');
    if (v) v.textContent = value;
    var s = document.getElementById('vital-' + id + '-sub');
    if (s && sub != null) s.textContent = sub;
    var d = document.getElementById('vital-' + id + '-dot');
    if (d && dotState) { d.classList.toggle('down', dotState === 'down'); d.style.display = ''; }
  }
  function emptyBox(text) { return '<div class="empty-state">' + esc(text) + '</div>'; }

  /* ---------- Tab1 日志查看 ---------- */
  var state = { source: 'audit', page: 1, perPage: 50 };
  var stream = null;

  function filterParams() {
    var form = document.querySelector('[data-console-filter]');
    var p = {};
    if (!form) return p;
    new FormData(form).forEach(function (v, k) { if (v) p[k] = v; });
    return p;
  }
  window.onFilterSearch = function () { state.page = 1; loadLogs(); };

  function logRowHtml(it, source) {
    if (source === 'audit') {
      return '<div class="log-row" data-detail="' + esc(JSON.stringify(it)) + '">' +
        '<span class="log-ts">' + esc((it.created_at || '').slice(5, 19)) + '</span>' +
        '<span class="severity-bar sev-info" style="min-width:52px">' + esc(it.action_label || actionLabel(it.action_type)) + '</span>' +
        '<span class="log-msg">' + esc(it.operator_display || it.operator_name || it.operator_code || '-') + ' · ' + esc(entityTag(it.action_type, it.achievement_id)) + '</span></div>';
    }
    if (source === 'system') {
      var lv = (it.event_level || 'info').toLowerCase();
      return '<div class="log-row" data-detail="' + esc(JSON.stringify(it)) + '">' +
        '<span class="log-ts">' + esc((it.created_at || '').slice(5, 19)) + '</span>' +
        '<span class="severity-bar sev-' + esc(lv) + '" style="min-width:60px">' + esc(lv) + '</span>' +
        '<span class="log-msg">[' + esc(it.event_category) + '] ' + esc(it.event_message) + '</span></div>';
    }
    var lv2 = (it.level || 'info').toLowerCase();
    return '<div class="log-row">' +
      '<span class="log-ts">' + esc((it.ts || '').slice(5, 19)) + '</span>' +
      '<span class="severity-bar sev-' + esc(lv2) + '" style="min-width:60px">' + esc(lv2) + '</span>' +
      '<span class="log-msg">[' + esc(it.logger || '') + '] ' + esc(it.msg || it.raw || '') + '</span></div>';
  }

  function loadLogs() {
    var box = document.getElementById('logStream');
    var status = document.getElementById('logStreamStatus');
    if (state.source === 'stream') { startStream(); return; }
    stopStream();
    var p = filterParams();
    var url;
    if (state.source === 'app') {
      if (p.keyword || p.level || p.start_date || p.end_date) {
        // 带过滤：search（旧→新，全文匹配）
        url = '/admin/api/logs/app?limit=' + state.perPage +
          (p.keyword ? '&keyword=' + encodeURIComponent(p.keyword) : '') +
          (p.level ? '&level=' + p.level : '') +
          (p.start_date ? '&start_time=' + p.start_date : '') + (p.end_date ? '&end_time=' + p.end_date + ' 23:59:59' : '');
      } else {
        // 默认视图：tail 倒读最新 N 条（新→旧，avoid 拿到文件头旧日志）
        url = '/admin/api/logs/app/tail?lines=' + state.perPage;
      }
    } else {
      url = '/admin/api/logs/' + state.source + '?page=' + state.page + '&per_page=' + state.perPage +
        (p.level ? '&level=' + p.level : '') +
        (p.keyword ? '&trace_id=' + encodeURIComponent(p.keyword) : '') +
        (p.start_date ? '&start_date=' + p.start_date : '') + (p.end_date ? '&end_date=' + p.end_date + ' 23:59:59' : '');
    }
    box.innerHTML = '<div class="empty-state">加载中…</div>';
    api(url).then(function (d) {
      var items = d.items || [];
      box.innerHTML = items.length
        ? items.map(function (it) { return logRowHtml(it, state.source); }).join('')
        : emptyBox('暂无日志记录——系统安静运行中');
      if (state.source !== 'app' && d.total != null) {
        var pages = Math.max(1, Math.ceil(d.total / state.perPage));
        document.getElementById('logPageInfo').textContent = state.page + ' / ' + pages;
        status.textContent = '共 ' + d.total + ' 条';
      } else {
        document.getElementById('logPageInfo').textContent = '—';
        status.textContent = '最近 ' + items.length + ' 行';
      }
    }).catch(function (e) { box.innerHTML = emptyBox('加载失败：' + e.message); });
  }

  /* 行点击展开详情（JSON 格式化） */
  document.addEventListener('click', function (ev) {
    var row = ev.target.closest('.log-row');
    if (!row || !row.dataset.detail) return;
    var open = row.nextElementSibling;
    if (open && open.classList.contains('log-detail')) { open.remove(); return; }
    document.querySelectorAll('.log-detail').forEach(function (n) { n.remove(); });
    var div = document.createElement('div');
    div.className = 'log-detail mono-data';
    div.style.cssText = 'padding:10px 14px;background:color-mix(in srgb,var(--ink) 4%,var(--panel));border-bottom:1px solid var(--line);font-size:.76rem;white-space:pre-wrap;color:var(--ink-2)';
    try { div.textContent = JSON.stringify(JSON.parse(row.dataset.detail), null, 2); }
    catch (e) { div.textContent = row.dataset.detail; }
    row.after(div);
  });

  /* SSE 实时流 */
  function startStream() {
    stopStream();
    var box = document.getElementById('logStream');
    var status = document.getElementById('logStreamStatus');
    box.innerHTML = '';
    var count = 0, lines = [];
    status.textContent = '实时流连接中…';
    try {
      stream = new EventSource('/admin/api/logs/stream?source=all');
      stream.addEventListener('open', function () { status.textContent = '实时流已连接'; });
      stream.addEventListener('log', function (ev) {
        try {
          var it = JSON.parse(ev.data);
          var src = it.source || 'app';
          var html = src === 'app'
            ? logRowHtml(it, 'app')
            : logRowHtml(Object.assign({ created_at: it.created_at, event_level: it.event_level, event_category: it.event_category, event_message: it.event_message || it.operator_name || '' }, it), src);
          lines.push(html); count++;
          if (lines.length > 200) lines.shift();
          box.innerHTML = lines.join('');
          status.textContent = '实时流已连接 · 已接收 ' + count + ' 条';
        } catch (e) { /* 忽略坏帧 */ }
      });
      stream.onerror = function () { status.textContent = '实时流已断开，正在重连…'; };
    } catch (e) { status.textContent = '浏览器不支持 EventSource'; }
  }
  function stopStream() { if (stream) { stream.close(); stream = null; } }

  document.querySelectorAll('#srcTabs [data-log-source]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      document.querySelectorAll('#srcTabs .nav-link').forEach(function (b) { b.classList.remove('active'); });
      btn.classList.add('active');
      state.source = btn.dataset.logSource; state.page = 1;
      loadLogs();
    });
  });
  document.getElementById('logPrevPage').addEventListener('click', function () { if (state.page > 1) { state.page--; loadLogs(); } });
  document.getElementById('logNextPage').addEventListener('click', function () { state.page++; loadLogs(); });
  document.addEventListener('reset-filter', function () { state.page = 1; });

  /* ---------- Tab2 分析看板 ---------- */
  var charts = {};
  function mkChart(id) {
    var el = document.getElementById(id);
    if (!el || typeof echarts === 'undefined') return null;
    if (charts[id]) { charts[id].dispose(); }
    charts[id] = echarts.init(el);
    return charts[id];
  }
  function baseText() {
    return { color: cssVar('--ink'), fontFamily: 'ui-monospace, Consolas, monospace' };
  }

  function loadDashboard() {
    /* 体征带 */
    api('/admin/api/logs/daily-report').then(function (d) {
      setVital('auditToday', d.audit_actions || 0);
    }).catch(function () { setVital('auditToday', '—'); });
    api('/admin/api/logs/analysis/bottleneck').then(function (b) {
      setVital('backlog', b.pending_total, '超 48h：' + b.over_48h + ' 条 · 最长等待 ' + b.max_wait_hours + 'h');
    }).catch(function () {});
    api('/admin/api/logs/analysis/ai-health').then(function (d) {
      var ai = d.ai_health || {};
      var breakers = ai.breakers || {};
      var bad = Object.keys(breakers).some(function (k) { return breakers[k] === 'open'; });
      setVital('aiState', bad ? '降级' : '正常', Object.keys(breakers).map(function (k) { return k + ':' + breakers[k]; }).join(' · ') || '—',
        bad ? 'down' : 'ok');
      chartAi(ai);
      chartAuditRate(d.audit_write || {});
    }).catch(function () {});
    api('/admin/api/logs/alerts').then(function (d) {
      setVital('alertCount', d.total || 0);
      var list = document.getElementById('alertList');
      document.getElementById('alertSummary').textContent = d.total ? (d.total + ' 条待处理') : '';
      list.innerHTML = d.total
        ? d.items.map(function (a) {
            return '<div style="display:flex;gap:10px;padding:8px 6px;border-bottom:1px solid var(--line);align-items:baseline">' +
              '<span class="sev-chip sev-' + (a.severity === 'critical' ? 'critical' : 'warning') + '">' + esc(a.id) + '</span>' +
              '<span style="flex:1;font-size:.85rem">' + esc(a.message) + '</span>' +
              '<span style="font-size:.76rem;color:var(--ink-2)">' + esc(a.action || '') + '</span></div>';
          }).join('')
        : emptyBox('暂无告警——系统安静运行中');
    }).catch(function () {});

    /* 图表 */
    api('/admin/api/logs/analysis/actions').then(function (d) {
      var c = mkChart('chartActions'); if (!c) return;
      var keys = Object.keys(d);
      c.setOption({
        title: { text: '审核动作分布', left: 'center', textStyle: { fontSize: 13, color: cssVar('--ink') } },
        tooltip: { trigger: 'item' },
        series: [{ type: 'pie', radius: ['38%', '62%'], data: keys.map(function (k) { return { name: actionLabel(k), value: d[k] }; }) }]
      });
    }).catch(function () {});
    api('/admin/api/logs/analysis/errors?days=7').then(function (d) {
      var c = mkChart('chartErrors'); if (!c) return;
      c.setOption({
        title: { text: '错误趋势（7 日）', left: 'center', textStyle: { fontSize: 13, color: cssVar('--ink') } },
        tooltip: { trigger: 'axis' }, grid: { left: 40, right: 16, top: 40, bottom: 24 },
        xAxis: { type: 'category', data: d.map(function (x) { return x.date; }) },
        yAxis: { type: 'value' },
        series: [
          { name: 'error', type: 'line', smooth: true, data: d.map(function (x) { return x.error; }), itemStyle: { color: cssVar('--sev-error') } },
          { name: 'warning', type: 'line', smooth: true, data: d.map(function (x) { return x.warning; }), itemStyle: { color: cssVar('--sev-warning') } }
        ]
      });
    }).catch(function () {});
    api('/admin/api/logs/analysis/activity?top_n=8').then(function (d) {
      var c = mkChart('chartActivity'); if (!c) return;
      c.setOption({
        title: { text: '活跃用户 Top 8', left: 'center', textStyle: { fontSize: 13, color: cssVar('--ink') } },
        tooltip: {}, grid: { left: 90, right: 20, top: 40, bottom: 24 },
        xAxis: { type: 'value' },
        yAxis: { type: 'category', data: d.map(function (x) { return x.operator_display || x.operator_name || x.operator_code; }).reverse() },
        series: [{ type: 'bar', data: d.map(function (x) { return x.count; }).reverse(), itemStyle: { color: cssVar('--brand') } }]
      });
    }).catch(function () {});
    api('/admin/api/logs/analysis/bottleneck').then(function (b) {
      var c = mkChart('chartBottleneck'); if (!c) return;
      c.setOption({
        title: { text: '审核瓶颈（等待小时）', left: 'center', textStyle: { fontSize: 13, color: cssVar('--ink') } },
        tooltip: {}, grid: { left: 40, right: 20, top: 40, bottom: 24 },
        xAxis: { type: 'category', data: ['平均等待', '最长等待'] },
        yAxis: { type: 'value' },
        series: [{ type: 'bar', data: [b.avg_wait_hours, b.max_wait_hours], itemStyle: { color: cssVar('--sev-warning') }, barWidth: 46 }]
      });
    }).catch(function () {});
  }
  function chartAi(ai) {
    var c = mkChart('chartAi'); if (!c) return;
    var rate = ai.llm_success_rate;
    var val = rate == null ? 0 : Math.round(rate * 100);
    c.setOption({
      title: { text: 'LLM 成功率', left: 'center', textStyle: { fontSize: 13, color: cssVar('--ink') } },
      series: [{
        type: 'gauge', center: ['50%', '58%'], radius: '80%',
        detail: { formatter: rate == null ? '—' : '{value}%', fontSize: 18, color: cssVar('--ink') },
        data: [{ value: val }],
        axisLine: { lineStyle: { width: 12, color: [[0.5, cssVar('--sev-error')], [0.8, cssVar('--sev-warning')], [1, cssVar('--ok')]] } }
      }]
    });
  }
  function chartAuditRate(w) {
    var c = mkChart('chartAuditRate'); if (!c) return;
    var rate = w.total ? Math.round((1 - w.failure_rate) * 100) : 100;
    c.setOption({
      title: { text: '留痕写入成功率', left: 'center', textStyle: { fontSize: 13, color: cssVar('--ink') } },
      tooltip: {}, grid: { left: 50, right: 20, top: 50, bottom: 30 },
      xAxis: { type: 'category', data: ['成功率'] }, yAxis: { type: 'value', max: 100 },
      series: [{ type: 'bar', data: [rate], itemStyle: { color: rate >= 99 ? cssVar('--ok') : cssVar('--sev-warning') }, barWidth: 46 }]
    });
  }

  /* 主题切换 → 图表重绘（配色随 token） */
  document.addEventListener('console-theme-changed', function () {
    if (document.getElementById('tab-dashboard').classList.contains('active')) loadDashboard();
  });

  /* ---------- Tab3 行动计划 ---------- */
  function loadPlans() {
    var box = document.getElementById('planList');
    api('/admin/api/logs/plan').then(function (d) {
      if (!d.total) { box.innerHTML = emptyBox('暂无待办计划——没有需要处理的事项'); return; }
      box.innerHTML = d.items.map(function (p) {
        return '<div class="c-panel p-3 mb-2">' +
          '<div class="d-flex align-items-center gap-2 mb-1">' +
          '<span class="sev-chip sev-' + (p.priority === '高' ? 'critical' : 'warning') + '">' + esc(p.priority) + '优先</span>' +
          '<span class="sev-chip sev-info">' + esc(p.category) + '</span>' +
          '<strong style="font-size:.9rem">' + esc(p.title) + '</strong></div>' +
          '<div style="font-size:.84rem;color:var(--ink);margin-bottom:4px">' + esc(p.description) + '</div>' +
          '<div style="font-size:.78rem;color:var(--ink-2);margin-bottom:8px">建议：' + esc((p.suggested_actions || []).join('；')) + '</div>' +
          '<button class="c-btn c-btn-primary btn-sm" data-plan-ack="' + esc(p.id) + '">确认</button> ' +
          '<button class="c-btn btn-sm" data-plan-resolve="' + esc(p.id) + '">标记已解决</button></div>';
      }).join('');
    }).catch(function (e) { box.innerHTML = emptyBox('加载失败：' + e.message); });
  }
  document.addEventListener('click', function (ev) {
    var ack = ev.target.closest('[data-plan-ack]');
    var res = ev.target.closest('[data-plan-resolve]');
    var url, id;
    if (ack) { id = ack.dataset.planAck; url = '/admin/api/logs/plan/' + encodeURIComponent(id) + '/acknowledge'; }
    else if (res) { id = res.dataset.planResolve; url = '/admin/api/logs/plan/' + encodeURIComponent(id) + '/resolve'; }
    else return;
    api(url, { method: 'POST' }).then(function () { loadPlans(); })
      .catch(function (e) { alert('操作失败：' + e.message); });
  });

  /* ---------- Tab 懒加载初始化 ---------- */
  loadLogs();
  document.getElementById('tab-btn-dashboard').addEventListener('click', loadDashboard);
  document.getElementById('tab-btn-plan').addEventListener('click', loadPlans);
})();
