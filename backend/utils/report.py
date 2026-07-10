"""
报告生成模块
用于生成获奖情况分析报告（HTML + Excel + Images）的压缩包
"""
import io
import json
import logging
import zipfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
import pandas as pd

logger = logging.getLogger(__name__)

# 首页HTML模板
MAIN_HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>竞赛分析报告</title>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
    <style>
        :root {
            --primary-color: #1a73e8;
            --primary-light: #4285f4;
            --primary-dark: #1557b0;
            --secondary-color: #34a853;
            --accent-color: #ea4335;
            --text-primary: #202124;
            --text-secondary: #5f6368;
            --bg-primary: #ffffff;
            --bg-secondary: #f8f9fa;
            --border-color: #dadce0;
            --shadow-sm: 0 2px 4px rgba(0,0,0,0.05);
            --shadow-md: 0 4px 8px rgba(0,0,0,0.1);
            --shadow-lg: 0 8px 16px rgba(0,0,0,0.15);
            --transition: all 0.3s ease;
            --radius-sm: 4px;
            --radius-md: 8px;
            --radius-lg: 12px;
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'Helvetica Neue', Helvetica, Arial, sans-serif;
        }
        
        body {
            background: linear-gradient(135deg, var(--bg-primary) 0%, var(--bg-secondary) 100%);
            color: var(--text-primary);
            line-height: 1.6;
            padding: 20px;
            min-height: 100vh;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: var(--bg-primary);
            border-radius: var(--radius-lg);
            box-shadow: var(--shadow-lg);
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, var(--primary-color) 0%, var(--primary-dark) 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }
        
        .header h1 {
            font-size: 2.5rem;
            margin-bottom: 10px;
            font-weight: 700;
        }
        
        .header .subtitle {
            font-size: 1.2rem;
            opacity: 0.9;
            margin-bottom: 20px;
        }
        
        .header .meta-info {
            display: flex;
            justify-content: center;
            gap: 30px;
            flex-wrap: wrap;
            margin-top: 20px;
        }
        
        .header .meta-item {
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        
        .header .meta-label {
            font-size: 0.9rem;
            opacity: 0.8;
            margin-bottom: 5px;
        }
        
        .header .meta-value {
            font-size: 1.1rem;
            font-weight: 600;
        }
        
        .content {
            padding: 40px;
        }
        
        .section {
            margin-bottom: 50px;
        }
        
        .section h2 {
            color: var(--primary-color);
            font-size: 1.8rem;
            margin-bottom: 25px;
            padding-bottom: 10px;
            border-bottom: 2px solid var(--border-color);
            font-weight: 600;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .stat-card {
            background: var(--bg-secondary);
            padding: 25px;
            border-radius: var(--radius-md);
            box-shadow: var(--shadow-sm);
            text-align: center;
            transition: var(--transition);
        }
        
        .stat-card:hover {
            transform: translateY(-5px);
            box-shadow: var(--shadow-md);
        }
        
        .stat-number {
            font-size: 2.5rem;
            font-weight: 700;
            color: var(--primary-color);
            margin-bottom: 5px;
        }
        
        .stat-label {
            font-size: 0.9rem;
            color: var(--text-secondary);
        }
        
        .chart-container {
            background: var(--bg-secondary);
            padding: 20px;
            border-radius: var(--radius-md);
            box-shadow: var(--shadow-sm);
            margin-bottom: 30px;
        }
        
        .chart {
            width: 100%;
            height: 400px;
        }
        
        .chart-title {
            font-size: 1.2rem;
            font-weight: 600;
            color: var(--text-primary);
            margin-bottom: 15px;
            text-align: center;
        }
        
        .table-container {
            overflow-x: auto;
            margin-bottom: 30px;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            background: var(--bg-primary);
            box-shadow: var(--shadow-sm);
            border-radius: var(--radius-md);
            overflow: hidden;
        }
        
        th {
            background: var(--primary-color);
            color: white;
            padding: 15px;
            text-align: left;
            font-weight: 600;
        }
        
        td {
            padding: 15px;
            border-bottom: 1px solid var(--border-color);
        }
        
        tr:last-child td {
            border-bottom: none;
        }
        
        tr:hover {
            background: var(--bg-secondary);
        }
        
        .competition-details {
            display: flex;
            flex-direction: column;
            gap: 30px;
            margin-bottom: 30px;
        }
        
        .competition-card {
            background: var(--bg-secondary);
            border-radius: var(--radius-md);
            box-shadow: var(--shadow-sm);
            padding: 20px;
            transition: var(--transition);
        }
        
        .competition-card:hover {
            transform: translateY(-5px);
            box-shadow: var(--shadow-md);
        }
        
        .competition-name {
            font-size: 1.3rem;
            font-weight: 600;
            color: var(--primary-color);
            margin-bottom: 10px;
            cursor: pointer;
        }
        
        .competition-info {
            color: var(--text-secondary);
            font-size: 0.95rem;
            margin-bottom: 5px;
        }
        
        .competition-details-content {
            margin-top: 15px;
            display: none;
            max-height: 0;
            overflow: hidden;
            transition: max-height 0.3s ease;
        }
        
        .competition-card.expanded .competition-details-content {
            display: block;
            max-height: 10000px;
        }
        
        .competition-name::after {
            content: ' ▼';
            font-size: 0.8rem;
            transition: transform 0.3s ease;
        }
        
        .competition-card.expanded .competition-name::after {
            content: ' ▲';
        }
        
        .award-list {
            list-style: none;
            margin-top: 10px;
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
        }
        
        .award-item {
            padding: 15px;
            background: var(--bg-primary);
            border-radius: var(--radius-sm);
            font-size: 0.95rem;
            box-shadow: var(--shadow-sm);
            display: flex;
            flex-direction: column;
            transition: var(--transition);
        }
        
        .award-item:hover {
            box-shadow: var(--shadow-md);
            transform: translateY(-2px);
        }
        
        .award-item-header {
            font-weight: 600;
            color: var(--text-primary);
            margin-bottom: 8px;
            font-size: 0.95rem;
            line-height: 1.5;
        }
        
        .award-level {
            font-weight: 600;
            color: var(--accent-color);
        }
        
        .award-info {
            display: flex;
            flex-direction: row;
            flex-wrap: wrap;
            gap: 20px;
            margin-bottom: 15px;
            font-size: 0.9rem;
            line-height: 1.6;
            align-items: center;
        }
        
        .award-info-item {
            display: inline;
            white-space: nowrap;
        }
        
        .award-info-label {
            color: var(--text-secondary);
            margin-right: 4px;
        }
        
        .award-info-value {
            font-weight: 500;
            color: var(--text-primary);
        }
        
        .award-image-container {
            margin-top: auto;
            text-align: center;
        }
        
        .award-image-container img {
            width: 100%;
            height: auto;
            max-height: 300px;
            object-fit: contain;
            border-radius: var(--radius-sm);
            box-shadow: var(--shadow-sm);
            cursor: pointer;
            transition: var(--transition);
        }
        
        .award-image-container img:hover {
            transform: scale(1.05);
            box-shadow: var(--shadow-md);
        }
        
        @media (max-width: 1200px) {
            .award-list {
                grid-template-columns: repeat(2, 1fr);
            }
        }
        
        @media (max-width: 768px) {
            .award-list {
                grid-template-columns: 1fr;
            }
        }
        
        @media (max-width: 768px) {
            body {
                padding: 10px;
            }
            
            .container {
                border-radius: var(--radius-md);
            }
            
            .header {
                padding: 20px;
            }
            
            .header h1 {
                font-size: 2rem;
            }
            
            .content {
                padding: 20px;
            }
            
            .competition-details {
                grid-template-columns: 1fr;
            }
            
            .chart {
                height: 300px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>竞赛分析报告</h1>
            <div class="subtitle">专业赛事数据分析与可视化</div>
            <div class="meta-info">
                <div class="meta-item">
                    <div class="meta-label">统计年份</div>
                    <div class="meta-value">{YEAR}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">统计范围</div>
                    <div class="meta-value">{FILTER_SCOPE}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">生成时间</div>
                    <div class="meta-value">{GENERATE_TIME}</div>
                </div>
            </div>
        </div>
        
        <div class="content">
            <div class="section">
                <h2>整体统计概览</h2>
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-number">{TOTAL_AWARDS}</div>
                        <div class="stat-label">获奖总数</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">{TOTAL_COMPETITIONS}</div>
                        <div class="stat-label">参与竞赛数</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">{TOTAL_WINNERS}</div>
                        <div class="stat-label">获奖人数</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">{NATIONAL_COUNT}</div>
                        <div class="stat-label">国赛数</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">{PROVINCE_COUNT}</div>
                        <div class="stat-label">省赛数</div>
                    </div>
                </div>
            </div>
            
            <div class="section">
                <h2>竞赛类型分布</h2>
                <div class="chart-container">
                    <div class="chart-title">竞赛类型饼图</div>
                    <div id="competitionTypeChart" class="chart"></div>
                </div>
            </div>
            
            <div class="section">
                <h2>竞赛等级分布</h2>
                <div class="chart-container">
                    <div class="chart-title">不同等级竞赛成果数量</div>
                    <div id="competitionLevelChart" class="chart"></div>
                </div>
                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>等级</th>
                                <th>一等奖数量</th>
                                <th>二等奖数量</th>
                                <th>三等奖数量</th>
                                <th>其他奖数量</th>
                                <th>总计</th>
                            </tr>
                        </thead>
                        <tbody>
                            {LEVEL_TABLE_DATA}
                        </tbody>
                    </table>
                </div>
            </div>
            
            <div class="section">
                <h2>竞赛详情</h2>
                <div class="competition-details">
                    {COMPETITION_DETAILS}
                </div>
            </div>
        </div>
    </div>
    
    <script>
        // 竞赛类型饼图数据
        const competitionTypeData = {COMPETITION_TYPE_DATA};
        const competitionTypeChart = echarts.init(document.getElementById('competitionTypeChart'));
        const competitionTypeOption = {
            tooltip: {
                trigger: 'item',
                formatter: '{a} <br/>{b}: {c} ({d}%)'
            },
            legend: {
                orient: 'horizontal',
                bottom: 10,
                data: competitionTypeData.map(item => item.name)
            },
            series: [
                {
                    name: '竞赛类型',
                    type: 'pie',
                    radius: ['40%', '70%'],
                    avoidLabelOverlap: false,
                    itemStyle: {
                        borderRadius: 10,
                        borderColor: '#fff',
                        borderWidth: 2
                    },
                    label: {
                        show: false,
                        position: 'center'
                    },
                    emphasis: {
                        label: {
                            show: true,
                            fontSize: '18',
                            fontWeight: 'bold'
                        }
                    },
                    labelLine: {
                        show: false
                    },
                    data: competitionTypeData
                }
            ]
        };
        competitionTypeChart.setOption(competitionTypeOption);
        
        // 竞赛等级柱状图数据
        const competitionLevelData = {COMPETITION_LEVEL_DATA};
        const competitionLevelChart = echarts.init(document.getElementById('competitionLevelChart'));
        const competitionLevelOption = {
            tooltip: {
                trigger: 'axis',
                axisPointer: {
                    type: 'shadow'
                }
            },
            legend: {
                data: ['一等奖', '二等奖', '三等奖', '其他奖']
            },
            grid: {
                left: '3%',
                right: '4%',
                bottom: '3%',
                containLabel: true
            },
            xAxis: [
                {
                    type: 'category',
                    data: competitionLevelData.map(item => item.name),
                    axisTick: {
                        alignWithLabel: true
                    }
                }
            ],
            yAxis: [
                {
                    type: 'value'
                }
            ],
            series: [
                {
                    name: '一等奖',
                    type: 'bar',
                    emphasis: {
                        focus: 'series'
                    },
                    itemStyle: {
                        color: '#ea4335'
                    },
                    data: competitionLevelData.map(item => item.first_prize)
                },
                {
                    name: '二等奖',
                    type: 'bar',
                    emphasis: {
                        focus: 'series'
                    },
                    itemStyle: {
                        color: '#fbbc05'
                    },
                    data: competitionLevelData.map(item => item.second_prize)
                },
                {
                    name: '三等奖',
                    type: 'bar',
                    emphasis: {
                        focus: 'series'
                    },
                    itemStyle: {
                        color: '#4285f4'
                    },
                    data: competitionLevelData.map(item => item.third_prize)
                },
                {
                    name: '其他奖',
                    type: 'bar',
                    emphasis: {
                        focus: 'series'
                    },
                    itemStyle: {
                        color: '#34a853'
                    },
                    data: competitionLevelData.map(item => item.other_prize)
                }
            ]
        };
        competitionLevelChart.setOption(competitionLevelOption);
        
        // 响应式处理
        window.addEventListener('resize', function() {
            competitionTypeChart.resize();
            competitionLevelChart.resize();
        });
        
        // 竞赛详情卡片展开/收起
        function toggleCompetition(element) {
            const card = element.closest('.competition-card');
            card.classList.toggle('expanded');
        }
        
        // 图片查看器模态框
        function openImageModal(imageSrc) {
            const modal = document.getElementById('imageModal');
            const modalImg = document.getElementById('modalImage');
            if (modal && modalImg) {
                modalImg.src = imageSrc;
                modal.classList.add('active');
                document.body.style.overflow = 'hidden';
            }
        }
        
        function closeImageModal() {
            const modal = document.getElementById('imageModal');
            if (modal) {
                modal.classList.remove('active');
                document.body.style.overflow = 'auto';
            }
        }
        
        // 点击模态框背景关闭
        document.addEventListener('DOMContentLoaded', function() {
            const modal = document.getElementById('imageModal');
            const closeBtn = document.querySelector('.close-modal');
            
            if (modal) {
                modal.addEventListener('click', function(event) {
                    if (event.target === modal) {
                        closeImageModal();
                    }
                });
            }
            
            if (closeBtn) {
                closeBtn.addEventListener('click', closeImageModal);
            }
            
            // 按ESC键关闭模态框
            document.addEventListener('keydown', function(event) {
                if (event.key === 'Escape') {
                    closeImageModal();
                }
            });
        });
    </script>
    
    <!-- 图片查看器模态框 -->
    <div id="imageModal" class="modal">
        <div class="modal-content">
            <span class="close-modal">×</span>
            <img id="modalImage" src="" alt="大图查看">
        </div>
    </div>
    
    <style>
        /* 图片查看器样式 */
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.9);
            z-index: 1000;
            justify-content: center;
            align-items: center;
        }
        
        .modal.active {
            display: flex;
        }
        
        .modal-content {
            max-width: 90%;
            max-height: 90%;
            position: relative;
        }
        
        .modal-content img {
            max-width: 100%;
            max-height: 90vh;
            object-fit: contain;
        }
        
        .close-modal {
            position: absolute;
            top: -40px;
            right: 0;
            color: white;
            font-size: 2rem;
            cursor: pointer;
            transition: var(--transition);
        }
        
        .close-modal:hover {
            opacity: 0.7;
        }
    </style>
</body>
</html>
"""

# 详细页面HTML模板
DETAIL_HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>竞赛详情 - {COMPETITION_NAME}<title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root {
            --primary-color: #1a73e8;
            --primary-light: #4285f4;
            --primary-dark: #1557b0;
            --secondary-color: #34a853;
            --accent-color: #ea4335;
            --text-primary: #202124;
            --text-secondary: #5f6368;
            --bg-primary: #ffffff;
            --bg-secondary: #f8f9fa;
            --border-color: #dadce0;
            --shadow-sm: 0 2px 4px rgba(0,0,0,0.05);
            --shadow-md: 0 4px 8px rgba(0,0,0,0.1);
            --shadow-lg: 0 8px 16px rgba(0,0,0,0.15);
            --transition: all 0.3s ease;
            --radius-sm: 4px;
            --radius-md: 8px;
            --radius-lg: 12px;
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'Helvetica Neue', Helvetica, Arial, sans-serif;
        }
        
        body {
            background: linear-gradient(135deg, var(--bg-primary) 0%, var(--bg-secondary) 100%);
            color: var(--text-primary);
            line-height: 1.6;
            padding: 20px;
            min-height: 100vh;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: var(--bg-primary);
            border-radius: var(--radius-lg);
            box-shadow: var(--shadow-lg);
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, var(--primary-color) 0%, var(--primary-dark) 100%);
            color: white;
            padding: 30px 40px;
            text-align: center;
            position: relative;
        }
        
        .header h1 {
            font-size: 2.2rem;
            font-weight: 700;
            margin-bottom: 10px;
        }
        
        .header .subtitle {
            font-size: 1.1rem;
            opacity: 0.9;
        }
        
        .back-link {
            position: absolute;
            top: 20px;
            left: 20px;
            color: white;
            text-decoration: none;
            font-size: 1rem;
            transition: var(--transition);
            display: flex;
            align-items: center;
            gap: 5px;
        }
        
        .back-link:hover {
            opacity: 0.8;
            transform: translateX(-3px);
        }
        
        .content {
            padding: 40px;
        }
        
        .stats-section {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }
        
        .stat-card {
            background: var(--bg-secondary);
            padding: 20px;
            border-radius: var(--radius-md);
            box-shadow: var(--shadow-sm);
            text-align: center;
            transition: var(--transition);
        }
        
        .stat-card:hover {
            transform: translateY(-5px);
            box-shadow: var(--shadow-md);
        }
        
        .stat-number {
            font-size: 2.2rem;
            font-weight: 700;
            color: var(--primary-color);
            margin-bottom: 5px;
        }
        
        .stat-label {
            font-size: 0.9rem;
            color: var(--text-secondary);
        }
        
        .section {
            margin-bottom: 40px;
        }
        
        .section h2 {
            color: var(--primary-color);
            font-size: 1.6rem;
            margin-bottom: 25px;
            padding-bottom: 10px;
            border-bottom: 2px solid var(--border-color);
            font-weight: 600;
        }
        
        .award-cards {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
            gap: 25px;
        }
        
        .award-card {
            background: var(--bg-secondary);
            border-radius: var(--radius-md);
            box-shadow: var(--shadow-sm);
            padding: 25px;
            transition: var(--transition);
            position: relative;
            overflow: hidden;
        }
        
        .award-card:hover {
            transform: translateY(-5px);
            box-shadow: var(--shadow-md);
        }
        
        .award-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 4px;
            height: 100%;
            background: var(--primary-color);
        }
        
        .award-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 15px;
        }
        
        .award-level {
            font-size: 1.1rem;
            font-weight: 600;
            color: var(--accent-color);
            padding: 5px 12px;
            background: rgba(234, 67, 53, 0.1);
            border-radius: var(--radius-sm);
        }
        
        .award-date {
            font-size: 0.9rem;
            color: var(--text-secondary);
        }
        
        .award-details {
            margin-bottom: 20px;
        }
        
        .detail-item {
            margin-bottom: 10px;
            display: flex;
            align-items: flex-start;
            gap: 10px;
        }
        
        .detail-label {
            font-weight: 600;
            color: var(--text-secondary);
            min-width: 80px;
            flex-shrink: 0;
        }
        
        .detail-value {
            color: var(--text-primary);
            flex-grow: 1;
        }
        
        .image-preview {
            margin-top: 20px;
            position: relative;
        }
        
        .image-container {
            position: relative;
            border-radius: var(--radius-sm);
            overflow: hidden;
            cursor: pointer;
            transition: var(--transition);
            box-shadow: var(--shadow-sm);
        }
        
        .image-container:hover {
            transform: scale(1.02);
            box-shadow: var(--shadow-md);
        }
        
        .image-container img {
            width: 100%;
            height: auto;
            display: block;
            transition: var(--transition);
        }
        
        .image-overlay {
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            background: rgba(0, 0, 0, 0.6);
            color: white;
            padding: 8px 12px;
            font-size: 0.9rem;
            transform: translateY(100%);
            transition: var(--transition);
        }
        
        .image-container:hover .image-overlay {
            transform: translateY(0);
        }
        
        /* 图片查看器 */
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.9);
            z-index: 1000;
            justify-content: center;
            align-items: center;
        }
        
        .modal.active {
            display: flex;
        }
        
        .modal-content {
            max-width: 90%;
            max-height: 90%;
            position: relative;
        }
        
        .modal-content img {
            max-width: 100%;
            max-height: 90vh;
            object-fit: contain;
        }
        
        .close-modal {
            position: absolute;
            top: -40px;
            right: 0;
            color: white;
            font-size: 2rem;
            cursor: pointer;
            transition: var(--transition);
        }
        
        .close-modal:hover {
            opacity: 0.7;
        }
        
        @media (max-width: 768px) {
            body {
                padding: 10px;
            }
            
            .container {
                border-radius: var(--radius-md);
            }
            
            .header {
                padding: 30px 20px 20px;
            }
            
            .header h1 {
                font-size: 1.8rem;
                margin-top: 20px;
            }
            
            .content {
                padding: 20px;
            }
            
            .award-cards {
                grid-template-columns: 1fr;
            }
            
            .stats-section {
                grid-template-columns: repeat(2, 1fr);
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <a href="{MAIN_PAGE}" class="back-link">
                <i class="fas fa-arrow-left"></i> 返回首页
            </a>
            <h1>{COMPETITION_NAME}</h1>
            <div class="subtitle">竞赛获奖详情分析</div>
        </div>
        
        <div class="content">
            <div class="stats-section">
                <div class="stat-card">
                    <div class="stat-number">{TOTAL_AWARDS}</div>
                    <div class="stat-label">获奖总数</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{FIRST_PRIZE}</div>
                    <div class="stat-label">一等奖数量</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{SECOND_PRIZE}</div>
                    <div class="stat-label">二等奖数量</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{THIRD_PRIZE}</div>
                    <div class="stat-label">三等奖数量</div>
                </div>
            </div>
            
            <div class="section">
                <h2>获奖详情列表</h2>
                <div class="award-cards">
                    {AWARD_CARDS}
                </div>
            </div>
        </div>
    </div>
    
    <!-- 图片查看器模态框 -->
    <div id="imageModal" class="modal">
        <div class="modal-content">
            <span class="close-modal">×</span>
            <img id="modalImage" src="" alt="大图查看">
        </div>
    </div>
    
    <script>
        // 图片查看器功能
        const modal = document.getElementById('imageModal');
        const modalImg = document.getElementById('modalImage');
        const closeBtn = document.getElementsByClassName('close-modal')[0];
        
        // 为所有图片容器添加点击事件
        document.querySelectorAll('.image-container').forEach(container => {
            container.addEventListener('click', function() {
                modal.classList.add('active');
                modalImg.src = this.querySelector('img').src;
                document.body.style.overflow = 'hidden'; // 防止背景滚动
            });
        });
        
        // 关闭模态框
        closeBtn.addEventListener('click', function() {
            modal.classList.remove('active');
            document.body.style.overflow = 'auto'; // 恢复背景滚动
        });
        
        // 点击模态框背景关闭
        modal.addEventListener('click', function(event) {
            if (event.target === modal) {
                modal.classList.remove('active');
                document.body.style.overflow = 'auto';
            }
        });
        
        // 按ESC键关闭模态框
        document.addEventListener('keydown', function(event) {
            if (event.key === 'Escape' && modal.classList.contains('active')) {
                modal.classList.remove('active');
                document.body.style.overflow = 'auto';
            }
        });
    </script>
</body>
</html>
"""


def generate_excel_data(awards: List[Any]) -> Optional[bytes]:
    """
    生成Excel数据
    
    Args:
        awards: 奖状对象列表
    
    Returns:
        Excel文件的bytes数据，如果生成失败返回None
    """
    try:
        excel_rows = []
        for a in awards:
            # 标准竞赛名
            std_comp_name = a.competition_obj.name if a.competition_obj else (a.competition_name_in_file or "")

            row = {
                "标准竞赛名称": std_comp_name,
                "原始竞赛名称": a.competition_name_in_file or "",
                "奖项等级": a.award_level or "",
                "获奖者": a.winner_name or "",
                "指导教师": a.supervisor_name or "",
                "比赛等级": a.competition_level or "",
                "年份": str(a.year) if a.year else "",
                "届数": str(a.edition) if a.edition else "",
                "日期": a.date or "",
                "证书编号": str(a.certificate_id) if a.certificate_id is not None else "",
                "授予角色": a.granted_role or "",
                "作品名称": a.project_title or "",
                "赛道": a.track or "",
                "组别": a.group_name or "",
                "颁发机构": a.issuer or "",
                "省份": a.province or "",
                "相关学生": a.related_student_name or ""
            }
            excel_rows.append(row)
        
        df_excel = pd.DataFrame(excel_rows)
        excel_buffer = io.BytesIO()
        
        # 尝试使用 openpyxl，如果失败则尝试 xlsxwriter
        try:
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                df_excel.to_excel(writer, index=False, sheet_name='奖状数据')
            return excel_buffer.getvalue()
        except Exception:
            try:
                excel_buffer2 = io.BytesIO()
                with pd.ExcelWriter(excel_buffer2, engine='xlsxwriter') as writer:
                    df_excel.to_excel(writer, index=False, sheet_name='奖状数据')
                return excel_buffer2.getvalue()
            except Exception as e:
                logger.error(f"Excel generation failed: {e}")
                return None
    except Exception as e:
        logger.error(f"生成Excel数据失败: {e}")
        return None


def _get_competition_type_stats(awards: List[Any]) -> Dict[str, int]:
    """
    统计白名单赛事、观察名单赛事和其他类别的数量
    
    Args:
        awards: 奖状对象列表
    
    Returns:
        包含各类赛事数量的字典
    """
    stats = {"白名单赛事": 0, "观察名单赛事": 0, "其他": 0}
    
    # 只统计学生奖状
    student_awards = [a for a in awards if not (a.granted_role and "教师" in a.granted_role)]
    
    for a in student_awards:
        # 检查竞赛对象
        if hasattr(a, 'competition_obj') and a.competition_obj:
            # 直接使用Competition对象的is_white_list和is_watch_list属性
            if a.competition_obj.is_white_list:
                stats["白名单赛事"] += 1
            elif a.competition_obj.is_watch_list:
                stats["观察名单赛事"] += 1
            else:
                stats["其他"] += 1
        else:
            # 如果没有关联的竞赛对象，使用默认规则
            # 假设国赛更可能是白名单，省赛可能是观察名单
            if a.competition_level == "国赛":
                stats["白名单赛事"] += 1
            elif a.competition_level == "省赛":
                stats["观察名单赛事"] += 1
            else:
                stats["其他"] += 1
    
    return stats


def _generate_competition_type_pie_chart(stats: Dict[str, int]) -> str:
    """
    生成竞赛类型分布饼图
    
    Args:
        stats: 包含各类赛事数量的字典
    
    Returns:
        饼图HTML字符串
    """
    pie_data = [
        {"value": stats["白名单赛事"], "name": "白名单赛事"},
        {"value": stats["观察名单赛事"], "name": "观察名单赛事"},
        {"value": stats["其他"], "name": "其他"}
    ]
    
    pie_chart_option = {
        "tooltip": {"trigger": "item", "formatter": '{a} <br/>{b}: {c} ({d}%)'},
        "legend": {"orient": "vertical", "left": "left"},
        "series": [
            {
                "name": "竞赛类型",
                "type": "pie",
                "radius": ["40%", "70%"],
                "avoidLabelOverlap": False,
                "itemStyle": {
                    "borderColor": "#fff",
                    "borderWidth": 2
                },
                "label": {
                    "show": True,
                    "formatter": '{b}: {d}%'
                },
                "emphasis": {
                    "label": {
                        "show": True,
                        "fontSize": 16,
                        "fontWeight": "bold"
                    }
                },
                "data": pie_data
            }
        ]
    }
    
    chart_html = f"""
    <div class="chart-wrapper">
        <div class="chart-title">📊 竞赛类型分布</div>
        <div id="type_chart" class="chart-container"></div>
        <div class="chart-note">
            说明：按照奖状计算，因此同一个参赛同时获得国赛和省赛都被计算在内，教师只统计第一导师，只统计学生奖状。
        </div>
    </div>
    <script>
        var chartDom_type = document.getElementById('type_chart');
        var myChart_type = echarts.init(chartDom_type);
        var option_type = {json.dumps(pie_chart_option, ensure_ascii=False)};
        myChart_type.setOption(option_type);
        window.addEventListener('resize', function() {{
            myChart_type.resize();
        }});
    </script>
    """
    
    return chart_html


def _generate_competition_level_chart(awards: List[Any]) -> str:
    """
    生成不同等级竞赛成果图表和表格
    
    Args:
        awards: 奖状对象列表
    
    Returns:
        图表和表格HTML字符串
    """
    # 只统计学生奖状
    student_awards = [a for a in awards if not (a.granted_role and "教师" in a.granted_role)]
    
    # 统计各竞赛的省赛和国赛数量
    comp_stats = {}
    for a in student_awards:
        comp_name = a.competition_obj.name if a.competition_obj else (a.competition_name_in_file or "未知竞赛")
        if comp_name not in comp_stats:
            comp_stats[comp_name] = {"省赛": 0, "国赛": 0}
        
        if a.competition_level == "省赛":
            comp_stats[comp_name]["省赛"] += 1
        elif a.competition_level == "国赛":
            comp_stats[comp_name]["国赛"] += 1
    
    # 按竞赛名称排序
    sorted_comps = sorted(comp_stats.items(), key=lambda x: (x[1]["国赛"], x[1]["省赛"]), reverse=True)
    comp_names = [item[0] for item in sorted_comps]
    province_data = [item[1]["省赛"] for item in sorted_comps]
    national_data = [item[1]["国赛"] for item in sorted_comps]
    
    # 生成柱状图选项
    bar_chart_option = {
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
        "legend": {"data": ["省赛", "国赛"], "top": "0%"},
        "xAxis": {
            "type": "category",
            "data": comp_names,
            "axisLabel": {"rotate": 60, "interval": 0}
        },
        "yAxis": {"type": "value"},
        "series": [
            {
                "name": "省赛", 
                "type": "bar", 
                "data": province_data, 
                "itemStyle": {"color": "#5470C6"},
                "label": {
                    "show": True,
                    "position": "top"
                }
            },
            {
                "name": "国赛", 
                "type": "bar", 
                "data": national_data, 
                "itemStyle": {"color": "#91CC75"},
                "label": {
                    "show": True,
                    "position": "top"
                }
            }
        ],
        "grid": {"bottom": "35%"}
    }
    
    # 生成图表HTML
    chart_html = f"""
    <div class="chart-wrapper">
        <div class="chart-title">📈 不同等级竞赛成果</div>
        <div id="level_chart" class="chart-container"></div>
        """
    
    # 生成表格HTML
    table_html = """
        <table class="data-table">
            <thead>
                <tr>
                    <th>竞赛名称</th>
                    <th>省赛数量</th>
                    <th>国赛数量</th>
                    <th>总计</th>
                </tr>
            </thead>
            <tbody>
    """
    
    for comp_name, stats in sorted_comps:
        total = stats["省赛"] + stats["国赛"]
        table_html += f"""
                <tr>
                    <td>{comp_name}</td>
                    <td>{stats["省赛"]}</td>
                    <td>{stats["国赛"]}</td>
                    <td>{total}</td>
                </tr>
        """
    
    table_html += """
            </tbody>
        </table>
        <div class="chart-note">
            说明：按照奖状计算，因此同一个参赛同时获得国赛和省赛都被计算在内，教师只统计第一导师，只统计学生奖状。
        </div>
    </div>
    <script>
        var chartDom_level = document.getElementById('level_chart');
        var myChart_level = echarts.init(chartDom_level);
        var option_level = {json.dumps(bar_chart_option, ensure_ascii=False)};
        myChart_level.setOption(option_level);
        window.addEventListener('resize', function() {{
            myChart_level.resize();
        }});
    </script>
    """
    
    return chart_html + table_html


def _generate_competition_details_inline(competitions, competition_name):
    """
    生成竞赛详情的内嵌HTML（可展开内容）
    
    Args:
        competitions: 竞赛数据列表
        competition_name: 竞赛名称（已清理，用于文件路径）
        
    Returns:
        竞赛详情的HTML字符串
    """
    logger.info(f"生成竞赛详情内嵌内容: {competition_name}")
    
    # 统计不同等级的获奖数量
    total_awards = len(competitions)
    first_prize_count = len([c for c in competitions if '一等奖' in (c.award_level or '') or '一等' in (c.award_level or '')])
    second_prize_count = len([c for c in competitions if '二等奖' in (c.award_level or '') or '二等' in (c.award_level or '')])
    third_prize_count = len([c for c in competitions if '三等奖' in (c.award_level or '') or '三等' in (c.award_level or '')])
    
    # 生成奖项列表HTML
    award_items = []
    
    for a in competitions:
        # 获取竞赛名称（用于图片路径）
        comp_name_for_path = getattr(a, 'competition_name_in_file', '') or getattr(a.competition_obj, 'name', '') or "未知竞赛"
        comp_name_for_path = comp_name_for_path.replace('/', '_').replace('\\', '_').replace(':', '').replace('*', '').replace('?', '').replace('"', '').replace('<', '').replace('>', '').replace('|', '')
        
        # 构建图片文件名
        track = getattr(a, 'track', '') or ''
        winner_name = getattr(a, 'winner_name', '') or ''
        first_winner = winner_name.replace('、', ',').replace('，', ',').split(',')[0].strip() if winner_name else ''
        first_winner = first_winner.replace('\\', '_').replace('/', '_')
        competition_level = getattr(a, 'competition_level', '') or ''
        award_level = getattr(a, 'award_level', '') or ''
        
        # 获取图片路径和扩展名
        image_path = a.get_image_path()
        img_ext = ''
        if image_path and image_path.exists():
            img_ext = image_path.suffix
        elif hasattr(a, 'image_path') and a.image_path:
            if isinstance(a.image_path, str) and '.' in a.image_path:
                img_ext = '.' + a.image_path.rsplit('.', 1)[1]
        
        # 构建图片文件名
        if track:
            img_filename = f"{track}_{first_winner}_{competition_level}{award_level}_{a.id}{img_ext}"
        else:
            img_filename = f"{first_winner}_{competition_level}{award_level}_{a.id}{img_ext}"
        img_filename = img_filename.replace('/', '_').replace('\\', '_').replace(':', '').replace('*', '').replace('?', '').replace('"', '').replace('<', '').replace('>', '').replace('|', '')
        
        # 构建图片路径（相对于HTML文件的路径）
        img_path = f"images/{comp_name_for_path}/{img_filename}"
        
        # 获取字段值
        winner_display = winner_name or ''
        supervisor_display = getattr(a, 'supervisor_name', '') or ''
        track_display = track or ''
        date_display = getattr(a, 'date', '') or ''
        certificate_id_display = getattr(a, 'certificate_id', '') or ''
        project_title_display = getattr(a, 'project_title', '') or ''
        
        # 构建第一行：国赛/省赛 x等奖   获奖者：xxx    指导教师：xxx
        level_award_text = f"{competition_level or '未知'}{award_level or '未知等级'}"
        
        # 构建信息行（按顺序：奖项等级、获奖者、指导教师）
        info_parts = []
        if level_award_text and level_award_text != '未知未知等级':
            info_parts.append(f'<span class="award-info-item"><span class="award-level">{level_award_text}</span></span>')
        if winner_display:
            info_parts.append(f'<span class="award-info-item"><span class="award-info-label">获奖者：</span><span class="award-info-value">{winner_display}</span></span>')
        if supervisor_display:
            info_parts.append(f'<span class="award-info-item"><span class="award-info-label">指导教师：</span><span class="award-info-value">{supervisor_display}</span></span>')
        
        # 构建奖项项HTML
        award_item_html = f"""
            <li class="award-item">
                <div class="award-item-header">
                    {''.join(info_parts)}
                </div>
                {f'<div class="award-image-container"><img src="{img_path}" alt="奖状图片" onclick="openImageModal(this.src)" /></div>' if image_path and image_path.exists() else ''}
            </li>
        """
        award_items.append(award_item_html)
    
    # 生成完整的竞赛卡片HTML
    competition_html = f"""
        <div class="competition-card">
            <div class="competition-name" onclick="toggleCompetition(this)">
                {competition_name}
                <span class="competition-info">({total_awards}项 - 一等奖:{first_prize_count} 二等奖:{second_prize_count} 三等奖:{third_prize_count})</span>
            </div>
            <div class="competition-details-content">
                <ul class="award-list">
                    {''.join(award_items)}
                </ul>
            </div>
        </div>
    """
    
    return competition_html


def generate_analysis_report(
    awards: List[Any],
    filter_year: Optional[str] = None,
    filter_teacher: Optional[str] = None
) -> bytes:
    """
    生成分析报告压缩包（HTML + Excel + Images）
    
    Args:
        awards: 奖状对象列表（需要包含 competition_obj 等关联对象）
        filter_year: 筛选年份（用于显示，可选）
        filter_teacher: 筛选教师（用于显示，可选）
    
    Returns:
        zip文件的bytes数据
    """
    logger.info(f"开始生成分析报告，共 {len(awards)} 个奖状")
    
    # 1. 生成Excel数据
    excel_data = generate_excel_data(awards)

    # 2. 生成数据
    # 只统计学生奖状用于分析
    student_awards = [a for a in awards if not (a.granted_role and "教师" in a.granted_role)]

    # 2.1 生成竞赛类型分布饼图数据
    type_stats = _get_competition_type_stats(awards)
    competition_type_data = [
        {"value": type_stats["白名单赛事"], "name": "白名单赛事"},
        {"value": type_stats["观察名单赛事"], "name": "观察名单赛事"},
        {"value": type_stats["其他"], "name": "其他"}
    ]
    
    # 2.2 生成竞赛等级分布数据（按国赛/省赛统计各奖项数量）
    level_stats = {}
    for a in student_awards:
        level = a.competition_level or "未知"
        if level not in level_stats:
            level_stats[level] = {"first_prize": 0, "second_prize": 0, "third_prize": 0, "other_prize": 0}
        
        award_level = a.award_level or ""
        if "一等奖" in award_level or "一等" in award_level:
            level_stats[level]["first_prize"] += 1
        elif "二等奖" in award_level or "二等" in award_level:
            level_stats[level]["second_prize"] += 1
        elif "三等奖" in award_level or "三等" in award_level:
            level_stats[level]["third_prize"] += 1
        else:
            level_stats[level]["other_prize"] += 1
    
    # 转换为模板需要的格式
    competition_level_data = []
    level_table_rows = []
    for level, stats in sorted(level_stats.items()):
        total = stats["first_prize"] + stats["second_prize"] + stats["third_prize"] + stats["other_prize"]
        competition_level_data.append({
            "name": level,
            "first_prize": stats["first_prize"],
            "second_prize": stats["second_prize"],
            "third_prize": stats["third_prize"],
            "other_prize": stats["other_prize"]
        })
        level_table_rows.append(f"""
                            <tr>
                                <td>{level}</td>
                                <td>{stats["first_prize"]}</td>
                                <td>{stats["second_prize"]}</td>
                                <td>{stats["third_prize"]}</td>
                                <td>{stats["other_prize"]}</td>
                                <td>{total}</td>
                            </tr>
        """)

    # 2.3 生成竞赛详情（可展开，内嵌在主HTML中）
    # 按竞赛名称分组
    competitions_by_name = {}
    for a in awards:
        comp_name = getattr(a, 'competition_name_in_file', '') or getattr(a.competition_obj, 'name', '') or "未知竞赛"
        comp_name_clean = comp_name.replace('/', '_').replace('\\', '_').replace(':', '').replace('*', '').replace('?', '').replace('"', '').replace('<', '').replace('>', '').replace('|', '')
        if comp_name_clean not in competitions_by_name:
            competitions_by_name[comp_name_clean] = []
        competitions_by_name[comp_name_clean].append(a)
    
    # 生成竞赛详情的可展开内容
    competition_details_html = ""
    for competition_name, competition_awards in competitions_by_name.items():
        competition_details_html += _generate_competition_details_inline(
            competition_awards,
            competition_name=competition_name
        )
    # 3. 生成首页HTML
    final_html = MAIN_HTML_TEMPLATE.replace("{DATE}", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    final_html = final_html.replace("{FILTER_YEAR}", str(filter_year) if filter_year else "全部")
    final_html = final_html.replace("{FILTER_TEACHER}", filter_teacher or "全部")
    
    # 添加缺失的统计变量替换
    final_html = final_html.replace("{YEAR}", str(filter_year) if filter_year else "全部")
    final_html = final_html.replace("{FILTER_SCOPE}", f"{filter_teacher or '全部教师'} - {filter_year or '全部年份'}")
    final_html = final_html.replace("{GENERATE_TIME}", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    final_html = final_html.replace("{TOTAL_AWARDS}", str(len(awards)))
    final_html = final_html.replace("{TOTAL_COMPETITIONS}", str(len(competitions_by_name)))
    
    # 计算获奖人数、国赛数和省赛数
    winners = set()
    national_count = 0
    province_count = 0
    
    for a in awards:
        if hasattr(a, 'winner_name') and a.winner_name:
            for winner in a.winner_name.replace('、', ',').replace('，', ',').split(','):
                if winner.strip():
                    winners.add(winner.strip())
        
        # 统计国赛和省赛数量（只统计学生奖状）
        if not (a.granted_role and "教师" in a.granted_role):
            competition_level = getattr(a, 'competition_level', '') or ''
            if competition_level == '国赛':
                national_count += 1
            elif competition_level == '省赛':
                province_count += 1
    
    final_html = final_html.replace("{TOTAL_WINNERS}", str(len(winners)))
    final_html = final_html.replace("{NATIONAL_COUNT}", str(national_count))
    final_html = final_html.replace("{PROVINCE_COUNT}", str(province_count))
    
    # 确保图表数据变量也被替换
    final_html = final_html.replace("{COMPETITION_DETAILS}", competition_details_html)
    
    # 替换图表数据变量
    final_html = final_html.replace("{COMPETITION_TYPE_DATA}", json.dumps(competition_type_data, ensure_ascii=False))
    final_html = final_html.replace("{COMPETITION_LEVEL_DATA}", json.dumps(competition_level_data, ensure_ascii=False))
    final_html = final_html.replace("{LEVEL_TABLE_DATA}", "".join(level_table_rows))
    
    # 4. 创建Zip压缩包
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # Write HTML (只有一个主HTML文件)
        html_filename = f"{filter_year or 'all'}_{filter_teacher or 'all'}.html"
        zf.writestr(html_filename, final_html)
        
        # Write Excel (如果生成成功)
        if excel_data:
            excel_filename = f"{filter_year or 'all'}_{filter_teacher or 'all'}.xlsx"
            zf.writestr(excel_filename, excel_data)
        
        # Write Images
        for a in awards:
            image_bytes = a.get_image_bytes()
            if image_bytes:
                # 确定文件扩展名
                image_path = a.get_image_path()
                if image_path and image_path.exists():
                    try:
                        # 创建新的图片路径结构
                        competition_name = getattr(a, 'competition_name_in_file', '') or getattr(a.competition_obj, 'name', '') or "未知竞赛"
                        # 清理竞赛名称，避免路径问题
                        competition_name = competition_name.replace('/', '_').replace('\\', '_').replace(':', '').replace('*', '').replace('?', '').replace('"', '').replace('<', '').replace('>', '').replace('|', '')
                        
                        # 获取第一个获奖者名字
                        winner_name = getattr(a, 'winner_name', '').replace('、', ',').replace('，', ',')
                        first_winner = winner_name.split(',')[0]
                        # 获取赛道
                        track = getattr(a, 'track', '') 
                        
                        # 获取竞赛等级和获奖等级
                        competition_level = getattr(a, 'competition_level', '') or "未知级别"
                        award_level = getattr(a, 'award_level', '') or "未知奖项"
                        
                        # 构建图片文件名
                        if track:
                            img_filename = f"{track}_{first_winner}_{competition_level}{award_level}_{a.id}{image_path.suffix}"
                        else:
                            img_filename = f"{first_winner}_{competition_level}{award_level}_{a.id}{image_path.suffix}"
                        # 清理文件名
                        img_filename = img_filename.replace('/', '_').replace('\\', '_').replace(':', '').replace('*', '').replace('?', '').replace('"', '').replace('<', '').replace('>', '').replace('|', '')
                        
                        # 构建完整路径
                        full_img_path = f"images/{competition_name}/{img_filename}"
                        #logger.info(f"添加图片到压缩包: {full_img_path}")
                        
                        zf.write(str(image_path), full_img_path)
                    except Exception as e:
                        logger.warning(f"无法添加图片 {a.id}: {e}")
    
    logger.info(f"分析报告生成完成，共 {len(awards)} 个奖状")
    return zip_buffer.getvalue()


# 学生个人成果导出 HTML 模板（左侧导航 + 右侧主内容，现代简洁风格）
PERSONAL_EXPORT_HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>个人成果 - {STUDENT_NAME}</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
            background: #f0f2f5;
            line-height: 1.6;
            color: #1a1a2e;
        }
        .main-wrapper { display: flex; min-height: 100vh; }
        .sidebar {
            width: 300px;
            background: #fff;
            height: 100vh;
            position: sticky;
            top: 0;
            overflow-y: auto;
            box-shadow: 2px 0 12px rgba(0,0,0,0.06);
            flex-shrink: 0;
        }
        .sidebar::-webkit-scrollbar { width: 6px; }
        .sidebar::-webkit-scrollbar-thumb { background: #cbd5e0; border-radius: 3px; }
        .sidebar-header {
            background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
            color: #fff;
            padding: 24px 20px;
            position: sticky;
            top: 0;
            z-index: 10;
        }
        .sidebar-header h2 { font-size: 1.15rem; font-weight: 600; letter-spacing: 0.02em; margin-bottom: 6px; }
        .sidebar-header .meta { font-size: 0.8rem; opacity: 0.92; line-height: 1.5; }
        .sidebar-summary {
            padding: 16px 20px;
            background: #f8fafc;
            border-bottom: 1px solid #e2e8f0;
        }
        .sidebar-summary-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 6px 0;
            font-size: 0.9rem;
        }
        .sidebar-summary-label { color: #64748b; }
        .sidebar-summary-value { font-weight: 600; color: #4f46e5; font-size: 1rem; }
        .nav-list { padding: 12px 0; }
        .nav-item {
            display: flex;
            align-items: center;
            padding: 12px 20px;
            color: #334155;
            text-decoration: none;
            border-left: 3px solid transparent;
            transition: background 0.15s, border-color 0.15s;
            cursor: pointer;
            font-size: 0.9rem;
        }
        .nav-item:hover { background: #f1f5f9; border-left-color: #a5b4fc; }
        .nav-item.active { background: #eef2ff; border-left-color: #4f46e5; color: #4f46e5; }
        .nav-number { color: #4f46e5; font-weight: 600; margin-right: 10px; flex-shrink: 0; font-size: 0.85rem; }
        .nav-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .main-content { flex: 1; overflow-y: auto; padding: 24px; background: #f0f2f5; }
        .container {
            max-width: 960px;
            margin: 0 auto;
            background: #fff;
            border-radius: 16px;
            box-shadow: 0 4px 24px rgba(0,0,0,0.08);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
            color: #fff;
            padding: 36px 32px;
            text-align: center;
        }
        .header h1 { font-size: 1.75rem; font-weight: 600; letter-spacing: 0.02em; margin-bottom: 8px; }
        .header .meta { font-size: 0.9rem; opacity: 0.92; }
        .summary {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 16px;
            padding: 24px 32px;
            background: #f8fafc;
            border-bottom: 1px solid #e2e8f0;
        }
        .summary-card {
            background: #fff;
            padding: 20px 16px;
            border-radius: 12px;
            text-align: center;
            border: 1px solid #e2e8f0;
            transition: box-shadow 0.2s;
        }
        .summary-card:hover { box-shadow: 0 4px 12px rgba(79,70,229,0.12); }
        .summary-card .number { font-size: 2rem; font-weight: 700; color: #4f46e5; line-height: 1.2; }
        .summary-card .label { color: #64748b; font-size: 0.85rem; margin-top: 4px; }
        .content-inner { padding: 24px 32px 32px; }
        .test-item {
            background: #fff;
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 24px 28px;
            margin-bottom: 20px;
            scroll-margin-top: 24px;
        }
        .test-item:last-of-type { margin-bottom: 0; }
        .test-header {
            display: flex;
            align-items: flex-start;
            flex-wrap: wrap;
            gap: 10px 12px;
            margin-bottom: 20px;
            padding-bottom: 16px;
            border-bottom: 1px solid #f1f5f9;
        }
        .test-header h3 { font-size: 1.1rem; font-weight: 600; color: #1e293b; line-height: 1.4; flex: 1; min-width: 0; }
        .test-header h3 a { color: #4f46e5; text-decoration: none; }
        .test-header h3 a:hover { text-decoration: underline; }
        .status-badge {
            padding: 4px 12px;
            border-radius: 999px;
            font-weight: 500;
            font-size: 0.8rem;
            background: #eef2ff;
            color: #4f46e5;
            flex-shrink: 0;
        }
        .image-container {
            text-align: center;
            margin-bottom: 20px;
            background: #f8fafc;
            padding: 20px;
            border-radius: 12px;
            border: 1px solid #e2e8f0;
        }
        .image-container img {
            max-width: 100%;
            max-height: 380px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            transition: transform 0.2s;
        }
        .image-container img:hover { transform: scale(1.01); }
        .image-container a { display: inline-block; }
        .info-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
            gap: 12px;
        }
        .info-item {
            background: #f8fafc;
            padding: 14px 16px;
            border-radius: 8px;
            border-left: 3px solid #4f46e5;
        }
        .info-label { color: #64748b; font-size: 0.8rem; margin-bottom: 4px; }
        .info-value { font-weight: 500; color: #1e293b; word-break: break-word; font-size: 0.9rem; }
        .section {
            margin-top: 32px;
            padding-top: 24px;
            scroll-margin-top: 24px;
        }
        .section-title {
            font-size: 1.15rem;
            font-weight: 600;
            color: #1e293b;
            margin-bottom: 16px;
            padding-bottom: 10px;
            border-bottom: 2px solid #4f46e5;
        }
        .block-card {
            background: #f8fafc;
            padding: 16px 20px;
            border-radius: 10px;
            margin-bottom: 12px;
            border: 1px solid #e2e8f0;
            border-left: 4px solid #4f46e5;
        }
        .block-card .title { font-weight: 600; color: #1e293b; margin-bottom: 4px; font-size: 0.95rem; }
        .block-card .sub { font-size: 0.85rem; color: #64748b; line-height: 1.5; }
        @media (max-width: 768px) {
            .main-wrapper { flex-direction: column; }
            .sidebar { width: 100%; height: auto; max-height: 280px; }
            .summary { grid-template-columns: repeat(2, 1fr); }
        }
    </style>
</head>
<body>
    <div class="main-wrapper">
        <div class="sidebar">
            <div class="sidebar-header">
                <h2>个人成果导航</h2>
                <div class="meta">学号：{STUDENT_ID}<br>{GENERATE_TIME}</div>
            </div>
            <div class="sidebar-summary">
                {SUMMARY_SIDEBAR}
            </div>
            <div class="nav-list">
                {NAV_ITEMS}
            </div>
        </div>
        <div class="main-content">
            <div class="container">
                <div class="header">
                    <h1>{STUDENT_NAME} · 个人成果</h1>
                    <div class="meta">学号：{STUDENT_ID} &nbsp;|&nbsp; 生成时间：{GENERATE_TIME}</div>
                </div>
                <div class="summary">
                    {SUMMARY_CARDS}
                </div>
                <div class="content-inner">
                    {CONTENT_BODY}
                </div>
            </div>
        </div>
    </div>
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            var navItems = document.querySelectorAll('.nav-item');
            var testItems = document.querySelectorAll('.test-item');
            for (var i = 0; i < navItems.length; i++) {
                navItems[i].addEventListener('click', function() {
                    for (var j = 0; j < navItems.length; j++) navItems[j].classList.remove('active');
                    this.classList.add('active');
                });
            }
            function highlightNavOnScroll() {
                var current = '';
                for (var k = 0; k < testItems.length; k++) {
                    var rect = testItems[k].getBoundingClientRect();
                    if (rect.top <= 150 && rect.bottom >= 150) current = testItems[k].id;
                }
                for (var m = 0; m < navItems.length; m++) {
                    navItems[m].classList.remove('active');
                    if (navItems[m].getAttribute('href') === '#' + current) navItems[m].classList.add('active');
                }
            }
            var mainContent = document.querySelector('.main-content');
            if (mainContent) mainContent.addEventListener('scroll', highlightNavOnScroll);
            window.addEventListener('scroll', highlightNavOnScroll);
        });
    </script>
</body>
</html>
"""


def _escape_html(s: Optional[str]) -> str:
    """简单 HTML 转义，用于表格单元格。"""
    if s is None:
        return ""
    s = str(s)
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _get_award_image_relative_path(award: Any, base_path: str = "images") -> Optional[str]:
    """
    计算奖状在导出 zip 中对应的佐证图片相对路径（与 export_utils.add_award_images_to_zip 规则一致）。
    若该奖状无图片或找不到文件，返回 None。
    """
    if not getattr(award, "image_hash", None):
        return None
    try:
        from backend.services.unified_file_manager import get_unified_file_manager
        file_manager = get_unified_file_manager()
        ext = None
        for possible_ext in [".jpg", ".jpeg", ".png", ".gif"]:
            try:
                file_manager.find_file_by_path(f"awards/{award.image_hash}{possible_ext}")
                ext = possible_ext
                break
            except FileNotFoundError:
                continue
        if ext is None:
            return None
    except Exception:
        return None

    competition_name = (
        getattr(award, "competition_name_in_file", "")
        or (getattr(award.competition_obj, "name", "") if getattr(award, "competition_obj", None) else "")
        or "未知竞赛"
    )
    competition_name = competition_name.replace("/", "_").replace("\\", "_").replace(":", "").replace("*", "").replace("?", "").replace('"', "").replace("<", "").replace(">", "").replace("|", "")

    winner_name = getattr(award, "winner_name", "") or ""
    first_winner = (winner_name.replace("、", ",").replace("，", ",").split(",")[0] or "未知").strip()
    first_winner = first_winner.replace("\\", "_").replace("/", "_")
    track = getattr(award, "track", "") or ""
    competition_level = getattr(award, "competition_level", "") or "未知级别"
    award_level = getattr(award, "award_level", "") or "未知奖项"

    if track:
        img_filename = f"{track}_{first_winner}_{competition_level}{award_level}_{award.id}{ext}"
    else:
        img_filename = f"{first_winner}_{competition_level}{award_level}_{award.id}{ext}"
    img_filename = img_filename.replace("/", "_").replace("\\", "_").replace(":", "").replace("*", "").replace("?", "").replace('"', "").replace("<", "").replace(">", "").replace("|", "")

    return f"{base_path}/{competition_name}/{img_filename}"


def generate_personal_export_student(
    student: Any,
    awards: List[Any],
    patents: Optional[List[Any]] = None,
    software_list: Optional[List[Any]] = None,
    innovation_projects: Optional[List[Any]] = None,
) -> bytes:
    """
    生成学生个人成果导出 zip（HTML + 佐证材料）。
    佐证材料仅包含奖状图片，复用 export_utils.add_award_images_to_zip 的路径与命名规则。

    Args:
        student: 学生对象（需有 name、student_id）
        awards: 奖状对象列表
        patents: 专利列表（可选）
        software_list: 软著列表（可选）
        innovation_projects: 大创项目列表（可选）

    Returns:
        zip 文件的 bytes
    """
    patents = patents or []
    software_list = software_list or []
    innovation_projects = innovation_projects or []

    student_name = _escape_html(getattr(student, "name", None) or getattr(student, "student_id", "") or "学生")
    student_id = _escape_html(getattr(student, "student_id", None) or "")
    generate_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 左侧摘要：获奖/大创/专利/软著数量
    summary_sidebar_lines = [
        '<div class="sidebar-summary-item"><span class="sidebar-summary-label">获奖</span><span class="sidebar-summary-value">{}</span></div>'.format(len(awards)),
        '<div class="sidebar-summary-item"><span class="sidebar-summary-label">大创</span><span class="sidebar-summary-value">{}</span></div>'.format(len(innovation_projects)),
        '<div class="sidebar-summary-item"><span class="sidebar-summary-label">专利</span><span class="sidebar-summary-value">{}</span></div>'.format(len(patents)),
        '<div class="sidebar-summary-item"><span class="sidebar-summary-label">软著</span><span class="sidebar-summary-value">{}</span></div>'.format(len(software_list)),
    ]
    summary_sidebar = "\n                ".join(summary_sidebar_lines)

    # 顶部统计卡片（与参考一致）
    summary_cards = (
        '<div class="summary-card"><div class="number">{}</div><div class="label">获奖</div></div>'
        '<div class="summary-card"><div class="number">{}</div><div class="label">大创</div></div>'
        '<div class="summary-card"><div class="number">{}</div><div class="label">专利</div></div>'
        '<div class="summary-card"><div class="number">{}</div><div class="label">软著</div></div>'
    ).format(len(awards), len(innovation_projects), len(patents), len(software_list))

    # 左侧导航：每条获奖记录一项，再加大创/专利/软著区块锚点
    nav_items = []
    for i, a in enumerate(awards, 1):
        comp_name = (getattr(a, "competition_obj", None) and getattr(a.competition_obj, "name", "")) or getattr(a, "competition_name_in_file", "") or "未知竞赛"
        nav_name = comp_name[:40] + ("…" if len(comp_name) > 40 else "")
        nav_items.append(
            '<a href="#award-{}" class="nav-item" data-target="award-{}">'
            '<span class="nav-number">[{}]</span><span class="nav-name">{}</span></a>'
            .format(i, i, i, _escape_html(nav_name))
        )
    if innovation_projects:
        nav_items.append('<a href="#section-innovation" class="nav-item" data-target="section-innovation">'
                         '<span class="nav-number">[大创]</span><span class="nav-name">大创项目（{} 项）</span></a>'.format(len(innovation_projects)))
    if patents:
        nav_items.append('<a href="#section-patents" class="nav-item" data-target="section-patents">'
                         '<span class="nav-number">[专利]</span><span class="nav-name">专利（{} 项）</span></a>'.format(len(patents)))
    if software_list:
        nav_items.append('<a href="#section-software" class="nav-item" data-target="section-software">'
                         '<span class="nav-number">[软著]</span><span class="nav-name">软著（{} 项）</span></a>'.format(len(software_list)))
    nav_items_html = "\n                ".join(nav_items)

    def _info_item(label: str, val: Any) -> str:
        if val is None or str(val).strip() == "":
            return ""
        return (
            '<div class="info-item">'
            '<div class="info-label">{}</div><div class="info-value">{}</div></div>'
            .format(_escape_html(label), _escape_html(str(val)))
        )

    # 主内容：获奖记录为 test-item（参考标准答案布局），再加大创/专利/软著 section
    content_parts = []
    for i, a in enumerate(awards, 1):
        comp_name = (getattr(a, "competition_obj", None) and getattr(a.competition_obj, "name", "")) or getattr(a, "competition_name_in_file", "") or "未知竞赛"
        level = getattr(a, "competition_level", "") or ""
        award_level = getattr(a, "award_level", "") or ""
        img_path = _get_award_image_relative_path(a, base_path="images")
        title_html = ('<a href="{}" target="_blank">{}</a>'.format(img_path, _escape_html(comp_name))) if img_path else _escape_html(comp_name)
        badge_parts = []
        if level:
            badge_parts.append('<span class="status-badge status-success">{}</span>'.format(_escape_html(level)))
        if award_level:
            badge_parts.append('<span class="status-badge status-success">{}</span>'.format(_escape_html(award_level)))
        badges_html = " ".join(badge_parts)

        info_cells = []
        for label, key in [
            ("年份", "year"), ("届数", "edition"), ("获奖日期", "date"), ("赛道", "track"),
            ("组别", "group_name"), ("主办单位", "issuer"), ("省份", "province"),
            ("获奖者", "winner_name"), ("指导教师", "supervisor_name"), ("作品名称", "project_title"),
            ("证书编号", "certificate_id"), ("授予角色", "granted_role"), ("相关学生", "related_student_name"),
        ]:
            cell = _info_item(label, getattr(a, key, None))
            if cell:
                info_cells.append(cell)
        info_grid_html = '<div class="info-grid">' + "".join(info_cells) + "</div>" if info_cells else ""

        image_block = ""
        if img_path:
            image_block = (
                '<div class="image-container">'
                '<a href="{}" target="_blank"><img src="{}" alt="佐证" onerror="this.style.display=\'none\'"></a>'
                '</div>'
            ).format(img_path, img_path)

        content_parts.append(
            '<div class="test-item" id="award-{}">'
            '<div class="test-header"><h3>[{}] {}</h3>{}</div>'
            '{}'
            '{}'
            '</div>'
            .format(i, i, title_html, badges_html, image_block, info_grid_html)
        )

    awards_section = "".join(content_parts)

    # 大创项目：块状卡片
    innovation_cards = []
    for p in innovation_projects:
        year = (p.start_date or "")[:4] if getattr(p, "start_date", None) else ""
        name = getattr(p, "project_name", "") or "-"
        no_ = getattr(p, "project_no", "") or "-"
        typ = getattr(p, "project_type", "") or "-"
        leader = getattr(p, "student_leader_name", "") or "-"
        supervisors = getattr(p, "supervisors", "") or "-"
        status = getattr(p, "status", "") or "-"
        innovation_cards.append(
            f'<div class="block-card"><div class="title">{_escape_html(year)} {_escape_html(name)}</div>'
            f'<div class="sub">项目编号：{_escape_html(no_)} · 级别：{_escape_html(typ)} · 负责人：{_escape_html(leader)} · 指导教师：{_escape_html(supervisors)} · 状态：{_escape_html(status)}</div></div>'
        )
    innovation_section = ""
    if innovation_projects:
        innovation_section = (
            '<section class="section" id="section-innovation">'
            '<span class="section-title">大创项目（{} 项）</span><div>{}</div></section>'
        ).format(len(innovation_projects), "".join(innovation_cards))

    # 专利：块状卡片
    patent_cards = []
    for p in patents:
        name = getattr(p, "patent_name", "") or "-"
        typ = getattr(p, "patent_type", "") or "-"
        patent_cards.append(
            f'<div class="block-card"><div class="title">{_escape_html(name)}</div><div class="sub">类型：{_escape_html(typ)} · ID：{p.id}</div></div>'
        )
    patents_section = ""
    if patents:
        patents_section = (
            '<section class="section" id="section-patents">'
            '<span class="section-title">专利（{} 项）</span><div>{}</div></section>'
        ).format(len(patents), "".join(patent_cards))

    # 软著：块状卡片
    software_cards = []
    for s in software_list:
        name = getattr(s, "software_name", "") or "-"
        reg = getattr(s, "registration_number", "") or "-"
        software_cards.append(
            f'<div class="block-card"><div class="title">{_escape_html(name)}</div><div class="sub">登记号：{_escape_html(reg)} · ID：{s.id}</div></div>'
        )
    software_section = ""
    if software_list:
        software_section = (
            '<section class="section" id="section-software">'
            '<span class="section-title">软著（{} 项）</span><div>{}</div></section>'
        ).format(len(software_list), "".join(software_cards))

    content_body = awards_section + innovation_section + patents_section + software_section

    html_content = PERSONAL_EXPORT_HTML_TEMPLATE.replace("{STUDENT_NAME}", student_name)
    html_content = html_content.replace("{STUDENT_ID}", student_id)
    html_content = html_content.replace("{GENERATE_TIME}", generate_time)
    html_content = html_content.replace("{SUMMARY_SIDEBAR}", summary_sidebar)
    html_content = html_content.replace("{NAV_ITEMS}", nav_items_html)
    html_content = html_content.replace("{SUMMARY_CARDS}", summary_cards)
    html_content = html_content.replace("{CONTENT_BODY}", content_body)

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        name_safe = (getattr(student, "name", None) or getattr(student, "student_id", "") or "student").replace("/", "_").replace("\\", "_")
        html_filename = f"个人成果_{name_safe}_{datetime.now().strftime('%Y%m%d')}.html"
        zf.writestr(html_filename, html_content.encode("utf-8"))

        from backend.utils.export_utils import add_award_images_to_zip
        add_award_images_to_zip(zf, awards, base_path="images")

    zip_buffer.seek(0)
    logger.info(f"学生个人成果导出 zip 生成完成，奖状 {len(awards)} 项")
    return zip_buffer.getvalue()


def generate_personal_export_teacher(
    teacher: Any,
    awards: List[Any],
    patents: Optional[List[Any]] = None,
    software_list: Optional[List[Any]] = None,
    innovation_projects: Optional[List[Any]] = None,
    include_images: bool = True,
) -> bytes:
    """
    生成教师个人成果导出 zip（HTML + 佐证材料），与学生导出一致的布局风格。

    Args:
        teacher: 教师对象（需有 name、teacher_id）
        awards: 奖状对象列表
        patents: 专利列表（可选）
        software_list: 软著列表（可选）
        innovation_projects: 大创项目列表（可选）
        include_images: 是否包含奖状佐证图片

    Returns:
        zip 文件的 bytes
    """
    patents = patents or []
    software_list = software_list or []
    innovation_projects = innovation_projects or []

    teacher_name = _escape_html(getattr(teacher, "name", None) or getattr(teacher, "teacher_id", "") or "教师")
    teacher_id = _escape_html(getattr(teacher, "teacher_id", None) or "")
    generate_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 左侧摘要：获奖/大创/专利/软著数量
    summary_sidebar_lines = [
        '<div class="sidebar-summary-item"><span class="sidebar-summary-label">获奖</span><span class="sidebar-summary-value">{}</span></div>'.format(len(awards)),
        '<div class="sidebar-summary-item"><span class="sidebar-summary-label">大创</span><span class="sidebar-summary-value">{}</span></div>'.format(len(innovation_projects)),
        '<div class="sidebar-summary-item"><span class="sidebar-summary-label">专利</span><span class="sidebar-summary-value">{}</span></div>'.format(len(patents)),
        '<div class="sidebar-summary-item"><span class="sidebar-summary-label">软著</span><span class="sidebar-summary-value">{}</span></div>'.format(len(software_list)),
    ]
    summary_sidebar = "\n                ".join(summary_sidebar_lines)

    # 顶部统计卡片
    summary_cards = (
        '<div class="summary-card"><div class="number">{}</div><div class="label">获奖</div></div>'
        '<div class="summary-card"><div class="number">{}</div><div class="label">大创</div></div>'
        '<div class="summary-card"><div class="number">{}</div><div class="label">专利</div></div>'
        '<div class="summary-card"><div class="number">{}</div><div class="label">软著</div></div>'
    ).format(len(awards), len(innovation_projects), len(patents), len(software_list))

    # 左侧导航
    nav_items = []
    for i, a in enumerate(awards, 1):
        comp_name = (getattr(a, "competition_obj", None) and getattr(a.competition_obj, "name", "")) or getattr(a, "competition_name_in_file", "") or "未知竞赛"
        nav_name = comp_name[:40] + ("…" if len(comp_name) > 40 else "")
        nav_items.append(
            '<a href="#award-{}" class="nav-item" data-target="award-{}">'
            '<span class="nav-number">[{}]</span><span class="nav-name">{}</span></a>'
            .format(i, i, i, _escape_html(nav_name))
        )
    if innovation_projects:
        nav_items.append('<a href="#section-innovation" class="nav-item" data-target="section-innovation">'
                         '<span class="nav-number">[大创]</span><span class="nav-name">大创项目（{} 项）</span></a>'.format(len(innovation_projects)))
    if patents:
        nav_items.append('<a href="#section-patents" class="nav-item" data-target="section-patents">'
                         '<span class="nav-number">[专利]</span><span class="nav-name">专利（{} 项）</span></a>'.format(len(patents)))
    if software_list:
        nav_items.append('<a href="#section-software" class="nav-item" data-target="section-software">'
                         '<span class="nav-number">[软著]</span><span class="nav-name">软著（{} 项）</span></a>'.format(len(software_list)))
    nav_items_html = "\n                ".join(nav_items)

    def _info_item(label: str, val: Any) -> str:
        if val is None or str(val).strip() == "":
            return ""
        return (
            '<div class="info-item">'
            '<div class="info-label">{}</div><div class="info-value">{}</div></div>'
            .format(_escape_html(label), _escape_html(str(val)))
        )

    # 主内容：获奖记录
    content_parts = []
    for i, a in enumerate(awards, 1):
        comp_name = (getattr(a, "competition_obj", None) and getattr(a.competition_obj, "name", "")) or getattr(a, "competition_name_in_file", "") or "未知竞赛"
        level = getattr(a, "competition_level", "") or ""
        award_level = getattr(a, "award_level", "") or ""
        img_path = _get_award_image_relative_path(a, base_path="images")
        title_html = ('<a href="{}" target="_blank">{}</a>'.format(img_path, _escape_html(comp_name))) if img_path else _escape_html(comp_name)
        badge_parts = []
        if level:
            badge_parts.append('<span class="status-badge status-success">{}</span>'.format(_escape_html(level)))
        if award_level:
            badge_parts.append('<span class="status-badge status-success">{}</span>'.format(_escape_html(award_level)))
        badges_html = " ".join(badge_parts)

        info_cells = []
        for label, key in [
            ("年份", "year"), ("届数", "edition"), ("获奖日期", "date"), ("赛道", "track"),
            ("组别", "group_name"), ("主办单位", "issuer"), ("省份", "province"),
            ("获奖者", "winner_name"), ("指导教师", "supervisor_name"), ("作品名称", "project_title"),
            ("证书编号", "certificate_id"), ("授予角色", "granted_role"), ("相关学生", "related_student_name"),
        ]:
            cell = _info_item(label, getattr(a, key, None))
            if cell:
                info_cells.append(cell)
        info_grid_html = '<div class="info-grid">' + "".join(info_cells) + "</div>" if info_cells else ""

        image_block = ""
        if img_path:
            image_block = (
                '<div class="image-container">'
                '<a href="{}" target="_blank"><img src="{}" alt="佐证" onerror="this.style.display=\'none\'"></a>'
                '</div>'
            ).format(img_path, img_path)

        content_parts.append(
            '<div class="test-item" id="award-{}">'
            '<div class="test-header"><h3>[{}] {}</h3>{}</div>'
            '{}'
            '{}'
            '</div>'
            .format(i, i, title_html, badges_html, image_block, info_grid_html)
        )

    awards_section = "".join(content_parts)

    # 大创项目
    innovation_cards = []
    for p in innovation_projects:
        year = (getattr(p, "start_date", None) or "")[:4] if getattr(p, "start_date", None) else ""
        name = getattr(p, "project_name", "") or "-"
        no_ = getattr(p, "project_no", "") or "-"
        typ = getattr(p, "project_type", "") or "-"
        leader = getattr(p, "student_leader_name", "") or "-"
        supervisors = getattr(p, "supervisors", "") or "-"
        status = getattr(p, "status", "") or "-"
        innovation_cards.append(
            f'<div class="block-card"><div class="title">{_escape_html(str(year))} {_escape_html(name)}</div>'
            f'<div class="sub">项目编号：{_escape_html(no_)} · 级别：{_escape_html(typ)} · 负责人：{_escape_html(leader)} · 指导教师：{_escape_html(supervisors)} · 状态：{_escape_html(status)}</div></div>'
        )
    innovation_section = ""
    if innovation_projects:
        innovation_section = (
            '<section class="section" id="section-innovation">'
            '<span class="section-title">大创项目（{} 项）</span><div>{}</div></section>'
        ).format(len(innovation_projects), "".join(innovation_cards))

    # 专利
    patent_cards = []
    for p in patents:
        name = getattr(p, "patent_name", "") or "-"
        typ = getattr(p, "patent_type", "") or "-"
        patent_cards.append(
            f'<div class="block-card"><div class="title">{_escape_html(name)}</div><div class="sub">类型：{_escape_html(typ)} · ID：{p.id}</div></div>'
        )
    patents_section = ""
    if patents:
        patents_section = (
            '<section class="section" id="section-patents">'
            '<span class="section-title">专利（{} 项）</span><div>{}</div></section>'
        ).format(len(patents), "".join(patent_cards))

    # 软著
    software_cards = []
    for s in software_list:
        name = getattr(s, "software_name", "") or "-"
        reg = getattr(s, "registration_number", "") or "-"
        software_cards.append(
            f'<div class="block-card"><div class="title">{_escape_html(name)}</div><div class="sub">登记号：{_escape_html(reg)} · ID：{s.id}</div></div>'
        )
    software_section = ""
    if software_list:
        software_section = (
            '<section class="section" id="section-software">'
            '<span class="section-title">软著（{} 项）</span><div>{}</div></section>'
        ).format(len(software_list), "".join(software_cards))

    content_body = awards_section + innovation_section + patents_section + software_section

    # 使用与学生相同的模板，将学号改为工号
    html_content = PERSONAL_EXPORT_HTML_TEMPLATE.replace("学号：", "工号：")
    html_content = html_content.replace("{STUDENT_NAME}", teacher_name)
    html_content = html_content.replace("{STUDENT_ID}", teacher_id)
    html_content = html_content.replace("{GENERATE_TIME}", generate_time)
    html_content = html_content.replace("{SUMMARY_SIDEBAR}", summary_sidebar)
    html_content = html_content.replace("{NAV_ITEMS}", nav_items_html)
    html_content = html_content.replace("{SUMMARY_CARDS}", summary_cards)
    html_content = html_content.replace("{CONTENT_BODY}", content_body)

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        name_safe = (getattr(teacher, "name", None) or getattr(teacher, "teacher_id", "") or "teacher").replace("/", "_").replace("\\", "_")
        html_filename = f"个人成果_{name_safe}_{datetime.now().strftime('%Y%m%d')}.html"
        zf.writestr(html_filename, html_content.encode("utf-8"))

        if include_images:
            from backend.utils.export_utils import add_award_images_to_zip
            add_award_images_to_zip(zf, awards, base_path="images")

    zip_buffer.seek(0)
    logger.info(f"教师个人成果导出 zip 生成完成，奖状 {len(awards)} 项")
    return zip_buffer.getvalue()

