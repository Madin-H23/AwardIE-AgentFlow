/* dashboard.js —— 成果数据总览看板（仿百度云消费总览页信息架构）
   fetch 聚合接口 → 渲染资产条/汇总卡/竞赛表/趋势图；ECharts 读 token 随暗黑主题重绘。 */
(function () {
    'use strict';

    const $ = (id) => document.getElementById(id);

    function themeVars() {
        const s = getComputedStyle(document.documentElement);
        return {
            ink: s.getPropertyValue('--ink').trim(),
            ink2: s.getPropertyValue('--ink-2').trim(),
            line: s.getPropertyValue('--line').trim(),
            brand: s.getPropertyValue('--brand').trim(),
            panel: s.getPropertyValue('--panel').trim(),
            ok: s.getPropertyValue('--ok').trim(),
        };
    }

    let chart = null;
    let currentMonths = null;   // 周期筛选：近 N 月；null=全部
    const fmt = (n) => (n == null ? '–' : n.toLocaleString());

    function renderSummary(d) {
        const s = d.summary || {};
        const cat = d.category || {};
        const total = (s.total_awards || 0) + (cat.patent || 0) + (cat.software || 0) + (cat.innovation || 0) + (cat.other || 0);

        $('cTotal').textContent = fmt(total);
        $('sTotal').textContent = `奖状 ${s.total_awards || 0} · 专利 ${cat.patent || 0} · 软著 ${cat.software || 0} · 大创 ${cat.innovation || 0} · 其他 ${cat.other || 0}`;

        $('cPending').textContent = fmt(s.pending);
        $('sPending').textContent = s.pending > 0 ? '需人工处理' : '无积压';
        if (s.pending > 0) $('cPending').classList.add('alarming');

        $('cWhitelist').textContent = fmt(s.whitelist);
        $('sWhitelist').textContent = s.competitions ? `占 ${(s.whitelist / s.competitions * 100).toFixed(0)}% 竞赛` : '';

        const density = s.competitions ? (total / s.competitions) : 0;
        $('cDensity').textContent = density.toFixed(1);
        $('sDensity').textContent = `共 ${s.competitions || 0} 个竞赛`;

        // 汇总卡
        $('payNum').textContent = fmt(total);
        const cmp = d.compare || {};
        let cmpTxt = `本月新增 ${fmt(cmp.this)} · 上月 ${fmt(cmp.last)}`;
        if (cmp.delta_pct != null) {
            const up = cmp.delta_pct >= 0;
            cmpTxt += ` · 环比 <span class="mono-data ${up ? 'text-success' : 'text-danger'}">${up ? '▲' : '▼'}${Math.abs(cmp.delta_pct)}%</span>`;
        }
        $('paySub').innerHTML = `待审核 ${s.pending || 0} · 白名单竞赛 ${s.whitelist || 0}<br>${cmpTxt}`;
        $('catAward').textContent = fmt(s.total_awards);
        $('catPatent').textContent = fmt(cat.patent || 0);
        $('catSoftware').textContent = fmt(cat.software || 0);
        $('catInnovation').textContent = fmt(cat.innovation || 0);
        $('catOther').textContent = fmt(cat.other || 0);
    }

    function renderCompetitions(list) {
        const body = $('compBody');
        if (!list || !list.length) {
            body.innerHTML = '<tr><td colspan="3" class="text-center py-4 text-muted">暂无数据</td></tr>';
            return;
        }
        const sum = list.reduce((a, b) => a + b.total, 0);
        body.innerHTML = list.map((r) => {
            const pct = sum ? (r.total / sum * 100).toFixed(1) : '0';
            const bar = `<div class="position-relative" style="height:5px;border-radius:3px;background:var(--line)">
                            <div class="position-absolute start-0 top-0 h-100" style="width:${pct}%;border-radius:3px;background:var(--brand)"></div>
                         </div>`;
            return `<tr>
                <td>${r.name}</td>
                <td class="text-end mono-data">${fmt(r.total)}</td>
                <td class="text-end" style="width:180px"><span class="mono-data text-muted" style="font-size:.78rem">${pct}%</span></td>
            </tr>`;
        }).join('');
    }

    function renderTrend(d) {
        let list = (d.trend || []).map((r) => ({ m: r.month, c: r.count }));
        // 补全连续月份（填补无记录月份为 0），让趋势不断裂
        if (list.length) {
            const first = list[0].m, last = list[list.length - 1].m;
            const filled = [];
            let cur = first;
            while (cur <= last) {
                const hit = list.find((x) => x.m === cur);
                filled.push({ m: cur, c: hit ? hit.c : 0 });
                const [y, mo] = cur.split('-').map(Number);
                cur = mo === 12 ? `${y + 1}-01` : `${y}-${String(mo + 1).padStart(2, '0')}`;
            }
            list = filled;
        }
        const t = themeVars();
        const el = $('trendChart');
        if (chart) chart.dispose();
        if (typeof echarts === 'undefined') {
            el.innerHTML = '<div class="empty-state">图表库 ECharts 未加载（外网 CDN 被拦截）</div>';
            return;
        }
        chart = echarts.init(el);
        chart.setOption({
            grid: { left: 48, right: 20, top: 24, bottom: 30 },
            tooltip: { trigger: 'axis' },
            xAxis: {
                type: 'category',
                data: list.map((x) => x.m),
                axisLine: { lineStyle: { color: t.line } },
                axisLabel: { color: t.ink2 },
            },
            yAxis: {
                type: 'value', minInterval: 1,
                axisLine: { show: false },
                splitLine: { lineStyle: { color: t.line } },
                axisLabel: { color: t.ink2 },
            },
            series: [{
                name: '入库数',
                type: 'line',
                smooth: true,
                symbolSize: 7,
                data: list.map((x) => x.c),
                lineStyle: { color: t.brand, width: 2 },
                itemStyle: { color: t.brand },
                areaStyle: { color: 'transparent' },
            }],
        });
    }

    function applyTheme() {
        if (chart) renderTrend(window._dashData || {});
    }
    window._applyChartTheme = applyTheme;

    async function load() {
        try {
            const q = currentMonths ? `?months=${currentMonths}` : '';
            const r = await fetch('/admin/api/dashboard/overview' + q);
            const d = await r.json();
            if (!d.ok) throw new Error(d.error || '接口异常');
            window._dashData = d;
            renderSummary(d);
            renderCompetitions(d.by_competition);
            renderTrend(d);
        } catch (e) {
            console.error('dashboard load error:', e);
            document.querySelectorAll('.vital-value').forEach((n) => (n.textContent = '!'));
            $('compBody').innerHTML = `<tr><td colspan="3" class="text-center py-4">加载失败：${e.message}</td></tr>`;
        }
    }

    // 周期切换：影响趋势与环比（对应百度云"账单周期"选择器）
    const periodSel = $('periodSelect');
    if (periodSel) {
        periodSel.addEventListener('change', () => {
            const v = Number(periodSel.value);
            currentMonths = Number.isFinite(v) && v > 0 ? v : null;
            load();
        });
    }

    // 监听控制台主题切换（console_theme.js 会派发 data-theme 变化）
    const mo = new MutationObserver(() => applyTheme());
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });

    load();
})();
