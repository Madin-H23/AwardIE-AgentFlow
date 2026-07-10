"""
模板管理器模块

管理奖状、专利、软著三种类型的证书模板。
"""
import json
import logging
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Any

from .template import Template
from .matcher import TemplateMatcher, MatchResult, TypeMatcher
from ..types import TemplateList

logger = logging.getLogger(__name__)


class TemplateManager:
    """
    模板管理器

    支持管理三种类型的证书模板：奖状、专利、软著

    使用示例:
        >>> manager = TemplateManager(db_path="data/validation.db", config_dir="config")
        >>> template = manager.match_template(ocr_text)
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        base_fields_map: Optional[Dict[str, Dict[str, str]]] = None,
        config_dir: Optional[str] = None
    ):
        """
        初始化模板管理器

        Args:
            db_path: 数据库文件路径（与验证规则共用数据库）
            base_fields_map: 各类型的字段定义映射 {type: fields_dict}
            config_dir: 配置文件目录（包含 type_rules.json 等）
        """
        self.db_path = Path(db_path) if db_path else None
        self.base_fields_map = base_fields_map or {}
        self.templates: TemplateList = []
        self.default_prompts: Dict[str, str] = {}

        # 加载配置文件
        if config_dir:
            self._load_configs(config_dir)
        elif self.db_path:
            # 默认使用数据库目录的 config 子目录
            config_path = self.db_path.parent / "config"
            if config_path.exists():
                self._load_configs(str(config_path))

        # 从数据库加载模板
        if self.db_path:
            self._load_from_db()
        else:
            logger.warning("未指定数据库路径，模板管理器将无法加载模板")

        logger.info(f"模板管理器初始化完成，加载了 {len(self.templates)} 个模板")

    def _get_db_connection(self):
        """获取数据库连接"""
        if not self.db_path:
            raise ValueError("数据库路径未设置")
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    # ==================== 存储操作 ====================

    def _load_from_db(self) -> None:
        """从数据库加载模板"""
        if not self.db_path or not self.db_path.exists():
            logger.warning(f"数据库文件不存在: {self.db_path}")
            return

        try:
            # 尝试初始化数据库表（如果migrations模块存在）
            try:
                # 旧的migrations模块已被移除
                # from backend.document_extract.migrations.init_template_tables import init_template_tables
                # init_template_tables(str(self.db_path))

                # 检查是否有新的migrations模块
                try:
                    from backend.extract.migrations.init_template_tables import init_template_tables
                    init_template_tables(str(self.db_path))
                except (ImportError, ModuleNotFoundError):
                    # migrations 模块不存在，假设表已经存在
                    logger.debug("migrations 模块不存在，假设表已经存在")
            except Exception as e:
                logger.warning(f"表初始化失败: {e}")

            conn = self._get_db_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM templates ORDER BY id")
            rows = cursor.fetchall()

            self.templates = [Template.from_db_row(row) for row in rows]
            conn.close()

            logger.info(f"从数据库加载了 {len(self.templates)} 个模板")
            # 输出每个模板的详细信息（调试用）
            for t in self.templates:
                logger.debug(f"  - 模板 {t.template_id}: {t.get_display_name()}, 关键词={t.keywords}")

        except Exception as e:
            logger.error(f"从数据库加载模板失败: {e}", exc_info=True)
            self.templates = []

    def _save_template_to_db(self, template: Template) -> Optional[int]:
        """
        保存模板到数据库

        Args:
            template: 模板对象

        Returns:
            模板 ID（如果是新插入的）
        """
        if not self.db_path:
            logger.error("数据库路径未设置，无法保存模板")
            return None

        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()

            # 将复杂数据类型转换为 JSON 字符串
            keywords_json = json.dumps(template.keywords, ensure_ascii=False)
            default_fields_json = json.dumps(template.default_fields, ensure_ascii=False)
            llm_fields_json = json.dumps(template.llm_fields, ensure_ascii=False)
            is_manual_edited = 1 if template.is_manual_edited else 0
            need_translate = 1 if template.need_translate else 0
            sample_image_blob = template.get_sample_image_bytes()

            if template.template_id:
                # 更新现有记录
                cursor.execute("""
                    UPDATE templates
                    SET template_type = ?,
                        min_length = ?,
                        max_length = ?,
                        keywords = ?,
                        sample_text = ?,
                        sample_extracted = ?,
                        default_fields = ?,
                        llm_fields = ?,
                        language = ?,
                        need_translate = ?,
                        is_manual_edited = ?,
                        sample_image_blob = ?,
                        competition_id = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (
                    template.template_type,
                    template.min_length,
                    template.max_length,
                    keywords_json,
                    template.sample_text,
                    template.sample_extracted,
                    default_fields_json,
                    llm_fields_json,
                    template.language,
                    need_translate,
                    is_manual_edited,
                    sample_image_blob,
                    template.competition_id,
                    template.template_id
                ))
                conn.commit()
                conn.close()
                return template.template_id
            else:
                # 插入新记录
                cursor.execute("""
                    INSERT INTO templates (
                        template_type, min_length, max_length, keywords,
                        sample_text, sample_extracted, default_fields, llm_fields,
                        language, need_translate, is_manual_edited, sample_image_blob, competition_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    template.template_type,
                    template.min_length,
                    template.max_length,
                    keywords_json,
                    template.sample_text,
                    template.sample_extracted,
                    default_fields_json,
                    llm_fields_json,
                    template.language,
                    need_translate,
                    is_manual_edited,
                    sample_image_blob,
                    template.competition_id
                ))
                new_id = cursor.lastrowid
                template.template_id = new_id
                conn.commit()
                conn.close()
                return new_id

        except Exception as e:
            logger.error(f"保存模板到数据库失败: {e}", exc_info=True)
            return None

    def _delete_template_from_db(self, template_id: int) -> bool:
        """
        从数据库删除模板

        Args:
            template_id: 模板 ID

        Returns:
            是否删除成功
        """
        if not self.db_path:
            logger.error("数据库路径未设置，无法删除模板")
            return False

        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()

            cursor.execute("DELETE FROM templates WHERE id = ?", (template_id,))
            deleted = cursor.rowcount > 0

            conn.commit()
            conn.close()

            return deleted

        except Exception as e:
            logger.error(f"从数据库删除模板失败: {e}", exc_info=True)
            return False

    # ==================== 模板 CRUD ====================

    def add_template(self, template: Template) -> bool:
        """
        添加模板

        Args:
            template: 证书模板实例

        Returns:
            是否添加成功（如果已存在则返回 False）
        """
        # 检查是否已存在（相同类型和默认字段名称）
        for t in self.templates:
            if (t.template_type == template.template_type and
                t.get_display_name() == template.get_display_name()):
                return False

        # 保存到数据库
        template_id = self._save_template_to_db(template)
        if template_id is None:
            return False

        self.templates.append(template)
        logger.info(f"添加模板: {template}")
        return True

    def get_template(
        self,
        template_id: int
    ) -> Optional[Template]:
        """
        获取指定 ID 的模板

        Args:
            template_id: 模板 ID

        Returns:
            匹配的模板，未找到返回 None
        """
        for template in self.templates:
            if template.template_id == template_id:
                return template
        return None

    def get_all_templates(self) -> TemplateList:
        """获取所有模板"""
        return self.templates.copy()

    def get_templates_by_type(self, template_type: str) -> TemplateList:
        """
        获取指定类型的所有模板

        Args:
            template_type: 模板类型（award/patent/software）

        Returns:
            该类型的模板列表
        """
        return [t for t in self.templates if t.template_type == template_type]

    def get_template_count(self) -> int:
        """获取模板数量"""
        return len(self.templates)

    def update_template(self, template: Template) -> bool:
        """
        更新模板

        Args:
            template: 要更新的模板对象（必须有 template_id）

        Returns:
            是否更新成功
        """
        if template.template_id is None:
            logger.error("无法更新模板：template_id 为 None")
            return False

        # 检查模板是否存在
        existing = self.get_template(template.template_id)
        if not existing:
            logger.error(f"无法更新模板：template_id={template.template_id} 不存在")
            return False

        # 保存到数据库
        new_id = self._save_template_to_db(template)
        if new_id is None:
            return False

        # 更新内存中的模板
        for i, t in enumerate(self.templates):
            if t.template_id == template.template_id:
                self.templates[i] = template
                logger.info(f"更新模板: {template}")
                return True

        return False

    def delete_template(self, template_id: int) -> bool:
        """
        删除指定 ID 的模板

        Args:
            template_id: 模板 ID

        Returns:
            是否删除成功
        """
        # 从数据库删除
        if not self._delete_template_from_db(template_id):
            return False

        # 从内存中删除
        for i, template in enumerate(self.templates):
            if template.template_id == template_id:
                removed = self.templates.pop(i)
                logger.info(f"删除模板: {removed}")
                return True

        logger.warning(f"未找到要删除的模板: template_id={template_id}")
        return False

    def clear_templates(self) -> None:
        """清空所有模板"""
        if not self.db_path:
            logger.error("数据库路径未设置，无法清空模板")
            return

        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM templates")
            conn.commit()
            conn.close()

            count = len(self.templates)
            self.templates.clear()
            logger.info(f"清空了所有模板 (共 {count} 个)")
        except Exception as e:
            logger.error(f"清空模板失败: {e}", exc_info=True)

    def clear_templates_by_type(self, template_type: str) -> int:
        """清空指定类型的所有模板"""
        if not self.db_path:
            logger.error("数据库路径未设置，无法清空模板")
            return 0

        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM templates WHERE template_type = ?", (template_type,))
            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()

            original_count = len(self.templates)
            self.templates = [t for t in self.templates if t.template_type != template_type]
            logger.info(f"清空了 {template_type} 类型模板，共 {deleted_count} 个")
            return deleted_count
        except Exception as e:
            logger.error(f"清空模板失败: {e}", exc_info=True)
            return 0

    # ==================== 配置加载 ====================

    def _load_configs(self, config_dir: str) -> None:
        """
        加载配置文件

        Args:
            config_dir: 配置文件目录
        """
        config_path = Path(config_dir)
        if not config_path.exists():
            logger.warning(f"配置目录不存在: {config_path}")
            return

        # 获取竞赛数据库路径（用于加载竞赛数据）
        db_path = None
        try:
            from config.loader import get_config
            config_loader = get_config()
            db_path = str(config_loader.get_path("database", "competitions_db"))
        except Exception as e:
            logger.debug(f"无法从配置获取竞赛数据库路径，将跳过竞赛数据加载: {e}")

        # 使用 TemplateMatcher 加载所有配置（包括从数据库加载竞赛数据）
        TemplateMatcher.load_configs(str(config_path), db_path=db_path)

        # 加载默认提示词（从 prompts 目录加载）
        prompts_dir = config_path.parent / "prompts"
        default_prompt_file = prompts_dir / "default_prompt.json"

        if default_prompt_file.exists():
            try:
                with open(default_prompt_file, 'r', encoding='utf-8') as f:
                    self.default_prompts = json.load(f)
            except Exception as e:
                logger.warning(f"加载默认提示词失败: {e}")

    # ==================== 匹配操作 ====================

    def match_template(self, ocr_text: str) -> Optional[Template]:
        """
        匹配最佳模板

        Args:
            ocr_text: OCR 识别的文本

        Returns:
            匹配的模板，未匹配返回 None
        """
        match_result = self.match_full(ocr_text)
        return match_result.template

    def match_type(self, ocr_text: str) -> str:
        """
        识别文档类型

        Args:
            ocr_text: OCR 识别的文本

        Returns:
            文档类型（award/patent/software/other）
        """
        return TypeMatcher.match(ocr_text)

    def match_full(self, ocr_text: str) -> MatchResult:
        """
        完整的模板匹配流程

        返回类型、模板、相似度和默认提示词

        Args:
            ocr_text: OCR 识别的文本

        Returns:
            MatchResult: 包含 type、template、similarity、default_prompt
        """
        return TemplateMatcher.match_full(
            ocr_text=ocr_text,
            templates=self.templates,
            default_prompts=self.default_prompts
        )

    def get_default_prompt(self, template_type: str) -> Optional[str]:
        """
        获取指定类型的默认提示词（未匹配到模板时使用）。

        Args:
            template_type: 模板类型（award/patent/software）

        Returns:
            默认提示词字符串，未配置则返回 None
        """
        return self.default_prompts.get(template_type)

    # ==================== 字段定义管理 ====================

    def get_base_fields(self, template_type: str) -> Dict[str, str]:
        """
        获取指定类型的基础字段定义

        Args:
            template_type: 模板类型

        Returns:
            字段定义字典
        """
        return self.base_fields_map.get(template_type, {})

    def set_base_fields(self, template_type: str, fields: Dict[str, str]) -> None:
        """
        设置指定类型的基础字段定义

        Args:
            template_type: 模板类型
            fields: 字段定义字典
        """
        self.base_fields_map[template_type] = fields

    # ==================== 统计信息 ====================

    def get_stats(self) -> Dict[str, Any]:
        """
        获取模板统计信息

        Returns:
            统计信息字典
        """
        stats = {
            "total": len(self.templates),
            "by_type": {},
            "by_name": {}
        }

        for template in self.templates:
            # 按类型统计
            type_name = template.get_type_display_name()
            stats["by_type"][type_name] = stats["by_type"].get(type_name, 0) + 1

            # 按名称统计
            display_name = template.get_display_name()
            key = f"{type_name}:{display_name}"
            stats["by_name"][key] = stats["by_name"].get(key, 0) + 1

        return stats

    # ==================== 批量操作 ====================

    def add_templates_from_data(
        self,
        templates_data: List[Dict[str, Any]]
    ) -> int:
        """
        从数据列表批量添加模板

        Args:
            templates_data: 模板数据字典列表

        Returns:
            添加的模板数量
        """
        count = 0
        for data in templates_data:
            try:
                template = Template.from_dict(data)
                if self.add_template(template):
                    count += 1
            except Exception as e:
                logger.error(f"添加模板失败: {e}")
                continue

        return count

    # ==================== 字符串表示 ====================

    def __str__(self) -> str:
        return f"TemplateManager(templates={len(self.templates)})"

    def __repr__(self) -> str:
        return self.__str__()
