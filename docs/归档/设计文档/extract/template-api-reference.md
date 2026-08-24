> ⚠️ 已归档（2026-08-24）：本文档为历史资料，不反映项目现状。现行权威文档见 docs/README.md 路由。

# 模板模块 API 参考文档

**文档日期**: 2026-01-23
**适用范围**: backend/extract/template/

---

## 一、模块概述

### 1.1 模块结构

```
backend/extract/template/
├── __init__.py              # 公共接口导出
├── template.py              # Template 类
├── manager.py               # TemplateManager 类
├── matcher.py               # 匹配器类
├── competition.py           # CompetitionMatcher 类
└── utils.py                 # 公共工具函数
```

### 1.2 主要类和接口

| 类名 | 文件 | 职责 |
|------|------|------|
| `Template` | template.py | 证书模板类，封装模板数据和匹配逻辑 |
| `TemplateManager` | manager.py | 模板管理器，负责 CRUD 和匹配 |
| `TemplateMatcher` | matcher.py | 模板匹配器，提供完整匹配流程 |
| `TypeMatcher` | matcher.py | 类型识别器，判断文档类型 |
| `MatchResult` | matcher.py | 匹配结果数据类 |
| `CompetitionMatcher` | competition.py | 竞赛名称匹配器 |

---

## 二、Template 类

### 2.1 类定义

```python
class Template:
    """证书模板类

    支持奖状、专利、软著三种类型的证书模板。
    """

    def __init__(
        self,
        template_type: str,
        keywords: List[str],
        sample_text: str = "",
        sample_extracted: str = "",
        default_fields: Optional[Dict[str, Any]] = None,
        llm_fields: Optional[Dict[str, str]] = None,
        template_id: Optional[int] = None,
        min_length: int = 0,
        max_length: int = 0,
        sample_image_blob: Optional[bytes] = None,
        language: str = "zh",
        need_translate: bool = False,
        is_manual_edited: bool = False,
        competition_id: Optional[int] = None
    )
```

### 2.2 构造函数参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `template_type` | str | 是 | - | 模板类型：award/patent/software |
| `keywords` | List[str] | 是 | - | 关键词列表（AND 关系） |
| `sample_text` | str | 否 | "" | 样本文本（OCR 结果） |
| `sample_extracted` | str | 否 | "" | 样本抽取结果（JSON 字符串） |
| `default_fields` | Dict[str, Any] | 否 | {} | 固定值字段字典 |
| `llm_fields` | Dict[str, str] | 否 | {} | LLM 抽取字段定义 |
| `template_id` | Optional[int] | 否 | None | 模板 ID（从数据库加载时使用） |
| `min_length` | int | 否 | 0 | 最小字符数阈值 |
| `max_length` | int | 否 | 0 | 最大字符数阈值（0=不限制） |
| `sample_image_blob` | Optional[bytes] | 否 | None | 样本图片二进制数据 |
| `language` | str | 否 | "zh" | 语言：zh=中文, en=英文 |
| `need_translate` | bool | 否 | False | 是否需要翻译（英文时有效） |
| `is_manual_edited` | bool | 否 | False | 是否手工编辑 |
| `competition_id` | Optional[int] | 否 | None | 关联的竞赛 ID |

### 2.3 实例属性

```python
# 基本属性
template.template_type      # 模板类型
template.keywords           # 关键词列表
template.min_length         # 最小长度
template.max_length         # 最大长度
template.template_id        # 模板 ID
template.competition_id     # 竞赛 ID

# 样本数据
template.sample_text        # 样本文本
template.sample_extracted   # 样本抽取结果
template._cached_image_blob # 样本图片数据

# 字段定义
template.default_fields     # 默认字段
template.llm_fields         # LLM 字段

# 语言设置
template.language           # 语言代码
template.need_translate     # 是否需要翻译

# 状态
template.is_manual_edited   # 是否手工编辑
```

### 2.4 核心方法

#### match_by_keywords()

```python
def match_by_keywords(self, ocr_text: str) -> bool:
    """仅通过关键词进行匹配（不检查长度）

    用于奖状匹配的优先策略：如果所有关键词都命中，则直接匹配

    Args:
        ocr_text: OCR 识别的文本

    Returns:
        是否匹配关键词
    """
```

**示例：**
```python
template = Template(
    template_type="award",
    keywords=["蓝桥杯", "省赛"]
)

# 全部关键词匹配
assert template.match_by_keywords("蓝桥杯省赛获奖证书") == True

# 部分关键词不匹配
assert template.match_by_keywords("蓝桥杯国赛获奖证书") == False
```

#### match_score()

```python
def match_score(self, ocr_text: str) -> float:
    """计算匹配分数

    规则：
    1. 字符数检查（min_length 和 max_length）
    2. 关键词检查（所有关键词都要命中）
    3. 相似度匹配（基于样本文本）

    Args:
        ocr_text: OCR 识别的文本

    Returns:
        匹配分数 0.0-1.0
    """
```

**示例：**
```python
template = Template(
    template_type="award",
    keywords=[],
    min_length=10,
    sample_text="蓝桥杯全国软件和信息技术专业人才大赛"
)

# 高相似度
score = template.match_score("蓝桥杯全国软件和信息技术专业人才大赛")
assert score > 0.9

# 低于最小长度
score = template.match_score("短文本")
assert score == 0.0
```

#### generate_prompt()

```python
def generate_prompt(self, ocr_text: str, base_fields: Dict[str, str]) -> str:
    """生成提示词

    Args:
        ocr_text: OCR 识别的文本
        base_fields: 基础字段定义（从 *_fields.json 加载）

    Returns:
        完整的提示词字符串
    """
```

**示例：**
```python
template = Template(
    template_type="award",
    default_fields={"competition_name": "蓝桥杯", "granted_role": "学生"},
    sample_text="蓝桥杯获奖证书获得者：张三",
    sample_extracted='{"winner_name": "张三", "award_level": "一等奖"}'
)

base_fields = {
    "winner_name": "获奖者姓名",
    "award_level": "获奖等级"
}

prompt = template.generate_prompt("蓝桥杯省赛获奖证书获得者：李明", base_fields)
```

#### complete_result()

```python
def complete_result(
    self,
    extracted: Dict[str, Any],
    base_fields: Dict[str, str]
) -> Dict[str, Any]:
    """补全抽取结果（合并固定字段）

    Args:
        extracted: LLM 抽取的原始结果
        base_fields: 基础字段定义

    Returns:
        补全后的完整结果
    """
```

**示例：**
```python
template = Template(
    template_type="award",
    default_fields={"competition_name": "蓝桥杯"}
)

base_fields = {
    "winner_name": "获奖者姓名",
    "award_level": "获奖等级"
}

extracted = {"winner_name": "李明"}
result = template.complete_result(extracted, base_fields)

# result = {
#     "winner_name": "李明",
#     "award_level": None,  # 缺失字段填充 null
#     "competition_name": "蓝桥杯"  # 默认字段合并
# }
```

#### to_dict() / from_dict()

```python
def to_dict(self, include_image: bool = False) -> Dict[str, Any]:
    """转换为字典（用于存储）"""

@classmethod
def from_dict(cls, data: Dict[str, Any]) -> 'Template':
    """从字典创建"""
```

**示例：**
```python
template = Template(
    template_type="award",
    keywords=["蓝桥杯"],
    default_fields={"competition_name": "蓝桥杯"}
)

# 序列化
data = template.to_dict(include_image=False)

# 反序列化
new_template = Template.from_dict(data)
```

#### from_db_row()

```python
@classmethod
def from_db_row(cls, row) -> 'Template':
    """从数据库行创建模板对象

    Args:
        row: sqlite3.Row 对象或字典

    Returns:
        证书模板实例
    """
```

#### compress_image()

```python
def compress_image(
    self,
    image_bytes: bytes,
    max_size_kb: int = 500
) -> bytes:
    """压缩图片到指定大小以下

    Args:
        image_bytes: 原始图片二进制数据
        max_size_kb: 最大大小（KB），默认 500KB

    Returns:
        压缩后的图片二进制数据
    """
```

---

## 三、TemplateManager 类

### 3.1 类定义

```python
class TemplateManager:
    """模板管理器

    支持管理三种类型的证书模板：奖状、专利、软著
    """

    def __init__(
        self,
        db_path: str,
        base_fields_map: Optional[Dict[str, Dict[str, str]]] = None,
        config_dir: Optional[str] = None
    )
```

### 3.2 构造函数参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `db_path` | str | 是 | - | 数据库文件路径 |
| `base_fields_map` | Dict[str, Dict[str, str]] | 否 | None | 各类型的字段定义映射 |
| `config_dir` | str | 否 | None | 配置文件目录 |

### 3.3 核心 CRUD 方法

#### add_template()

```python
def add_template(self, template: Template) -> bool:
    """添加模板

    Args:
        template: 证书模板实例

    Returns:
        是否添加成功（如果已存在则返回 False）
    """
```

**示例：**
```python
manager = TemplateManager(db_path="database/document_extract_validation.db")

template = Template(
    template_type="award",
    keywords=["蓝桥杯"],
    default_fields={"competition_name": "蓝桥杯"}
)

success = manager.add_template(template)
assert success == True
```

#### get_template()

```python
def get_template(self, template_id: int) -> Optional[Template]:
    """获取指定 ID 的模板

    Args:
        template_id: 模板 ID

    Returns:
        匹配的模板，未找到返回 None
    """
```

#### get_templates_by_type()

```python
def get_templates_by_type(self, template_type: str) -> TemplateList:
    """获取指定类型的所有模板

    Args:
        template_type: 模板类型（award/patent/software）

    Returns:
        该类型的模板列表
    """
```

#### delete_template()

```python
def delete_template(self, template_id: int) -> bool:
    """删除指定 ID 的模板

    Args:
        template_id: 模板 ID

    Returns:
        是否删除成功
    """
```

#### clear_templates()

```python
def clear_templates(self) -> None:
    """清空所有模板"""
```

### 3.4 匹配方法

#### match_template()

```python
def match_template(self, ocr_text: str) -> Optional[Template]:
    """匹配最佳模板

    Args:
        ocr_text: OCR 识别的文本

    Returns:
        匹配的模板，未匹配返回 None
    """
```

#### match_type()

```python
def match_type(self, ocr_text: str) -> str:
    """识别文档类型

    Args:
        ocr_text: OCR 识别的文本

    Returns:
        文档类型（award/patent/software/other）
    """
```

#### match_full()

```python
def match_full(self, ocr_text: str) -> MatchResult:
    """完整的模板匹配流程

    返回类型、模板、相似度和默认提示词

    Args:
        ocr_text: OCR 识别的文本

    Returns:
        MatchResult: 包含 type、template、similarity、default_prompt
    """
```

**示例：**
```python
manager = TemplateManager(db_path="database/document_extract_validation.db")

result = manager.match_full("蓝桥杯省赛获奖证书获得者：李明")

print(f"类型: {result.type}")
print(f"模板: {result.template}")
print(f"相似度: {result.similarity}")
print(f"默认提示词: {result.default_prompt}")
```

---

## 四、TemplateMatcher 类

### 4.1 类定义

```python
class TemplateMatcher:
    """模板匹配器，提供完整的模板匹配流程"""
```

### 4.2 类方法

#### load_configs()

```python
@classmethod
def load_configs(
    cls,
    config_dir: str,
    db_path: Optional[str] = None,
    competition_manager=None
) -> None:
    """加载所有配置文件

    Args:
        config_dir: 配置文件目录
        db_path: 数据库文件路径（用于加载竞赛数据）
        competition_manager: CompetitionManager 实例（优先使用）
    """
```

#### match_full()

```python
@classmethod
def match_full(
    cls,
    ocr_text: str,
    templates: List[Template],
    default_prompts: Dict[str, str]
) -> MatchResult:
    """完整的模板匹配流程

    Args:
        ocr_text: OCR 识别的文本
        templates: 所有模板列表
        default_prompts: 默认提示词字典 {type: prompt}

    Returns:
        MatchResult: 匹配结果
    """
```

**匹配流程：**
1. 类型识别（TypeMatcher.match）
2. 根据类型选择匹配策略
3. 奖状：关键词匹配 → 相似度匹配 → 竞赛名称验证
4. 专利/软著：简单匹配

---

## 五、TypeMatcher 类

### 5.1 类定义

```python
class TypeMatcher:
    """类型匹配器，根据配置规则判断 OCR 文本属于哪种类型"""
```

### 5.2 类方法

#### load_rules()

```python
@classmethod
def load_rules(cls, config_path: str) -> None:
    """加载类型匹配规则

    Args:
        config_path: type_matching_rules.json 文件路径
    """
```

#### match()

```python
@classmethod
def match(cls, ocr_text: str) -> str:
    """匹配文本类型

    Args:
        ocr_text: OCR 识别的文本

    Returns:
        类型: award/patent/software/other
    """
```

**匹配规则顺序：**
1. patent - 检查 "专利证书"
2. software - 检查 "软件著作权"
3. award - 检查奖状相关关键词
4. other - 无匹配

---

## 六、MatchResult 数据类

### 6.1 类定义

```python
@dataclass
class MatchResult:
    """匹配结果数据类"""
    type: str                      # 类型: award/patent/software/other
    template: Optional[Template]    # 匹配的模板（可能为 None）
    similarity: float               # 相似度（0.0-1.0，无模板时为 0.0）
    default_prompt: Optional[str]   # 默认提示词（使用模板时为 None）
```

### 6.2 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `type` | str | 文档类型 |
| `template` | Optional[Template] | 匹配到的模板，未匹配时为 None |
| `similarity` | float | 相似度分数，范围 0.0-1.0 |
| `default_prompt` | Optional[str] | 默认提示词，使用模板时为 None |

### 6.3 方法

#### to_dict()

```python
def to_dict(self) -> Dict[str, Any]:
    """转换为字典"""
```

---

## 七、CompetitionMatcher 类

### 7.1 类定义

```python
class CompetitionMatcher:
    """竞赛名称匹配器，从 OCR 文本中提取竞赛名称"""
```

### 7.2 类方法

#### load_from_database()

```python
@classmethod
def load_from_database(
    cls,
    db_path: Optional[str] = None,
    competition_manager=None
) -> None:
    """从数据库加载竞赛数据

    Args:
        db_path: 数据库文件路径
        competition_manager: CompetitionManager 实例（优先使用）
    """
```

#### match()

```python
@classmethod
def def match(cls, ocr_text: str) -> Optional[str]:
    """从 OCR 文本中匹配竞赛名称

    Args:
        ocr_text: OCR 识别的文本

    Returns:
        匹配到的竞赛名称，未匹配返回 None
    """
```

---

## 八、使用示例

### 8.1 基本使用

```python
from backend.extract.template import TemplateManager

# 初始化管理器
manager = TemplateManager(db_path="database/document_extract_validation.db")

# 匹配模板
ocr_text = "蓝桥杯全国软件和信息技术专业人才大赛省赛获奖证书"
result = manager.match_full(ocr_text)

if result.template:
    print(f"匹配到模板: {result.template.get_display_name()}")
    print(f"相似度: {result.similarity}")
else:
    print("未匹配到模板，使用默认提示词")
```

### 8.2 添加新模板

```python
from backend.extract.template import Template, TemplateManager

manager = TemplateManager(db_path="database/document_extract_validation.db")

# 创建新模板
new_template = Template(
    template_type="award",
    keywords=["支付宝", "小程序"],
    default_fields={
        "competition_name": "支付宝小程序创新大赛",
        "granted_role": "学生"
    },
    min_length=50
)

# 添加到数据库
success = manager.add_template(new_template)
if success:
    print("模板添加成功")
```

### 8.3 批量操作

```python
from backend.extract.template import TemplateManager

manager = TemplateManager(db_path="database/document_extract_validation.db")

# 获取所有奖状模板
award_templates = manager.get_templates_by_type("award")
print(f"共有 {len(award_templates)} 个奖状模板")

# 获取统计信息
stats = manager.get_stats()
print(f"总模板数: {stats['total']}")
print(f"按类型分布: {stats['by_type']}")
```

---

## 九、错误处理

### 9.1 异常类型

| 异常 | 触发条件 | 处理方式 |
|------|----------|----------|
| `ValueError` | 无效的模板类型 | 检查 template_type 参数 |
| `sqlite3.Error` | 数据库操作失败 | 检查数据库路径和权限 |
| `json.JSONDecodeError` | JSON 解析失败 | 检查 JSON 格式 |

### 9.2 错误处理示例

```python
from backend.extract.template import Template, TemplateManager

try:
    template = Template(
        template_type="invalid_type",  # 无效类型
        keywords=[]
    )
except ValueError as e:
    print(f"模板类型错误: {e}")

try:
    manager = TemplateManager(db_path="/invalid/path/db.sqlite")
except sqlite3.Error as e:
    print(f"数据库错误: {e}")
```

---

**文档版本**: 1.0
**最后更新**: 2026-01-23
