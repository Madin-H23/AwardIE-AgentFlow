// 学生活动管理系统 - 主要JavaScript文件

// 检查 anime.js 是否可用，如果不可用则创建空函数避免错误
if (typeof anime === 'undefined') {
    window.anime = function(options) {
        // 简单的动画包装，使用 CSS 过渡作为备选
        if (options.targets) {
            const targets = typeof options.targets === 'string' 
                ? document.querySelectorAll(options.targets)
                : Array.isArray(options.targets)
                    ? options.targets
                    : [options.targets];
            
            // 处理 delay 和 stagger
            let delayFunction = null;
            if (options.delay) {
                if (typeof options.delay === 'function') {
                    delayFunction = options.delay;
                } else {
                    const delayValue = options.delay;
                    delayFunction = function(el, i) { return i * delayValue; };
                }
            }
            
            targets.forEach((target, index) => {
                if (target && target.style) {
                    const delay = delayFunction ? delayFunction(target, index) : (options.delay || 0);
                    const duration = options.duration || 300;
                    
                    // 设置初始状态
                    if (options.opacity && Array.isArray(options.opacity)) {
                        target.style.opacity = options.opacity[0] || 0;
                    }
                    if (options.translateY && Array.isArray(options.translateY)) {
                        target.style.transform = `translateY(${options.translateY[0] || 0}px)`;
                    }
                    if (options.translateX && Array.isArray(options.translateX)) {
                        target.style.transform = `translateX(${options.translateX[0] || 0}px)`;
                    }
                    if (options.scale && Array.isArray(options.scale)) {
                        target.style.transform = `scale(${options.scale[0] || 1})`;
                    }
                    if (options.rotate && Array.isArray(options.rotate)) {
                        target.style.transform = `rotate(${options.rotate[0] || 0}deg)`;
                    }
                    
                    // 应用过渡
                    if (options.easing) {
                        target.style.transition = `all ${duration}ms ${options.easing}`;
                    } else {
                        target.style.transition = `all ${duration}ms ease`;
                    }
                    
                    // 延迟执行动画
                    setTimeout(() => {
                        if (options.opacity && Array.isArray(options.opacity)) {
                            target.style.opacity = options.opacity[options.opacity.length - 1];
                        }
                        if (options.translateY && Array.isArray(options.translateY)) {
                            const y = options.translateY[options.translateY.length - 1];
                            const currentTransform = target.style.transform;
                            const baseTransform = currentTransform.replace(/translateY\([^)]+\)/, '').trim();
                            target.style.transform = baseTransform ? `${baseTransform} translateY(${y}px)` : `translateY(${y}px)`;
                        }
                        if (options.translateX && Array.isArray(options.translateX)) {
                            const x = options.translateX[options.translateX.length - 1];
                            const currentTransform = target.style.transform;
                            const baseTransform = currentTransform.replace(/translateX\([^)]+\)/, '').trim();
                            target.style.transform = baseTransform ? `${baseTransform} translateX(${x}px)` : `translateX(${x}px)`;
                        }
                        if (options.scale && Array.isArray(options.scale)) {
                            const s = options.scale[options.scale.length - 1];
                            target.style.transform = `scale(${s})`;
                        }
                        if (options.rotate && Array.isArray(options.rotate)) {
                            const r = options.rotate[options.rotate.length - 1];
                            target.style.transform = `rotate(${r}deg)`;
                        }
                        
                        if (options.complete && typeof options.complete === 'function') {
                            setTimeout(options.complete, duration);
                        }
                    }, delay);
                }
            });
        }
        
        // 返回一个对象，模拟 anime.js 的行为
        return {
            pause: function() {},
            play: function() {},
            restart: function() {}
        };
    };
    
    // anime.stagger 函数
    window.anime.stagger = function(amount) {
        return function(el, i) {
            return i * amount;
        };
    };
}

// 全局变量
let currentUser = {
    id: 1,
    name: '张明',
    studentId: '2021001',
    grade: '2021级',
    class: '计科2101',
    major: '计算机科学与技术',
    specialization: '人工智能与机器学习',
    email: 'zhangming@student.edu.cn',
    phone: '138****5678',
    avatar: null,
    skills: ['Python', 'JavaScript', '机器学习', '数据分析', 'Web开发']
};

let activities = [
    {
        id: 'programming-marathon',
        title: '编程马拉松大赛',
        category: 'competition',
        description: '2024年度校园编程竞赛，挑战算法与编程能力，赢取丰厚奖品',
        startDate: '2024.12.15',
        endDate: '2024.12.20',
        location: '计算机楼301',
        status: 'active',
        participants: 24,
        maxParticipants: 30,
        image: 'https://kimi-web-img.moonshot.cn/img/lh7-rt.googleusercontent.com/c057b235feddbab1e77c7756fe2ce8e6ea68611d'
    },
    {
        id: 'ai-lecture',
        title: 'AI技术讲座',
        category: 'academic',
        description: '深度学习前沿技术分享，了解最新AI发展趋势',
        startDate: '2024.12.25',
        endDate: '2024.12.25',
        location: '学术报告厅',
        status: 'pending',
        participants: 156,
        maxParticipants: 200,
        image: 'https://kimi-web-img.moonshot.cn/img/globalconference.ca/9ab8d7792d0acec2ea986f97fd83d63effc0c099.jpg'
    },
    {
        id: 'web-workshop',
        title: 'Web开发工作坊',
        category: 'workshop',
        description: '前后端开发技能培训，掌握现代Web开发技术栈',
        startDate: '2024.11.10',
        endDate: '2024.11.15',
        location: '计算机楼205',
        status: 'completed',
        participants: 32,
        maxParticipants: 35,
        image: 'https://kimi-web-img.moonshot.cn/img/news.ok.ubc.ca/1d15544111627e962bd55a5e556954a5fb7163d5.jpg'
    }
];

let achievements = [
    {
        id: 'programming-marathon-award',
        title: '编程马拉松一等奖',
        type: 'competition',
        description: '2024年度校园编程竞赛中获得一等奖',
        date: '2024.12.20',
        owner: 'me',
        image: 'https://kimi-web-img.moonshot.cn/img/igniteworldwide.org/558dd3ecfc3e53fc6d93f53a910f7db3de570c36.png',
        rank: 1
    },
    {
        id: 'web-certification',
        title: 'Web开发技能证书',
        type: 'certification',
        description: '完成Web开发工作坊培训获得认证',
        date: '2024.11.15',
        owner: 'me',
        image: 'https://kimi-web-img.moonshot.cn/img/sbsmschooledu.in/780d6aeb76461dfc5f822613844322ae5ecea942.jpeg'
    }
];

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    initializePage();
    setupEventListeners();
    initializeAnimations();
    setupCharts();
});

// 初始化页面
function initializePage() {
    const currentPage = getCurrentPage();
    
    switch(currentPage) {
        case 'index':
            initializeDashboard();
            break;
        case 'activities':
            initializeActivities();
            break;
        case 'achievements':
            initializeAchievements();
            break;
        case 'profile':
            initializeProfile();
            break;
    }
}

// 获取当前页面
function getCurrentPage() {
    const path = window.location.pathname;
    if (path.includes('activities')) return 'activities';
    if (path.includes('achievements')) return 'achievements';
    if (path.includes('profile')) return 'profile';
    return 'index';
}

// 设置事件监听器
function setupEventListeners() {
    // 活动筛选器
    const filterBtns = document.querySelectorAll('.filter-btn');
    filterBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            const filter = this.dataset.filter;
            filterActivities(filter);
            updateFilterButtons(this);
        });
    });

    // 成果筛选器
    const achievementFilterBtns = document.querySelectorAll('.achievement-filter-btn');
    achievementFilterBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            const filter = this.dataset.filter;
            filterAchievements(filter);
            updateAchievementFilterButtons(this);
        });
    });

    // 标签页切换
    const tabBtns = document.querySelectorAll('.tab-btn');
    tabBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            const tab = this.dataset.tab;
            switchTab(tab);
            updateTabButtons(this);
        });
    });

    // 文件上传
    const fileUploadArea = document.getElementById('file-upload-area');
    const fileInput = document.getElementById('file-input');
    
    if (fileUploadArea && fileInput) {
        fileUploadArea.addEventListener('click', () => fileInput.click());
        fileUploadArea.addEventListener('dragover', handleDragOver);
        fileUploadArea.addEventListener('dragleave', handleDragLeave);
        fileUploadArea.addEventListener('drop', handleDrop);
        fileInput.addEventListener('change', handleFileSelect);
    }

    // 表单提交（排除登录表单和没有data-validate属性的表单）
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        // 不拦截登录表单和没有data-validate属性的表单
        // form.action 可能是字符串或 URL 对象，需要转换为字符串
        const formAction = form.action ? String(form.action) : '';
        const isLoginForm = (formAction && formAction.includes('/login')) || 
                           form.classList.contains('login-form') ||
                           form.id === 'login-form';
        const hasDataValidate = form.hasAttribute('data-validate');
        
        // 只为有 data-validate 属性且不是登录表单的表单绑定处理函数
        if (!isLoginForm && hasDataValidate) {
            form.addEventListener('submit', handleFormSubmit);
        }
    });
}

// 初始化动画
function initializeAnimations() {
    // 检查 anime.js 是否可用
    if (typeof anime === 'undefined') {
        // 如果没有 anime.js，使用原生 CSS 动画作为备选方案
        const cards = document.querySelectorAll('.card-hover');
        cards.forEach((card, index) => {
            card.style.opacity = '0';
            card.style.transform = 'translateY(30px)';
            card.style.transition = 'opacity 0.8s ease, transform 0.8s ease';
            setTimeout(() => {
                card.style.opacity = '1';
                card.style.transform = 'translateY(0)';
            }, index * 100);
        });
        return;
    }
    
    // 页面加载动画
    anime({
        targets: '.card-hover',
        opacity: [0, 1],
        translateY: [30, 0],
        delay: anime.stagger(100),
        duration: 800,
        easing: 'easeOutQuart'
    });

    // 粒子动画
    const particles = document.querySelectorAll('.particle');
    particles.forEach((particle, index) => {
        anime({
            targets: particle,
            translateY: [0, -20, 0],
            rotate: [0, 180, 360],
            duration: 6000 + Math.random() * 2000,
            delay: index * 200,
            loop: true,
            easing: 'easeInOutSine'
        });
    });
}

// 初始化图表
function setupCharts() {
    // 成果类型分布图表
    const achievementTypeChart = document.getElementById('achievement-type-chart');
    if (achievementTypeChart) {
        const typeChart = echarts.init(achievementTypeChart);
        const typeOption = {
            tooltip: {
                trigger: 'item'
            },
            series: [{
                name: '成果类型',
                type: 'pie',
                radius: '70%',
                data: [
                    { value: 35, name: '竞赛获奖', itemStyle: { color: '#38a169' } },
                    { value: 25, name: '学术成果', itemStyle: { color: '#3182ce' } },
                    { value: 20, name: '项目成果', itemStyle: { color: '#d69e2e' } },
                    { value: 20, name: '技能认证', itemStyle: { color: '#805ad5' } }
                ],
                emphasis: {
                    itemStyle: {
                        shadowBlur: 10,
                        shadowOffsetX: 0,
                        shadowColor: 'rgba(0, 0, 0, 0.5)'
                    }
                }
            }]
        };
        typeChart.setOption(typeOption);
    }

    // 月度成果统计图表
    const achievementMonthlyChart = document.getElementById('achievement-monthly-chart');
    if (achievementMonthlyChart) {
        const monthlyChart = echarts.init(achievementMonthlyChart);
        const monthlyOption = {
            tooltip: {
                trigger: 'axis'
            },
            xAxis: {
                type: 'category',
                data: ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月']
            },
            yAxis: {
                type: 'value'
            },
            series: [{
                name: '成果数量',
                data: [2, 1, 3, 2, 4, 3, 1, 2, 5, 4, 6, 3],
                type: 'line',
                smooth: true,
                itemStyle: {
                    color: '#f6ad55'
                },
                areaStyle: {
                    color: {
                        type: 'linear',
                        x: 0,
                        y: 0,
                        x2: 0,
                        y2: 1,
                        colorStops: [{
                            offset: 0, color: 'rgba(246, 173, 85, 0.3)'
                        }, {
                            offset: 1, color: 'rgba(246, 173, 85, 0.1)'
                        }]
                    }
                }
            }]
        };
        monthlyChart.setOption(monthlyOption);
    }
}

// 初始化仪表板
function initializeDashboard() {
    // 更新统计数据
    updateDashboardStats();
}

// 更新仪表板统计数据
function updateDashboardStats() {
    const totalActivities = activities.length;
    const totalAchievements = achievements.filter(a => a.owner === 'me').length;
    const pendingActivities = activities.filter(a => a.status === 'pending').length;

    // 动画更新数字
    animateNumber('total-activities', totalActivities);
    animateNumber('total-achievements', totalAchievements);
    animateNumber('pending-activities', pendingActivities);
}

// 数字动画
function animateNumber(elementId, targetNumber) {
    const element = document.getElementById(elementId);
    if (!element) return;

    // 检查 anime.js 是否可用
    if (typeof anime !== 'undefined' && anime.stagger) {
        anime({
            targets: { value: 0 },
            value: targetNumber,
            duration: 2000,
            easing: 'easeOutQuart',
            update: function(anim) {
                element.textContent = Math.round(anim.animatables[0].target.value);
            }
        });
    } else {
        // 使用简单的数字递增动画作为备选
        let current = 0;
        const increment = targetNumber / 60; // 60帧，约1秒
        const timer = setInterval(() => {
            current += increment;
            if (current >= targetNumber) {
                current = targetNumber;
                clearInterval(timer);
            }
            element.textContent = Math.round(current);
        }, 1000 / 60); // 60 FPS
    }
}

// 初始化活动页面
function initializeActivities() {
    // 活动筛选器已经通过事件监听器设置
}

// 筛选活动
function filterActivities(filter) {
    const activityCards = document.querySelectorAll('.activity-card');
    
    activityCards.forEach(card => {
        const category = card.dataset.category;
        
        if (filter === 'all' || category === filter) {
            card.style.display = 'block';
            anime({
                targets: card,
                opacity: [0, 1],
                scale: [0.8, 1],
                duration: 500,
                easing: 'easeOutQuart'
            });
        } else {
            anime({
                targets: card,
                opacity: [1, 0],
                scale: [1, 0.8],
                duration: 300,
                easing: 'easeInQuart',
                complete: function() {
                    card.style.display = 'none';
                }
            });
        }
    });
}

// 更新筛选按钮状态
function updateFilterButtons(activeButton) {
    const filterBtns = document.querySelectorAll('.filter-btn');
    
    filterBtns.forEach(btn => {
        btn.classList.remove('filter-active');
        btn.classList.add('bg-gray-100', 'text-gray-700', 'hover:bg-gray-200');
    });
    
    activeButton.classList.add('filter-active');
    activeButton.classList.remove('bg-gray-100', 'text-gray-700', 'hover:bg-gray-200');
}

// 显示活动详情
function showActivityDetail(activityId) {
    const activity = activities.find(a => a.id === activityId);
    if (!activity) return;

    const modal = document.getElementById('activity-modal');
    if (!modal) {
        // 如果没有模态框，直接跳转到活动页面
        window.location.href = 'activities.html';
        return;
    }

    const title = document.getElementById('modal-title');
    const content = document.getElementById('modal-content');

    title.textContent = activity.title;
    content.innerHTML = `
        <div class="space-y-6">
            <div class="relative h-64 rounded-lg overflow-hidden">
                <img src="${activity.image}" alt="${activity.title}" class="w-full h-full object-cover">
                <div class="absolute top-4 right-4">
                    <span class="status-${activity.status} text-white text-sm px-3 py-1 rounded-full">
                        ${getStatusText(activity.status)}
                    </span>
                </div>
            </div>
            
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                    <h4 class="font-semibold text-gray-800 mb-3">活动信息</h4>
                    <div class="space-y-3">
                        <div class="flex items-center text-sm">
                            <svg class="w-4 h-4 mr-2 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"></path>
                            </svg>
                            <span class="text-gray-600">时间：${activity.startDate} - ${activity.endDate}</span>
                        </div>
                        <div class="flex items-center text-sm">
                            <svg class="w-4 h-4 mr-2 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"></path>
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"></path>
                            </svg>
                            <span class="text-gray-600">地点：${activity.location}</span>
                        </div>
                        <div class="flex items-center text-sm">
                            <svg class="w-4 h-4 mr-2 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197m13.5-9a2.5 2.5 0 11-5 0 2.5 2.5 0 015 0z"></path>
                            </svg>
                            <span class="text-gray-600">参与人数：${activity.participants}/${activity.maxParticipants}</span>
                        </div>
                    </div>
                </div>
                
                <div>
                    <h4 class="font-semibold text-gray-800 mb-3">活动描述</h4>
                    <p class="text-gray-600 text-sm leading-relaxed">${activity.description}</p>
                </div>
            </div>
            
            <div class="flex justify-end space-x-4 pt-6 border-t">
                <button onclick="closeModal()" class="px-6 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors">
                    关闭
                </button>
                ${activity.status === 'pending' ? `
                    <button onclick="applyActivity('${activity.id}')" class="px-6 py-2 bg-gradient-to-r from-green-500 to-green-600 text-white rounded-lg hover:from-green-600 hover:to-green-700 transition-all">
                        立即报名
                    </button>
                ` : ''}
            </div>
        </div>
    `;

    modal.classList.remove('hidden');
    
    // 模态框动画
    anime({
        targets: modal.querySelector('.bg-white'),
        scale: [0.8, 1],
        opacity: [0, 1],
        duration: 300,
        easing: 'easeOutQuart'
    });
}

// 报名活动
function applyActivity(activityId) {
    const activity = activities.find(a => a.id === activityId);
    if (!activity) return;

    // 显示确认对话框
    if (confirm(`确定要报名参加"${activity.title}"吗？`)) {
        // 模拟报名成功
        showNotification('报名成功！', 'success');
        closeModal();
        
        // 更新活动状态（模拟）
        if (activity.status === 'pending') {
            activity.participants += 1;
        }
    }
}

// 关闭模态框
function closeModal() {
    const modal = document.getElementById('activity-modal');
    if (modal) {
        modal.classList.add('hidden');
    }
}

// 初始化成果页面
function initializeAchievements() {
    // 成果筛选器已经通过事件监听器设置
}

// 筛选成果
function filterAchievements(filter) {
    const achievementCards = document.querySelectorAll('.achievement-card');
    
    achievementCards.forEach(card => {
        const owner = card.dataset.owner;
        
        let shouldShow = false;
        
        switch(filter) {
            case 'my':
                shouldShow = owner === 'me';
                break;
            case 'others':
                shouldShow = owner === 'others';
                break;
            case 'all':
                shouldShow = true;
                break;
        }
        
        if (shouldShow) {
            card.style.display = 'block';
            anime({
                targets: card,
                opacity: [0, 1],
                scale: [0.8, 1],
                duration: 500,
                easing: 'easeOutQuart'
            });
        } else {
            anime({
                targets: card,
                opacity: [1, 0],
                scale: [1, 0.8],
                duration: 300,
                easing: 'easeInQuart',
                complete: function() {
                    card.style.display = 'none';
                }
            });
        }
    });
}

// 更新成果筛选按钮状态
function updateAchievementFilterButtons(activeButton) {
    const filterBtns = document.querySelectorAll('.achievement-filter-btn');
    
    filterBtns.forEach(btn => {
        btn.classList.remove('bg-gradient-to-r', 'from-orange-500', 'to-orange-600', 'text-white');
        btn.classList.add('bg-gray-100', 'text-gray-700', 'hover:bg-gray-200');
    });
    
    activeButton.classList.add('bg-gradient-to-r', 'from-orange-500', 'to-orange-600', 'text-white');
    activeButton.classList.remove('bg-gray-100', 'text-gray-700', 'hover:bg-gray-200');
}

// 显示成果详情
function showAchievementDetail(achievementId) {
    const achievement = achievements.find(a => a.id === achievementId);
    if (!achievement) return;

    const modal = document.getElementById('achievement-modal');
    const title = document.getElementById('achievement-modal-title');
    const content = document.getElementById('achievement-modal-content');

    title.textContent = achievement.title;
    content.innerHTML = `
        <div class="space-y-6">
            <div class="relative h-64 rounded-lg overflow-hidden">
                <img src="${achievement.image}" alt="${achievement.title}" class="w-full h-full object-cover">
                <div class="absolute top-4 right-4">
                    <span class="achievement-type-${achievement.type} text-white text-sm px-3 py-1 rounded-full">
                        ${getTypeText(achievement.type)}
                    </span>
                </div>
                ${achievement.rank ? `
                    <div class="absolute top-4 left-4">
                        <div class="w-12 h-12 bg-yellow-500 rounded-full flex items-center justify-center">
                            <span class="text-white font-bold">${achievement.rank}</span>
                        </div>
                    </div>
                ` : ''}
            </div>
            
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                    <h4 class="font-semibold text-gray-800 mb-3">成果信息</h4>
                    <div class="space-y-3">
                        <div class="flex items-center text-sm">
                            <svg class="w-4 h-4 mr-2 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"></path>
                            </svg>
                            <span class="text-gray-600">获得时间：${achievement.date}</span>
                        </div>
                        <div class="flex items-center text-sm">
                            <svg class="w-4 h-4 mr-2 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"></path>
                            </svg>
                            <span class="text-gray-600">获得者：${achievement.owner === 'me' ? currentUser.name : '其他学生'}</span>
                        </div>
                    </div>
                </div>
                
                <div>
                    <h4 class="font-semibold text-gray-800 mb-3">成果描述</h4>
                    <p class="text-gray-600 text-sm leading-relaxed">${achievement.description}</p>
                </div>
            </div>
            
            <div class="flex justify-end pt-6 border-t">
                <button onclick="closeAchievementModal()" class="px-6 py-2 bg-gradient-to-r from-orange-500 to-orange-600 text-white rounded-lg hover:from-orange-600 hover:to-orange-700 transition-all">
                    关闭
                </button>
            </div>
        </div>
    `;

    modal.classList.remove('hidden');
    
    // 模态框动画
    anime({
        targets: modal.querySelector('.bg-white'),
        scale: [0.8, 1],
        opacity: [0, 1],
        duration: 300,
        easing: 'easeOutQuart'
    });
}

// 关闭成果模态框
function closeAchievementModal() {
    const modal = document.getElementById('achievement-modal');
    if (modal) {
        modal.classList.add('hidden');
    }
}

// 显示添加成果模态框
function showAddAchievementModal() {
    const modal = document.getElementById('add-achievement-modal');
    if (modal) {
        modal.classList.remove('hidden');
        
        // 模态框动画
        anime({
            targets: modal.querySelector('.bg-white'),
            scale: [0.8, 1],
            opacity: [0, 1],
            duration: 300,
            easing: 'easeOutQuart'
        });
    }
}

// 关闭添加成果模态框
function closeAddAchievementModal() {
    const modal = document.getElementById('add-achievement-modal');
    if (modal) {
        modal.classList.add('hidden');
    }
}

// 个人主页相关函数
function editAvatar() {
    showNotification('头像上传功能开发中...', 'info');
}

function editProfile() {
    const modal = document.getElementById('edit-profile-modal');
    if (modal) {
        modal.classList.remove('hidden');
        
        // 模态框动画
        anime({
            targets: modal.querySelector('.bg-white'),
            scale: [0.8, 1],
            opacity: [0, 1],
            duration: 300,
            easing: 'easeOutQuart'
        });
    }
}

function closeEditModal() {
    const modal = document.getElementById('edit-profile-modal');
    if (modal) {
        modal.classList.add('hidden');
    }
}

function editSkills() {
    showNotification('技术标签编辑功能开发中...', 'info');
}

function editBio() {
    showNotification('个人简介编辑功能开发中...', 'info');
}

// 个人主页表单提交
function handlePersonalFormSubmit(e) {
    e.preventDefault();
    
    const formData = new FormData(e.target);
    const profileData = Object.fromEntries(formData);
    
    console.log('个人主页数据:', profileData);
    
    // 模拟保存成功
    showNotification('个人主页更新成功！', 'success');
    closeEditModal();
    
    // 更新页面显示
    updatePersonalPageDisplay(profileData);
}

// 更新个人主页显示
function updatePersonalPageDisplay(data) {
    // 这里可以添加更新页面显示的逻辑
    // 例如更新姓名、专业方向等信息的显示
    console.log('更新页面显示:', data);
}

// 初始化个人资料页面
function initializeProfile() {
    // 标签页切换已经通过事件监听器设置
}

// 切换标签页
function switchTab(tabName) {
    const tabContents = document.querySelectorAll('.tab-content');
    
    tabContents.forEach(content => {
        content.classList.add('hidden');
    });
    
    const targetTab = document.getElementById(tabName + '-tab');
    if (targetTab) {
        targetTab.classList.remove('hidden');
        
        // 标签页内容动画
        anime({
            targets: targetTab,
            opacity: [0, 1],
            translateY: [20, 0],
            duration: 500,
            easing: 'easeOutQuart'
        });
    }
}

// 更新标签页按钮状态
function updateTabButtons(activeButton) {
    const tabBtns = document.querySelectorAll('.tab-btn');
    
    tabBtns.forEach(btn => {
        btn.classList.remove('tab-active');
        btn.classList.add('bg-gray-100', 'text-gray-700', 'hover:bg-gray-200');
    });
    
    activeButton.classList.add('tab-active');
    activeButton.classList.remove('bg-gray-100', 'text-gray-700', 'hover:bg-gray-200');
}

// 文件上传相关函数
function handleDragOver(e) {
    e.preventDefault();
    e.currentTarget.classList.add('dragover');
}

function handleDragLeave(e) {
    e.preventDefault();
    e.currentTarget.classList.remove('dragover');
}

function handleDrop(e) {
    e.preventDefault();
    e.currentTarget.classList.remove('dragover');
    
    const files = e.dataTransfer.files;
    handleFiles(files);
}

function handleFileSelect(e) {
    const files = e.target.files;
    handleFiles(files);
}

function handleFiles(files) {
    Array.from(files).forEach(file => {
        console.log('上传文件:', file.name);
        // 这里可以添加实际的文件上传逻辑
        showNotification(`文件 "${file.name}" 上传成功！`, 'success');
    });
}

// 表单提交处理（仅用于有 data-validate 属性的表单）
function handleFormSubmit(e) {
    const form = e.target;
    
    // 检查是否是登录表单，如果是则不拦截，让其正常提交
    const isLoginForm = form.action && (form.action.includes('/login') || form.classList.contains('login-form'));
    
    if (isLoginForm) {
        // 登录表单，不拦截，让其正常提交
        return true;
    }
    
    // 其他表单，阻止默认提交并处理
    e.preventDefault();
    
    const formData = new FormData(form);
    console.log('表单数据:', Object.fromEntries(formData));
    
    // 模拟提交成功（对于有 data-validate 的表单）
    showNotification('表单提交成功！', 'success');
}

// 显示通知
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `fixed top-20 right-4 z-50 p-4 rounded-lg shadow-lg max-w-sm ${
        type === 'success' ? 'bg-green-500 text-white' :
        type === 'error' ? 'bg-red-500 text-white' :
        'bg-blue-500 text-white'
    }`;
    notification.textContent = message;
    notification.style.opacity = '0';
    notification.style.transform = 'translateX(300px)';
    notification.style.transition = 'all 0.3s ease';
    
    document.body.appendChild(notification);
    
    // 使用动画库（如果可用）或原生动画
    if (typeof anime !== 'undefined') {
        // 使用 anime.js 动画
        anime({
            targets: notification,
            translateX: [300, 0],
            opacity: [0, 1],
            duration: 300,
            easing: 'easeOutQuart'
        });
        
        // 3秒后自动消失
        setTimeout(() => {
            anime({
                targets: notification,
                translateX: [0, 300],
                opacity: [1, 0],
                duration: 300,
                easing: 'easeInQuart',
                complete: function() {
                    if (notification.parentNode) {
                        document.body.removeChild(notification);
                    }
                }
            });
        }, 3000);
    } else {
        // 使用原生 CSS 动画
        setTimeout(() => {
            notification.style.opacity = '1';
            notification.style.transform = 'translateX(0)';
        }, 10);
        
        // 3秒后自动消失
        setTimeout(() => {
            notification.style.opacity = '0';
            notification.style.transform = 'translateX(300px)';
            setTimeout(() => {
                if (notification.parentNode) {
                    document.body.removeChild(notification);
                }
            }, 300);
        }, 3000);
    }
}

// 工具函数
function getStatusText(status) {
    const statusMap = {
        'active': '进行中',
        'pending': '报名中',
        'completed': '已结束',
        'closed': '已截止'
    };
    return statusMap[status] || status;
}

function getTypeText(type) {
    const typeMap = {
        'academic': '学术成果',
        'competition': '竞赛获奖',
        'project': '项目成果',
        'certification': '技能认证'
    };
    return typeMap[type] || type;
}

// 响应式处理
window.addEventListener('resize', function() {
    // 重新调整图表大小
    const charts = document.querySelectorAll('[id$="-chart"]');
    charts.forEach(chartElement => {
        const chart = echarts.getInstanceByDom(chartElement);
        if (chart) {
            chart.resize();
        }
    });
});

// 滚动动画
window.addEventListener('scroll', function() {
    const cards = document.querySelectorAll('.card-hover');
    
    cards.forEach(card => {
        const rect = card.getBoundingClientRect();
        const isVisible = rect.top < window.innerHeight && rect.bottom > 0;
        
        if (isVisible && !card.dataset.animated) {
            card.dataset.animated = 'true';
            
            anime({
                targets: card,
                opacity: [0.5, 1],
                translateY: [20, 0],
                duration: 600,
                easing: 'easeOutQuart'
            });
        }
    });
});