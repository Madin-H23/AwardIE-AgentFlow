"""
模板匹配器模块

提供完整的模板匹配流程：类型检测、模板匹配、相似度计算。
"""
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Any

from .template import Template
from .competition import CompetitionMatcher
from .utils import clean_text

logger = logging.getLogger(__name__)


@dataclass
class MatchResult:
    """匹配结果数据类"""
    type: str                      # 类型: award/patent/software/other
    template: Optional[Template]    # 匹配的模板（可能为 None）
    similarity: float               # 相似度（0.0-1.0，无模板时为 0.0）
    default_prompt: Optional[str]   # 默认提示词（使用模板时为 None）

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "type": self.type,
            "template": self.template.to_dict() if self.template else None,
            "similarity": self.similarity,
            "default_prompt": self.default_prompt
        }


class TypeMatcher:
    """
    类型匹配器

    根据配置规则判断 OCR 文本属于哪种类型（奖状/专利/软著/其他）
    """

    _rules: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def load_rules(cls, config_path: str) -> None:
        """
        加载类型匹配规则

        Args:
            config_path: type_rules.json 文件路径
        """
        config_file = Path(config_path)
        if not config_file.exists():
            logger.warning(f"类型匹配规则文件不存在: {config_path}")
            cls._rules = {}
            return

        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                cls._rules = json.load(f)
            logger.info(f"加载了类型匹配规则: {list(cls._rules.keys())}")
        except Exception as e:
            logger.error(f"加载类型匹配规则失败: {e}")
            cls._rules = {}

    @classmethod
    def match(cls, ocr_text: str) -> str:
        """
        匹配文本类型

        Args:
            ocr_text: OCR 识别的文本

        Returns:
            类型: award/patent/software/other
        """
        if not ocr_text or not ocr_text.strip():
            return "other"

        # 检查规则是否已加载
        if not cls._rules:
            logger.warning("类型匹配规则未加载，无法识别证书类型。请确保已调用 TypeMatcher.load_rules() 或 TemplateMatcher.load_configs()")
            return "other"

        # 使用统一的清理函数
        clean_text_input = clean_text(ocr_text)
        text_len = len(clean_text_input)

        # 按顺序检查: patent -> software -> award
        # 注意：专利和软著的匹配条件更精确（如"专利证书"、"软件著作权"），
        # 应该优先于奖状的宽泛条件（如"证书"），避免专利证书被误判为奖状
        type_order = ["patent", "software", "award"]
        for type_name in type_order:
            if type_name not in cls._rules:
                continue
            rules = cls._rules[type_name]

            if cls._check_type(clean_text_input, text_len, rules):
                logger.debug(f"匹配到类型: {type_name}")
                return type_name

        logger.debug(f"未匹配到任何类型，文本长度: {text_len}")
        return "other"

    @classmethod
    def _check_type(cls, clean_text_input: str, text_len: int, rules: Dict[str, Any]) -> bool:
        """检查是否匹配某个类型"""
        # 检查最小字数
        min_length = rules.get('min_length', 0)
        if text_len < min_length:
            return False

        # 检查排除关键词（优先级最高）
        exclude_keywords = rules.get('exclude_keywords', [])
        for keyword in exclude_keywords:
            if keyword in clean_text_input:
                logger.debug(f"包含排除关键词: {keyword}，跳过此类型")
                return False

        # 检查条件
        conditions = rules.get('conditions', [])
        for idx, condition in enumerate(conditions):
            if cls._check_condition(clean_text_input, condition):
                return True

        return False

    @classmethod
    def _check_condition(cls, clean_text_input: str, condition: Dict[str, Any]) -> bool:
        """检查单个条件"""
        cond_type = condition.get('type')

        if cond_type == 'contains':
            keyword = condition.get('keyword', '')
            case_insensitive = condition.get('case_insensitive', False)

            if case_insensitive:
                return keyword.lower() in clean_text_input.lower()
            else:
                return keyword in clean_text_input

        elif cond_type == 'and':
            keywords = condition.get('keywords', [])
            return all(kw in clean_text_input for kw in keywords)

        return False


class TemplateMatcher:
    """
    模板匹配器

    提供完整的模板匹配流程
    """

    @classmethod
    def load_configs(cls, config_dir: str, db_path: Optional[str] = None, competition_manager=None) -> None:
        """
        加载所有配置文件

        Args:
            config_dir: 配置文件目录
            db_path: 数据库文件路径（用于加载竞赛数据）
            competition_manager: CompetitionManager 实例（优先使用）
        """
        config_path = Path(config_dir)

        # 加载类型匹配规则
        type_rules_file = config_path / "type_rules.json"
        if type_rules_file.exists():
            TypeMatcher.load_rules(str(type_rules_file))

        # 从数据库加载竞赛数据（不再从 competition.json 加载）
        if db_path or competition_manager:
            CompetitionMatcher.load_from_database(db_path=db_path, competition_manager=competition_manager)

    @classmethod
    def match_full(
        cls,
        ocr_text: str,
        templates: List[Template],
        default_prompts: Dict[str, str]
    ) -> MatchResult:
        """
        完整的模板匹配流程

        Args:
            ocr_text: OCR 识别的文本
            templates: 所有模板列表
            default_prompts: 默认提示词字典 {type: prompt}

        Returns:
            MatchResult: 匹配结果
        """
        # 第1步：类型匹配
        doc_type = TypeMatcher.match(ocr_text)

        if doc_type == "other":
            return MatchResult(
                type="other",
                template=None,
                similarity=0.0,
                default_prompt=None
            )

        # 第2步：模板匹配
        if doc_type in ["patent", "software"]:
            return cls._match_simple_type(ocr_text, doc_type, templates, default_prompts)
        else:  # award
            return cls._match_award(ocr_text, templates, default_prompts)

    @classmethod
    def _match_simple_type(
        cls,
        ocr_text: str,
        doc_type: str,
        templates: List[Template],
        default_prompts: Dict[str, str]
    ) -> MatchResult:
        """
        专利/软著的简单匹配逻辑

        - 如果只有 1 个模板 → 直接返回
        - 如果有多个 → 关键词匹配
        - 都不命中 → 返回默认提示词
        """
        # 筛选同类型模板
        type_templates = [t for t in templates if t.template_type == doc_type]

        if not type_templates:
            # 没有模板，使用默认提示词
            return MatchResult(
                type=doc_type,
                template=None,
                similarity=0.0,
                default_prompt=default_prompts.get(doc_type)
            )

        if len(type_templates) == 1:
            # 只有一个模板，直接返回
            return MatchResult(
                type=doc_type,
                template=type_templates[0],
                similarity=1.0,
                default_prompt=None
            )

        # 多个模板，进行关键词匹配
        # 使用统一的清理函数
        clean_text_input = clean_text(ocr_text)

        for template in type_templates:
            # 检查关键词（AND 关系）
            if template.keywords:
                # 同时清理关键词再匹配
                if all(clean_text(kw) in clean_text_input for kw in template.keywords):
                    return MatchResult(
                        type=doc_type,
                        template=template,
                        similarity=1.0,
                        default_prompt=None
                    )

        # 都不命中，使用默认提示词
        return MatchResult(
            type=doc_type,
            template=None,
            similarity=0.0,
            default_prompt=default_prompts.get(doc_type)
        )

    @classmethod
    def _match_award(
        cls,
        ocr_text: str,
        templates: List[Template],
        default_prompts: Dict[str, str]
    ) -> MatchResult:
        """
        奖状的复杂匹配逻辑

        1. 关键词匹配（优先，不检查长度）
           - 如果多个模板匹配，选择关键词数量最多的模板
        2. 相似度匹配（关键词未命中时）
           - 计算所有模板的相似度分数
           - 选择相似度最高且达到阈值的模板
           - 进行竞赛名称验证
        3. 如果都未匹配，使用默认提示词

        注意：匹配到模板后，根据模板的 granted_role 字段决定是教师还是学生模板
        """
        award_templates = [t for t in templates if t.template_type == "award"]
        #logger.debug(f"[关键词匹配] 开始检查 {len(award_templates)} 个奖状模板")

        if not award_templates:
            logger.debug("没有奖状模板，使用默认提示词")
            return MatchResult(
                type="award",
                template=None,
                similarity=0.0,
                default_prompt=default_prompts.get("award")
            )

        # 步骤1：关键词匹配（优先，不检查长度限制）
        keyword_matches = []
        for template in award_templates:
            #logger.debug(f"[关键词匹配] 检查模板 {template.template_id}: {template.get_display_name()}")
            #logger.debug(f"[关键词匹配]   关键词: {template.keywords}")
            match_result = template.match_by_keywords(ocr_text)
            #logger.debug(f"[关键词匹配]   结果: {'✓ 匹配' if match_result else '✗ 不匹配'}")
            if match_result:
                keyword_matches.append(template)
                #logger.debug(f"关键词匹配成功: {template.get_display_name()} (ID={template.template_id})")

        if keyword_matches:
            # 如果有多个模板匹配，按关键词数量排序（关键词多的优先）
            if len(keyword_matches) > 1:
                keyword_matches.sort(key=lambda t: len(t.keywords), reverse=True)
                #logger.debug(f"多个模板匹配，按关键词数量排序: {[(t.template_id, len(t.keywords)) for t in keyword_matches]}")

            # 选择关键词最多的模板
            template = keyword_matches[0]
            #logger.debug(f"选择关键词最多的模板: {template.get_display_name()} (ID={template.template_id}, {len(template.keywords)}个关键词)")

            # 关键词匹配成功，直接返回模板
            #logger.debug(f"关键词匹配成功，返回模板: {template.get_display_name()}")
            return MatchResult(
                type="award",
                template=template,
                similarity=1.0,
                default_prompt=None
            )

        # 步骤2：相似度匹配（关键词未命中时）
        best_template = None
        best_score = 0.0

        for template in award_templates:
            score = template.match_score(ocr_text)
            if score > best_score:
                best_score = score
                best_template = template

        logger.debug(f"相似度匹配结果: 最佳模板={best_template.get_display_name() if best_template else None}, 分数={best_score:.3f}")

        # 获取阈值
        threshold = TypeMatcher._rules.get("award", {}).get("similarity_threshold", 0.3)

        if best_template and best_score >= threshold:
            # 步骤3：竞赛名称验证
            matched_comp = CompetitionMatcher.match(ocr_text)
            template_comp = best_template.default_fields.get("competition_name", "")
            logger.debug(f"竞赛名称验证（相似度）: OCR='{matched_comp}', 模板='{template_comp}'")

            if matched_comp and matched_comp == template_comp:
                logger.debug(f"竞赛名称验证通过，返回模板: {best_template.get_display_name()}")
                return MatchResult(
                    type="award",
                    template=best_template,
                    similarity=best_score,
                    default_prompt=None
                )
            elif not matched_comp:
                # 如果没有匹配到竞赛名称，但相似度足够高，仍然返回（可能是新竞赛）
                logger.debug(f"未匹配到竞赛名称，但相似度足够，返回模板: {best_template.get_display_name()}")
                return MatchResult(
                    type="award",
                    template=best_template,
                    similarity=best_score,
                    default_prompt=None
                )

        # 竞赛名称验证失败或相似度不足，使用默认提示词
        logger.debug(f"未找到匹配模板，使用默认提示词")
        return MatchResult(
            type="award",
            template=None,
            similarity=best_score,
            default_prompt=default_prompts.get("award")
        )
