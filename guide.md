# 项目使用指南

## 项目概述

本项目是 AwardIE-AgentFlow（信息抽取与多智能体协作的奖状智能管理系统），包含两个Flask应用：
- **主应用** (端口5001)：业务系统，管理员、教师、学生使用
- **doc_rec应用** (端口5000)：文档识别模块，提供模板管理、抽取功能

---

## 快速启动

### 激活虚拟环境

```
cd D:\code\venv_competition\Scripts
activate

```

因为ollama不支持中文目录导致，所以单独创建虚拟环境



### 1. 安装依赖

```
python -m pip install paddlepaddle-gpu==3.2.0 -i https://www.paddlepaddle.org.cn/packages/stable/cu126/
python -m pip install "paddleocr[all]"
python -m pip install -U pip setuptools
```



```bash
pip install -r requirements.txt
```

### 2. 启动主应用

```bash
# 开发环境
python run.py

# 应用将在 http://localhost:5001 启动
```

### 3. 启动doc_rec应用（可选）

```bash
cd doc_rec
python app/run.py

# 管理后台将在 http://localhost:5000 启动
```

### 4. 默认登录信息

| 角色 | 用户名 | 密码 | 说明 |
|------|--------|------|------|
| 管理员 | admin | Mayy123 | 管理员密码独立设置 |
| 教师 | 工号 | P@ss301 | 默认密码，可在管理后台重置 |
| 学生 | 学号 | P@ss301 | 默认密码，首次登录需修改 |

**注意**：
- 学生首次使用默认密码登录后，系统会强制要求修改密码
- 管理员可在"学生管理"或"教师管理"的编辑页面重置用户密码
- 系统默认密码可在"系统设置 → 通用设置"中查看

---

## 测试套件使用

### 测试套件结构

```
tests/                    # 统一测试目录（项目根目录）
├── core/                 # 核心测试框架
│   ├── test_suite.py    # 从doc_rec迁移的测试套件
│   └── test_runner.py    # 统一测试运行器
├── fixtures/             # 测试数据
│   ├── images/           # 测试图片（从doc_rec迁移）
│   ├── excels/           # 测试Excel（从doc_rec迁移）
│   └── baseline/         # 手动维护的测试基线
├── unit/                 # 单元测试
│   └── detection/        # 检测规则模块测试
├── integration/          # API集成测试
├── ui/                   # 网页操作测试
├── reports/              # 测试报告输出
└── scripts/              # 辅助脚本
    └── run_all_tests.py  # 快速运行所有测试
```

### 运行所有测试

```bash
# 从项目根目录运行
python tests/scripts/run_all_tests.py
```

### 运行特定测试模块

```bash
# 仅运行doc_rec单元测试
cd tests
python core/test_suite.py

# 仅运行API测试
pytest tests/integration/ -v

# 仅运行UI测试
pytest tests/ui/ -v

# 仅运行回归测试
pytest tests/unit/test_regression.py -v
```

### 查看测试报告

```bash
# 报告生成在 tests/reports/test_report_<时间戳>/
# 用浏览器打开
# Windows:
start tests\\reports\\test_report_<最新时间戳>\\index.html
# Mac/Linux:
open tests/reports/test_report_<最新时间戳>/index.html
```

### 回归测试

```bash
# 运行回归测试，对比基线
pytest tests/unit/test_regression.py -v

# 如果有差异，会在控制台显示具体哪些字段发生了变化
```

### 更新测试基线

```bash
# 1. 运行测试并查看HTML报告
python tests/core/test_suite.py

# 2. 人工核对报告中的结果

# 3. 如果结果正确，手动更新基线文件
# 编辑 tests/fixtures/baseline/extraction_baseline.json
# 添加或更新测试用例的预期结果

# 基线格式示例：
{
  "test_蓝桥杯.jpg": {
    "verified": true,
    "verified_by": "你的名字",
    "verified_date": "2025-01-15",
    "expected": {
      "template_type": "award",
      "template_name": "蓝桥杯",
      "key_fields": {
        "winner_name": "陈鸿秋",
        "award_level": "省赛二等奖"
      }
    }
  }
}
```

---

## 开发工作流

### 1. 修改doc_rec模块后

```bash
# 运行完整测试套件
python tests/scripts/run_all_tests.py

# 或仅运行单元测试
cd tests
python core/test_suite.py

# 查看报告，确认无退化
start reports\\test_report_*/index.html
```

### 2. 修改主应用后

```bash
# 运行API和UI测试
pytest tests/integration/ tests/ui/ -v
```

### 3. 提交代码前

```bash
# 运行回归测试，确保没有破坏现有功能
pytest tests/unit/test_regression.py -v
```

---

## 测试基线维护指南

### 什么是测试基线？

测试基线是**人工验证过的标准答案**，用于回归测试对比。

### 如何维护基线？

1. **初次建立基线**
   - 运行测试，查看HTML报告
   - 人工核对每个测试结果
   - 手动编辑`tests/fixtures/baseline/extraction_baseline.json`
   - 添加验证通过的测试用例

2. **日常使用**
   - 修改代码后运行回归测试
   - 如果测试失败，检查是退化还是改进
   - 如果是退化，修复代码
   - 如果是改进，更新基线

3. **更新基线**
   - 人工确认新结果正确
   - 编辑baseline.json，更新expected值
   - 添加verified_by和verified_date
   - 提交baseline.json到版本控制

### 基线文件格式

```json
{
  "_metadata": {
    "version": "1.0",
    "notes": "手动维护的测试基线"
  },
  "文件名.jpg": {
    "verified": true,
    "verified_by": "验证人",
    "verified_date": "2025-01-15",
    "expected": {
      "template_type": "award",
      "key_fields": {
        "winner_name": "正确值"
      }
    }
  }
}
```

---

## 故障排查

### 测试失败

1. **查看详细报告**
   ```bash
   start reports\\test_report_*/index.html
   ```

2. **查看日志**
   ```bash
   # doc_rec日志
   cat doc_rec/document_extract/logs/test_*.log
   ```

3. **检查配置**
   ```bash
   # 查看测试配置
   cat tests/config/default.yaml
   ```

### 应用启动失败

1. **检查端口占用**
   ```bash
   # Windows
   netstat -ano | findstr :5000
   netstat -ano | findstr :5001
   ```

2. **检查数据库**
   ```bash
   # 主数据库
   sqlite3 database/competitions.db ".tables"
   
   # doc_rec数据库
   sqlite3 doc_rec/document_extract/data/validation.db ".tables"
   ```

3. **检查环境变量**
   ```bash
   # 确保API Key已设置
   echo $ZHIPUAI_API_KEY
   ```

---

## 相关文档

- [doc_rec模块文档](doc_rec/README.md)
- [迁移文档](docs/migration_summary.md)
- [实施计划](docs/plans/2025-01-15-test-suite-migration.md)
