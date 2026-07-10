"""
管理员 - 奖状模板管理路由
"""
import logging
import json
from pathlib import Path
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, current_app

from app.auth import require_role
from app.utils import get_app_context_instance

logger = logging.getLogger(__name__)
bp = Blueprint('admin_templates', __name__)

# ==================== 奖状模板管理 ====================

class TemplateAdapter:
    """适配器类，将 document_extract 的 Template 对象适配为页面期望的格式"""
    def __init__(self, template, competition_manager, base_fields=None):
        self._template = template
        self._competition_manager = competition_manager
        self.id = template.template_id
        self.is_manual_edited = template.is_manual_edited
        self.sample_text = template.sample_text
        self.sample_extracted = template.sample_extracted

        # 从 default_fields 中提取信息
        self.default_fields = template.default_fields or {}
        self.llm_fields = template.llm_fields or {}
        self.granted_role = self.default_fields.get('granted_role')

        # 基础字段定义（从 template_manager 获取）
        self.base_fields = base_fields or {}

        # 获取 competition_id（优先从模板对象获取，否则从 competition_name 查找）
        self.competition_id = getattr(template, 'competition_id', None)
        if not self.competition_id:
            competition_name = self.default_fields.get('competition_name')
            if competition_name and competition_manager:
                # 尝试通过名称查找竞赛ID
                try:
                    competitions = competition_manager.competitions if hasattr(competition_manager, 'competitions') else competition_manager._competitions
                    for comp in competitions:
                        if comp.name == competition_name:
                            self.competition_id = comp.id
                            break
                except:
                    pass

        # 关键词列表（兼容 AwardTemplate 的接口）
        self.competition_keywords = template.keywords or []
        self.extend_keywords = []  # Template 没有 extend_keywords，设为空列表

        # 处理授予角色：如果未设置或为空，默认为学生
        if not self.granted_role or not self.granted_role.strip():
            self.granted_role = '学生'

    def get_competition_name(self):
        """获取竞赛名称"""
        return self.default_fields.get('competition_name', '未知')

    def get_display_name(self):
        """获取显示名称"""
        return self._template.get_display_name()

    def get_sample_image_bytes(self):
        """获取样本图片二进制数据"""
        return self._template.get_sample_image_bytes()

@bp.route('/templates')
@require_role('admin')
def templates_list():
    """奖状模板管理主页"""
    try:
        app_context = get_app_context_instance()
        competition_manager = app_context.get_competition_manager()
        
        # 从 ServiceContext 获取 TemplateManager（使用 competitions.db）
        from app.utils import get_doc_rec_context
        doc_rec_context = get_doc_rec_context()
        template_manager = doc_rec_context.template_manager

        # 获取查询参数
        tab = request.args.get('tab', 'list')  # list, detail, create, test
        competition_id = request.args.get('competition_id', type=int)
        granted_role = request.args.get('granted_role', '').strip()
        template_id = request.args.get('template_id', type=int)
        index = request.args.get('index', type=int)  # 用于详细视图的导航

        # 获取所有 award 类型的模板
        all_templates_raw = template_manager.get_templates_by_type('award')

        # 获取 award 类型的 base_fields
        base_fields = template_manager.get_base_fields('award')

        # 转换为适配器对象
        all_templates = [TemplateAdapter(t, competition_manager, base_fields) for t in all_templates_raw]

        # 筛选模板
        filtered_templates = all_templates
        if competition_id:
            filtered_templates = [t for t in filtered_templates if t.competition_id == competition_id]
        if granted_role:
            filtered_templates = [t for t in filtered_templates if t.granted_role == granted_role]

        # 统计信息
        manual_count = sum(1 for t in all_templates if t.is_manual_edited)
        auto_count = len(all_templates) - manual_count

        # 获取所有竞赛（用于筛选）
        all_competitions = []
        if hasattr(competition_manager, 'competitions'):
            all_competitions = competition_manager.competitions
        elif hasattr(competition_manager, '_competitions'):
            all_competitions = competition_manager._competitions

        # 获取所有角色（用于筛选）
        all_roles = sorted(list(set([t.granted_role for t in all_templates if t.granted_role and t.granted_role.strip()])))

        # 获取已选竞赛的名称（用于显示）
        competition_id_name = None
        if competition_id:
            for comp in all_competitions:
                if comp.id == competition_id:
                    competition_id_name = comp.name
                    break

        # 处理详细视图：查找当前模板并计算索引
        current_template = None
        current_index = None
        sample_extracted_dict = {}
        if tab == 'detail':
            import json
            # 如果有 template_id，查找指定的模板
            if template_id:
                for t in filtered_templates:
                    if t.id == template_id:
                        current_template = t
                        break
            # 如果没有 template_id 或找不到指定模板，但有可用模板，自动选择第一个
            elif filtered_templates:
                current_template = filtered_templates[0]

            # 计算索引和解析 sample_extracted
            if current_template:
                current_index = filtered_templates.index(current_template)
                # 解析 sample_extracted JSON字符串
                if current_template.sample_extracted:
                    try:
                        sample_extracted_dict = json.loads(current_template.sample_extracted)
                    except:
                        sample_extracted_dict = {}

        # 获取验证规则数据（用于detail视图）
        # 注意：新的extract模块中验证逻辑已移至各抽取器内部，不再有独立的ValidationRuleManager
        field_rules = {}
        default_required_fields = []  # 默认必填字段列表
        if tab == 'detail' and current_template:
            try:
                # 旧的ValidationRuleManager已被移除，验证逻辑现在由各抽取器内部实现
                # from backend.document_extract.validation import ValidationRuleManager
                # from app.utils import get_doc_rec_context
                # doc_rec_context = get_doc_rec_context()
                # validation_db_path = doc_rec_context.validation_db_path
                #
                # rule_manager = ValidationRuleManager(str(validation_db_path))
                # rule_set = rule_manager.get_rule_set_by_template(current_template.id)
                #
                # if rule_set:
                #     rules = rule_manager.get_rules(rule_set.id)
                #     for rule in rules:
                #         field_rules[rule.field_name] = rule
                pass  # 验证规则功能已废弃
            except Exception as e:
                logger.warning(f"获取验证规则失败: {e}", exc_info=True)
                field_rules = {}
        
        return render_template('admin/templates/main.html',
                             templates=filtered_templates,
                             all_templates=all_templates,
                             competitions=all_competitions,
                             all_roles=all_roles,
                             tab=tab,
                             competition_id=competition_id,
                             competition_id_name=competition_id_name,
                             granted_role=granted_role,
                             template_id=template_id,
                             index=current_index,
                             current_template=current_template,
                             sample_extracted_dict=sample_extracted_dict,
                             field_rules=field_rules,
                             default_required_fields=default_required_fields,
                             base_fields=base_fields,
                             manual_count=manual_count,
                             auto_count=auto_count,
                             total_count=len(all_templates))
    except Exception as e:
        logger.error(f'加载模板列表失败: {e}', exc_info=True)
        flash(f'加载模板列表失败: {str(e)}', 'error')
        # 获取base_fields用于错误页面
        try:
            from app.utils import get_doc_rec_context
            doc_rec_context = get_doc_rec_context()
            template_manager = doc_rec_context.template_manager
            base_fields = template_manager.get_base_fields('award')
        except:
            base_fields = {}
        return render_template('admin/templates/main.html',
                             templates=[],
                             all_templates=[],
                             competitions=[],
                             all_roles=[],
                             tab='list',
                             competition_id=None,
                             granted_role='',
                             template_id=None,
                             index=None,
                             current_template=None,
                             sample_extracted_dict={},
                             field_rules={},
                             default_required_fields=[],
                             base_fields=base_fields,
                             manual_count=0,
                             auto_count=0,
                             total_count=0)

@bp.route('/templates/image/<int:template_id>')
@require_role('admin')
def template_image(template_id):
    """获取模板样本图片"""
    from flask import send_file
    import io
    try:
        # 从 ServiceContext 获取 TemplateManager（使用 competitions.db）
        from app.utils import get_doc_rec_context
        doc_rec_context = get_doc_rec_context()
        template_manager = doc_rec_context.template_manager

        # 查找模板（只查找 award 类型）
        template = None
        for t in template_manager.get_templates_by_type('award'):
            if t.template_id == template_id:
                template = t
                break

        if not template:
            return "模板不存在", 404

        # 获取图片二进制数据
        image_bytes = template.get_sample_image_bytes()
        if not image_bytes:
            return "图片不存在", 404

        # 返回图片响应
        return send_file(
            io.BytesIO(image_bytes),
            mimetype='image/jpeg',
            as_attachment=False
        )
    except Exception as e:
        import traceback
        error_msg = str(e)
        if current_app.config.get('DEBUG'):
            error_msg += f"\n{traceback.format_exc()}"
        return f"加载图片失败: {error_msg}", 500

@bp.route('/templates/refresh', methods=['POST'])
@require_role('admin')
def templates_refresh():
    """刷新模板（普通刷新，跳过手工编辑的模板）"""
    # 注意：批量从奖状创建模板的功能已移除，模板现在通过文档抽取系统自动管理
    return jsonify({
        'success': False,
        'message': '模板刷新功能已移除。模板现在通过文档抽取系统自动管理，无需手动刷新。'
    }), 400

@bp.route('/templates/force-refresh', methods=['POST'])
@require_role('admin')
def templates_force_refresh():
    """强制重置模板（删除所有模板并重建）"""
    # 注意：批量从奖状创建模板的功能已移除，模板现在通过文档抽取系统自动管理
    try:
        from app.utils import get_doc_rec_context
        doc_rec_context = get_doc_rec_context()
        template_manager = doc_rec_context.template_manager

        # 只清空 award 类型的模板
        deleted_count = template_manager.clear_templates_by_type('award')

        return jsonify({
            'success': True,
            'message': f'已清空 {deleted_count} 个奖状模板',
            'stats': {'deleted': deleted_count}
        })
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'message': f'清空模板失败: {str(e)}',
            'traceback': traceback.format_exc() if current_app.config.get('DEBUG') else None
        }), 500

@bp.route('/templates/<int:template_id>/delete', methods=['POST'])
@require_role('admin')
def template_delete(template_id):
    """删除模板"""
    try:
        from app.utils import get_doc_rec_context
        doc_rec_context = get_doc_rec_context()
        template_manager = doc_rec_context.template_manager

        if template_manager.delete_template(template_id):
            return jsonify({'success': True, 'message': '删除成功'})
        else:
            return jsonify({'success': False, 'message': '删除失败，模板不存在'}), 404
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'message': f'删除失败: {str(e)}',
            'traceback': traceback.format_exc() if current_app.config.get('DEBUG') else None
        }), 500

@bp.route('/templates/<int:template_id>/update', methods=['POST'])
@require_role('admin')
def template_update(template_id):
    """更新模板"""
    import json
    try:
        from app.utils import get_doc_rec_context
        doc_rec_context = get_doc_rec_context()
        template_manager = doc_rec_context.template_manager

        # 查找模板
        template = template_manager.get_template(template_id)
        if not template:
            return jsonify({'success': False, 'message': '模板不存在'}), 404

        data = request.get_json()

        # 更新关键词（合并 competition_keywords 和 extend_keywords）
        if 'competition_keywords' in data or 'extend_keywords' in data:
            keywords = []
            if 'competition_keywords' in data:
                comp_keywords = data['competition_keywords']
                if isinstance(comp_keywords, str):
                    comp_keywords = [k.strip() for k in comp_keywords.split('\n') if k.strip()]
                keywords.extend(comp_keywords)
            if 'extend_keywords' in data:
                ext_keywords = data['extend_keywords']
                if isinstance(ext_keywords, str):
                    ext_keywords = [k.strip() for k in ext_keywords.split('\n') if k.strip()]
                keywords.extend(ext_keywords)
            template.keywords = keywords

        # 更新字段
        if 'default_fields' in data:
            default_fields = data['default_fields']
            if isinstance(default_fields, str):
                default_fields = json.loads(default_fields)
            template.default_fields = default_fields

        if 'llm_fields' in data:
            llm_fields = data['llm_fields']
            if isinstance(llm_fields, str):
                llm_fields = json.loads(llm_fields)
            template.llm_fields = llm_fields

        if 'sample_extracted' in data:
            sample_extracted = data['sample_extracted']
            if isinstance(sample_extracted, dict):
                sample_extracted = json.dumps(sample_extracted, ensure_ascii=False)
            template.sample_extracted = sample_extracted

        # 更新关键词（如果直接提供keywords）
        if 'keywords' in data:
            keywords = data['keywords']
            if isinstance(keywords, str):
                keywords = [k.strip() for k in keywords.split('\n') if k.strip()]
            template.keywords = keywords

        # 更新语言设置
        if 'language' in data:
            template.language = data['language']
        if 'need_translate' in data:
            template.need_translate = bool(data['need_translate'])

        # 更新字数范围
        if 'min_length' in data:
            template.min_length = int(data['min_length']) if data['min_length'] else 0
        if 'max_length' in data:
            template.max_length = int(data['max_length']) if data['max_length'] else 0

        # 标记为手工编辑
        template.is_manual_edited = True

        # 保存到数据库
        template_manager._save_template_to_db(template)

        return jsonify({'success': True, 'message': '更新成功'})
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'message': f'更新失败: {str(e)}',
            'traceback': traceback.format_exc() if current_app.config.get('DEBUG') else None
        }), 500

@bp.route('/templates/<int:template_id>/update-granted-role', methods=['POST'])
@require_role('admin')
def template_update_granted_role(template_id):
    """更新模板的授予角色"""
    import json
    try:
        from app.utils import get_doc_rec_context
        doc_rec_context = get_doc_rec_context()
        template_manager = doc_rec_context.template_manager

        # 查找模板
        template = template_manager.get_template(template_id)
        if not template:
            return jsonify({'success': False, 'message': '模板不存在'}), 404

        data = request.get_json()
        new_role = data.get('granted_role')

        if not new_role:
            return jsonify({'success': False, 'message': '授予角色不能为空'}), 400

        if new_role not in ['学生', '教师']:
            return jsonify({'success': False, 'message': '授予角色必须是"学生"或"教师"'}), 400

        # 更新default_fields中的granted_role
        if template.default_fields is None:
            template.default_fields = {}
        template.default_fields['granted_role'] = new_role

        # 标记为手工编辑
        template.is_manual_edited = True

        # 保存到数据库
        template_manager._save_template_to_db(template)

        logger.info(f"模板 {template_id} 的授予角色已更新为: {new_role}")

        return jsonify({'success': True, 'message': f'授予角色已更新为: {new_role}'})
    except Exception as e:
        import traceback
        logger.error(f"更新授予角色失败: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'message': f'更新失败: {str(e)}',
            'traceback': traceback.format_exc() if current_app.config.get('DEBUG') else None
        }), 500

@bp.route('/templates/<int:template_id>/generate-prompt', methods=['POST'])
@require_role('admin')
def template_generate_prompt(template_id):
    """生成模板提示词"""
    try:
        from app.utils import get_doc_rec_context
        doc_rec_context = get_doc_rec_context()
        template_manager = doc_rec_context.template_manager

        # 查找模板
        template = template_manager.get_template(template_id)
        if not template:
            return jsonify({'success': False, 'message': '模板不存在'}), 404

        # 获取基础字段定义
        base_fields = template_manager.get_base_fields(template.template_type)
        
        # 生成提示词（使用示例OCR文本）
        sample_ocr_text = template.sample_text or "示例OCR文本"
        prompt = template.generate_prompt(sample_ocr_text, base_fields)

        return jsonify({
            'success': True,
            'prompt': prompt
        })
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'message': f'生成提示词失败: {str(e)}',
            'traceback': traceback.format_exc() if current_app.config.get('DEBUG') else None
        }), 500


@bp.route('/templates/generate-prompt-for-create', methods=['POST'])
@require_role('admin')
def template_generate_prompt_for_create():
    """创建模板页：根据当前表单数据生成提示词预览（无 template_id）"""
    import json
    try:
        from app.utils import get_doc_rec_context
        from backend.extract.template.template import Template
        from backend.extract.types import TemplateType

        data = request.get_json() or {}
        sample_text = (data.get('sample_text') or '').strip()
        sample_extracted_str = data.get('sample_extracted')
        if isinstance(sample_extracted_str, dict):
            sample_extracted_str = json.dumps(sample_extracted_str, ensure_ascii=False)
        sample_extracted = (sample_extracted_str or '{}').strip()
        default_fields = data.get('default_fields')
        if isinstance(default_fields, str):
            try:
                default_fields = json.loads(default_fields)
            except json.JSONDecodeError:
                default_fields = {}
        default_fields = default_fields or {}
        llm_fields = data.get('llm_fields')
        if isinstance(llm_fields, str):
            try:
                llm_fields = json.loads(llm_fields)
            except json.JSONDecodeError:
                llm_fields = {}
        llm_fields = llm_fields or {}
        keywords = data.get('keywords')
        if isinstance(keywords, str):
            keywords = [k.strip() for k in keywords.split('\n') if k.strip()]
        keywords = keywords or []
        language = (data.get('language') or 'zh').strip() or 'zh'
        need_translate = bool(data.get('need_translate'))

        doc_rec_context = get_doc_rec_context()
        template_manager = doc_rec_context.template_manager
        base_fields = template_manager.get_base_fields('award')

        temp_template = Template(
            template_type=TemplateType.AWARD,
            keywords=keywords,
            sample_text=sample_text or '示例OCR文本',
            sample_extracted=sample_extracted,
            default_fields=default_fields,
            llm_fields=llm_fields,
            min_length=0,
            max_length=0,
            language=language,
            need_translate=need_translate,
        )
        prompt = temp_template.generate_prompt(sample_text or '示例OCR文本', base_fields)
        return jsonify({'success': True, 'prompt': prompt})
    except Exception as e:
        import traceback
        logger.exception('generate-prompt-for-create 失败: %s', e)
        return jsonify({
            'success': False,
            'message': str(e),
            'traceback': traceback.format_exc() if current_app.config.get('DEBUG') else None
        }), 500


@bp.route('/templates/extract-for-create', methods=['POST'])
@require_role('admin')
def template_extract_for_create():
    """上传图片，使用通用模板（未命中任何模板）抽取，供创建模板页展示样本值"""
    import tempfile
    import os
    try:
        from app.utils import get_doc_rec_context
        from backend.extract.extractors.base import ExtractContext
        from backend.extract.types import ExtractStatus

        if 'file' not in request.files:
            return jsonify({'success': False, 'message': '请上传图片文件'}), 400
        file = request.files['file']
        if not file or not file.filename or not file.filename.strip():
            return jsonify({'success': False, 'message': '请选择文件'}), 400

        suffix = Path(file.filename).suffix or '.jpg'
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                file.save(tmp_file.name)
                temp_path = tmp_file.name

            doc_rec_context = get_doc_rec_context()
            framework = doc_rec_context.extract_framework
            award_extractor = framework.get_extractor('award')
            if not award_extractor:
                return jsonify({'success': False, 'message': '奖状抽取器未注册'}), 500

            ctx = ExtractContext(
                file_path=temp_path,
                use_ocr_cache=True,
                use_llm_cache=True,
                use_default_prompt_only=True,
                force_type=True,
                ocr_engine=framework.ocr_engine,
                llm_engine=framework.llm_engine,
            )
            result = award_extractor.extract(ctx)

            if result.status == ExtractStatus.SUCCESS:
                data = result.data if result.data else {}
                if isinstance(data, dict) and list(data.keys()) == ['note'] and 'note' in data:
                    return jsonify({
                        'success': False,
                        'message': data.get('note') or result.error_message or '抽取失败',
                        'error_message': data.get('note') or result.error_message,
                    }), 400
                ocr_text = getattr(result, 'ocr_text', None)
                if ocr_text is None:
                    ocr_text = ''
                return jsonify({
                    'success': True,
                    'ocr_text': ocr_text if isinstance(ocr_text, str) else str(ocr_text or ''),
                    'extracted_dict': data,
                })
            return jsonify({
                'success': False,
                'message': result.error_message or '抽取失败',
                'error_message': result.error_message,
            }), 400
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass
    except Exception as e:
        import traceback
        logger.exception('extract-for-create 失败: %s', e)
        return jsonify({
            'success': False,
            'message': str(e),
            'traceback': traceback.format_exc() if current_app.config.get('DEBUG') else None
        }), 500


@bp.route('/templates/create', methods=['POST'])
@require_role('admin')
def template_create():
    """从上传图片与表单创建模板（竞赛+角色+样本值+图片）"""
    import json
    try:
        from app.utils import get_doc_rec_context
        from backend.extract.template.template import Template
        from backend.extract.types import TemplateType

        if 'file' not in request.files:
            return jsonify({'success': False, 'message': '请上传样本图片'}), 400
        file = request.files['file']
        if not file or not file.filename or not file.filename.strip():
            return jsonify({'success': False, 'message': '请选择样本图片'}), 400

        competition_id = request.form.get('competition_id', type=int)
        granted_role = (request.form.get('granted_role') or '').strip()
        sample_extracted_str = request.form.get('sample_extracted', '{}')
        sample_text = (request.form.get('sample_text') or '').strip()
        keywords_str = (request.form.get('keywords') or '').strip()
        language = (request.form.get('language') or 'zh').strip() or 'zh'
        need_translate = request.form.get('need_translate') in ('1', 'true', 'yes')
        min_length = request.form.get('min_length', type=int) or 0
        max_length = request.form.get('max_length', type=int) or 0
        default_fields_str = request.form.get('default_fields', '{}')
        llm_fields_str = request.form.get('llm_fields', '{}')

        if not competition_id:
            return jsonify({'success': False, 'message': '请选择竞赛'}), 400
        if granted_role not in ('学生', '教师'):
            return jsonify({'success': False, 'message': '授予角色必须是学生或教师'}), 400

        try:
            sample_extracted = json.loads(sample_extracted_str) if sample_extracted_str else {}
        except json.JSONDecodeError:
            return jsonify({'success': False, 'message': '样本值格式错误'}), 400
        try:
            default_fields = json.loads(default_fields_str) if default_fields_str else {}
        except json.JSONDecodeError:
            default_fields = {}
        try:
            llm_fields = json.loads(llm_fields_str) if llm_fields_str else {}
        except json.JSONDecodeError:
            llm_fields = {}

        app_context = get_app_context_instance()
        competition_manager = app_context.get_competition_manager()
        comp = competition_manager.get_competition_by_id(competition_id)
        if not comp:
            return jsonify({'success': False, 'message': '竞赛不存在'}), 400
        # 竞赛名称：优先使用表单中用户输入的基本信息，否则用竞赛表名称
        competition_name = (default_fields.get('competition_name') or '').strip() or comp.name
        default_fields['competition_name'] = competition_name
        default_fields['granted_role'] = granted_role
        keywords = [k.strip() for k in keywords_str.split('\n') if k.strip()] if keywords_str else [competition_name]
        if competition_name and competition_name not in keywords:
            keywords.insert(0, competition_name)
        sample_image_blob = file.read()

        doc_rec_context = get_doc_rec_context()
        template_manager = doc_rec_context.template_manager

        new_template = Template(
            template_type=TemplateType.AWARD,
            keywords=keywords,
            sample_text=sample_text,
            sample_extracted=json.dumps(sample_extracted, ensure_ascii=False),
            default_fields=default_fields,
            llm_fields=llm_fields,
            min_length=min_length,
            max_length=max_length,
            sample_image_blob=sample_image_blob,
            is_manual_edited=True,
            competition_id=competition_id,
            language=language,
            need_translate=need_translate,
        )

        if template_manager.add_template(new_template):
            return jsonify({'success': True, 'message': '创建成功'})
        return jsonify({'success': False, 'message': '该竞赛已有相同角色的模板'}), 400

    except Exception as e:
        import traceback
        logger.exception('创建模板失败: %s', e)
        return jsonify({
            'success': False,
            'message': str(e),
            'traceback': traceback.format_exc() if current_app.config.get('DEBUG') else None
        }), 500

@bp.route('/templates/<int:template_id>/test', methods=['POST'])
@bp.route('/templates/0/test', methods=['POST'])  # 支持自动匹配
@require_role('admin')
def template_test(template_id=0):
    """测试模板（上传图片测试）"""
    import json
    import tempfile
    import os
    import re
    try:
        from app.utils import get_doc_rec_context
        doc_rec_context = get_doc_rec_context()
        template_manager = doc_rec_context.template_manager

        # 查找模板
        template = None
        matched_template_name = None

        # 检查文件上传
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': '请上传图片文件'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'message': '请选择文件'}), 400

        # 保存临时文件
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp_file:
                file.save(tmp_file.name)
                temp_path = tmp_file.name

            # 加载配置
            from app.utils import get_doc_rec_context

            doc_rec_context = get_doc_rec_context()
            framework = doc_rec_context.extract_framework

            # 根据 tests/extract_test.py 的模板，使用框架进行抽取
            # 如果是自动匹配（template_id == 0），直接执行完整的抽取流程
            if template_id == 0:
                result = framework.extract(temp_path)
                ocr_text = result.ocr_text
                
                if not ocr_text:
                    return jsonify({'success': False, 'message': 'OCR识别失败'}), 400
                
                # 从结果中获取模板信息
                matched_template_name = result.metadata.get('template_name', "未匹配到模板（使用默认模板）")
                matched_template_id = result.metadata.get('template_id', 0)
                
                # 填充返回数据
                return jsonify({
                    'success': True,
                    'ocr_text': ocr_text,
                    'llm_result': result.llm_response,
                    'extracted_result': result.llm_response,
                    'extracted_dict': result.data,
                    'completed_result': result.data,
                    'matched_template_name': matched_template_name,
                    'matched_template_id': matched_template_id
                })
            
            # 如果指定了模板 ID，我们需要手动进行后续步骤
            ocr_text, _ = framework.ocr_engine.get_text(temp_path)
            
            if not ocr_text:
                return jsonify({'success': False, 'message': 'OCR识别失败'}), 400

            # 使用指定的模板
            template = template_manager.get_template(template_id)
            if template:
                matched_template_name = template.get_display_name() or "未知竞赛"
            else:
                return jsonify({'success': False, 'message': '模板不存在'}), 404

            # 生成提示词
            base_fields = template_manager.get_base_fields('award')
            prompt_template = template.generate_prompt(ocr_text, base_fields)

            # 调用LLM进行抽取（使用框架内部的 LLM 引擎）
            llm_engine = framework.llm_engine
            messages = [{"role": "user", "content": prompt_template}]
            response_text, _ = llm_engine.chat(messages, temperature=0.1)

            # 解析LLM返回的JSON
            try:
                extracted_dict = json.loads(response_text)
            except json.JSONDecodeError:
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    extracted_dict = json.loads(json_match.group())
                else:
                    extracted_dict = {"error": "无法解析JSON", "raw_response": response_text}

            # 调用 complete_result 补齐结果
            if template:
                base_fields = template_manager.get_base_fields('award')
                completed_dict = template.complete_result(extracted_dict.copy() if isinstance(extracted_dict, dict) else {}, base_fields)
            else:
                completed_dict = extracted_dict.copy() if isinstance(extracted_dict, dict) else {}

            return jsonify({
                'success': True,
                'ocr_text': ocr_text,
                'llm_result': response_text,
                'extracted_result': response_text,
                'extracted_dict': extracted_dict,
                'completed_result': completed_dict,
                'matched_template_name': matched_template_name,
                'matched_template_id': template_id if template else 0
            })
        finally:
            # 清理临时文件
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'message': f'测试失败: {str(e)}',
            'traceback': traceback.format_exc() if current_app.config.get('DEBUG') else None
        }), 500

@bp.route('/api/validation-rules/<int:template_id>', methods=['POST'])
@require_role('admin')
def api_save_validation_rules(template_id):
    """API: 保存模板的验证规则"""
    # 注意：新的extract模块中验证逻辑已移至各抽取器内部，不再有独立的ValidationRuleManager
    # 此API已废弃，验证规则功能不再支持
    return jsonify({
        'success': False,
        'message': '验证规则管理功能已废弃。验证逻辑现在由各抽取器内部实现。'
    }), 400
