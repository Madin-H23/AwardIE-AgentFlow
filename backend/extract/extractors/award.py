"""
奖状抽取器

从奖状图片/PDF中提取结构化数据。
支持中文和英文奖状，自动检测并进行翻译。
"""
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.extract.exceptions import user_facing_message
from backend.extract.extractors.base import ExtractContext, Extractor
from backend.extract.template import TemplateManager
from backend.extract.types import (
    ExtractResult, ExtractStatus, TemplateType,
    ValidationResult, ValidationError
)

logger = logging.getLogger(__name__)


class AwardExtractor(Extractor):
    """
    奖状抽取器

    从奖状图片/PDF中提取结构化数据。
    支持中文和英文奖状，自动检测并进行翻译。
    """

    template_type = "award"
    fields_name = "award"

    # 关键词配置（用于框架层面选择抽取器）
    # 注意：这些关键词用于 ExtractFramework 的 matches_keywords 方法，

    PRIMARY_KEYWORDS = [
        '奖', '证书',
        'award', 'certificate'
    ]

    AWARD_KEYWORDS = [
        '赛', '竞赛', '比赛', '获奖', '名次', '第', '等', '名',
        '特等奖', '一等奖', '二等奖', '三等奖', '优秀奖', '鼓励奖',
        'honor', 'prize', 'competition', 'contest', 'winner'
    ]

    # 英文奖状翻译提示
    ENGLISH_TRANSLATION_NOTE = """
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

    def __init__(self, config: Dict[str, Any], template_manager: Optional[TemplateManager] = None):
        """
        初始化奖状抽取器

        Args:
            config: 配置字典，包含：
                - extensions: 支持的文件扩展名列表
                - keywords: 关键词列表
                - min_confidence: 最小置信度
                - enable_quick_screen: 是否启用快速OCR筛选
                - quick_screen_min_length: 快速筛选最小字数
                - quick_screen_max_length: 快速筛选最大字数
                - english_ratio_threshold: 英文字符比例阈值
            template_manager: 模板管理器（可选，用于模板匹配）
        """
        # 加载字段定义
        fields_file = config.get("fields_file", f"{self.fields_name}_fields.json")
        self._fields = self._load_fields(fields_file)

        # 构建关键词列表
        # 如果配置中没有提供关键词，使用默认的关键词列表
        keywords = config.get("keywords", [])
        if isinstance(keywords, list):
            keywords = [k for k in keywords if k]
        else:
            keywords = []
        
        # 如果配置中没有关键词，使用默认的关键词（PRIMARY_KEYWORDS + AWARD_KEYWORDS）
        if not keywords:
            keywords = list(self.PRIMARY_KEYWORDS) + list(self.AWARD_KEYWORDS)

        # 获取最小置信度
        self._min_confidence = config.get("min_confidence", 0.3)

        # 快速筛选配置
        self._enable_quick_screen = config.get("enable_quick_screen", True)
        self._quick_screen_min_length = config.get("quick_screen_min_length", 15)
        self._quick_screen_max_length = config.get("quick_screen_max_length", 1500)

        # 英文检测配置
        self._english_ratio_threshold = config.get("english_ratio_threshold", 0.7)

        # 模板管理器
        self._template_manager = template_manager

        # 初始化基类
        super().__init__(
            name="award",
            description="奖状/获奖证书",
            keywords=keywords,
            judgment_text="通常包含：包含授予对象（个人 / 团队）+ 奖励名称 + 颁发机构 + 获奖等级 / 荣誉称号 + 落款日期",
            extensions=config.get("extensions", [".pdf", ".jpg", ".jpeg", ".png", ".jfif"]),
        )

        self._config = config

    def _load_fields(self, fields_file: str) -> Dict[str, str]:
        """加载字段定义"""
        path = Path(__file__).parent.parent.parent / "extract" / "prompts" / fields_file
        if not path.exists():
            raise FileNotFoundError(f"字段定义文件不存在: {path}")
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            raise RuntimeError(f"加载字段定义失败 {path}: {e}") from e
        if not isinstance(data, dict):
            raise ValueError(f"字段定义文件格式错误，应为 JSON 对象: {path}")
        return data

    def _get_fields_description(self) -> str:
        """获取字段描述"""
        if not self._fields:
            return ""

        lines = ["请提取以下字段，以JSON格式返回：", "{"]
        for key, desc in self._fields.items():
            lines.append(f'  "{key}": "{desc}",')
        lines.append('  "is_valid_certificate": true')
        lines.append("}")
        lines.append("")
        lines.append("注意：")
        lines.append("- 如果某个字段无法从文本中提取，请使用null")
        lines.append("- 日期格式必须为YYYY-MM-DD、YYYY-MM或YYYY.MM（如：2025-05-26、2025-05、2025.05）")
        lines.append("- award_level必须是中文（如：一等奖、二等奖、金奖、银奖等），不要返回英文")
        lines.append("- 如果这是考级证书、认证证书等非竞赛获奖证书，请在 is_valid_certificate 字段返回 false")
        lines.append("- 不要返回除了json字符串之外的任何内容")
        return "\n".join(lines)

    def _build_prompt(self, ocr_text: str, is_english: bool = False) -> str:
        """构建LLM提示词"""
        fields_desc = self._get_fields_description()

        # 添加翻译说明（如果是英文奖状）
        translate_note = self.ENGLISH_TRANSLATION_NOTE if is_english else ""

        prompt = f"""你是一个专业的奖状信息提取助手。请从以下OCR识别的文本中提取奖状信息。

{ocr_text}

{fields_desc}
{translate_note}

**重要说明：**
奖状证书必须是**竞赛获奖证书**，必须同时包含：竞赛名称（competition_name）和获奖等级（award_level，如"一等奖"、"二等奖"等）。
以下情况请在 is_valid_certificate 字段返回 false：
- 考级证书、等级考试证书（如"等级考试证书"、"Level-1"等）
- 认证证书、资质证书、能力测试证书
- 没有竞赛名称或获奖等级的证书

**要求：**
1. 只返回JSON对象，不要包含说明文字或Markdown标记
2. 字段不存在时设为 `null`
3. is_valid_certificate: 真实奖状证书为 true，否则为 false

请直接返回JSON对象："""

        return prompt

    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """解析LLM响应"""
        # 尝试直接解析JSON
        try:
            data = json.loads(response.strip())
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

        # 尝试从代码块中提取JSON
        json_match = re.search(r'```(?:json)?\s*\n?\s*(\{.*?\})\s*\n?\s*```', response, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                pass

        # 尝试提取花括号内容
        brace_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response, re.DOTALL)
        if brace_match:
            try:
                data = json.loads(brace_match.group(0))
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                pass

        logger.error(f"无法解析LLM响应: {response[:200]}...")
        return {}

    def _quick_screen(self, ocr_text: str) -> tuple[bool, str]:
        """
        快速筛选：判断文本是否可能是奖状
        
        注意：这是在抽取器内部调用的，用于快速判断OCR文本是否可能是奖状。
        只检查文本长度，不检查关键词（关键词检查由框架层面的 matches_keywords 处理）。
        
        条件：文本长度在合理范围内（min_length 到 max_length）
        
        Returns:
            (是否通过, 失败时的说明，通过时为 ""）
        """
        if not ocr_text:
            return False, "OCR文本为空"

        # 清洗文本并统计（仅去除空格与换行）
        clean_text = ocr_text.replace(" ", "").replace("\n", "").replace("\r", "")
        text_count = len(clean_text)

        if text_count < self._quick_screen_min_length:
            detail = f"清洗后字数{text_count}小于最小值{self._quick_screen_min_length}"
            logger.info(f"[快速筛选] 未通过: {detail}")
            return False, detail
        if text_count > self._quick_screen_max_length:
            detail = f"清洗后字数{text_count}超过最大值{self._quick_screen_max_length}"
            logger.info(f"[快速筛选] 未通过: {detail}")
            return False, detail
        return True, ""

    def _is_english_certificate(self, ocr_text: str) -> bool:
        """
        检测是否为英文奖状

        Returns:
            True if 英文字符比例 > 阈值
        """
        if not ocr_text:
            return False

        english_chars = sum(1 for c in ocr_text if c.isascii() and c.isalpha())
        total_chars = sum(1 for c in ocr_text if c.isalpha())

        return total_chars > 0 and english_chars / total_chars > self._english_ratio_threshold

    def _check_valid_certificate(self, data: Dict[str, Any]) -> bool:
        """
        检查是否为真实奖状证书

        Args:
            data: LLM抽取的数据

        Returns:
            True if 是真实奖状证书
        """
        # 检查获奖者姓名（主要判断依据）
        winner_name = data.get("winner_name")

        # 如果获奖者姓名为空，视为无效
        if not winner_name:
            return False

        # 检查 winner_name 是否为空字符串
        if isinstance(winner_name, str) and not winner_name.strip():
            return False

        # 如果明确标记为无效证书
        if data.get("is_valid_certificate") is False:
            return False

        return True

    def _clean_field_value(self, field_name: str, value: Any) -> Any:
        """
        清理字段值

        - 姓名相关字段：去掉数字和特殊符号
        - 所有字段：去掉首尾空格和回车
        """
        # 姓名相关字段列表
        name_fields = {
            'winner_name', 'supervisor_name', 'supervisors'
        }

        if value is None or not isinstance(value, str):
            return value

        # 1. 先去掉首尾空格和回车（所有字段）
        cleaned = value.strip()

        # 2. 去掉字段内部的回车符（所有字段）
        cleaned = cleaned.replace('\n', '').replace('\r', '')

        # 3. 对姓名字段特殊处理
        if field_name in name_fields:
            # 去掉数字
            cleaned = re.sub(r'\d+', '', cleaned)

            # 去掉常见的不应该在姓名中出现的符号
            symbols_to_remove = r'[#$%^&*@!~`|\\/:;<>\[\]{}""'']'
            cleaned = re.sub(symbols_to_remove, '', cleaned)

            # 处理多人名：去掉重复的逗号
            cleaned = re.sub(r',+', ',', cleaned)

            # 去掉所有空格
            cleaned = re.sub(r'\s+', '', cleaned)

            # 去掉首尾可能残留的逗号
            cleaned = cleaned.strip(',. ')
        else:
            # 非姓名字段：将多个空格合并为一个
            cleaned = re.sub(r'\s+', ' ', cleaned)

        # 空字符串返回None（除非是必要的保留空字符串的情况）
        if not cleaned:
            return None

        return cleaned

    def _clean_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """清理所有字段值"""
        result = {}
        for field_name, value in data.items():
            result[field_name] = self._clean_field_value(field_name, value)
        return result

    def _validate_specific_fields(self, data: Dict[str, Any]) -> Dict[str, List[ValidationError]]:
        """验证奖状特定字段"""
        content_issues = []
        completeness_issues = []

        # 调用各个验证方法
        completeness_issues.extend(self._validate_required_fields(data))
        completeness_issues.extend(self._validate_winner_name(data))
        completeness_issues.extend(self._validate_supervisor_name(data))
        completeness_issues.extend(self._validate_date_year_edition(data))
        
        content_issues.extend(self._validate_date_format_field(data))
        content_issues.extend(self._validate_year_date_consistency(data))
        content_issues.extend(self._validate_award_level(data))

        return {"content": content_issues, "completeness": completeness_issues}

    def _validate_required_fields(self, data: Dict[str, Any]) -> List[ValidationError]:
        """验证必需字段"""
        issues = []
        required_fields = {
            "competition_name": "竞赛名称",
            "award_level": "获奖等级"
        }

        for field, display_name in required_fields.items():
            if not data.get(field):
                issues.append(ValidationError(
                    field_name=field,
                    error_type="missing",
                    error_message=f"缺少{display_name}",
                    error_category="completeness"
                ))
        
        return issues

    def _validate_winner_name(self, data: Dict[str, Any]) -> List[ValidationError]:
        """验证获奖者字段"""
        issues = []
        if not data.get("winner_name"):
            issues.append(ValidationError(
                field_name="winner_name",
                error_type="missing",
                error_message="缺少获奖者信息（winner_name）",
                error_category="completeness"
            ))
        return issues

    def _validate_supervisor_name(self, data: Dict[str, Any]) -> List[ValidationError]:
        """验证指导教师字段"""
        issues = []
        # 例外：授予教师的奖状不需要指导教师
        granted_role = data.get("granted_role")
        is_teacher_award = granted_role and "教师" in str(granted_role)
        
        if not is_teacher_award:
            supervisor_name_value = data.get("supervisor_name")
            if supervisor_name_value is None or (isinstance(supervisor_name_value, str) and not supervisor_name_value.strip()):
                issues.append(ValidationError(
                    field_name="supervisor_name",
                    error_type="missing",
                    error_message="缺少指导教师（所有奖状必须填写指导教师）",
                    error_category="completeness"
                ))
        return issues

    def _validate_date_year_edition(self, data: Dict[str, Any]) -> List[ValidationError]:
        """验证日期/年份/届次组合规则：至少需要有一项"""
        issues = []
        date_value = data.get("date")
        year_value = data.get("year")
        edition_value = data.get("edition")

        date_has_value = date_value is not None and (isinstance(date_value, str) and date_value.strip())
        year_has_value = year_value is not None
        edition_has_value = edition_value is not None

        if not (date_has_value or year_has_value or edition_has_value):
            issues.append(ValidationError(
                field_name="date,year,edition",
                error_type="missing",
                error_message="奖状无日期，需人工补充日期、年份或届次",
                error_category="completeness",
                suggestion="可以补充：date、year、edition 中任意一项"
            ))
        return issues

    def _validate_date_format_field(self, data: Dict[str, Any]) -> List[ValidationError]:
        """验证日期格式"""
        issues = []
        date_value = data.get("date")
        if date_value and not self._validate_date_format(date_value):
            issues.append(ValidationError(
                field_name="date",
                error_type="invalid",
                error_message=f"日期格式不正确: {date_value}（支持格式：YYYY-MM-DD、YYYY-MM、YYYY-M、YYYY.MM）",
                error_category="content",
                invalid_value=date_value
            ))
        return issues

    def _validate_year_date_consistency(self, data: Dict[str, Any]) -> List[ValidationError]:
        """验证year和date的一致性"""
        issues = []
        date_value = data.get("date")
        year_value = data.get("year")
        
        # 只有当year不为空时才进行一致性验证
        # 如果year为空，不进行验证，让用户自己补充（不从date中恢复）
        if not date_value or year_value is None:
            return issues
        
        # 确保year_value是整数类型
        try:
            year_int = int(year_value) if not isinstance(year_value, int) else year_value
        except (ValueError, TypeError):
            return issues  # 如果year不是有效的整数，跳过验证
        
        # 从date中提取年份
        date_year = self._extract_year_from_date(date_value)
        if date_year is not None:
            # year应该等于date的year，或者比date的year早一年（因为有些比赛在年底举行，证书日期可能是下一年）
            year_diff = year_int - date_year
            if year_diff not in [0, -1]:
                issues.append(ValidationError(
                    field_name="year",
                    error_type="invalid",
                    error_message=f"年份与日期不一致: year={year_int}, date={date_value}（date中的年份为{date_year}）。year应该等于date的年份，或者比date的年份早1年",
                    error_category="content",
                    invalid_value=year_int,
                    suggestion=f"请检查年份是否正确，建议修改为 {date_year} 或 {date_year - 1}"
                ))
        return issues

    def _validate_award_level(self, data: Dict[str, Any]) -> List[ValidationError]:
        """验证获奖等级"""
        issues = []
        award_level = data.get("award_level")
        if not award_level:
            return issues
        
        # 检查是否是英文（常见英文获奖等级）
        english_levels = ["First Prize", "Second Prize", "Third Prize",
                        "Gold Medal", "Silver Medal", "Bronze Medal",
                        "Honorable Mention", "Winner"]
        if award_level in english_levels or not self._is_chinese_award_level(award_level):
            issues.append(ValidationError(
                field_name="award_level",
                error_type="invalid",
                error_message=f"获奖等级应为中文，当前为英文: {award_level}",
                error_category="content",
                invalid_value=award_level,
                suggestion="请翻译为中文，如：First Prize → 一等奖"
            ))
        return issues

    def _extract_year_from_date(self, date_str: str) -> Optional[int]:
        """
        从日期字符串中提取年份

        Args:
            date_str: 日期字符串，支持多种格式：
                - YYYY-MM-DD、YYYY-MM 或 YYYY.MM
                - YYYY年MM月DD日、YYYY年MM月、YYYY年
                - MM/DD/YYYY、DD/MM/YYYY
                - 纯数字YYYY

        Returns:
            年份（整数），如果无法提取则返回 None
        """
        if not date_str:
            return None

        import re
        date_str = date_str.strip()

        # 模式1: YYYY-MM-DD、YYYY-MM 或 YYYY.MM.DD、YYYY.MM
        pattern1 = r'^(\d{4})[-.]\d{1,2}(?:[-.]\d{1,2})?$'
        match = re.match(pattern1, date_str)
        if match:
            try:
                return int(match.group(1))
            except (ValueError, IndexError):
                pass

        # 模式2: YYYY年MM月DD日、YYYY年MM月、YYYY年
        pattern2 = r'(\d{4})年'
        match = re.search(pattern2, date_str)
        if match:
            try:
                return int(match.group(1))
            except (ValueError, IndexError):
                pass

        # 模式3: MM/DD/YYYY 或 DD/MM/YYYY（美国/欧洲格式）
        pattern3 = r'\d{1,2}/\d{1,2}/(\d{4})'
        match = re.search(pattern3, date_str)
        if match:
            try:
                return int(match.group(1))
            except (ValueError, IndexError):
                pass

        # 模式4: 纯数字YYYY（4位数字开头）
        pattern4 = r'^(\d{4})'
        match = re.match(pattern4, date_str)
        if match:
            try:
                year = int(match.group(1))
                # 确保是合理的年份（1900-2100）
                if 1900 <= year <= 2100:
                    return year
            except (ValueError, IndexError):
                pass

        return None

    def _infer_year_from_edition(self, edition_str: str) -> Optional[int]:
        """
        从届数推断年份

        对于某些比赛（如蓝桥杯），可以通过届数推断年份
        例如：第16届蓝桥杯在2024-2025年举办

        Args:
            edition_str: 届数字符串，如 "16"、"第16届"

        Returns:
            推断的年份（整数），如果无法推断则返回 None
        """
        if not edition_str:
            return None

        import re
        from datetime import datetime

        # 提取数字
        match = re.search(r'(\d+)', edition_str)
        if not match:
            return None

        try:
            edition_num = int(match.group(1))

            # 蓝桥杯的特殊规则（根据公开信息）
            # 第16届蓝桥杯 = 2024-2025年（2025年5月举办）
            # 第15届蓝桥杯 = 2023-2024年（2024年5月举办）
            # 第14届蓝桥杯 = 2022-2023年（2023年5月举办）
            # 规律：第N届在 (N+2009) 年举办，例如第16届在2025年

            # 通用规则：假设第一届在2010年，每年举办一次
            inferred_year = 2009 + edition_num

            # 确保年份合理（不超过当前年份+1）
            current_year = datetime.now().year
            if inferred_year > current_year + 1:
                # 如果推断的年份太远，返回None
                logger.warning(f"推断的年份{inferred_year}超出合理范围（当前年份{current_year}）")
                return None

            return inferred_year

        except (ValueError, IndexError):
            return None

    def _validate_date_format(self, date_str: str) -> bool:
        """验证日期格式是否为 YYYY-MM-DD、YYYY-MM 或 YYYY.MM"""
        import re
        from datetime import datetime
        
        # 检查 YYYY-MM-DD 格式
        pattern_full = r'^\d{4}-\d{2}-\d{2}$'
        if re.match(pattern_full, date_str):
            try:
                datetime.strptime(date_str, "%Y-%m-%d")
                return True
            except ValueError:
                return False
        
        # 检查 YYYY-MM 或 YYYY.MM 格式
        pattern_month = r'^\d{4}[-.]\d{1,2}$'
        if re.match(pattern_month, date_str):
            # 验证月份是否有效（1-12）
            parts = date_str.replace('.', '-').split('-')
            if len(parts) == 2:
                try:
                    month = int(parts[1])
                    if 1 <= month <= 12:
                        return True
                except ValueError:
                    pass
            return False
        
        return False

    def _is_chinese_award_level(self, level: str) -> bool:
        """检查获奖等级是否为中文"""
        # 简单检查：包含中文字符
        return any('\u4e00' <= c <= '\u9fff' for c in level)

    def extract(self, ctx: ExtractContext) -> ExtractResult:
        """执行抽取"""
        try:
            # 1. 检查文件扩展名
            ext = Path(ctx.file_path).suffix.lower()
            if not self.matches_extension(ext):
                return self._other_result("不支持的文件扩展名")

            # 2. 执行OCR（高精度）
            ocr_text = ctx.ocr_text
            ocr_cache_hit = False
            try:
                ocr_text, ocr_cache_hit = ctx.ocr_engine.get_text(
                    ctx.file_path,
                    use_cache=ctx.use_ocr_cache,
                    is_precise=True
                )
            except Exception as e:
                logger.exception("奖状抽取 OCR 失败: %s", e)
                return self._other_result(user_facing_message(e))

            if not ocr_text or not str(ocr_text).strip():
                return self._other_result("OCR识别结果为空")

            # 3. 快速筛选（如果启用）
            if self._enable_quick_screen:
                screen_ok, detail = self._quick_screen(ocr_text)
                if not screen_ok:
                    return self._other_result(f"快速OCR筛选未通过，不是奖状证书（{detail}）")

            # 4. 模板匹配和提示词生成
            template = None
            default_prompt = None
            template_default_fields = {}
            template_id = None
            template_name = None

            use_default_prompt_only = getattr(ctx, 'use_default_prompt_only', None)
            if use_default_prompt_only and self._template_manager:
                # 创建模板场景：强制使用默认提示词，不进行模板匹配
                default_prompt = self._template_manager.get_default_prompt("award")
                logger.debug("使用仅默认提示词模式（未匹配任何模板）")
            elif self._template_manager:
                match_result = self._template_manager.match_full(ocr_text)

                # 手动导入模式：即使模板匹配为other，也继续处理（使用内置提示词）
                # 只在自动模式且匹配为other时才返回失败
                # 检查上下文是否有force_type标志（手动导入）
                force_type = getattr(ctx, 'force_type', None)
                if match_result.type == "other" and not force_type:
                    return self._other_result("无法识别证书类型", template_id=None, template_name=None)

                template = match_result.template
                default_prompt = match_result.default_prompt
                
                # 保存模板信息（即使为None也要保存）
                if template:
                    template_id = template.template_id
                    template_name = template.get_display_name()
                else:
                    template_id = None
                    template_name = None

            # 5. 生成提示词
            if template:
                # 使用模板提示词
                base_fields = self._template_manager.get_base_fields(self.template_type)
                prompt = template.generate_prompt(ocr_text, base_fields)
                template_default_fields = template.default_fields.copy() if template.default_fields else {}
                logger.debug(f"使用模板提示词: {template.get_display_name()}")
            elif default_prompt:
                # 使用默认提示词
                fields_desc = self._get_fields_description()
                is_english = self._is_english_certificate(ocr_text)
                translate_note = self.ENGLISH_TRANSLATION_NOTE if is_english else ""
                prompt = default_prompt.format(
                    ocr_text=ocr_text,
                    fields_desc=fields_desc,
                    translate_note=translate_note
                )
                logger.debug("使用默认提示词")
            else:
                # 既没有模板也没有默认提示词，使用内置提示词
                is_english = self._is_english_certificate(ocr_text)
                prompt = self._build_prompt(ocr_text, is_english=is_english)
                logger.debug("使用内置提示词")

            # 6. 调用LLM抽取结构化数据
            if not ctx.llm_engine:
                return self._other_result("LLM引擎未配置", template_id=template_id, template_name=template_name)

            try:
                llm_content, llm_cache_hit = ctx.llm_engine.chat(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                    use_cache=ctx.use_llm_cache
                )

                if not llm_content:
                    return self._other_result("LLM调用失败", template_id=template_id, template_name=template_name)

            except Exception as e:
                logger.error(f"LLM调用异常: {e}")
                return self._other_result(user_facing_message(e), template_id=template_id, template_name=template_name)

            # 7. 解析LLM响应
            data = self._parse_llm_response(llm_content)

            if not data:
                return self._other_result("LLM响应解析失败", template_id=template_id, template_name=template_name)

            # 7.1 如果year为空，尝试从date或edition字段提取年份
            year = data.get('year')
            # 检查year是否有效（非None、非空字符串、非"null"字符串、非0）
            year_is_empty = (
                year is None or
                year == '' or
                str(year).strip().lower() == 'null' or
                str(year).strip() == '0' or
                (isinstance(year, int) and year == 0)
            )

            if year_is_empty:
                # 首先尝试从date字段提取
                date_value = data.get('date')
                if date_value and str(date_value).strip():
                    extracted_year = self._extract_year_from_date(str(date_value))
                    if extracted_year:
                        data['year'] = extracted_year
                        logger.info(f"从date字段提取year: {date_value} -> {extracted_year}")
                    else:
                        logger.warning(f"无法从date字段提取year: {date_value}")
                else:
                    # 如果date也为空，尝试从edition推断年份
                    edition = data.get('edition')
                    if edition and str(edition).strip():
                        inferred_year = self._infer_year_from_edition(str(edition).strip())
                        if inferred_year:
                            data['year'] = inferred_year
                            logger.info(f"从edition推断year: 第{edition}届 -> {inferred_year}年")
                        else:
                            logger.debug(f"无法从edition推断year: 第{edition}届")
                    else:
                        logger.debug("year为空，date和edition字段也为空，无法补充年份")

            # 8. 合并模板默认字段
            if template_default_fields:
                for key, value in template_default_fields.items():
                    if key not in data or data[key] is None:
                        data[key] = value

            # 9. 检查奖状有效性（手动导入/创建模板时跳过，直接使用抽取结果）
            force_type = getattr(ctx, 'force_type', None)
            if not force_type and not self._check_valid_certificate(data):
                return self._other_result("不是真实的奖状证书（可能是获奖通知、空白模板等）", template_id=template_id, template_name=template_name)

            # 10. 清理数据
            #data = self._clean_data(data)

            # 11. 补丁：如果 competition_name 为空，尝试从模板关联的竞赛中获取
            competition_name = data.get("competition_name")
            if not competition_name or not str(competition_name).strip():
                if template and hasattr(template, 'competition_id') and template.competition_id:
                    # 尝试从模板管理器中获取竞赛信息
                    try:
                        from backend.extract.template.manager import get_template_manager
                        template_manager = get_template_manager()
                        if hasattr(template_manager, 'competition_manager'):
                            competition = template_manager.competition_manager.get_competition_by_id(template.competition_id)
                            if competition and hasattr(competition, 'competition_name') and competition.competition_name:
                                data["competition_name"] = competition.competition_name
                                competition_name = competition.competition_name
                                logger.info(f"[补丁] 从模板关联的竞赛获取名称: {competition_name}")
                    except Exception as e:
                        logger.warning(f"[补丁] 从模板获取竞赛名称失败: {e}")

            # 12. 验证数据
            validation_result = self._validate_data(data)

            # 13. 检查关键字段：competition_name、winner_name、award_level
            # 如果这三个字段中任何一个为空，认为是无效的奖状，返回other类型
            winner_name = data.get("winner_name")
            award_level = data.get("award_level")

            # 检查是否为手动导入/创建模板模式（force_type 已在步骤 9 处读取，此处复用）

            # 只在自动模式下进行严格验证
            # 手动导入模式下，允许字段为空，用户可以后续填写
            if not force_type:
                # 自动模式：检查三个关键字段是否都非空
                if not competition_name or not str(competition_name).strip():
                    return self._other_result("缺少竞赛名称（competition_name），无法识别为有效奖状", template_id=template_id, template_name=template_name)

                if not winner_name or not str(winner_name).strip():
                    return self._other_result("缺少获奖者信息（winner_name），无法识别为有效奖状", template_id=template_id, template_name=template_name)

                if not award_level or not str(award_level).strip():
                    return self._other_result("缺少获奖等级（award_level），无法识别为有效奖状", template_id=template_id, template_name=template_name)
            else:
                # 手动导入模式：记录警告，但继续处理
                logger.info(f"[手动导入] 跳过严格验证，允许字段为空")

            # 13. 返回成功结果
            is_english = self._is_english_certificate(ocr_text)
            metadata = {
                "is_english": is_english,
                "template_id": template_id,
                "template_name": template_name
            }
            ocr_warning = getattr(ctx.ocr_engine, "last_ocr_warning", None)
            if ocr_warning:
                metadata["ocr_warning"] = ocr_warning
            result = ExtractResult(
                status=ExtractStatus.SUCCESS,
                data=data,
                template_type=self.template_type,
                extractor_name=self.name,
                ocr_text=ocr_text,
                ocr_cache_hit=ocr_cache_hit,
                llm_prompt=prompt,
                llm_response=llm_content,
                llm_cache_hit=llm_cache_hit,
                validation_result=validation_result,
                metadata=metadata
            )

            return result

        except Exception as e:
            logger.exception(f"奖状抽取异常: {e}")
            return ExtractResult(
                status=ExtractStatus.FILE_ERROR,
                error_message=f"处理失败: {e}",
                template_type=TemplateType.OTHER,
                extractor_name=self.name,
            )

    def _other_result(self, message: str, template_id: Optional[int] = None, template_name: Optional[str] = None) -> ExtractResult:
        """返回other类型结果"""
        return ExtractResult(
            status=ExtractStatus.SUCCESS,
            data={"note": message},
            error_message=message,
            template_type=TemplateType.OTHER,
            extractor_name=self.name,
            metadata={
                "template_id": template_id,
                "template_name": template_name
            }
        )

    def _validate_data(self, data: Dict[str, Any]) -> ValidationResult:
        """验证抽取数据，返回 ValidationResult"""
        content_issues = []
        completeness_issues = []

        # 至少需要有一个非null字段
        has_any_field = False
        for value in data.values():
            if value is not None and value != "":
                has_any_field = True
                break

        if not has_any_field:
            completeness_issues.append(ValidationError(
                field_name="all",
                error_type="missing",
                error_message="未抽取到任何有效数据",
                error_category="completeness"
            ))
            return ValidationResult(
                is_valid=False,
                content_issues=content_issues,
                completeness_issues=completeness_issues
            )

        # 调用奖状特定验证
        specific_issues = self._validate_specific_fields(data)
        content_issues.extend(specific_issues.get("content", []))
        completeness_issues.extend(specific_issues.get("completeness", []))

        is_valid = len(content_issues) == 0 and len(completeness_issues) == 0

        return ValidationResult(
            is_valid=is_valid,
            content_issues=content_issues,
            completeness_issues=completeness_issues
        )

    @classmethod
    def from_config_loader(cls, config_loader) -> "AwardExtractor":
        """从配置加载器创建抽取器"""
        config = config_loader.load_config()
        extractor_cfg = config.get("extract", {}).get(cls.template_type, {})
        return cls(extractor_cfg)
