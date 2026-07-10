```
 4. 当前配置文件结构

  config/
  ├── __init__.py       # 配置模块入口
  ├── flask.py          # Flask 应用配置
  ├── loader.py         # 统一配置加载器
  ├── backend.json      # 后端配置（detection, pdf等）
  └── settings.json     # OCR/LLM 提供者配置

  .env                  # 环境变量（API密钥）

  5. 环境变量配置位置
  ┌────────────────┬──────────────────────────────────────────┐
  │     配置项     │                   位置                   │
  ├────────────────┼──────────────────────────────────────────┤
  │ OCR API Keys   │ .env (BAIDU_API_KEY, ZHIPUAI_API_KEY 等) │
  ├────────────────┼──────────────────────────────────────────┤
  │ LLM API Keys   │ .env (KIMI_API_KEY, DEEPSEEK_API_KEY 等) │
  ├────────────────┼──────────────────────────────────────────┤
  │ MinerU API Key │ .env (MINERU_API_KEY)                    │
  ├────────────────┼──────────────────────────────────────────┤
  │ Ollama URL     │ .env (OLLAMA_BASE_URL)                   │
  └────────────────┴──────────────────────────────────────────┘
```

# 激活环境

## windows

```
d:
cd D:\code\venv_competition\Scripts
 .\activate
cd D:\code\教学工具\信息管理rebuild

```

```
claude  --dangerously-skip-permissions 
```

```
$env:PORT=5002; python run.py
```

## linux

```
cd /home/ubuntu/csddata
source venv/bin/activate

```



# 验证OCR厂商

## 1. 来自厂商的demo验证

tests/demo/baidu_ocr.py 和glm_4v_flash_ocr_demo.py

## 2. 快速OCR验证

使用菜单的方式，提供厂商选择，OCR预设图片的验证。可以在输出报告中对比每个OCR的效果。

```
python tests/ocr/test_ocr_provider.py
```

1. 验证各个厂商ocr还能否正常工作。运行各个厂商的ocr对比测试，目的也是验证每个厂商的ocr哪个还能用。

使用交互式菜单，选择验证的厂商。然后是选择可以批量测试或者是单张图片测试。

# OCR完整的单元测试

```
python tests\ocr\test_ocr.py
```

使用预设的图片进行OCR的单元测试，生成测试报告在reports

# LLM模块的单元测试

```
# 直接运行测试程序
python tests/extract/unit/llm_unit_test.py
```



# 图片抽取接口验证

## 1. 快速单图片验证

```
python tests/quick_extract_test.py
```

输入图片，给出单张图片的解析报告，就是把抽取接口走了一遍。

## 2. 交互式验证

可以选择是否缓存，交互式选定目录，单个文件等。快速验证最重要的抽取接口，输出html报告在：`tests\reports\`

`html`

```
python tests/extract_test.py
```

# 文件提交流程验证

从文件提交（送临时目录）-->AI解析-->入待审核库-->审核-->归档全过程。

```
python tests/test_files_commit.py
```

输出：tests/reports/html

1.提交这个步骤，已经完成对所有目录种类的识别，并生成报告了。



# 清理缓存

```
python tools/clear_cache.py
```

==目前还没有支持大创的测试验证，懒得弄，后面再说==

# Flask API

```
python tests/integration/test_flask_api.py
```

测试完成后，报告会生成在: `tests/reports/Flask_API测试.html`

# 定时清理pending

```
# 实际执行清理
python tools/clean_expired_pending.py

# 只统计将要删除的条数，不删
python tools/clean_expired_pending.py --dry-run
```

把用户上传却没有提交的清理掉。

# DEMO

## zhipu demo

关键是模型免费：

tests\demo\glm_4v_flash_ocr_demo.py

```
# 激活虚拟环境
D:\code\venv_competition\Scripts\activate

# 运行所有测试
pytest tests/ -v --json-report --json-report-file=tests/reports/report.json --html=tests/reports/report.html --self-contained-html

# 查看报告
start tests\reports\report.html
```



D:\code\venv_competition

glm_4v_flash_ocr_demo.py

# 测试Step-by-Step

报告统一都去reports下面拿，不放心的话可以先把reports删除，再看看新生成的。

1. **先验证OCR这些底层组件**，包括它们的API行不行。调用`python tests/ocr/test_ocr.py`,对比厂商之间的调用效果。如果某个厂商无法生成，则单独测试这个厂商的demo（tests/demo），主要验证模型和费用还可否继续使用。
2. **验证最核心的接口：文档抽取组件**：`python tests/quick_extract_test.py`和`python tests/extract_test.py`,，如果遇到错误，需要清理缓存，调用功缓存清理工具`python tools/clear_cache.py`。可以清理全部或者清理某一张图片（需要上传图片）
3. **验证flask api**:`python tests/integration/test_flask_api.py`
4. 