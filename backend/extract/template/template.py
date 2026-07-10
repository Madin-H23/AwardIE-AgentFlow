"""
模板类模块

定义证书模板类，支持奖状、专利、软著三种类型的证书模板。
"""
import hashlib
import io
import json
import logging
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image

from ..types import TemplateType
from ..exceptions import TemplateError
from .utils import clean_text

logger = logging.getLogger(__name__)


class Template:
    """
    证书模板类

    支持三种类型：奖状、专利、软著

    使用示例:
        >>> template = Template(
        ...     template_type=TemplateType.AWARD,
        ...     min_length=100,
        ...     keywords=["蓝桥杯", "省赛"],
        ...     default_fields={"granted_role": "学生", "competition_name": "蓝桥杯"},
        ...     sample_text="...",
        ...     sample_extracted='{"winner_name": "张三"}'
        ... )
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
    ):
        """
        初始化证书模板

        Args:
            template_type: 模板类型（award/patent/software）
            keywords: 关键词列表（所有关键词都要命中）
            sample_text: 样本文本（OCR 结果）
            sample_extracted: 样本抽取结果（JSON 字符串）
            default_fields: 固定值字段字典
            llm_fields: LLM 抽取字段定义
            template_id: 模板 ID（从数据库加载时使用）
            min_length: 最小字符数阈值
            max_length: 最大字符数阈值（超过此长度不匹配）
            sample_image_blob: 样本图片二进制数据（从数据库加载）
            language: 语言（zh=中文, en=英文）
            need_translate: 是否需要翻译（英文时有效，true=翻译成中文）
            is_manual_edited: 是否手工编辑
            competition_id: 关联的竞赛 ID
        """
        # 验证类型
        if not TemplateType.validate(template_type):
            raise ValueError(f"无效的模板类型: {template_type}，必须是: {TemplateType.ALL}")

        self.template_type = template_type
        self.keywords = keywords or []
        self.min_length = min_length
        self.max_length = max_length
        self.template_id = template_id
        self.sample_text = sample_text
        self.sample_extracted = sample_extracted
        self.default_fields = default_fields or {}
        self.llm_fields = llm_fields or {}
        self.language = language  # 'zh' 或 'en'
        self.need_translate = need_translate  # 布尔值
        self._cached_image_blob = sample_image_blob  # 缓存的图片数据
        self.is_manual_edited = is_manual_edited
        self.competition_id = competition_id  # 竞赛 ID

    # ==================== 模板信息 ====================

    def get_display_name(self) -> str:
        """获取模板的显示名称"""
        # 优先使用 default_fields 中的名称
        if self.template_type == TemplateType.AWARD:
            base_name = self.default_fields.get("competition_name", "未命名奖状模板")
            # 如果有 granted_role，添加到名称中以便区分学生和教师模板
            role = self.default_fields.get("granted_role")
            if role:
                return f"{base_name}（{role}）"
            return base_name
        elif self.template_type == TemplateType.PATENT:
            return self.default_fields.get("patent_name", "未命名专利模板")
        elif self.template_type == TemplateType.SOFTWARE:
            return self.default_fields.get("software_name", "未命名软著模板")
        return TemplateType.get_display_name(self.template_type)

    def get_type_display_name(self) -> str:
        """获取类型的显示名称"""
        return TemplateType.get_display_name(self.template_type)

    def get_field_type(self, field_name: str) -> str:
        """
        获取字段的类型

        Args:
            field_name: 字段名称

        Returns:
            字段类型：'empty'（空）、'default'（默认）、'extract'（抽取）
        """
        # 如果在 default_fields 中，则是默认字段
        if field_name in self.default_fields:
            return 'default'

        # 如果在 llm_fields 中，则是抽取字段
        if field_name in self.llm_fields:
            return 'extract'

        # 否则为空
        return 'empty'

    # ==================== 模板匹配 ====================

    def match_by_keywords(self, ocr_text: str) -> bool:
        """
        仅通过关键词进行匹配（不检查长度）

        用于奖状匹配的优先策略：如果所有关键词都命中，则直接匹配

        Args:
            ocr_text: OCR 识别的文本

        Returns:
            是否匹配关键词
        """
        if not ocr_text or not ocr_text.strip():
            return False

        # 使用统一的清理函数
        clean_ocr = clean_text(ocr_text)

        # 关键词检查（所有关键词都要命中，AND 关系）
        if self.keywords:
            for keyword in self.keywords:
                clean_keyword = clean_text(keyword) if keyword else ""
                if clean_keyword and clean_keyword not in clean_ocr:
                    logger.debug(f"  关键词 '{keyword}' (清理后: '{clean_keyword}') 未在 OCR 文本中找到")
                    return False
                else:
                    logger.debug(f"  ✓ 关键词 '{keyword}' 匹配成功")
            return True

        return False

    def match_score(self, ocr_text: str) -> float:
        """
        计算匹配分数

        规则：
        1. 字符数检查（min_length 和 max_length）
        2. 关键词检查（所有关键词都要命中）
        3. 相似度匹配（基于样本文本）

        Args:
            ocr_text: OCR 识别的文本

        Returns:
            匹配分数 0.0-1.0
        """
        if not ocr_text or not ocr_text.strip():
            return 0.0

        # 使用统一的清理函数
        clean_ocr = clean_text(ocr_text)
        ocr_len = len(clean_ocr)

        # 规则1：字符数下限检查
        if ocr_len < self.min_length:
            return 0.0

        # 规则2：字符数上限检查（超过 max_length 直接返回 0）
        if self.max_length > 0 and ocr_len > self.max_length:
            return 0.0

        # 规则3：关键词检查（所有关键词都要命中）
        if self.keywords:
            for keyword in self.keywords:
                clean_keyword = clean_text(keyword) if keyword else ""
                if clean_keyword and clean_keyword not in clean_ocr:
                    return 0.0

        # 规则4：相似度匹配（基于样本文本）
        if self.sample_text:
            clean_sample = clean_text(self.sample_text)
            similarity = SequenceMatcher(None, clean_ocr, clean_sample).ratio()
            return similarity

        return 1.0

    # ==================== 提示词生成 ====================

    def generate_prompt(self, ocr_text: str, base_fields: Dict[str, str]) -> str:
        """
        生成提示词

        Args:
            ocr_text: OCR 识别的文本
            base_fields: 基础字段定义（从对应的 *_fields.json 加载）

        Returns:
            完整的提示词字符串
        """
        
        # 1. 字段描述
        fields_desc = self._get_fields_description(base_fields)

        # 2. One-shot 示例
        one_shot_text = ""
        if self.sample_text and self.sample_extracted:
            one_shot_text = f"""例如针对【】中的 OCR 文本，抽取结果如下：
【{self.sample_text}】
{self.sample_extracted}"""

        # 3. 根据语言设置调整提示词
        type_name = self.get_type_display_name()
        language_prefix = ""
        translate_note = ""

        if self.language == 'en':
            language_prefix = "英文"
            if self.need_translate:
                translate_note = """
**重要翻译要求：**
1. **人名保持原文**：学生姓名、指导教师姓名等所有人名必须保持原文的英文形式，不要翻译或音译。例如：Zenan Xiang 应保持为 "Zenan Xiang"，不要翻译成 "曾楠翔"。
2. **其他内容翻译**：除人名外的所有英文内容必须转换为对应的中文正式表述，确保专业术语准确。例如：
   - "Winner" 应翻译为 "获奖者"
   - "Honorable Mention" 应翻译为 "荣誉提名"
   - "First Prize" 应翻译为 "一等奖"
   - "Bronze Medal" 应翻译为 "铜奖"
   - "Certificate of Achievement" 应翻译为 "获奖证书"
3. 如果学校名、公司名等有官方中文名，使用官方中文名；否则保持原文。
"""

        # 4. 为 award 类型构建新的提示词结构：先判断类型，再抽取
        if self.template_type == TemplateType.AWARD:
            # 奖状类型：先判断是否是奖状，再抽取
            intro_text = f"下面是一张图片中提取的文本（已按行拼接）："
            prompt = f"""{intro_text}

{ocr_text}

**第一步：请先判断这是否是一张奖状证书。**

奖状证书的特征：
- 明确授予某个具体获奖者（包含获奖者姓名）
- 包含竞赛名称、获奖等级等信息
- 是正式的获奖证书，而非通知、名单、模板等

以下情况**不是**奖状证书，应设置 `is_valid_certificate: false`：
- 获奖通知、获奖名单、获奖公示等通知类文档
- 空白奖状模板、示例奖状等未填写具体获奖者信息的文档
- 比赛规则、比赛说明、比赛通知等非证书类文档
- 其他类型的证书（如认证证书、资质证书、职业资格证书等，如 HCIE 证书、CISSP 证书、PMP 证书等）
- 其他不包含明确授予某个具体获奖者证书信息的文档

如果不是奖状证书，则返回如下 json 字符串，并且结束处理（忽略后续所有任务）：
{{
  "is_valid_certificate": false
}}

只有明确授予某个具体获奖者（包含获奖者姓名）的奖状证书，才应设置 `is_valid_certificate: true`。

**第二步：如果这是奖状证书，根据以下字段要求进行信息抽取。**

**字段要求：**
{fields_desc}
- `is_valid_certificate`: 固定为 true
{translate_note}
{one_shot_text}

重要要求：
1. 只返回一个有效的 JSON 对象，不要包含任何说明文字、示例代码或注释
2. 不要返回 Markdown 代码块标记（如 ```json 或 ```）
3. 不要返回任何解释性文字，只返回 JSON 对象本身
4. JSON 中不要包含注释（// 或 /* */）
5. 如果某个字段在文本中不存在或无法确定，请将该字段值设为 `null`。

请直接返回 JSON 对象："""
        else:
            # 非奖状类型（专利、软著等）：保持原有逻辑
            intro_text = f"下面是一张{type_name}的 OCR 文本（已按行拼接）："
            prompt = f"""{intro_text}

{ocr_text}

请你只根据以上文本，抽取并返回一个 JSON 对象，字段要求如下：
{fields_desc}
{translate_note}
{one_shot_text}

如果某个字段在文本中不存在或无法确定，请将该字段值设为 null。
重要要求：
1. 只返回一个有效的 JSON 对象，不要包含任何说明文字、示例代码或注释
2. 不要返回 Markdown 代码块标记（如 ```json 或 ```）
3. 不要返回任何解释性文字，只返回 JSON 对象本身
4. JSON 中不要包含注释（// 或 /* */）
请直接返回 JSON 对象："""

        return prompt

    def _get_fields_description(self, base_fields: Dict[str, str]) -> str:
        """
        获取字段描述

        Args:
            base_fields: 基础字段定义

        Returns:
            格式化的字段描述字符串
        """
        # 优先使用模板的 llm_fields，否则使用 base_fields
        fields_to_use = self.llm_fields if self.llm_fields else base_fields

        # 排除 default_fields 中已有的字段（不需要抽取）
        excluded_fields = set(self.default_fields.keys())

        desc_lines = []
        for field, description in fields_to_use.items():
            if field not in excluded_fields:
                line = f"- {field}：{description}"
                desc_lines.append(line)

        return "\n".join(desc_lines)

    # ==================== 结果补全 ====================

    def complete_result(
        self,
        extracted: Dict[str, Any],
        base_fields: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        补全抽取结果（合并固定字段）

        Args:
            extracted: LLM 抽取的原始结果
            base_fields: 基础字段定义

        Returns:
            补全后的完整结果
        """
        if extracted is None:
            extracted = {}

        result = extracted.copy()

        # 1. 合并默认字段（包括类型特定的固定值）
        result.update(self.default_fields)

        # 2. 确保所有字段都存在（缺失的设为 null）
        all_fields = base_fields if base_fields else {}
        for field in all_fields.keys():
            if field not in result:
                result[field] = None

        return result

    # ==================== 图片处理 ====================

    @property
    def _sample_image_blob(self) -> Optional[bytes]:
        """
        获取样本图片的二进制数据（属性，支持懒加载）

        Returns:
            图片二进制数据，不存在返回 None
        """
        # 返回缓存的图片数据（从数据库加载时设置）
        return self._cached_image_blob

    def get_sample_image_bytes(self) -> Optional[bytes]:
        """
        获取样本图片的二进制数据

        Returns:
            图片二进制数据，不存在返回 None
        """
        return self._sample_image_blob

    def compress_image(
        self,
        image_bytes: bytes,
        max_size_kb: int = 500
    ) -> bytes:
        """
        压缩图片到指定大小以下

        Args:
            image_bytes: 原始图片二进制数据
            max_size_kb: 最大大小（KB），默认 500KB

        Returns:
            压缩后的图片二进制数据
        """
        try:
            img = Image.open(io.BytesIO(image_bytes))

            # 转换为 RGB 模式
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')

            max_size_bytes = max_size_kb * 1024

            # 如果图片已经小于目标大小，直接返回
            output = io.BytesIO()
            img.save(output, format='JPEG', quality=95)
            if len(output.getvalue()) <= max_size_bytes:
                return output.getvalue()

            # 逐步降低质量
            quality = 85
            step = 10
            min_quality = 20

            while quality >= min_quality:
                output = io.BytesIO()
                img.save(output, format='JPEG', quality=quality)
                compressed = output.getvalue()

                if len(compressed) <= max_size_bytes:
                    return compressed

                quality -= step

            # 如果质量降到最低仍然太大，缩小尺寸
            scale = (max_size_bytes / len(compressed)) ** 0.5
            new_size = (int(img.width * scale), int(img.height * scale))
            img_resized = img.resize(new_size, Image.Resampling.LANCZOS)

            output = io.BytesIO()
            img_resized.save(output, format='JPEG', quality=min_quality)
            return output.getvalue()

        except Exception:
            return image_bytes

    # ==================== 序列化 ====================

    def to_dict(self, include_image: bool = False) -> Dict[str, Any]:
        """
        转换为字典（用于存储）

        Args:
            include_image: 是否包含样本图片数据（默认不包含）

        Returns:
            模板数据字典
        """
        data = {
            "template_id": self.template_id,
            "type": self.template_type,
            "min_length": self.min_length,
            "max_length": self.max_length,
            "keywords": self.keywords,
            "sample_text": self.sample_text,
            "sample_extracted": self.sample_extracted,
            "default_fields": self.default_fields,
            "llm_fields": self.llm_fields,
            "language": self.language,
            "need_translate": self.need_translate,
            "is_manual_edited": self.is_manual_edited,
            "competition_id": self.competition_id
        }

        # 图片数据不能直接序列化到 JSON，只有在明确需要时才包含
        if include_image:
            image_blob = self._sample_image_blob
            if image_blob:
                data["sample_image_blob"] = image_blob.hex()

        return data

    @staticmethod
    def _load_image_blob(blob_data: Any) -> Optional[bytes]:
        """从加载的数据恢复图片 blob"""
        if blob_data is None:
            return None
        if isinstance(blob_data, bytes):
            return blob_data
        if isinstance(blob_data, str):
            try:
                return bytes.fromhex(blob_data)
            except ValueError:
                return None
        return None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Template':
        """
        从字典创建

        Args:
            data: 模板数据字典

        Returns:
            证书模板实例
        """
        return cls(
            template_type=data["type"],
            keywords=data.get("keywords", []),
            template_id=data.get("template_id"),
            sample_text=data.get("sample_text", ""),
            sample_extracted=data.get("sample_extracted", ""),
            default_fields=data.get("default_fields", {}),
            llm_fields=data.get("llm_fields", {}),
            min_length=data.get("min_length", 0),
            max_length=data.get("max_length", 0),
            sample_image_blob=cls._load_image_blob(data.get("sample_image_blob")),
            language=data.get("language", "zh"),
            need_translate=data.get("need_translate", False),
            is_manual_edited=data.get("is_manual_edited", False),
            competition_id=data.get("competition_id")
        )

    @classmethod
    def from_db_row(cls, row) -> 'Template':
        """
        从数据库行创建模板对象

        Args:
            row: sqlite3.Row 对象或字典

        Returns:
            证书模板实例
        """
        def get_field(key, default=None):
            """统一的字段获取方法"""
            if hasattr(row, 'keys'):
                # sqlite3.Row - 不支持 get() 方法，直接访问
                return row[key] if key in row.keys() else default
            # 普通字典
            return getattr(row, key, default)

        # JSON 解析辅助函数
        def parse_json(value, default=None):
            if not value:
                return default or {}
            try:
                return json.loads(value) if isinstance(value, str) else value
            except (json.JSONDecodeError, TypeError):
                return default or {}

        return cls(
            template_type=get_field('template_type'),
            template_id=get_field('id'),
            keywords=parse_json(get_field('keywords'), []),
            sample_text=get_field('sample_text', ''),
            sample_extracted=get_field('sample_extracted', ''),
            default_fields=parse_json(get_field('default_fields'), {}),
            llm_fields=parse_json(get_field('llm_fields'), {}),
            min_length=get_field('min_length', 0),
            max_length=get_field('max_length', 0),
            language=get_field('language', 'zh'),
            need_translate=bool(get_field('need_translate', False)),
            is_manual_edited=bool(get_field('is_manual_edited', False)),
            sample_image_blob=get_field('sample_image_blob'),
            competition_id=get_field('competition_id')
        )

    # ==================== 竞赛匹配 ====================

    @classmethod
    def match_competition(cls, ocr_text: str) -> Optional[str]:
        """
        从 OCR 文本中匹配竞赛名称

        Args:
            ocr_text: OCR 识别的文本

        Returns:
            匹配到的竞赛名称，未匹配返回 None
        """
        # 导入 CompetitionMatcher（延迟导入避免循环依赖）
        from .competition import CompetitionMatcher
        return CompetitionMatcher.match(ocr_text)

    # ==================== 字符串表示 ====================

    def __str__(self) -> str:
        """字符串表示"""
        type_name = self.get_type_display_name()
        display_name = self.get_display_name()
        return f"Template(id={self.template_id}, type={type_name}, name={display_name})"

    def __repr__(self) -> str:
        return self.__str__()
