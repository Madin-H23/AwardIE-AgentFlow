/**
 * 数据分析与可视化模块
 * 实现竞赛信息的图表展示和分析功能
 */

// ==================== 年份标签筛选组件 ====================
class YearTagFilter {
    constructor(containerId, availableYears, defaultAll = true, onChange) {
        this.container = document.getElementById(containerId);
        this.availableYears = availableYears;
        this.selectedYears = defaultAll ? [...availableYears] : [availableYears[availableYears.length - 1]];
        this.onChange = onChange;
        this.render();
    }

    toggleYear(year) {
        const index = this.selectedYears.indexOf(year);
        if (index > -1) {
            if (this.selectedYears.length > 1) {
                this.selectedYears.splice(index, 1);
            }
        } else {
            this.selectedYears.push(year);
        }
        this.render();
        if (this.onChange) {
            this.onChange(this.selectedYears);
        }
    }

    render() {
        if (!this.container) return;

        this.container.innerHTML = '';

        this.availableYears.forEach(year => {
            const tag = document.createElement('span');
            tag.className = 'year-tag';
            tag.textContent = year;

            if (this.selectedYears.includes(year)) {
                tag.classList.add('selected');
            } else {
                tag.classList.add('unselected');
            }

            tag.addEventListener('click', () => this.toggleYear(year));
            this.container.appendChild(tag);
        });
    }
}

// ==================== 实验室×竞赛热力图组件 ====================
class LabCompetitionHeatmap {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.chart = null;
    }

    render(data) {
        if (!this.container) return;

        // data: { competitions: [...], laboratories: [...], data: [[...]] }
        if (this.chart) {
            this.chart.dispose();
        }

        this.chart = echarts.init(this.container);

        const heatmapData = [];
        data.competitions.forEach((comp, i) => {
            data.laboratories.forEach((lab, j) => {
                heatmapData.push([j, i, data.data[i][j]]);
            });
        });

        // 计算最大值
        const maxValue = Math.max(...heatmapData.map(d => d[2])) || 10;

        const option = {
            title: {
                text: '竞赛×实验室 获奖数量',
                left: 'center',
                textStyle: { fontSize: 20, fontWeight: 600, color: '#333' }
            },
            tooltip: {
                formatter: params => {
                    const comp = data.competitions[params.data[1]];
                    const lab = data.laboratories[params.data[0]];
                    return `${comp}<br/>${lab}: ${params.data[2]} 项`;
                }
            },
            grid: {
                top: '10%',
                bottom: '18%',
                left: '8%',
                right: '8%',
                containLabel: true
            },
            xAxis: {
                type: 'category',
                data: data.laboratories,
                axisLabel: {
                    interval: 0,
                    margin: 14,
                    fontSize: 15
                }
            },
            yAxis: {
                type: 'category',
                data: data.competitions,
                axisLabel: {
                    width: 220,
                    overflow: 'truncate',
                    fontSize: 15
                }
            },
            visualMap: {
                min: 0,
                max: maxValue,
                calculable: true,
                orient: 'horizontal',
                left: 'center',
                bottom: '0%',
                inRange: { color: ['#f7f7f7', '#1890ff', '#003a8c'] },
                textStyle: { fontSize: 14 }
            },
            series: [{
                type: 'heatmap',
                data: heatmapData,
                label: {
                    show: true,
                    fontSize: 14
                },
                emphasis: {
                    itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.5)' }
                }
            }]
        };

        this.chart.setOption(option);
    }

    resize() {
        if (this.chart && !this.chart.isDisposed()) {
            this.chart.resize();
        }
    }

    dispose() {
        if (this.chart && !this.chart.isDisposed()) {
            this.chart.dispose();
        }
    }
}

// ==================== 主数据分析类 ====================
class DataAnalysis {
    constructor() {
        this.charts = {};
        this.competitions = [];
        // 年份筛选组件
        this.yearFilter = null;
        // 热力图组件
        this.heatmapChart = null;
        this.init();
    }

    async init() {
        try {
            this.initEventListeners();
            await this.loadCompetitions();
            this.renderTab1();
        } catch (error) {
            console.error('初始化失败:', error);
            this.showError('加载数据失败，请刷新页面重试');
        }
    }

    initEventListeners() {
        // Tab切换事件
        const tabButtons = document.querySelectorAll('#analysisTabs .nav-link');
        tabButtons.forEach(button => {
            button.addEventListener('shown.bs.tab', (event) => {
                const tabId = event.target.id;
                this.onTabChange(tabId);
            });
        });

        // 白名单筛选监听
        const whitelistFilter = document.getElementById('tab2WhitelistFilter');
        if (whitelistFilter) {
            whitelistFilter.addEventListener('change', () => {
                this.updateTab2Charts();
            });
        }

        // 教师证书筛选监听
        const teacherCertFilter = document.getElementById('tab2TeacherCertFilter');
        if (teacherCertFilter) {
            teacherCertFilter.addEventListener('change', () => {
                this.updateTab2Charts();
            });
        }
    }

    async loadCompetitions() {
        try {
            const response = await fetch('/api/admin/data-analysis/competitions');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            this.competitions = await response.json();
        } catch (error) {
            console.error('加载竞赛数据失败:', error);
            throw error;
        }
    }

    onTabChange(tabId) {
        console.log('切换到Tab:', tabId);
        setTimeout(() => {
            switch (tabId) {
                case 'tab1-tab':
                    break;
                case 'tab2-tab':
                    this.renderTab2();
                    break;
                case 'tab3-tab':
                    this.renderTab3();
                    break;
            }
            this.resizeCharts();
        }, 100);
    }

    // ==================== Tab 1: 竞赛信息 ====================
    renderTab1() {
        this.renderTimelineChart();
        this.renderCompetitionsTable();
    }

    /**
     * 渲染时间点标记图（散点图）
     * 显示三个时间点：报名开始、比赛时间、出奖时间
     */
    renderTimelineChart() {
        const chartDom = document.getElementById('timelineChart');
        if (!chartDom) {
            console.error('找不到timelineChart容器');
            return;
        }

        if (this.charts.timeline) {
            this.charts.timeline.dispose();
        }

        this.charts.timeline = echarts.init(chartDom);

        if (this.competitions.length === 0) {
            chartDom.innerHTML = '<div class="text-center text-muted p-5">暂无数据</div>';
            return;
        }

        // 直接使用所有竞赛
        const yAxisData = this.competitions.map(c => c.name);

        const seriesStart = [];
        const seriesMiddle = [];
        const seriesEnd = [];

        this.competitions.forEach(c => {
            if (c.start_month !== null && c.end_month !== null) {
                seriesStart.push([c.start_month, c.name]);

                const midMonth = c.is_cross_year
                    ? this.getMidMonthCross(c.start_month, c.end_month)
                    : (c.start_month + c.end_month) / 2;
                seriesMiddle.push([parseFloat(midMonth.toFixed(1)), c.name]);

                seriesEnd.push([c.end_month, c.name]);
            } else {
                seriesStart.push([null, c.name]);
                seriesMiddle.push([null, c.name]);
                seriesEnd.push([null, c.name]);
            }
        });

        const option = {
            title: {
                text: '竞赛时间分布',
                left: 'center',
                textStyle: {
                    fontSize: 16,
                    fontWeight: 600,
                    color: '#333'
                }
            },
            tooltip: {
                trigger: 'item',
                formatter: params => {
                    if (params.data[0] === null) {
                        return `${params.marker} ${params.data[1]}<br/><span style="color: #999;">时间数据未知</span>`;
                    }
                    const month = Math.floor(params.data[0]);
                    return `${params.marker} ${params.data[1]}<br/>月份: ${month}月`;
                }
            },
            legend: {
                data: ['报名开始', '比赛时间', '出奖时间'],
                top: 30,
                left: 'center'
            },
            grid: {
                left: '3%',
                right: '4%',
                bottom: '3%',
                top: 80,
                containLabel: true
            },
            xAxis: {
                type: 'value',
                min: 0.5,
                max: 12.5,
                name: '月份',
                nameLocation: 'middle',
                nameGap: 30,
                interval: 1,
                axisLabel: {
                    formatter: value => {
                        const months = ['', '1月', '2月', '3月', '4月', '5月', '6月',
                                      '7月', '8月', '9月', '10月', '11月', '12月'];
                        return months[Math.floor(value)] || '';
                    }
                }
            },
            yAxis: {
                type: 'category',
                data: yAxisData,
                axisLabel: {
                    width: 180,
                    overflow: 'truncate',
                    ellipsis: '...'
                }
            },
            series: [
                {
                    name: '报名开始',
                    type: 'scatter',
                    symbolSize: 14,
                    data: seriesStart,
                    itemStyle: {
                        color: '#3498db'
                    },
                    emphasis: {
                        itemStyle: {
                            color: '#2980b9'
                        }
                    }
                },
                {
                    name: '比赛时间',
                    type: 'scatter',
                    symbolSize: 14,
                    data: seriesMiddle,
                    itemStyle: {
                        color: '#f39c12'
                    },
                    emphasis: {
                        itemStyle: {
                            color: '#e67e22'
                        }
                    }
                },
                {
                    name: '出奖时间',
                    type: 'scatter',
                    symbolSize: 14,
                    data: seriesEnd,
                    itemStyle: {
                        color: '#27ae60'
                    },
                    emphasis: {
                        itemStyle: {
                            color: '#229954'
                        }
                    }
                }
            ]
        };

        this.charts.timeline.setOption(option);
    }

    getMidMonthCross(start, end) {
        const startToEnd = 12 - start + end;
        const mid = startToEnd / 2;
        const result = start + mid;
        return result > 12 ? result - 12 : result;
    }

    renderCompetitionsTable() {
        const tbody = document.querySelector('#competitionsTable tbody');
        if (!tbody) {
            console.error('找不到competitionsTable tbody');
            return;
        }

        tbody.innerHTML = '';

        if (this.competitions.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted">暂无数据</td></tr>';
            return;
        }

        this.competitions.forEach(c => {
            const tr = document.createElement('tr');

            const nameCell = document.createElement('td');
            nameCell.textContent = c.name;
            tr.appendChild(nameCell);

            const timeCell = document.createElement('td');
            if (c.time_raw) {
                const timeText = c.time_raw + (c.is_cross_year ? ' (跨年)' : '');
                timeCell.textContent = timeText;
            } else {
                timeCell.textContent = '-';
                timeCell.className = 'text-muted';
            }
            tr.appendChild(timeCell);

            const websiteCell = document.createElement('td');
            if (c.website) {
                const link = document.createElement('a');
                link.href = c.website;
                link.target = '_blank';
                link.rel = 'noopener noreferrer';
                link.textContent = '访问';
                link.className = 'btn btn-sm btn-outline-primary';
                websiteCell.appendChild(link);
            } else {
                websiteCell.textContent = '-';
                websiteCell.className = 'text-muted';
            }
            tr.appendChild(websiteCell);

            const whitelistCell = document.createElement('td');
            if (c.white_list) {
                whitelistCell.innerHTML = '<span class="badge bg-success">是</span>';
            } else {
                whitelistCell.innerHTML = '<span class="badge bg-secondary">否</span>';
            }
            tr.appendChild(whitelistCell);

            tbody.appendChild(tr);
        });
    }

    // ==================== Tab 2: 竞赛分析 ====================
    async renderTab2() {
        // 初始化年份筛选组件
        if (!this.yearFilter) {
            const availableYears = this.getAvailableYears();
            this.yearFilter = new YearTagFilter(
                'yearTags',
                availableYears,
                true,  // 默认全选
                () => this.updateTab2Charts()
            );
        }

        // 初始化热力图组件
        if (!this.heatmapChart) {
            this.heatmapChart = new LabCompetitionHeatmap('labCompetitionHeatmap');
        }

        // 初始渲染
        await this.updateTab2Charts();
    }

    getAvailableYears() {
        const currentYear = new Date().getFullYear();
        const years = [];
        for (let y = 2022; y <= currentYear + 1; y++) {
            years.push(y);
        }
        return years;
    }

    /**
     * 更新Tab 2的所有图表
     */
    async updateTab2Charts() {
        if (!this.yearFilter) return;

        const filters = {
            years: this.yearFilter.selectedYears,
            white_list_only: document.getElementById('tab2WhitelistFilter')?.checked || false,
            include_teacher_certificates: document.getElementById('tab2TeacherCertFilter')?.checked || false
        };

        await Promise.all([
            this.renderContributionChart(filters),
            this.renderHeatmapChart(filters)
        ]);
    }

    /**
     * 渲染贡献度图
     */
    async renderContributionChart(filters) {
        try {
            const params = new URLSearchParams();
            if (filters.years && filters.years.length > 0) {
                params.append('years', filters.years.join(','));
            }
            if (filters.white_list_only) {
                params.append('white_list_only', 'true');
            }
            if (filters.include_teacher_certificates) {
                params.append('include_teacher_certificates', 'true');
            }

            const response = await fetch(`/api/admin/data-analysis/contribution?${params}`);
            const data = await response.json();

            const chartDom = document.getElementById('contributionChart');
            if (!chartDom) {
                console.error('找不到contributionChart容器');
                return;
            }

            if (this.charts.contribution) {
                this.charts.contribution.dispose();
            }

            if (!data || data.length === 0) {
                chartDom.innerHTML = '<div class="text-center text-muted p-5">暂无数据，请调整筛选条件</div>';
                return;
            }

            this.charts.contribution = echarts.init(chartDom);

            const option = {
                title: {
                    text: '竞赛贡献度（奖状数量）',
                    left: 'center',
                    textStyle: {
                        fontSize: 16,
                        fontWeight: 600,
                        color: '#333'
                    }
                },
                tooltip: {
                    trigger: 'axis',
                    axisPointer: {
                        type: 'shadow'
                    }
                },
                grid: {
                    left: '3%',
                    right: '5%',
                    bottom: '18%',
                    top: '15%',
                    containLabel: true
                },
                xAxis: {
                    type: 'category',
                    data: data.map(d => d.name),
                    axisLabel: {
                        rotate: 90,
                        interval: 0,
                        margin: 12
                    }
                },
                yAxis: {
                    type: 'value',
                    name: '奖状数量'
                },
                series: [{
                    type: 'bar',
                    data: data.map(d => d.award_count),
                    itemStyle: {
                        color: '#3498db'
                    }
                }]
            };

            this.charts.contribution.setOption(option);
        } catch (error) {
            console.error('渲染贡献度图失败:', error);
        }
    }

    /**
     * 渲染热力图
     */
    async renderHeatmapChart(filters) {
        try {
            const params = new URLSearchParams();
            if (filters.years && filters.years.length > 0) {
                params.append('years', filters.years.join(','));
            }
            if (filters.white_list_only) {
                params.append('white_list_only', 'true');
            }
            if (filters.include_teacher_certificates) {
                params.append('include_teacher_certificates', 'true');
            }

            const response = await fetch(`/api/admin/data-analysis/lab-competition-heatmap?${params}`);
            const data = await response.json();

            if (this.heatmapChart) {
                this.heatmapChart.render(data);
            }
        } catch (error) {
            console.error('渲染热力图失败:', error);
        }
    }

    /**
     * Tab切换事件处理
     */
    onTabChange(tabId) {
        console.log('切换到Tab:', tabId);

        setTimeout(() => {
            switch (tabId) {
                case 'tab1-tab':
                    break;
                case 'tab2-tab':
                    this.renderTab2();
                    break;
                case 'tab3-tab':
                    this.renderTab3();
                    break;
            }
            this.resizeCharts();
        }, 100);
    }

    /**
     * 渲染Tab 3: 动态图表控制面板
     */
    renderTab3() {
        this.initTab3Controls();
        this.renderDynamicChart();
    }

    initTab3Controls() {
        const xAxisSelect = document.getElementById('xAxisSelect');
        const colorBySelect = document.getElementById('colorBySelect');

        if (!xAxisSelect || !colorBySelect) {
            console.error('Tab 3控件未找到');
            return;
        }

        xAxisSelect.addEventListener('change', () => {
            this.syncXAxisColorByConflict(xAxisSelect, colorBySelect);
            this.updateDynamicFilters();
        });

        colorBySelect.addEventListener('change', () => {
            this.syncXAxisColorByConflict(xAxisSelect, colorBySelect);
            this.updateDynamicFilters();
        });

        const chartTypeSelect = document.getElementById('chartTypeSelect');
        if (chartTypeSelect) {
            chartTypeSelect.addEventListener('change', () => {
                this.renderDynamicChart();
            });
        }

        const updateBtn = document.getElementById('updateChartBtn');
        if (updateBtn) {
            updateBtn.addEventListener('click', () => {
                this.renderDynamicChart();
            });
        }

        this.syncXAxisColorByConflict(xAxisSelect, colorBySelect);
        this.updateDynamicFilters();
    }

    /**
     * 保证 X 轴与颜色分组不能选同一项：互相禁用冲突项，冲突时自动修正另一侧。
     */
    syncXAxisColorByConflict(xAxisSelect, colorBySelect) {
        const xAxis = xAxisSelect.value;
        const colorBy = colorBySelect.value;

        if (xAxis === colorBy) {
            const availableColorBy = Array.from(colorBySelect.options).filter(o => o.value && o.value !== xAxis);
            if (availableColorBy.length > 0) {
                colorBySelect.value = availableColorBy[0].value;
            }
        }

        Array.from(colorBySelect.options).forEach(opt => {
            opt.disabled = opt.value === xAxisSelect.value;
        });
        if (colorBySelect.value === xAxisSelect.value) {
            const available = Array.from(colorBySelect.options).filter(o => !o.disabled && o.value);
            if (available.length > 0) colorBySelect.value = available[0].value;
        }

        Array.from(xAxisSelect.options).forEach(opt => {
            opt.disabled = opt.value === colorBySelect.value;
        });
        if (xAxisSelect.value === colorBySelect.value) {
            const available = Array.from(xAxisSelect.options).filter(o => !o.disabled && o.value);
            if (available.length > 0) xAxisSelect.value = available[0].value;
        }
    }

    updateDynamicFilters() {
        const xAxis = document.getElementById('xAxisSelect')?.value;
        const colorBy = document.getElementById('colorBySelect')?.value;
        const container = document.getElementById('dynamicFilters');

        if (!container || !xAxis || !colorBy) return;

        container.innerHTML = '';

        if (xAxis !== 'year' && colorBy !== 'year') {
            const yearHtml = `
                <div class="mb-3">
                    <label class="form-label">年份范围</label>
                    <select class="form-select" id="filterYear" multiple size="4">
                        <option value="2022" selected>2022</option>
                        <option value="2023" selected>2023</option>
                        <option value="2024" selected>2024</option>
                        <option value="2025" selected>2025</option>
                    </select>
                </div>
            `;
            container.innerHTML += yearHtml;
        }

        if (xAxis !== 'laboratory' && colorBy !== 'laboratory') {
            const labHtml = `
                <div class="mb-3">
                    <label class="form-label">实验室（勾选即包含该实验室数据）</label>
                    <div id="filterLabContainer" class="border rounded p-2" style="max-height: 160px; overflow-y: auto;">
                        <span class="text-muted small">正在加载...</span>
                    </div>
                </div>
            `;
            container.innerHTML += labHtml;
            this.loadLaboratoriesForFilter();
        }
    }

    async loadLaboratoriesForFilter() {
        const container = document.getElementById('filterLabContainer');
        if (!container) return;
        try {
            const response = await fetch('/admin/api/laboratories');
            if (!response.ok) {
                container.innerHTML = '<span class="text-danger small">加载失败</span>';
                return;
            }
            const data = await response.json();
            const labs = data.laboratories || (Array.isArray(data) ? data : []);
            if (labs.length === 0) {
                container.innerHTML = '<span class="text-muted small">暂无实验室</span>';
                return;
            }
            container.innerHTML = labs.map(lab =>
                `<label class="d-flex align-items-center mb-1 small"><input type="checkbox" name="filterLab" value="${lab.id}" checked class="me-2 form-check-input">${lab.name}</label>`
            ).join('');
        } catch (error) {
            console.error('加载实验室列表失败:', error);
            container.innerHTML = '<span class="text-danger small">加载失败</span>';
        }
    }

    async renderDynamicChart() {
        const xAxis = document.getElementById('xAxisSelect')?.value;
        const colorBy = document.getElementById('colorBySelect')?.value;
        const chartType = document.getElementById('chartTypeSelect')?.value;

        if (!xAxis || !colorBy || !chartType) {
            console.error('缺少必要的图表参数');
            return;
        }

        const params = new URLSearchParams({
            x_axis: xAxis,
            color_by: colorBy
        });

        const yearSelect = document.getElementById('filterYear');
        if (yearSelect) {
            const selectedYears = Array.from(yearSelect.selectedOptions).map(o => o.value);
            if (selectedYears.length > 0) {
                const sortedYears = selectedYears.map(y => parseInt(y)).sort((a, b) => a - b);
                params.append('year_range', `${sortedYears[0]},${sortedYears[sortedYears.length - 1]}`);
            }
        }

        const labCheckboxes = document.querySelectorAll('#dynamicFilters input[name="filterLab"]:checked');
        if (labCheckboxes && labCheckboxes.length > 0) {
            const selectedLabs = Array.from(labCheckboxes).map(el => el.value);
            params.append('laboratories', selectedLabs.join(','));
        }

        try {
            const response = await fetch(`/api/admin/data-analysis/dynamic-chart?${params}`);
            const data = await response.json();

            if (data.error) {
                console.error(data.error);
                this.showError(data.error);
                return;
            }

            this.renderDynamicChartByType(chartType, data);
        } catch (error) {
            console.error('加载图表数据失败:', error);
            this.showError('加载图表数据失败');
        }
    }

    renderDynamicChartByType(chartType, data) {
        const chartDom = document.getElementById('dynamicChart');
        if (!chartDom) {
            console.error('找不到dynamicChart容器');
            return;
        }

        if (chartType !== 'donut') {
            chartDom.style.height = '960px';
            chartDom.style.minHeight = '960px';
        }

        if (this.charts.dynamic) {
            this.charts.dynamic.dispose();
        }
        this.charts.dynamic = echarts.init(chartDom);

        let option;
        const baseOption = {
            title: { text: '获奖数据分析', left: 'center' },
            tooltip: { trigger: 'axis' },
            legend: { data: data.series_data.map(s => s.name), top: 30 },
            xAxis: {
                type: 'category',
                data: data.x_data
            },
            yAxis: { type: 'value', name: '数量' },
            grid: { left: '8%', right: '5%', bottom: '10%', top: '20%' }
        };

        const colors = ['#3498db', '#e74c3c', '#2ecc71', '#f39c12', '#9b59b6', '#1abc9c', '#34495e'];

        switch (chartType) {
            case 'grouped_bar':
                option = {
                    ...baseOption,
                    series: data.series_data.map((s, i) => ({
                        name: s.name,
                        type: 'bar',
                        data: s.data,
                        itemStyle: { color: colors[i % colors.length] }
                    }))
                };
                break;

            case 'line':
                option = {
                    ...baseOption,
                    series: data.series_data.map((s, i) => ({
                        name: s.name,
                        type: 'line',
                        data: s.data,
                        smooth: true,
                        itemStyle: { color: colors[i % colors.length] }
                    }))
                };
                break;

            case 'donut': {
                const xData = data.x_data;
                const N = xData.length;
                const cols = Math.min(2, N);
                const rows = Math.ceil(N / cols);
                const legendTop = 10;
                const usableHeight = 100 - legendTop;
                const rowHeight = rows > 0 ? usableHeight / rows : usableHeight;
                const centerXStep = 100 / cols;
                const labelGap = 6;
                const outerRadius = Math.min(28, (rowHeight - labelGap) / 2);
                const radiusPercent = Math.max(8, outerRadius - 12);

                const nameToColor = {};
                data.series_data.forEach((s, i) => { nameToColor[s.name] = colors[i % colors.length]; });

                const pieSeries = xData.map((xVal, xIdx) => {
                    const col = xIdx % cols;
                    const row = Math.floor(xIdx / cols);
                    const cx = (col + 0.5) * centerXStep;
                    const cy = legendTop + (row + 0.5) * rowHeight;
                    const sliceData = data.series_data.map((s) => ({
                        name: s.name,
                        value: s.data[xIdx] || 0
                    })).filter(d => d.value > 0).map((d) => ({
                        ...d,
                        itemStyle: { color: nameToColor[d.name] }
                    }));
                    const hasData = sliceData.length > 0;
                    return {
                        type: 'pie',
                        radius: [radiusPercent + '%', outerRadius + '%'],
                        center: [cx + '%', cy + '%'],
                        data: hasData ? sliceData : [{ name: '无数据', value: 1, itemStyle: { color: '#e0e0e0' } }],
                        label: { show: true, formatter: '{d}%' },
                        labelLine: { show: hasData },
                        emphasis: { itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0,0,0,0.2)' } }
                    };
                });

                const titleBelowList = xData.map((xVal, i) => {
                    const col = i % cols;
                    const row = Math.floor(i / cols);
                    const cy = legendTop + (row + 0.5) * rowHeight;
                    const topPercent = cy + outerRadius + (labelGap / 2);
                    return {
                        text: String(xVal),
                        left: (col + 0.5) * centerXStep + '%',
                        top: topPercent + '%',
                        textAlign: 'center',
                        textStyle: { fontSize: 18, fontWeight: 600, color: '#1a1a1a' }
                    };
                });

                const legendNames = data.series_data.map(s => s.name);
                option = {
                    title: [{ text: '获奖数据分析', left: 'center', top: 0 }, ...titleBelowList],
                    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
                    legend: { data: legendNames, top: 22 },
                    series: pieSeries
                };

                const chartContainer = document.getElementById('dynamicChart');
                if (chartContainer) {
                    const heightPx = Math.max(960, 520 * rows);
                    chartContainer.style.height = heightPx + 'px';
                    chartContainer.style.minHeight = heightPx + 'px';
                }
                break;
            }

            default:
                option = baseOption;
        }

        this.charts.dynamic.setOption(option);
        if (chartType === 'donut' && this.charts.dynamic && !this.charts.dynamic.isDisposed()) {
            this.charts.dynamic.resize();
        }
    }

    resizeCharts() {
        Object.values(this.charts).forEach(chart => {
            if (chart && !chart.isDisposed()) {
                chart.resize();
            }
        });
        if (this.heatmapChart) {
            this.heatmapChart.resize();
        }
    }

    showError(message) {
        const toastHtml = `
            <div class="toast-container position-fixed top-0 end-0 p-3">
                <div class="toast show" role="alert">
                    <div class="toast-header bg-danger text-white">
                        <strong class="me-auto">错误</strong>
                        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast"></button>
                    </div>
                    <div class="toast-body">
                        ${message}
                    </div>
                </div>
            </div>
        `;
        document.body.insertAdjacentHTML('beforeend', toastHtml);

        setTimeout(() => {
            const toast = document.querySelector('.toast-container');
            if (toast) {
                toast.remove();
            }
        }, 3000);
    }

    destroy() {
        Object.values(this.charts).forEach(chart => {
            if (chart && !chart.isDisposed()) {
                chart.dispose();
            }
        });
        if (this.heatmapChart) {
            this.heatmapChart.dispose();
        }
        this.charts = {};
    }
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    window.dataAnalysis = new DataAnalysis();
});

// 窗口大小改变时重新调整图表
window.addEventListener('resize', () => {
    if (window.dataAnalysis) {
        window.dataAnalysis.resizeCharts();
    }
});

// 页面卸载时清理资源
window.addEventListener('beforeunload', () => {
    if (window.dataAnalysis) {
        window.dataAnalysis.destroy();
    }
});
