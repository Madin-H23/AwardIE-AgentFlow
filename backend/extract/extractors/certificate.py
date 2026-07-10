"""
证书抽取器：专利和软著抽取器

支持从PDF/图片格式的专利证书和软件著作权证书中提取结构化数据。
"""
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.extract.extractors.base import ExtractContext, Extractor
from backend.extract.types import (
    ExtractResult, ExtractStatus, TemplateType,
    ValidationResult, ValidationError
)

logger = logging.getLogger(__name__)


class CertificateExtractor(Extractor):
    """
    证书抽取器基类

    用于从PDF/图片格式的证书中提取结构化数据。
    使用OCR识别文本，然后通过LLM进行结构化抽取。
    """

    # 子类需要定义这些类属性
    template_type: str = ""
    fields_name: str = ""
    prompt_template: str = ""

    def __init__(self, config: Dict[str, Any]):
        """
        初始化证书抽取器

        Args:
            config: 配置字典，包含：
                - extensions: 支持的文件扩展名列表
                - keywords: 关键词列表
                - min_confidence: 最小置信度
        """
        # 获取子类定义的类型和模板
        template_type = getattr(self.__class__, 'template_type', '')
        fields_name = getattr(self.__class__, 'fields_name', '')

        # 加载字段定义
        fields_file = config.get("fields_file", f"{fields_name}_fields.json")
        self._fields = self._load_fields(fields_file)

        # 构建关键词列表
        keywords = config.get("keywords", [])
        if isinstance(keywords, list):
            keywords = [k for k in keywords if k]
        else:
            keywords = []

        # 获取最小置信度
        self._min_confidence = config.get("min_confidence", 0.3)

        # 获取子类自定义的描述（必须定义）
        description = getattr(self.__class__, 'description', None)
        if description is None:
            raise ValueError(f"{self.__class__.__name__} 必须定义 'description' 类属性")
        
        judgment_text = getattr(self.__class__, 'judgment_text', None)
        if judgment_text is None:
            raise ValueError(f"{self.__class__.__name__} 必须定义 'judgment_text' 类属性")

        # 初始化基类
        super().__init__(
            name=template_type,
            description=description,
            keywords=keywords,
            judgment_text=judgment_text,
            extensions=config.get("extensions", [".pdf", ".jpg", ".jpeg", ".png", ".jfif"]),
        )

        self._config = config

    def _load_fields(self, fields_file: str) -> Dict[str, str]:
        """加载字段定义。路径固定为 backend/extract/prompts/{fields_file}。"""
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
        lines.append("}")
        lines.append("")
        lines.append("注意：")
        lines.append("- 如果某个字段无法从文本中提取，请使用null")
        lines.append("- 日期格式必须为YYYY-MM-DD")
        lines.append("- 不要返回除了json字符串之外的任何内容")
        return "\n".join(lines)

    def _build_prompt(self, ocr_text: str) -> str:
        """构建LLM提示词"""
        # 使用子类定义的提示词模板
        prompt_template = getattr(self.__class__, 'prompt_template', '')

        if not prompt_template:
            # 默认提示词
            prompt_template = """你是一个专业的证书信息提取助手。请从以下OCR识别的文本中提取{template_type}信息。

{ocr_text}

{fields_description}"""

        fields_desc = self._get_fields_description()

        return prompt_template.format(
            template_type=self.template_type,
            ocr_text=ocr_text,
            fields_description=fields_desc
        )

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

        # 调用子类特定的验证
        specific_issues = self._validate_specific_fields(data)
        content_issues.extend(specific_issues.get("content", []))
        completeness_issues.extend(specific_issues.get("completeness", []))

        is_valid = len(content_issues) == 0 and len(completeness_issues) == 0

        return ValidationResult(
            is_valid=is_valid,
            content_issues=content_issues,
            completeness_issues=completeness_issues
        )

    def _validate_specific_fields(self, data: Dict[str, Any]) -> Dict[str, List[ValidationError]]:
        """
        验证特定字段（由子类覆盖）

        Returns:
            {"content": [...], "completeness": [...]}
        """
        return {"content": [], "completeness": []}

    def extract(self, ctx: ExtractContext) -> ExtractResult:
        """
        执行抽取

        Args:
            ctx: 抽取上下文

        Returns:
            抽取结果
        """
        try:
            # 1. 检查文件扩展名
            ext = Path(ctx.file_path).suffix.lower()
            if not self.matches_extension(ext):
                return self._other_result("不支持的文件扩展名")

            # 2. 执行OCR（如果ocr_text为空）
            ocr_text = ctx.ocr_text
            ocr_cache_hit = False

            if not ocr_text:
                if not ctx.ocr_engine:
                    return self._other_result("OCR引擎未配置")

                # 使用OCR引擎提取文本
                cache_enabled = ctx.use_ocr_cache
                ocr_text, from_cache = ctx.ocr_engine.get_text(
                    ctx.file_path,
                    use_cache=cache_enabled,
                    is_precise=True
                )
                ocr_cache_hit = from_cache

            # 3. 检查关键词匹配（手动导入模式下跳过）
            force_type = getattr(ctx, 'force_type', None)
            if not force_type:
                # 只在自动模式下检查关键词
                if not self.matches_keywords(ocr_text):
                    return self._other_result("不是证书文件")
            else:
                # 手动导入模式：记录日志，继续处理
                logger.info(f"[手动导入] 跳过关键词匹配检查")

            # 4. 调用LLM抽取结构化数据
            if not ctx.llm_engine:
                return self._other_result("LLM引擎未配置")

            prompt = self._build_prompt(ocr_text)

            try:
                # LLMEngine.chat() 接受 messages 格式: [{"role": "user", "content": "..."}]
                # 返回 (response_text, from_cache)
                llm_content, llm_cache_hit = ctx.llm_engine.chat(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                    use_cache=ctx.use_llm_cache
                )

                if not llm_content:
                    return self._other_result("LLM调用失败")

            except Exception as e:
                logger.error(f"LLM调用异常: {e}")
                return self._other_result(f"LLM调用异常: {e}")

            # 5. 解析LLM响应
            data = self._parse_llm_response(llm_content)

            if not data:
                return self._other_result("LLM响应解析失败")

            # 6. 验证数据
            validation_result = self._validate_data(data)

            # 如果没有任何有效数据，返回失败
            if not validation_result.is_valid and not any(
                v for v in data.values() if v
            ):
                return self._other_result("抽取数据验证失败")

            # 7. 返回成功结果
            logger.info(f"{self.template_type}抽取成功: {data.get(list(data.keys())[0])}")

            metadata = {}
            ocr_warning = getattr(ctx.ocr_engine, "last_ocr_warning", None) if ctx.ocr_engine else None
            if ocr_warning:
                metadata["ocr_warning"] = ocr_warning
            return ExtractResult(
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

        except Exception as e:
            logger.exception(f"{self.template_type}抽取异常: {e}")
            return ExtractResult(
                status=ExtractStatus.FILE_ERROR,
                error_message=f"处理失败: {e}",
                template_type=TemplateType.OTHER,
                extractor_name=self.name,
            )

    def _other_result(self, message: str) -> ExtractResult:
        """返回other类型结果"""
        return ExtractResult(
            status=ExtractStatus.SUCCESS,
            data={"note": message},
            template_type=TemplateType.OTHER,
            extractor_name=self.name,
        )

    @classmethod
    def from_config_loader(cls, config_loader) -> "CertificateExtractor":
        """从配置加载器创建抽取器"""
        config = config_loader.load_config()
        extractor_cfg = config.get("extract", {}).get(cls.template_type, {})
        return cls(extractor_cfg)


class PatentExtractor(CertificateExtractor):
    """
    专利证书抽取器

    从专利证书（PDF/图片）中提取专利信息。
    """

    template_type = "patent"
    fields_name = "patent"
    description = f"专利证书"
    judgment_text = "通常包含：专利名称 + 专利类型（发明专利/实用新型/外观设计）+ 申请日期 + 发明人 + 专利号"

    # 专利抽取提示词模板
    prompt_template = """你是一个专业的专利证书信息提取助手。请从以下OCR识别的文本中提取专利信息。

{ocr_text}

{fields_description}

额外注意：
- patent_type: 只能是"发明专利"、"实用新型"或"外观设计"之一
- application_date: 申请日期格式必须为YYYY-MM-DD，如无法确定具体日期则使用当年1月1日
- inventor: 发明人多人用逗号分隔，如"张三,李四,王五"
"""

    def _validate_specific_fields(self, data: Dict[str, Any]) -> Dict[str, List[ValidationError]]:
        """验证专利特定字段"""
        content_issues = []
        completeness_issues = []

        # 必需字段检查
        required_fields = {
            "patent_name": "专利名称",
            "patent_type": "专利类型",
            "application_number": "申请号"
        }

        for field, display_name in required_fields.items():
            if not data.get(field):
                completeness_issues.append(ValidationError(
                    field_name=field,
                    error_type="missing",
                    error_message=f"缺少{display_name}",
                    error_category="completeness"
                ))

        # 专利类型验证
        patent_type = data.get("patent_type", "")
        if patent_type and patent_type not in ["发明专利", "实用新型", "外观设计"]:
            content_issues.append(ValidationError(
                field_name="patent_type",
                error_type="invalid",
                error_message=f"专利类型不正确: {patent_type}（应为：发明专利、实用新型、外观设计之一）",
                error_category="content",
                invalid_value=patent_type
            ))

        # 申请日期格式验证
        application_date = data.get("application_date", "")
        if application_date:
            if not self._validate_date_format(application_date):
                content_issues.append(ValidationError(
                    field_name="application_date",
                    error_type="invalid",
                    error_message=f"申请日期格式不正确: {application_date}（应为YYYY-MM-DD）",
                    error_category="content",
                    invalid_value=application_date
                ))

        return {"content": content_issues, "completeness": completeness_issues}

    @staticmethod
    def _validate_date_format(date_str: str) -> bool:
        """验证日期格式是否为 YYYY-MM-DD"""
        import re
        pattern = r'^\d{4}-\d{2}-\d{2}$'
        if not re.match(pattern, date_str):
            return False
        try:
            from datetime import datetime
            datetime.strptime(date_str, "%Y-%m-%d")
            return True
        except ValueError:
            return False


class SoftwareExtractor(CertificateExtractor):
    """
    软件著作权证书抽取器

    从软件著作权证书（PDF/图片）中提取软著信息。
    """

    template_type = "software"
    fields_name = "software"
    description = f"软著证书"
    judgment_text = "通常包含：软件名称 + 登记日期 + 著作权人 + 登记号"

    # 软著抽取提示词模板
    prompt_template = """你是一个专业的软件著作权证书信息提取助手。请从以下OCR识别的文本中提取软件著作权信息。

{ocr_text}

{fields_description}

额外注意：
- software_version: 版本号格式如V1.0、V2.1.3，保留V前缀
- registration_number: 登记号格式如2023SR123456
- certificate_no: 证书号格式如"软著登字第XXXX号"
- registration_date: 登记日期格式必须为YYYY-MM-DD
- copyright_owner: 著作权人多个用逗号分隔
"""

    def _validate_specific_fields(self, data: Dict[str, Any]) -> Dict[str, List[ValidationError]]:
        """验证软著特定字段"""
        content_issues = []
        completeness_issues = []

        # 必需字段检查
        required_fields = {
            "software_name": "软件名称",
            "registration_number": "登记号"
        }

        for field, display_name in required_fields.items():
            if not data.get(field):
                completeness_issues.append(ValidationError(
                    field_name=field,
                    error_type="missing",
                    error_message=f"缺少{display_name}",
                    error_category="completeness"
                ))

        # 登记日期格式验证
        registration_date = data.get("registration_date", "")
        if registration_date:
            if not self._validate_date_format(registration_date):
                content_issues.append(ValidationError(
                    field_name="registration_date",
                    error_type="invalid",
                    error_message=f"登记日期格式不正确: {registration_date}（应为YYYY-MM-DD）",
                    error_category="content",
                    invalid_value=registration_date
                ))

        return {"content": content_issues, "completeness": completeness_issues}

    @staticmethod
    def _validate_date_format(date_str: str) -> bool:
        """验证日期格式是否为 YYYY-MM-DD"""
        import re
        pattern = r'^\d{4}-\d{2}-\d{2}$'
        if not re.match(pattern, date_str):
            return False
        try:
            from datetime import datetime
            datetime.strptime(date_str, "%Y-%m-%d")
            return True
        except ValueError:
            return False
