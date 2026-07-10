# Flask API 业务流程测试框架

## 设计理念

1. **数据驱动**：测试用例与数据分离，通过YAML/JSON配置
2. **业务流程优先**：从前端用户角度验证完整业务流程
3. **复用性强**：一个测试样本可以覆盖多个API和功能点
4. **自动化**：模拟用户操作，自动化执行业务流程
5. **可扩展**：模块化设计，易于添加新的测试场景
6. **可追溯**：详细记录错误信息，生成BUG清单

## 目录结构

```
tests/flask_api/
├── fixtures/              # 测试数据配置
│   ├── test_cases.yaml   # 测试用例定义
│   ├── test_data.yaml    # 测试样本数据
│   └── expected_results.yaml # 预期结果
├── scenarios/            # 测试场景实现
│   ├── __init__.py
│   ├── auth_flow.py      # 认证流程
│   ├── award_flow.py     # 奖状业务流程
│   ├── patent_flow.py    # 专利业务流程
│   └── review_flow.py    # 审核业务流程
├── utils/                # 测试工具
│   ├── __init__.py
│   ├── api_client.py     # API客户端封装
│   ├── assertions.py     # 断言工具
│   └── reporters.py      # 报告生成器
├── reports/              # 测试报告输出
│   └── bug_list.md       # BUG清单
└── run_tests.py          # 测试执行入口
```

## 核心业务流程

### 流程1: 奖状导入业务流程
```
1. 管理员登录
2. 访问批量导入页面
3. 上传图片文件
4. 系统自动OCR+LLM抽取
5. 预览抽取结果
6. 修改错误字段
7. 重新验证
8. 批量提交到主数据库
9. 学生/教师登录查看成果
```

### 流程2: 审核业务流程
```
1. 学生/教师上传文件
2. 系统自动抽取
3. 用户提交审核
4. 管理员查看待审核列表
5. 管理员审核通过/拒绝
6. 查看审核日志
```

### 流程3: 成果查看业务流程
```
1. 学生登录
2. 查看个人成果列表
3. 验证可见性（只能看到自己的）
4. 教师登录
5. 查看指导成果列表
6. 验证可见性（只能看到自己指导的）
```

## 测试数据管理

### 测试样本分类

**按业务类型**：
- 奖状类（有模板）
- 奖状类（无模板）
- 专利类
- 软著类
- 其他文件类

**按验证状态**：
- 验证通过
- 验证失败（需修正）
- 边界情况

**按覆盖功能**：
- 上传→审核→入库（完整流程）
- 上传→删除（分支流程）
- 修改→重新验证（分支流程）

## 快速开始

```bash
# 执行所有测试
python tests/flask_api/run_tests.py

# 执行特定场景
python tests/flask_api/run_tests.py --scenario award_import

# 生成详细报告
python tests/flask_api/run_tests.py --verbose

# 只执行快速测试
python tests/flask_api/run_tests.py --fast
```

## BUG清单格式

```markdown
### BUG-001: 奖状导入后学生无法查看

**发现时间**: 2026-01-24 14:30
**严重程度**: 高
**状态**: 待修复

**复现步骤**:
1. 管理员导入奖状...
2. 学生登录...

**错误信息**:
```
AssertionError: 预期学生能看到奖状ID 123，实际未找到
```

**相关API**:
- POST /admin/awards/import
- GET /student/dashboard

**预期行为**: 学生应该能看到导入的奖状
**实际行为**: 奖状未显示在学生列表中

**测试数据**:
- 文件: images/测试图片/奖状/2025蓝桥杯...
- 学生ID: 2021001

**相关日志**:
```
[ERROR] student_association refresh failed: ...
```
```
