/**
 * 奖状模板管理 JavaScript
 */

(function () {
    'use strict';

    // 等待DOM加载完成
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    function init() {
        initRefreshButtons();
        initDeleteTemplate();
        initCreateTemplate();
        initUpdateFields();
        initGeneratePrompt();
        initTestTemplate();
        initSubmitTemplate();
        initFieldTypeSelects();
        initLanguageToggle();
    }

    /**
     * 初始化字段类型选择事件
     */
    function initFieldTypeSelects() {
        const typeSelects = document.querySelectorAll('.field-type-select');
        typeSelects.forEach(select => {
            select.addEventListener('change', function () {
                const field = this.getAttribute('data-field');
                const valueInput = document.querySelector(`.default-value-input[data-field="${field}"]`);
                if (valueInput) {
                    if (this.value === 'default') {
                        valueInput.disabled = false;
                        valueInput.placeholder = '请输入默认值';
                    } else {
                        valueInput.disabled = true;
                        valueInput.placeholder = '选择"默认"时填写';
                        valueInput.value = '';
                    }
                }
            });
        });
    }

    /**
     * 初始化语言切换事件
     */
    function initLanguageToggle() {
        const langZhRadio = document.getElementById('lang_zh');
        const langEnRadio = document.getElementById('lang_en');
        const translateOption = document.getElementById('translateOption');

        if (langZhRadio && langEnRadio && translateOption) {
            const handleLanguageChange = function () {
                if (langEnRadio.checked) {
                    translateOption.style.display = 'block';
                } else {
                    translateOption.style.display = 'none';
                }
            };

            langZhRadio.addEventListener('change', handleLanguageChange);
            langEnRadio.addEventListener('change', handleLanguageChange);
        }
    }

    /**
     * 刷新模板按钮
     */
    function initRefreshButtons() {
        const refreshBtn = document.getElementById('refreshTemplatesBtn');
        const forceRefreshBtn = document.getElementById('forceRefreshTemplatesBtn');

        if (refreshBtn) {
            refreshBtn.addEventListener('click', function () {
                if (confirm('确定要刷新模板吗？这将跳过手工编辑的模板。')) {
                    refreshTemplates(false);
                }
            });
        }

        if (forceRefreshBtn) {
            forceRefreshBtn.addEventListener('click', function () {
                if (confirm('⚠️ 确定要强制重置所有模板吗？这将删除所有模板（包括手工编辑的）并重新创建！')) {
                    refreshTemplates(true);
                }
            });
        }
    }

    function refreshTemplates(force) {
        const url = force ? '/admin/templates/force-refresh' : '/admin/templates/refresh';
        const btn = force ? document.getElementById('forceRefreshTemplatesBtn') : document.getElementById('refreshTemplatesBtn');

        if (btn) {
            btn.disabled = true;
            btn.textContent = '刷新中...';
        }

        fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('刷新成功！\n' +
                        '新建模板: ' + data.stats.created + ' 个\n' +
                        '跳过: ' + data.stats.skipped + ' 个\n' +
                        '错误: ' + data.stats.errors + ' 个');
                    window.location.reload();
                } else {
                    alert('刷新失败: ' + data.message);
                    if (btn) {
                        btn.disabled = false;
                        btn.textContent = force ? '强制重置' : '模板刷新';
                    }
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('刷新失败: ' + error.message);
                if (btn) {
                    btn.disabled = false;
                    btn.textContent = force ? '强制重置' : '模板刷新';
                }
            });
    }

    /**
     * 删除模板
     */
    function initDeleteTemplate() {
        const deleteBtn = document.getElementById('deleteTemplateBtn');
        if (deleteBtn) {
            deleteBtn.addEventListener('click', function () {
                const templateId = this.getAttribute('data-template-id');
                if (confirm('⚠️ 确认删除此模板？此操作不可恢复！')) {
                    deleteTemplate(templateId);
                }
            });
        }
    }

    function deleteTemplate(templateId) {
        fetch('/admin/templates/' + templateId + '/delete', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('删除成功');
                    window.location.href = '/admin/templates?tab=list';
                } else {
                    alert('删除失败: ' + data.message);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('删除失败: ' + error.message);
            });
    }

    /**
     * 创建模板：抽取与提交由 create tab 内联脚本处理（上传图片 → extract-for-create → 编辑样本值 → multipart create）
     */
    function initCreateTemplate() {
        // 创建流程在 admin/templates/tabs/create.html 的脚本中实现
    }

    /**
     * 更新字段配置
     */
    function initUpdateFields() {
        const updateBtn = document.getElementById('updateFieldsBtn');
        if (updateBtn) {
            updateBtn.addEventListener('click', function () {
                const templateId = this.getAttribute('data-template-id');
                updateFields(templateId);
            });
        }
    }

    function updateFields(templateId) {
        // 收集字段管理数据
        const fieldsData = {};
        const rows = document.querySelectorAll('#fieldManagementTable tbody tr');

        rows.forEach(row => {
            const fieldName = row.getAttribute('data-field-name');
            if (fieldName) {
                const description = row.querySelector('.field-description').value;
                const sampleValue = row.querySelector('.field-sample-value').value;
                const type = row.querySelector('.field-type').value;

                fieldsData[fieldName] = {
                    description: description,
                    sample_value: sampleValue,
                    type: type
                };
            }
        });

        // 构建 default_fields 和 llm_fields
        const defaultFields = {};
        const llmFields = {};
        const sampleExtracted = {};

        Object.keys(fieldsData).forEach(fieldName => {
            const fieldData = fieldsData[fieldName];
            sampleExtracted[fieldName] = fieldData.sample_value || null;

            if (fieldData.type === '默认') {
                defaultFields[fieldName] = fieldData.sample_value || '';
            } else if (fieldData.type === '抽取') {
                llmFields[fieldName] = fieldData.description || '';
            }
        });

        const data = {
            default_fields: defaultFields,
            llm_fields: llmFields,
            sample_extracted: sampleExtracted
        };

        fetch('/admin/templates/' + templateId + '/update', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('字段配置已更新');
                    window.location.reload();
                } else {
                    alert('更新失败: ' + data.message);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('更新失败: ' + error.message);
            });
    }

    /**
     * 生成提示词
     */
    function initGeneratePrompt() {
        const generateBtn = document.getElementById('generatePromptBtn');
        if (generateBtn) {
            generateBtn.addEventListener('click', function () {
                const templateId = this.getAttribute('data-template-id');
                generatePrompt(templateId);
            });
        }
    }

    function generatePrompt(templateId) {
        const generateBtn = document.getElementById('generatePromptBtn');
        const promptDiv = document.getElementById('generatedPrompt');

        if (generateBtn) {
            generateBtn.disabled = true;
            generateBtn.textContent = '生成中...';
        }

        fetch('/admin/templates/' + templateId + '/generate-prompt', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    if (promptDiv) {
                        promptDiv.textContent = data.prompt;
                    }
                    alert('提示词已生成');
                } else {
                    alert('生成提示词失败: ' + data.message);
                }

                if (generateBtn) {
                    generateBtn.disabled = false;
                    generateBtn.textContent = '🔧 生成专用模板提示词';
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('生成提示词失败: ' + error.message);
                if (generateBtn) {
                    generateBtn.disabled = false;
                    generateBtn.textContent = '🔧 生成专用模板提示词';
                }
            });
    }

    /**
     * 测试模板
     */
    function initTestTemplate() {
        const testBtn = document.getElementById('testTemplateBtn');
        const fileInput = document.getElementById('testImageUpload');

        if (testBtn && fileInput) {
            testBtn.addEventListener('click', function () {
                if (!fileInput.files || !fileInput.files.length) {
                    alert('请先选择图片文件');
                    fileInput.click();
                    return;
                }

                const templateId = this.getAttribute('data-template-id');
                if (!templateId) {
                    alert('无法确定模板ID');
                    return;
                }

                const formData = new FormData();
                formData.append('file', fileInput.files[0]);

                testBtn.disabled = true;
                testBtn.textContent = '测试中...';

                fetch('/admin/templates/' + templateId + '/test', {
                    method: 'POST',
                    body: formData
                })
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            displayTestResults(data);
                        } else {
                            alert('测试失败: ' + data.message);
                        }

                        testBtn.disabled = false;
                        testBtn.textContent = '🧪 开始测试';
                    })
                    .catch(error => {
                        console.error('Error:', error);
                        alert('测试失败: ' + error.message);
                        testBtn.disabled = false;
                        testBtn.textContent = '🧪 开始测试';
                    });
            });
        }
    }

    function displayTestResults(data) {
        const resultsDiv = document.getElementById('testResults');
        const ocrText = document.getElementById('testOcrText');
        const llmResult = document.getElementById('testLlmResult');
        const completedResult = document.getElementById('testCompletedResult');

        if (resultsDiv) {
            resultsDiv.style.display = 'block';
        }

        if (ocrText) {
            ocrText.value = data.ocr_text || '';
        }

        if (llmResult) {
            llmResult.textContent = data.extracted_result || data.llm_result || '';
        }

        if (completedResult) {
            completedResult.textContent = JSON.stringify(data.completed_result || data.extracted_dict || {}, null, 2);
        }

        // 滚动到结果区域
        if (resultsDiv) {
            resultsDiv.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    }

    /**
     * 提交模板修改
     */
    function initSubmitTemplate() {
        const submitBtn = document.getElementById('submitTemplateBtn');
        if (submitBtn) {
            submitBtn.addEventListener('click', function () {
                const templateId = this.getAttribute('data-template-id');
                submitTemplate(templateId);
            });
        }
    }

    function submitTemplate(templateId) {
        const submitBtn = document.getElementById('submitTemplateBtn');
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.textContent = '提交中...';
        }

        // 1. 收集关键词
        const keywordsInput = document.getElementById('keywordsInput');
        const keywords = keywordsInput ? keywordsInput.value.split('\n').map(k => k.trim()).filter(k => k) : [];

        // 2. 收集语言设置
        const langZhRadio = document.getElementById('lang_zh');
        const langEnRadio = document.getElementById('lang_en');
        const translateCheck = document.getElementById('needTranslateCheck');
        const language = langEnRadio && langEnRadio.checked ? 'en' : 'zh';
        const needTranslate = translateCheck ? translateCheck.checked : false;

        // 3. 收集字数范围
        const minLengthInput = document.getElementById('minLengthInput');
        const maxLengthInput = document.getElementById('maxLengthInput');
        const minLength = minLengthInput ? parseInt(minLengthInput.value) || 0 : 0;
        const maxLength = maxLengthInput ? parseInt(maxLengthInput.value) || 0 : 0;

        // 4. 收集字段配置
        const typeSelects = document.querySelectorAll('.field-type-select');
        const llmInputs = document.querySelectorAll('.llm-field-input');
        const defaultInputs = document.querySelectorAll('.default-value-input');
        const sampleInputs = document.querySelectorAll('.sample-value-input');

        const fieldTypes = {};
        typeSelects.forEach(select => {
            const field = select.getAttribute('data-field');
            fieldTypes[field] = select.value;
        });

        const llmFields = {};
        const defaultFields = {};
        const sampleExtracted = {};

        llmInputs.forEach(input => {
            const field = input.getAttribute('data-field');
            const fieldType = fieldTypes[field];
            const description = input.value.trim();
            if (fieldType === 'extract' && description) {
                llmFields[field] = description;
            }
        });

        defaultInputs.forEach(input => {
            const field = input.getAttribute('data-field');
            const fieldType = fieldTypes[field];
            const value = input.value.trim();
            if (fieldType === 'default' && value) {
                defaultFields[field] = value;
            }
        });

        sampleInputs.forEach(input => {
            const field = input.getAttribute('data-field');
            const value = input.value.trim();
            if (value) {
                sampleExtracted[field] = value;
            }
        });

        // 5. 收集授予角色
        const grantedRoleRadio = document.querySelector('input[name="granted_role"]:checked');
        const grantedRole = grantedRoleRadio ? grantedRoleRadio.value : null;

        // 更新default_fields中的granted_role
        if (grantedRole) {
            defaultFields['granted_role'] = grantedRole;
        }

        // 5.5. 保留原有的 competition_name 和 issuer（这两个字段不在字段管理表格中）
        // submitBtn 已在函数开头声明，直接使用
        if (submitBtn) {
            const originalCompetitionName = submitBtn.getAttribute('data-original-competition-name');
            const originalIssuer = submitBtn.getAttribute('data-original-issuer');

            // 如果原有值存在且default_fields中没有，则保留
            if (originalCompetitionName && originalCompetitionName.trim() !== '') {
                if (!defaultFields['competition_name']) {
                    defaultFields['competition_name'] = originalCompetitionName.trim();
                }
            }
            if (originalIssuer && originalIssuer.trim() !== '') {
                if (!defaultFields['issuer']) {
                    defaultFields['issuer'] = originalIssuer.trim();
                }
            }
        }

        // 6. 保存模板数据
        fetch('/admin/templates/' + templateId + '/update', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                keywords: keywords,
                language: language,
                need_translate: needTranslate,
                min_length: minLength,
                max_length: maxLength,
                llm_fields: llmFields,
                default_fields: defaultFields,
                sample_extracted: JSON.stringify(sampleExtracted)
            })
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('所有修改已保存');
                    window.location.reload();
                } else {
                    throw new Error(data.message || '保存模板失败');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('保存失败: ' + error.message);
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.textContent = '💾 提交修改';
                }
            });
    }
})();

