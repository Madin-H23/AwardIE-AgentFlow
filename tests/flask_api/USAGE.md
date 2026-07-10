# Flask API 测试框架使用指南

## 快速开始

### 1. 准备工作

确保 Flask 服务器正在运行：
```bash
python run.py
```

### 2. 运行测试

```bash
# 列出所有测试用例
python tests/flask_api/run_tests.py --list

# 运行所有测试
python tests/flask_api/run_tests.py

# 只运行 P0 优先级（核心业务流程）
python tests/flask_api/run_tests.py --priority P0

# 运行指定测试用例
python tests/flask_api/run_tests.py --scenario TC_001

# 详细输出模式
python tests/flask_api/run_tests.py --verbose
```

### 3. 查看报告

测试完成后，报告将保存在 `tests/flask_api/reports/` 目录：

- **test_report.md**: 测试执行报告
- **bug_list.md**: BUG清单（Markdown格式，便于AI分析）

## 测试框架结构

```
tests/flask_api/
├── fixtures/                    # 测试配置文件
│   ├── test_data.yaml          # 测试样本数据（文件、预期结果）
│   └── test_cases.yaml         # 测试用例定义（步骤、断言）
├── utils/                       # 测试工具
│   ├── api_client.py           # API客户端（模拟用户操作）
│   ├── assertions.py           # 断言工具（生成BUG报告）
│   └── test_runner.py          # 测试执行器（核心引擎）
├── reports/                     # 测试报告输出
│   ├── test_report.md          # 测试报告
│   └── bug_list.md             # BUG清单
├── run_tests.py                # 测试执行入口
└── README.md                   # 本文档
```

## 测试数据管理

### 添加新的测试样本

编辑 `fixtures/test_data.yaml`：

```yaml
test_samples:
  - id: "sample_010"
    file_path: "images/测试图片/奖状/新奖状.jpg"
    type: "award"
    has_template: true
    expected_validation: "pass"
    key_fields:
      competition_name: "竞赛名称"
      award_level: "奖项等级"
    cover_scenarios:
      - "award_import"
      - "student_view"
```

### 添加新的测试用例

编辑 `fixtures/test_cases.yaml`：

```yaml
test_scenarios:
  - id: "TC_009"
    name: "新测试用例名称"
    description: "测试描述"
    priority: "P0"
    samples: ["sample_010"]
    category: "award_import"

    steps:
      - action: "login"
        user: "admin_1"
        api: "POST /login"
        assertions:
          - "status_code == 302"

      - action: "get_page"
        api: "GET /admin/dashboard"
        assertions:
          - "status_code == 200"
```

## 测试用例设计指南

### 优先级划分

- **P0**: 核心业务流程（奖状导入、审核、查看等）
- **P1**: 重要功能（专利、软著导入等）
- **P2**: 边缘情况、辅助功能

### 测试步骤类型

#### 登录相关
```yaml
- action: "login"
  user: "admin_1"  # 对应 test_data.yaml 中的 test_users
  api: "POST /login"
```

#### 页面访问
```yaml
- action: "get_page"
  api: "GET /admin/awards"
  assertions:
    - "status_code == 200"
```

#### 文件上传
```yaml
- action: "upload_files"
  api: "POST /admin/awards/import"
  files: ["sample_001"]  # 引用 test_samples
  params:
    action: "upload"
  capture:
    pending_ids: "response['pending_ids']"  # 捕获变量供后续使用
```

#### 提交审核
```yaml
- action: "batch_submit"
  api: "POST /admin/awards/import"
  params:
    action: "submit"
    pending_ids: "${pending_ids}"  # 使用捕获的变量
```

#### 审核通过
```yaml
- action: "approve"
  api: "POST /admin/achievement-review/${pending_id}/approve"
  capture:
    award_id: "response['award_id']"
```

### 断言类型

#### HTTP状态码断言
```yaml
assertions:
  - "status_code == 200"
```

#### 响应字段断言
```yaml
assertions:
  - "response['success'] == True"
  - "response['uploaded_count'] >= 1"
```

#### Session断言
```yaml
assertions:
  - "session['user_type'] == 'admin'"
```

#### 条件断言
```yaml
assertions:
  - "has_extract_result == True"
  - "award_count > 0"
```

## BUG清单分析

### BUG清单格式

每个BUG包含以下信息：

- **bug_id**: 唯一标识（BUG-001, BUG-002...）
- **test_case_id**: 关联的测试用例
- **timestamp**: 发现时间
- **severity**: 严重程度（Critical/High/Medium/Low）
- **title**: BUG标题
- **description**: 错误描述
- **step**: 发生错误的步骤
- **api**: 相关的API
- **test_data**: 测试数据
- **expected**: 预期行为
- **actual**: 实际行为

### 严重程度说明

| 严重程度 | 说明 | 示例 |
|----------|------|------|
| Critical | 导致系统无法使用 | 登录失败、服务器崩溃 |
| High | 影响核心功能 | 奖状导入失败、审核流程中断 |
| Medium | 功能部分受影响 | 显示错误、验证逻辑问题 |
| Low | 不影响使用的小问题 | 文案错误、UI问题 |

### 使用BUG清单定位问题

1. **根据test_case_id定位**：
   找到对应的测试用例，了解测试场景

2. **根据step定位**：
   确定是哪个步骤失败

3. **根据api定位**：
   找到对应的Flask路由函数

4. **根据test_data复现**：
   使用相同的测试数据重现问题

5. **根据expected/actual分析**：
   理解预期与实际的差异

## 扩展测试框架

### 添加新的动作类型

在 `utils/test_runner.py` 的 `_execute_step` 方法中添加：

```python
elif action == 'your_new_action':
    self._action_your_new_action(step, context)
```

然后实现对应的方法：

```python
def _action_your_new_action(self, step: Dict, context: AssertionContext):
    """实现新的动作逻辑"""
    # 你的代码
    pass
```

### 添加新的断言类型

在 `utils/test_runner.py` 的 `_evaluate_assertion` 方法中添加解析逻辑。

## 测试最佳实践

### 1. 测试用例设计原则

- **单一职责**: 每个测试用例验证一个核心业务流程
- **独立性**: 测试用例之间相互独立
- **可重复**: 测试用例可以重复执行
- **数据驱动**: 测试数据与用例分离

### 2. 测试数据复用

一个测试样本可以用于多个测试用例：

```yaml
# sample_001 可以用于
cover_scenarios:
  - "award_import"      # 导入流程
  - "student_view"      # 学生查看
  - "visibility_test"   # 可见性测试
```

### 3. 变量捕获与传递

使用 `capture` 字段捕获响应中的变量，后续步骤使用 `${var_name}` 引用：

```yaml
# 步骤1: 上传文件，捕获 pending_id
- action: "upload_files"
  capture:
    pending_ids: "response['pending_ids']"

# 步骤2: 使用捕获的 pending_id
- action: "approve"
  api: "POST /admin/achievement-review/${pending_ids[0]}/approve"
```

### 4. 复杂断言处理

对于复杂的断言，可以在步骤中添加多个断言：

```yaml
assertions:
  - "status_code == 200"
  - "response['success'] == True"
  - "response['uploaded_count'] >= 1"
  - "len(response['pending_ids']) > 0"
```

## 常见问题

### Q1: 测试运行时提示"Flask 服务器未运行"

**A**: 确保先启动Flask服务器：
```bash
python run.py
```

### Q2: 测试数据文件找不到

**A**: 检查 `test_data.yaml` 中的路径是否正确，相对于项目根目录。

### Q3: 断言表达式解析失败

**A**: 简化断言表达式，或扩展 `test_runner.py` 中的解析逻辑。

### Q4: 如何调试测试用例

**A**:
1. 使用 `--scenario` 参数运行单个测试用例
2. 查看 `reports/test_run.log` 日志文件
3. 使用 `--verbose` 模式获取详细输出

## 进阶功能

### 并行测试执行

修改 `test_cases.yaml` 中的 `execution_config`：

```yaml
execution_config:
  parallel: true  # 启用并行执行
  max_workers: 4  # 最大并行数
```

### 数据库备份与恢复

```yaml
execution_config:
  database_backup: true  # 测试前自动备份数据库
  backup_dir: "database/backup"
```

### 失败截图

```yaml
execution_config:
  screenshot_on_fail: true  # 失败时自动截图（需要Selenium）
  screenshot_dir: "tests/flask_api/screenshots"
```

## 更新日志

### v1.0.0 (2026-01-24)
- 初始版本
- 支持基本的API测试
- 数据驱动的测试框架
- BUG清单自动生成
- 测试报告导出
