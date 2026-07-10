"""
奖状检测规则配置

所有检测规则在此配置，便于统一管理
"""

# 必填字段配置
REQUIRED_FIELDS = {
    # 所有奖状都必须有的字段
    'all': ['competition_id', 'winner_name', 'year'],

    # 学生奖状额外必填
    'student': ['award_level'],

    # 教师奖状额外必填（目前无额外要求）
    'teacher': []
}

# 业务规则配置
BUSINESS_RULES = {
    # 学生奖状建议填写指导教师（warning，不影响 is_valid）
    'student_requires_supervisor': {
        'enabled': True,
        'severity': 'warning',
        'code': 'STUDENT_NO_SUPERVISOR',
        'message': '学生奖状建议填写指导教师'
    },

    # 教师证书建议填写关联学生（warning，不影响 is_valid）
    'teacher_certificate_suggest_related_students': {
        'enabled': True,
        'severity': 'warning',
        'code': 'TEACHER_NO_RELATED_STUDENTS',
        'message': '教师证书建议填写关联学生，以便关联师生奖状'
    },

    # 获奖等级不能为空
    'award_level_required': {
        'enabled': True,
        'severity': 'error',
        'code': 'AWARD_LEVEL_MISSING',
        'message': '获奖等级不能为空'
    },

    # 竞赛等级不能为空（缺失则算异常）
    'competition_level_required': {
        'enabled': True,
        'severity': 'error',
        'code': 'COMPETITION_LEVEL_MISSING',
        'message': '竞赛等级不能为空'
    }
}

# 字段映射：前端表单字段 -> 检测字段
FIELD_MAPPING = {
    'competition_id': 'competition_id',
    'competition_name': 'competition_id',  # 最终需要映射到 competition_id
    'winner_name': 'winner_name',
    'supervisor_name': 'supervisor_name',
    'teacher_winner_ids': 'winner_name',  # 教师获奖者 ID -> winner_name
    'student_winner_ids': 'winner_name',  # 学生获奖者 ID -> winner_name
    'award_level': 'award_level',
    'competition_level': 'competition_level',
    'track': 'track',
    'year': 'year',
    'date': 'date',
    'province': 'province',
    'issuer': 'issuer',
    'project_title': 'project_title',
    'granted_role': 'granted_role',
    'related_student': 'related_student',
    'certificate_id': 'certificate_id',
    'laboratory_id': 'laboratory_id'
}
