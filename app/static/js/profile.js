/**
 * 个人设置页面JavaScript
 * 处理个人信息的获取、显示和更新
 */

// 技能标签常用列表
const COMMON_SKILLS = [
    'Python', 'JavaScript', 'Java', 'C++', 'C#',
    '机器学习', '深度学习', '数据分析', '数据挖掘',
    'Web开发', '前端开发', '后端开发', '全栈开发',
    '数据库', '算法', '数据结构', '软件工程',
    '人工智能', '计算机视觉', '自然语言处理'
];

// 技能标签颜色列表
const SKILL_TAG_COLORS = [
    'bg-blue-100 text-blue-800',
    'bg-green-100 text-green-800',
    'bg-purple-100 text-purple-800',
    'bg-yellow-100 text-yellow-800',
    'bg-pink-100 text-pink-800',
    'bg-indigo-100 text-indigo-800',
    'bg-red-100 text-red-800',
    'bg-teal-100 text-teal-800'
];

// 当前用户类型
let userType = '';

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    // 从URL判断用户类型
    if (window.location.pathname.includes('/student/')) {
        userType = 'student';
    } else if (window.location.pathname.includes('/teacher/')) {
        userType = 'teacher';
    }
    
    initializeProfilePage();
});

/**
 * 初始化个人设置页面
 */
async function initializeProfilePage() {
    try {
        // 获取用户信息
        const response = await fetch(`/${userType}/profile/data`);
        const result = await response.json();
        
        if (result.success && result.data) {
            populateProfileForm(result.data);
        } else {
            console.error('获取用户信息失败:', result.message);
            showNotification('获取用户信息失败', 'error');
        }
    } catch (error) {
        console.error('获取用户信息出错:', error);
        showNotification('获取用户信息出错', 'error');
    }
    
    // 设置表单提交处理
    setupFormSubmit();
    
    // 设置技能标签处理
    setupSkillsInput();
    
    // 设置密码修改表单处理
    setupPasswordForm();
    
    // 检查URL参数是否需要切换到特定标签页
    handleUrlTab();
}

/**
 * 检查URL参数并切换标签页
 */
function handleUrlTab() {
    const urlParams = new URLSearchParams(window.location.search);
    const tab = urlParams.get('tab');
    if (tab) {
        // 查找对应的标签按钮
        const tabBtn = document.querySelector(`.tab-btn[data-tab="${tab}"]`);
        if (tabBtn) {
            // 模拟点击切换
            tabBtn.click();
        }
    }
}

/**
 * 填充表单数据
 */
function populateProfileForm(data) {
    if (userType === 'student') {
        // 学生字段（部分只读）
        document.getElementById('form-name').value = data.name || '';
        document.getElementById('form-student-id').value = data.student_id || '';
        document.getElementById('form-major').value = data.major || '';
        document.getElementById('form-grade').value = data.grade || '';
        document.getElementById('form-qq').value = data.qq || '';
        document.getElementById('form-phone').value = data.phone || '';
        
        // 更新左侧卡片信息
        updateStudentCard(data);
    } else {
        // 教师字段（可修改）
        document.getElementById('form-name').value = data.name || '';
        document.getElementById('form-teacher-id').value = data.teacher_id || '';
        document.getElementById('form-department').value = data.department || '';
        document.getElementById('form-qq').value = data.qq || '';
        document.getElementById('form-phone').value = data.phone || '';
        
        // 更新左侧卡片信息
        updateTeacherCard(data);
    }
    
    // 填充技能标签（即使为空也要清空容器）
    if (data.skills && Array.isArray(data.skills) && data.skills.length > 0) {
        displaySkills(data.skills);
    } else {
        // 如果没有技能数据，清空容器
        const skillsContainer = document.getElementById('skills-container');
        if (skillsContainer) {
            skillsContainer.innerHTML = '';
        }
    }
}

/**
 * 更新学生卡片信息
 */
function updateStudentCard(data) {
    const nameEl = document.getElementById('profile-name');
    if (nameEl) nameEl.textContent = data.name || '学生';
    
    const majorEl = document.getElementById('profile-major');
    if (majorEl) majorEl.textContent = data.major || '计算机科学与技术专业';
    
    const gradeIdEl = document.getElementById('profile-grade-id');
    if (gradeIdEl && data.grade && data.student_id) {
        gradeIdEl.textContent = `${data.grade} · 学号：${data.student_id}`;
    }
    
    const qqEl = document.getElementById('profile-qq');
    if (qqEl) qqEl.textContent = data.qq || '-';
    
    const phoneEl = document.getElementById('profile-phone');
    if (phoneEl) phoneEl.textContent = data.phone || '-';
}

/**
 * 更新教师卡片信息
 */
function updateTeacherCard(data) {
    const nameEl = document.getElementById('profile-name');
    if (nameEl) nameEl.textContent = data.name || '教师';
    
    const departmentEl = document.getElementById('profile-department');
    if (departmentEl) departmentEl.textContent = data.department || '计算机科学系';
    
    const teacherIdEl = document.getElementById('profile-teacher-id');
    if (teacherIdEl && data.teacher_id) {
        teacherIdEl.textContent = `工号：${data.teacher_id}`;
    }
    
    const qqEl = document.getElementById('profile-qq');
    if (qqEl) qqEl.textContent = data.qq || '-';
    
    const phoneEl = document.getElementById('profile-phone');
    if (phoneEl) phoneEl.textContent = data.phone || '-';
}

/**
 * 设置表单提交处理
 */
function setupFormSubmit() {
    const form = document.getElementById('profile-form');
    if (form) {
        form.addEventListener('submit', async function(e) {
            e.preventDefault();
            e.stopPropagation();
            console.log('表单提交事件触发');
            await submitProfileUpdate();
            return false;
        });
        
        // 也检查保存按钮
        const submitBtn = form.querySelector('button[type="submit"]');
        if (submitBtn) {
            console.log('找到提交按钮');
            // 确保按钮点击也会触发提交
            submitBtn.addEventListener('click', function(e) {
                e.preventDefault();
                form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
            });
        } else {
            console.error('未找到提交按钮');
        }
    } else {
        console.error('未找到表单元素 #profile-form');
    }
}

/**
 * 提交个人信息更新
 */
async function submitProfileUpdate() {
    try {
        // 收集表单数据
        const formData = {};
        
        // 学生和教师共同字段
        const qqValue = document.getElementById('form-qq')?.value || '';
        const phoneValue = document.getElementById('form-phone')?.value || '';
        const skillsArray = getSkillsArray();
        
        // 只在有值时才添加到formData（允许空字符串更新）
        formData.qq = qqValue;
        formData.phone = phoneValue;
        formData.skills = skillsArray;
        
        // 教师可以修改更多字段
        if (userType === 'teacher') {
            const nameValue = document.getElementById('form-name')?.value?.trim() || '';
            const teacherIdValue = document.getElementById('form-teacher-id')?.value?.trim() || '';
            const departmentValue = document.getElementById('form-department')?.value?.trim() || '';
            
            // 只添加非空字段
            if (nameValue) formData.name = nameValue;
            if (teacherIdValue) formData.teacher_id = teacherIdValue;
            if (departmentValue) formData.department = departmentValue;
        }
        
        console.log('提交的数据:', formData);
        
        // 提交更新
        const response = await fetch(`/${userType}/profile/update`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(formData)
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const result = await response.json();
        
        console.log('服务器响应:', result);
        
        if (result.success) {
            showNotification('个人信息更新成功', 'success');
            // 重新加载数据
            setTimeout(() => {
                initializeProfilePage();
            }, 1000);
        } else {
            showNotification(result.message || '更新失败', 'error');
        }
    } catch (error) {
        console.error('更新个人信息出错:', error);
        showNotification('更新个人信息出错: ' + error.message, 'error');
    }
}

/**
 * 设置密码修改表单处理
 */
function setupPasswordForm() {
    const passwordForm = document.getElementById('password-form');
    if (passwordForm) {
        passwordForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            await submitPasswordChange();
        });
    }
}

/**
 * 提交密码修改
 */
async function submitPasswordChange() {
    const oldPassword = document.getElementById('old-password').value;
    const newPassword = document.getElementById('new-password').value;
    const confirmPassword = document.getElementById('confirm-password').value;
    
    if (newPassword !== confirmPassword) {
        showNotification('两次输入的新密码不一致', 'error');
        return;
    }
    
    if (newPassword.length < 6) {
        showNotification('新密码长度至少为6位', 'error');
        return;
    }
    
    try {
        const response = await fetch(`/${userType}/change_password`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                old_password: oldPassword,
                new_password: newPassword
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showNotification('密码修改成功', 'success');
            document.getElementById('password-form').reset();
            
            // 如果是因为强制修改密码进来的，修改成功后跳转到首页
            if (document.querySelector('.bg-orange-50')) {
                setTimeout(() => {
                    window.location.href = `/${userType}/dashboard`;
                }, 1500);
            }
        } else {
            showNotification(result.message || '密码修改失败', 'error');
        }
    } catch (error) {
        console.error('修改密码出错:', error);
        showNotification('修改密码出错', 'error');
    }
}

/**
 * 设置技能标签输入处理
 */
function setupSkillsInput() {
    const skillInput = document.getElementById('skill-input');
    const skillSelect = document.getElementById('skill-select');
    const skillsContainer = document.getElementById('skills-container');
    
    if (!skillInput || !skillSelect || !skillsContainer) return;
    
    // 下拉框选择处理
    skillSelect.addEventListener('change', function(e) {
        const selectedSkill = e.target.value;
        if (selectedSkill) {
            addSkill(selectedSkill);
            e.target.value = ''; // 重置选择
        }
    });
    
    // 输入框回车处理
    skillInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            const skill = e.target.value.trim();
            if (skill) {
                addSkill(skill);
                e.target.value = '';
            }
        }
    });
}

/**
 * 添加技能标签
 */
function addSkill(skill) {
    if (!skill || !skill.trim()) return;
    
    skill = skill.trim();
    const skillsContainer = document.getElementById('skills-container');
    if (!skillsContainer) {
        console.error('未找到技能标签容器');
        return;
    }
    
    // 检查是否已存在
    const existingSkills = Array.from(skillsContainer.querySelectorAll('span'))
        .map(tag => {
            const clone = tag.cloneNode(true);
            const btn = clone.querySelector('button');
            if (btn) btn.remove();
            return clone.textContent.trim();
        });
    
    if (existingSkills.includes(skill)) {
        showNotification('该技能标签已存在', 'info');
        return;
    }
    
    // 创建标签元素
    const skillTag = document.createElement('span');
    const colorClass = SKILL_TAG_COLORS[existingSkills.length % SKILL_TAG_COLORS.length];
    skillTag.className = `${colorClass} px-3 py-1 rounded-full text-sm cursor-pointer inline-flex items-center gap-1`;
    skillTag.innerHTML = `
        <span>${skill}</span>
        <button type="button" onclick="this.parentElement.remove()" class="text-gray-600 hover:text-red-600 ml-1">
            <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
            </svg>
        </button>
    `;
    
    skillsContainer.appendChild(skillTag);
    console.log('已添加技能标签:', skill);
}

/**
 * 显示技能标签
 */
function displaySkills(skills) {
    const skillsContainer = document.getElementById('skills-container');
    if (!skillsContainer) return;
    
    // 清空现有标签
    skillsContainer.innerHTML = '';
    
    // 直接创建标签元素，不调用addSkill（避免重复检查）
    if (!skills || !Array.isArray(skills) || skills.length === 0) {
        return;
    }
    
    // 去重（防止数据本身有重复）
    const uniqueSkills = [...new Set(skills.map(s => s.trim()).filter(s => s))];
    
    uniqueSkills.forEach((skill, index) => {
        const skillTag = document.createElement('span');
        const colorClass = SKILL_TAG_COLORS[index % SKILL_TAG_COLORS.length];
        skillTag.className = `${colorClass} px-3 py-1 rounded-full text-sm cursor-pointer inline-flex items-center gap-1`;
        skillTag.innerHTML = `
            <span>${skill}</span>
            <button type="button" onclick="this.parentElement.remove()" class="text-gray-600 hover:text-red-600 ml-1">
                <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                </svg>
            </button>
        `;
        skillsContainer.appendChild(skillTag);
    });
    
    console.log('已显示技能标签:', uniqueSkills);
}

/**
 * 获取当前技能标签数组
 */
function getSkillsArray() {
    const skillsContainer = document.getElementById('skills-container');
    if (!skillsContainer) {
        console.warn('未找到技能标签容器');
        return [];
    }
    
    const skills = Array.from(skillsContainer.querySelectorAll('span'))
        .map(tag => {
            // 检查是否有内层span（技能名称）
            const innerSpan = tag.querySelector('span');
            if (innerSpan) {
                return innerSpan.textContent.trim();
            }
            // 如果没有内层span，移除删除按钮后获取文本
            const clone = tag.cloneNode(true);
            const btn = clone.querySelector('button');
            if (btn) btn.remove();
            return clone.textContent.trim();
        })
        .filter(skill => skill && skill.length > 0);
    
    console.log('获取到的技能标签:', skills);
    return skills;
}

/**
 * 编辑字段（点击卡片上的编辑按钮）
 */
function editField(fieldName) {
    const formFieldId = `form-${fieldName}`;
    const formField = document.getElementById(formFieldId);
    if (formField) {
        formField.scrollIntoView({ behavior: 'smooth', block: 'center' });
        formField.focus();
    }
}

/**
 * 编辑头像
 */
function editAvatar() {
    showNotification('头像上传功能开发中...', 'info');
}

/**
 * 显示通知消息（避免与common.js冲突，使用独立的函数名）
 */
function showProfileNotification(message, type = 'info') {
    // 创建通知元素（Tailwind CSS样式）
    const notification = document.createElement('div');
    const bgColor = type === 'error' ? 'bg-red-500' : type === 'success' ? 'bg-green-500' : 'bg-blue-500';
    notification.className = `${bgColor} text-white px-6 py-3 rounded-lg shadow-lg fixed top-20 right-4 z-50 max-w-sm`;
    notification.style.cssText = 'animation: slideIn 0.3s ease-out;';
    notification.innerHTML = `
        <div class="flex items-center justify-between">
            <span>${message}</span>
            <button onclick="this.parentElement.parentElement.remove()" class="ml-4 text-white hover:text-gray-200">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                </svg>
            </button>
        </div>
    `;
    
    document.body.appendChild(notification);
    
    // 3秒后自动移除
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease-out';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// 创建别名以便兼容现有调用
function showNotification(message, type = 'info') {
    showProfileNotification(message, type);
}
