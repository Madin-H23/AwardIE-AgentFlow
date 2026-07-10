"""
奖状检测器

提供统一的奖状数据检测功能
"""

import logging
from typing import Dict, Any, Optional, TYPE_CHECKING

from .models import ValidationResult, ValidationError, ValidationErrorSeverity
from .rules import REQUIRED_FIELDS, BUSINESS_RULES

if TYPE_CHECKING:
    from backend.models.award import Award

logger = logging.getLogger(__name__)


class AwardValidator:
    """
    奖状检测器

    用于检测奖状数据的完整性和正确性。
    可以检测字典格式的数据或 Award 对象。
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化检测器

        Args:
            config: 可选的配置，用于覆盖默认的检测规则
        """
        self.config = config or {}
        self.required_fields = self.config.get('required_fields', REQUIRED_FIELDS)
        self.business_rules = self.config.get('business_rules', BUSINESS_RULES)

    def validate(self, data: Dict[str, Any]) -> ValidationResult:
        """
        检测奖状数据

        Args:
            data: 奖状数据字典，需包含以下关键字段：
                - competition_id: int
                - winner_name: str
                - supervisor_name: str (可选)
                - granted_role: str ('学生' 或 '教师')
                - related_student: str (教师奖状可选)
                - award_level: str
                - year: int
                - 以及其他奖状字段

        Returns:
            ValidationResult: 检测结果
        """
        completeness_issues = []
        content_issues = []
        warnings = []

        # 确定证书类型
        granted_role = data.get('granted_role', '学生')
        is_student_certificate = granted_role and '学生' in granted_role
        is_teacher_certificate = granted_role and '教师' in granted_role

        # 1. 检测必填字段
        completeness_issues.extend(self._check_required_fields(data, is_student_certificate))

        # 2. 检测业务规则
        content_issues.extend(self._check_business_rules(data, is_student_certificate, is_teacher_certificate))

        # 3. 生成警告
        warnings.extend(self._generate_warnings(data, is_student_certificate, is_teacher_certificate))

        # 判断是否通过检测（只有 error 级别的问题会导致不通过）
        is_valid = not any(issue.severity.value == 'error'
                         for issue in completeness_issues + content_issues)

        return ValidationResult(
            is_valid=is_valid,
            completeness_issues=completeness_issues,
            content_issues=content_issues,
            warnings=warnings
        )

    def validate_for_db_object(self, award: 'Award') -> ValidationResult:
        """
        检测数据库中的 Award 对象

        Args:
            award: Award 对象

        Returns:
            ValidationResult: 检测结果
        """
        # 将 Award 对象转换为字典
        data = self._award_to_dict(award)
        return self.validate(data)

    def _award_to_dict(self, award: 'Award') -> Dict[str, Any]:
        """将 Award 对象转换为字典格式"""
        return {
            'competition_id': award.competition_id,
            'winner_name': award.winner_name,
            'supervisor_name': award.supervisor_name,
            'granted_role': award.granted_role,
            'related_student': award.related_student_name,
            'award_level': award.award_level,
            'competition_level': award.competition_level,
            'year': award.year,
            'track': award.track,
            'date': award.date,
            'province': award.province,
            'issuer': award.issuer,
            'project_title': award.project_title,
            'certificate_id': award.certificate_id,
            'laboratory_id': award.laboratory_id
        }

    def _check_required_fields(self, data: Dict[str, Any],
                               is_student_certificate: bool) -> list:
        """检测必填字段"""
        issues = []

        # 获取该类型证书的必填字段列表
        required = self.required_fields.get('all', []).copy()
        if is_student_certificate:
            required.extend(self.required_fields.get('student', []))
        else:
            required.extend(self.required_fields.get('teacher', []))

        # 检测每个必填字段
        for field in required:
            value = data.get(field)
            if value is None or value == '' or value == 'None':
                issues.append(ValidationError.error(
                    field=field,
                    message=f'必填字段缺失: {self._get_field_display_name(field)}',
                    code='REQUIRED_FIELD_MISSING'
                ))

        return issues

    def _check_business_rules(self, data: Dict[str, Any],
                              is_student_certificate: bool,
                              is_teacher_certificate: bool) -> list:
        """检测业务规则"""
        issues = []

        # 规则1: 学生奖状必须有指导教师
        if is_student_certificate:
            rule = self.business_rules.get('student_requires_supervisor')
            if rule and rule.get('enabled'):
                supervisor_name = data.get('supervisor_name')
                if not supervisor_name or supervisor_name.strip() == '':
                    issues.append(ValidationError(
                        field='supervisor_name',
                        message=rule['message'],
                        severity=ValidationErrorSeverity.ERROR,
                        code=rule['code']
                    ))

        # 规则2: 获奖等级不能为空（学生奖状）
        if is_student_certificate:
            rule = self.business_rules.get('award_level_required')
            if rule and rule.get('enabled'):
                award_level = data.get('award_level')
                if not award_level or award_level.strip() == '':
                    issues.append(ValidationError(
                        field='award_level',
                        message=rule['message'],
                        severity=ValidationErrorSeverity.ERROR,
                        code=rule['code']
                    ))

        # 规则3: 竞赛等级不能为空（所有奖状，缺失则算异常）
        rule = self.business_rules.get('competition_level_required')
        if rule and rule.get('enabled'):
            competition_level = data.get('competition_level')
            if not competition_level or str(competition_level).strip() == '':
                issues.append(ValidationError(
                    field='competition_level',
                    message=rule['message'],
                    severity=ValidationErrorSeverity.ERROR,
                    code=rule['code']
                ))

        return issues

    def _generate_warnings(self, data: Dict[str, Any],
                           is_student_certificate: bool,
                           is_teacher_certificate: bool) -> list:
        """生成警告"""
        warnings = []

        # 警告1: 教师证书建议填写关联学生
        if is_teacher_certificate:
            rule = self.business_rules.get('teacher_certificate_suggest_related_students')
            if rule and rule.get('enabled'):
                related_student = data.get('related_student')
                if not related_student or related_student.strip() == '':
                    warnings.append(ValidationError(
                        field='related_student',
                        message=rule['message'],
                        severity=ValidationErrorSeverity.WARNING,
                        code=rule['code']
                    ))

        return warnings

    def _get_field_display_name(self, field: str) -> str:
        """获取字段的显示名称"""
        display_names = {
            'competition_id': '竞赛',
            'winner_name': '获奖者',
            'year': '年份',
            'award_level': '获奖等级',
            'competition_level': '竞赛等级',
            'supervisor_name': '指导教师',
            'related_student': '关联学生'
        }
        return display_names.get(field, field)
