"""
文件流转API测试

通过调用Flask路由API，模拟真实的业务流程（上传→提交审核→审核通过），
验证文件在各阶段的正确流转，并最终验证文件的可访问性。
"""
from __future__ import annotations

import os
import sys
import json
import logging
import webbrowser
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from werkzeug.datastructures import FileStorage

# 设置项目根目录
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

os.chdir(project_root)

# 配置日志捕获
log_capture = StringIO()
log_handler = logging.StreamHandler(log_capture)
log_handler.setLevel(logging.DEBUG)

# 为关键模块添加日志处理器
for logger_name in ['backend.services.unified_file_manager', 'backend.services.file_upload_service', 
                    'backend.services.review_service', 'backend.models.award']:
    logger = logging.getLogger(logger_name)
    logger.addHandler(log_handler)
    logger.setLevel(logging.DEBUG)


@dataclass
class StepResult:
    """测试步骤结果"""
    category: str
    step: str
    expected: str
    actual: str
    passed: bool
    detail: str = ""
    log_snippet: str = ""


@dataclass
class CategoryResult:
    """类别测试结果"""
    category: str
    file_path: str
    steps: List[StepResult] = field(default_factory=list)
    passed: bool = True
    final_file_location: str = ""
    final_record_id: Optional[int] = None


class FileFlowTester:
    """文件流转测试器"""
    
    def __init__(self):
        """初始化测试器"""
        from app import create_app
        from config.flask import get_config
        from backend.services.unified_file_manager import get_unified_file_manager
        
        # 创建Flask应用（测试期禁用 WTF CSRF——T31-T34 批次4）
        self.app = create_app(get_config())
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()
        
        # 在Flask应用上下文中初始化，确保使用相同的AppContext实例
        with self.app.app_context():
            from app.utils import get_app_context_instance
            self.app_context = get_app_context_instance()
        
        # 获取文件管理器
        self.file_manager = get_unified_file_manager()
        self.files_root = self.file_manager.files_root
        
        # 测试结果
        self.results: List[CategoryResult] = []
        
    def _login_as_admin(self):
        """模拟admin用户登录"""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['role'] = 'admin'
            sess['username'] = 'admin'
            sess['user_name'] = 'admin'
            sess['user_type'] = 'admin'
    
    def _create_upload_file(self, file_path: Path) -> FileStorage:
        """创建模拟的上传文件对象"""
        with open(file_path, 'rb') as f:
            data = f.read()
        
        # 根据文件扩展名确定content_type
        ext = file_path.suffix.lower()
        content_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.pdf': 'application/pdf',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        }
        content_type = content_types.get(ext, 'application/octet-stream')
        
        return FileStorage(
            stream=BytesIO(data),
            filename=file_path.name,
            content_type=content_type
        )
    
    def _get_log_snippet(self, keyword: str = '[文件流转]') -> str:
        """获取包含关键字的日志片段"""
        log_contents = log_capture.getvalue()
        lines = log_contents.split('\n')
        relevant = [line for line in lines if keyword in line]
        return '\n'.join(relevant[-5:]) if relevant else ""  # 返回最后5条相关日志
    
    def _verify_file_exists(self, relative_path: str) -> bool:
        """验证文件是否存在"""
        full_path = self.files_root / relative_path
        return full_path.exists() and full_path.is_file()
    
    def _verify_file_not_exists(self, relative_path: str) -> bool:
        """验证文件不存在"""
        full_path = self.files_root / relative_path
        return not full_path.exists()
    
    def _get_laboratory_id(self) -> Optional[int]:
        """获取一个实验室ID（用于other类型测试）"""
        lab_manager = self.app_context.get_laboratory_manager()
        labs = lab_manager.get_all() if hasattr(lab_manager, 'get_all') else []
        if labs:
            return labs[0].id
        # 如果没有实验室，创建一个测试实验室
        try:
            lab_id = lab_manager.add_laboratory(
                name='测试实验室',
                description='文件流转测试用实验室'
            )
            return lab_id
        except Exception as e:
            print(f"创建测试实验室失败: {e}")
            return None
    
    def _pick_test_files(self) -> Dict[str, Path]:
        """选择每个类别的一个测试文件"""
        base = project_root / "images" / "测试图片"
        mapping: Dict[str, Path] = {}
        for sub in ["奖状", "专利", "软著", "其他", "大创"]:
            d = base / sub
            if not d.is_dir():
                continue
            files = [f for f in d.iterdir() if f.is_file()]
            if not files:
                continue
            mapping[sub] = files[0]
        return mapping
    
    def test_award_flow(self, file_path: Path) -> CategoryResult:
        """测试奖状文件流转"""
        result = CategoryResult(category="奖状", file_path=str(file_path))
        steps = result.steps
        
        try:
            # 步骤1: 上传文件
            self._login_as_admin()
            upload_file = self._create_upload_file(file_path)
            
            # Flask test_client文件上传格式
            # API使用request.files.getlist('files')，需要传递列表
            # 格式: data={'files': [(file_obj, filename), ...]}
            response = self.client.post(
                '/admin/file-import/upload',
                data={
                    'files': [(upload_file, upload_file.filename)],
                    'use_ocr_cache': '1',
                    'use_llm_cache': '1'
                }
            )
            
            if response.status_code != 200:
                steps.append(StepResult(
                    "奖状", "上传文件",
                    "HTTP 200", f"HTTP {response.status_code}",
                    False, response.get_data(as_text=True)
                ))
                result.passed = False
                return result
            
            data = json.loads(response.data)
            if not data.get('success'):
                steps.append(StepResult(
                    "奖状", "上传文件",
                    "success=True", f"success={data.get('success')}",
                    False, data.get('message', '')
                ))
                result.passed = False
                return result
            
            import_session_id = data.get('import_session_id')
            uploaded_count = data.get('uploaded_count', 0)
            
            steps.append(StepResult(
                "奖状", "上传文件-响应",
                "success=True, uploaded_count=1",
                f"success=True, uploaded_count={uploaded_count}",
                uploaded_count == 1,
                f"session_id={import_session_id}"
            ))
            
            # 查找pending记录 - 在Flask应用上下文中查询，确保使用相同的AppContext
            with self.app.app_context():
                pending_manager = self.app_context.get_pending_achievement_manager()
                from backend.models.pending_achievement import PendingAchievementFilter
                
                # 先查询所有pending记录，用于调试
                all_pending = pending_manager.query_pending(PendingAchievementFilter(limit=1000))
                debug_info = f"总pending记录数: {len(all_pending)}, import_session_id: {import_session_id}"
                
                # 检查是否有任何pending记录包含这个import_session_id
                matching_records = []
                for p in all_pending:
                    data = p.get_achievement_data()
                    if isinstance(data, dict) and data.get('import_session_id') == import_session_id:
                        matching_records.append(f"ID={p.id}, type={p.achievement_type}, status={p.status}")
                
                if matching_records:
                    debug_info += f", 匹配记录: {', '.join(matching_records)}"
                
                filter_obj = PendingAchievementFilter(
                    achievement_type='award',
                    status='pending',
                    import_session_id=import_session_id,
                    limit=1000
                )
                pending_items = pending_manager.query_pending(filter_obj)
                
                if not pending_items:
                    steps.append(StepResult(
                        "奖状", "上传文件-数据库",
                        "pending记录存在", "pending记录不存在",
                        False, debug_info
                    ))
                    result.passed = False
                    return result
                
                pending_item = pending_items[0]
                file_path_in_db = pending_item.file_path
                file_hash = pending_item.file_hash
                
                # 验证文件位置
                if not file_path_in_db.startswith('temp_upload/'):
                    steps.append(StepResult(
                        "奖状", "上传文件-位置",
                        "temp_upload/{sid}/{hash}.ext",
                        file_path_in_db,
                        False, ""
                    ))
                    result.passed = False
                else:
                    file_exists = self._verify_file_exists(file_path_in_db)
                    steps.append(StepResult(
                        "奖状", "上传文件-位置",
                        "文件存在于temp_upload/",
                        "存在" if file_exists else "不存在",
                        file_exists,
                        file_path_in_db,
                        self._get_log_snippet()
                    ))
                    if not file_exists:
                        result.passed = False
                
                # 保存pending_item_id用于后续步骤
                pending_item_id = pending_item.id
            
            # 步骤2: 提交审核
            response = self.client.post(
                f'/admin/file-import/award-submit/{import_session_id}/0',
                data={
                    'tab_type': 'award',
                    'status': 'valid'
                }
            )
            
            if response.status_code not in [200, 302]:
                steps.append(StepResult(
                    "奖状", "提交审核",
                    "HTTP 200/302", f"HTTP {response.status_code}",
                    False, response.get_data(as_text=True)
                ))
                result.passed = False
                return result
            
            # 重新查询pending记录 - 在Flask应用上下文中
            with self.app.app_context():
                pending_manager = self.app_context.get_pending_achievement_manager()
                pending_item = pending_manager.get_pending_by_id(pending_item_id)
                
                if not pending_item:
                    steps.append(StepResult(
                        "奖状", "提交审核-状态",
                        "pending记录存在", "pending记录不存在",
                        False, ""
                    ))
                    result.passed = False
                    return result
                
                new_file_path = pending_item.file_path
                new_status = pending_item.status
                
                # 验证状态和文件位置
                if new_status != 'submit':
                    steps.append(StepResult(
                        "奖状", "提交审核-状态",
                        "status=submit", f"status={new_status}",
                        False, ""
                    ))
                    result.passed = False
                else:
                    steps.append(StepResult(
                        "奖状", "提交审核-状态",
                        "status=submit", f"status={new_status}",
                        True, ""
                    ))
                
                if not new_file_path.startswith('review/'):
                    steps.append(StepResult(
                        "奖状", "提交审核-位置",
                        "review/{sid}/{hash}.ext",
                        new_file_path,
                        False, ""
                    ))
                    result.passed = False
                else:
                    file_exists = self._verify_file_exists(new_file_path)
                    old_file_exists = self._verify_file_exists(file_path_in_db)
                    steps.append(StepResult(
                        "奖状", "提交审核-位置",
                        "文件移动到review/, temp_upload/文件删除",
                        f"review文件{'存在' if file_exists else '不存在'}, temp_upload文件{'仍存在' if old_file_exists else '已删除'}",
                        file_exists and not old_file_exists,
                        f"新路径={new_file_path}",
                        self._get_log_snippet()
                    ))
                    if not file_exists or old_file_exists:
                        result.passed = False
                
                # 保存pending_item_id用于后续步骤
                pending_item_id_for_approve = pending_item.id
            
            # 步骤3: 审核通过
            response = self.client.post(
                f'/admin/api/achievement-review/{pending_item_id_for_approve}/approve-with-data',
                json={},
                content_type='application/json'
            )
            
            if response.status_code != 200:
                steps.append(StepResult(
                    "奖状", "审核通过",
                    "HTTP 200", f"HTTP {response.status_code}",
                    False, response.get_data(as_text=True)
                ))
                result.passed = False
                return result
            
            data = json.loads(response.data)
            if not data.get('success'):
                steps.append(StepResult(
                    "奖状", "审核通过",
                    "success=True", f"success={data.get('success')}",
                    False, data.get('message', '')
                ))
                result.passed = False
                return result
            
            # 验证pending记录已删除 - 在Flask应用上下文中
            with self.app.app_context():
                pending_manager = self.app_context.get_pending_achievement_manager()
                pending_item_after = pending_manager.get_pending_by_id(pending_item_id_for_approve)
                
                if pending_item_after:
                    steps.append(StepResult(
                        "奖状", "审核通过-数据库",
                        "pending记录已删除", "pending记录仍存在",
                        False, ""
                    ))
                    result.passed = False
                else:
                    steps.append(StepResult(
                        "奖状", "审核通过-数据库",
                        "pending记录已删除", "pending记录已删除",
                        True, ""
                    ))
                
                # 验证文件移动到awards目录
                award_manager = self.app_context.get_award_manager()
                awards = award_manager.query_awards()
                matching_award = None
                for award in awards:
                    if award.image_hash == file_hash:
                        matching_award = award
                        break
                
                if not matching_award:
                    steps.append(StepResult(
                        "奖状", "审核通过-入库",
                        "awards表中有新记录", "awards表中无新记录",
                        False, ""
                    ))
                    result.passed = False
                    award_id_for_access = None
                else:
                    result.final_record_id = matching_award.id
                    award_file_path = matching_award.get_image_path()
                    if award_file_path:
                        relative_path = str(award_file_path.relative_to(self.files_root))
                        result.final_file_location = relative_path
                        
                        file_exists = self._verify_file_exists(relative_path)
                        review_file_exists = self._verify_file_exists(new_file_path)
                        
                        steps.append(StepResult(
                            "奖状", "审核通过-文件",
                            "文件移动到awards/{hash}.ext, review/文件删除",
                            f"awards文件{'存在' if file_exists else '不存在'}, review文件{'仍存在' if review_file_exists else '已删除'}",
                            file_exists and not review_file_exists,
                            f"最终路径={relative_path}",
                            self._get_log_snippet()
                        ))
                        if not file_exists or review_file_exists:
                            result.passed = False
                    else:
                        steps.append(StepResult(
                            "奖状", "审核通过-文件",
                            "award有image_path", "award无image_path",
                            False, ""
                        ))
                        result.passed = False
                    
                    # 保存award_id用于后续步骤
                    award_id_for_access = matching_award.id
            
            # 步骤4: 验证文件可访问性（在with块外，使用保存的award_id）
            if award_id_for_access:
                response = self.client.get(f'/admin/awards/{award_id_for_access}/image')
                
                steps.append(StepResult(
                    "奖状", "验证文件访问",
                    "HTTP 200, Content-Type=image/jpeg",
                    f"HTTP {response.status_code}, Content-Type={response.content_type}",
                    response.status_code == 200 and 'image' in response.content_type,
                    f"响应长度={len(response.data)}",
                    ""
                ))
                if response.status_code != 200 or 'image' not in response.content_type:
                    result.passed = False
                
                # 步骤5: 验证编辑页面图片显示
                edit_response = self.client.get(f'/admin/awards/{award_id_for_access}/edit')
                if edit_response.status_code == 200:
                    # 从HTML中提取图片URL（通常页面中会有图片标签）
                    html_content = edit_response.get_data(as_text=True)
                    # 检查页面中是否包含图片URL
                    image_url_in_page = f'/admin/awards/{award_id_for_access}/image' in html_content
                    steps.append(StepResult(
                        "奖状", "编辑页面图片显示",
                        "页面包含图片URL",
                        "包含" if image_url_in_page else "不包含",
                        image_url_in_page,
                        f"编辑页面状态码={edit_response.status_code}",
                        ""
                    ))
                    if not image_url_in_page:
                        result.passed = False
                else:
                    steps.append(StepResult(
                        "奖状", "编辑页面访问",
                        "HTTP 200",
                        f"HTTP {edit_response.status_code}",
                        False,
                        ""
                    ))
                    result.passed = False
            
        except Exception as e:
            import traceback
            steps.append(StepResult(
                "奖状", "异常",
                "无异常", str(e),
                False, traceback.format_exc()
            ))
            result.passed = False
        
        return result
    
    def test_patent_flow(self, file_path: Path) -> CategoryResult:
        """测试专利文件流转"""
        result = CategoryResult(category="专利", file_path=str(file_path))
        steps = result.steps
        
        try:
            # 步骤1: 上传文件
            self._login_as_admin()
            upload_file = self._create_upload_file(file_path)
            
            # Flask test_client文件上传格式
            # API使用request.files.getlist('files')，需要传递列表
            # 格式: data={'files': [(file_obj, filename), ...]}
            response = self.client.post(
                '/admin/file-import/upload',
                data={
                    'files': [(upload_file, upload_file.filename)],
                    'use_ocr_cache': '1',
                    'use_llm_cache': '1'
                }
            )
            
            if response.status_code != 200:
                steps.append(StepResult("专利", "上传文件", "HTTP 200", f"HTTP {response.status_code}", False, ""))
                result.passed = False
                return result
            
            data = json.loads(response.data)
            if not data.get('success'):
                steps.append(StepResult("专利", "上传文件", "success=True", f"success=False", False, data.get('message', '')))
                result.passed = False
                return result
            
            import_session_id = data.get('import_session_id')
            
            # 查找pending记录
            pending_manager = self.app_context.get_pending_achievement_manager()
            from backend.models.pending_achievement import PendingAchievementFilter
            
            filter_obj = PendingAchievementFilter(
                achievement_type='patent',
                status='pending',
                import_session_id=import_session_id,
                limit=1000
            )
            pending_items = pending_manager.query_pending(filter_obj)
            
            if not pending_items:
                steps.append(StepResult("专利", "上传文件-数据库", "pending记录存在", "pending记录不存在", False, ""))
                result.passed = False
                return result
            
            pending_item = pending_items[0]
            file_path_in_db = pending_item.file_path
            
            # 步骤2: 提交审核
            response = self.client.post(
                '/admin/file-import/api/submit',
                json={
                    'item_id': pending_item.id,
                    'force_submit': True
                },
                content_type='application/json'
            )
            
            if response.status_code != 200:
                steps.append(StepResult("专利", "提交审核", "HTTP 200", f"HTTP {response.status_code}", False, ""))
                result.passed = False
                return result
            
            data = json.loads(response.data)
            if not data.get('success'):
                steps.append(StepResult("专利", "提交审核", "success=True", f"success=False", False, data.get('message', '')))
                result.passed = False
                return result
            
            # 重新查询pending记录
            pending_item = pending_manager.get_pending_by_id(pending_item.id)
            new_file_path = pending_item.file_path if pending_item else None
            new_status = pending_item.status if pending_item else None
            
            if new_status != 'submit':
                steps.append(StepResult("专利", "提交审核-状态", "status=submit", f"status={new_status}", False, ""))
                result.passed = False
            else:
                steps.append(StepResult("专利", "提交审核-状态", "status=submit", f"status={new_status}", True, ""))
            
            if new_file_path and not new_file_path.startswith('review/'):
                steps.append(StepResult("专利", "提交审核-位置", "review/...", new_file_path, False, ""))
                result.passed = False
            
            # 步骤3: 审核通过
            response = self.client.post(
                f'/admin/api/achievement-review/{pending_item.id}/approve-with-data',
                json={},
                content_type='application/json'
            )
            
            if response.status_code != 200:
                steps.append(StepResult("专利", "审核通过", "HTTP 200", f"HTTP {response.status_code}", False, ""))
                result.passed = False
                return result
            
            data = json.loads(response.data)
            if not data.get('success'):
                steps.append(StepResult("专利", "审核通过", "success=True", f"success=False", False, data.get('message', '')))
                result.passed = False
                return result
            
            # 验证文件移动到patents目录
            patent_manager = self.app_context.get_patent_manager()
            patents = patent_manager.query_patents(filter_obj=None)
            matching_patent = None
            for patent in patents:
                if patent.certificate_file and 'patent_' in patent.certificate_file:
                    matching_patent = patent
                    break
            
            if matching_patent:
                result.final_record_id = matching_patent.id
                result.final_file_location = matching_patent.certificate_file
                
                file_exists = self._verify_file_exists(matching_patent.certificate_file)
                steps.append(StepResult(
                    "专利", "审核通过-文件",
                    "文件移动到patents/patent_{ts}.ext",
                    f"文件{'存在' if file_exists else '不存在'}",
                    file_exists,
                    f"路径={matching_patent.certificate_file}",
                    self._get_log_snippet()
                ))
                
                # 步骤4: 验证文件可访问性
                response = self.client.get(f'/admin/patents/{matching_patent.id}/file')
                steps.append(StepResult(
                    "专利", "验证文件访问",
                    "HTTP 200",
                    f"HTTP {response.status_code}",
                    response.status_code == 200,
                    ""
                ))
                
                # 步骤5: 验证编辑页面文件显示
                edit_response = self.client.get(f'/admin/patents/{matching_patent.id}/edit')
                if edit_response.status_code == 200:
                    html_content = edit_response.get_data(as_text=True)
                    file_url_in_page = f'/admin/patents/{matching_patent.id}/file' in html_content
                    steps.append(StepResult(
                        "专利", "编辑页面文件显示",
                        "页面包含文件URL",
                        "包含" if file_url_in_page else "不包含",
                        file_url_in_page,
                        f"编辑页面状态码={edit_response.status_code}",
                        ""
                    ))
                    if not file_url_in_page:
                        result.passed = False
                else:
                    steps.append(StepResult(
                        "专利", "编辑页面访问",
                        "HTTP 200",
                        f"HTTP {edit_response.status_code}",
                        False,
                        ""
                    ))
                    result.passed = False
            else:
                steps.append(StepResult("专利", "审核通过-入库", "patents表中有新记录", "patents表中无新记录", False, ""))
                result.passed = False
            
        except Exception as e:
            import traceback
            steps.append(StepResult("专利", "异常", "无异常", str(e), False, traceback.format_exc()))
            result.passed = False
        
        return result
    
    def test_software_flow(self, file_path: Path) -> CategoryResult:
        """测试软著文件流转"""
        result = CategoryResult(category="软著", file_path=str(file_path))
        steps = result.steps
        
        try:
            # 步骤1: 上传文件
            self._login_as_admin()
            upload_file = self._create_upload_file(file_path)
            
            # Flask test_client文件上传格式
            # API使用request.files.getlist('files')，需要传递列表
            # 格式: data={'files': [(file_obj, filename), ...]}
            response = self.client.post(
                '/admin/file-import/upload',
                data={
                    'files': [(upload_file, upload_file.filename)],
                    'use_ocr_cache': '1',
                    'use_llm_cache': '1'
                }
            )
            
            if response.status_code != 200:
                steps.append(StepResult("软著", "上传文件", "HTTP 200", f"HTTP {response.status_code}", False, ""))
                result.passed = False
                return result
            
            data = json.loads(response.data)
            if not data.get('success'):
                steps.append(StepResult("软著", "上传文件", "success=True", f"success=False", False, data.get('message', '')))
                result.passed = False
                return result
            
            import_session_id = data.get('import_session_id')
            
            # 查找pending记录
            pending_manager = self.app_context.get_pending_achievement_manager()
            from backend.models.pending_achievement import PendingAchievementFilter
            
            filter_obj = PendingAchievementFilter(
                achievement_type='software',
                status='pending',
                import_session_id=import_session_id,
                limit=1000
            )
            pending_items = pending_manager.query_pending(filter_obj)
            
            if not pending_items:
                steps.append(StepResult("软著", "上传文件-数据库", "pending记录存在", "pending记录不存在", False, ""))
                result.passed = False
                return result
            
            pending_item = pending_items[0]
            
            # 步骤2: 提交审核
            response = self.client.post(
                '/admin/file-import/api/submit',
                json={
                    'item_id': pending_item.id,
                    'force_submit': True
                },
                content_type='application/json'
            )
            
            if response.status_code != 200 or not json.loads(response.data).get('success'):
                steps.append(StepResult("软著", "提交审核", "success=True", "失败", False, ""))
                result.passed = False
                return result
            
            pending_item = pending_manager.get_pending_by_id(pending_item.id)
            
            # 步骤3: 审核通过
            response = self.client.post(
                f'/admin/api/achievement-review/{pending_item.id}/approve-with-data',
                json={},
                content_type='application/json'
            )
            
            if response.status_code != 200 or not json.loads(response.data).get('success'):
                steps.append(StepResult("软著", "审核通过", "success=True", "失败", False, ""))
                result.passed = False
                return result
            
            # 验证文件移动到software目录
            software_manager = self.app_context.get_software_copyright_manager()
            software_list = software_manager.query_copyrights(filter_obj=None)
            matching_software = None
            for sw in software_list:
                if sw.certificate_file and 'software_' in sw.certificate_file:
                    matching_software = sw
                    break
            
            if matching_software:
                result.final_record_id = matching_software.id
                result.final_file_location = matching_software.certificate_file
                
                file_exists = self._verify_file_exists(matching_software.certificate_file)
                steps.append(StepResult(
                    "软著", "审核通过-文件",
                    "文件移动到software/software_{ts}.ext",
                    f"文件{'存在' if file_exists else '不存在'}",
                    file_exists,
                    f"路径={matching_software.certificate_file}",
                    self._get_log_snippet()
                ))
                
                # 步骤4: 验证文件可访问性
                response = self.client.get(f'/admin/software/{matching_software.id}/file')
                steps.append(StepResult(
                    "软著", "验证文件访问",
                    "HTTP 200",
                    f"HTTP {response.status_code}",
                    response.status_code == 200,
                    ""
                ))
                
                # 步骤5: 验证编辑页面文件显示
                edit_response = self.client.get(f'/admin/software/{matching_software.id}/edit')
                if edit_response.status_code == 200:
                    html_content = edit_response.get_data(as_text=True)
                    file_url_in_page = f'/admin/software/{matching_software.id}/file' in html_content
                    steps.append(StepResult(
                        "软著", "编辑页面文件显示",
                        "页面包含文件URL",
                        "包含" if file_url_in_page else "不包含",
                        file_url_in_page,
                        f"编辑页面状态码={edit_response.status_code}",
                        ""
                    ))
                    if not file_url_in_page:
                        result.passed = False
                else:
                    steps.append(StepResult(
                        "软著", "编辑页面访问",
                        "HTTP 200",
                        f"HTTP {edit_response.status_code}",
                        False,
                        ""
                    ))
                    result.passed = False
            else:
                steps.append(StepResult("软著", "审核通过-入库", "software_copyrights表中有新记录", "无新记录", False, ""))
                result.passed = False
            
        except Exception as e:
            import traceback
            steps.append(StepResult("软著", "异常", "无异常", str(e), False, traceback.format_exc()))
            result.passed = False
        
        return result
    
    def test_other_flow(self, file_path: Path) -> CategoryResult:
        """测试其他文件流转（关联实验室）"""
        result = CategoryResult(category="其他", file_path=str(file_path))
        steps = result.steps
        
        try:
            # 步骤1: 上传文件
            self._login_as_admin()
            upload_file = self._create_upload_file(file_path)
            
            # Flask test_client文件上传格式
            # API使用request.files.getlist('files')，需要传递列表
            # 格式: data={'files': [(file_obj, filename), ...]}
            response = self.client.post(
                '/admin/file-import/upload',
                data={
                    'files': [(upload_file, upload_file.filename)],
                    'use_ocr_cache': '1',
                    'use_llm_cache': '1'
                }
            )
            
            if response.status_code != 200:
                steps.append(StepResult("其他", "上传文件", "HTTP 200", f"HTTP {response.status_code}", False, ""))
                result.passed = False
                return result
            
            data = json.loads(response.data)
            if not data.get('success'):
                steps.append(StepResult("其他", "上传文件", "success=True", f"success=False", False, data.get('message', '')))
                result.passed = False
                return result
            
            import_session_id = data.get('import_session_id')
            
            # 查找pending记录
            pending_manager = self.app_context.get_pending_achievement_manager()
            from backend.models.pending_achievement import PendingAchievementFilter
            
            filter_obj = PendingAchievementFilter(
                achievement_type='other',
                status='pending',
                import_session_id=import_session_id,
                limit=1000
            )
            pending_items = pending_manager.query_pending(filter_obj)
            
            if not pending_items:
                steps.append(StepResult("其他", "上传文件-数据库", "pending记录存在", "pending记录不存在", False, ""))
                result.passed = False
                return result
            
            pending_item = pending_items[0]
            
            # 步骤2: 提交审核
            response = self.client.post(
                '/admin/file-import/api/submit',
                json={
                    'item_id': pending_item.id,
                    'force_submit': True
                },
                content_type='application/json'
            )
            
            if response.status_code != 200 or not json.loads(response.data).get('success'):
                steps.append(StepResult("其他", "提交审核", "success=True", "失败", False, ""))
                result.passed = False
                return result
            
            pending_item = pending_manager.get_pending_by_id(pending_item.id)
            
            # 步骤3: 提交到实验室（替代审核通过）
            lab_id = self._get_laboratory_id()
            if not lab_id:
                steps.append(StepResult("其他", "获取实验室ID", "有实验室ID", "无实验室ID", False, ""))
                result.passed = False
                return result
            
            response = self.client.post(
                '/admin/file-import/api/other/submit',
                json={
                    'item_id': pending_item.id,
                    'lab_id': lab_id,
                    'target_type': 'downloads',
                    'file_title': '测试文件'
                },
                content_type='application/json'
            )
            
            if response.status_code != 200:
                steps.append(StepResult("其他", "提交到实验室", "HTTP 200", f"HTTP {response.status_code}", False, ""))
                result.passed = False
                return result
            
            data = json.loads(response.data)
            if not data.get('success'):
                steps.append(StepResult("其他", "提交到实验室", "success=True", f"success=False", False, data.get('message', '')))
                result.passed = False
                return result
            
            file_path_after = data.get('file_path', '')
            result.final_file_location = file_path_after
            
            # 验证文件移动到laboratories目录
            file_exists = self._verify_file_exists(file_path_after) if file_path_after else False
            steps.append(StepResult(
                "其他", "提交到实验室-文件",
                "文件移动到laboratories/{lab_id}/downloads/...",
                f"文件{'存在' if file_exists else '不存在'}",
                file_exists,
                f"路径={file_path_after}",
                self._get_log_snippet()
            ))
            
            # 验证pending记录已删除
            pending_item_after = pending_manager.get_pending_by_id(pending_item.id)
            if pending_item_after:
                steps.append(StepResult("其他", "提交到实验室-数据库", "pending记录已删除", "pending记录仍存在", False, ""))
                result.passed = False
            else:
                steps.append(StepResult("其他", "提交到实验室-数据库", "pending记录已删除", "pending记录已删除", True, ""))
            
            # 步骤4: 验证文件可访问性（通过实验室下载专区）
            lab_manager = self.app_context.get_laboratory_manager()
            lab = lab_manager.get_laboratory_by_id(lab_id)
            if lab and lab.downloads:
                download_id = lab.downloads[-1].get('id')  # 获取最新的下载文件ID
                response = self.client.get(f'/admin/laboratories/{lab_id}/downloads/{download_id}/file')
                steps.append(StepResult(
                    "其他", "验证文件访问",
                    "HTTP 200",
                    f"HTTP {response.status_code}",
                    response.status_code == 200,
                    ""
                ))
                result.final_record_id = download_id
            
        except Exception as e:
            import traceback
            steps.append(StepResult("其他", "异常", "无异常", str(e), False, traceback.format_exc()))
            result.passed = False
        
        return result
    
    def test_innovation_flow(self, file_path: Path) -> CategoryResult:
        """测试大创文件流转"""
        result = CategoryResult(category="大创", file_path=str(file_path))
        steps = result.steps
        
        try:
            # 步骤1: 上传文件
            self._login_as_admin()
            upload_file = self._create_upload_file(file_path)
            
            # Flask test_client文件上传格式
            # API使用request.files.getlist('files')，需要传递列表
            # 格式: data={'files': [(file_obj, filename), ...]}
            response = self.client.post(
                '/admin/file-import/upload',
                data={
                    'files': [(upload_file, upload_file.filename)],
                    'use_ocr_cache': '1',
                    'use_llm_cache': '1'
                }
            )
            
            if response.status_code != 200:
                steps.append(StepResult("大创", "上传文件", "HTTP 200", f"HTTP {response.status_code}", False, ""))
                result.passed = False
                return result
            
            data = json.loads(response.data)
            if not data.get('success'):
                steps.append(StepResult("大创", "上传文件", "success=True", f"success=False", False, data.get('message', '')))
                result.passed = False
                return result
            
            import_session_id = data.get('import_session_id')
            
            # 查找pending记录
            pending_manager = self.app_context.get_pending_achievement_manager()
            from backend.models.pending_achievement import PendingAchievementFilter
            
            filter_obj = PendingAchievementFilter(
                achievement_type='innovation',
                status='pending',
                import_session_id=import_session_id,
                limit=1000
            )
            pending_items = pending_manager.query_pending(filter_obj)
            
            if not pending_items:
                steps.append(StepResult("大创", "上传文件-数据库", "pending记录存在", "pending记录不存在", False, ""))
                result.passed = False
                return result
            
            pending_item = pending_items[0]
            review_file_path = pending_item.file_path
            
            # 步骤2: 提交审核
            response = self.client.post(
                '/admin/file-import/api/submit',
                json={
                    'item_id': pending_item.id,
                    'force_submit': True
                },
                content_type='application/json'
            )
            
            if response.status_code != 200 or not json.loads(response.data).get('success'):
                steps.append(StepResult("大创", "提交审核", "success=True", "失败", False, ""))
                result.passed = False
                return result
            
            pending_item = pending_manager.get_pending_by_id(pending_item.id)
            
            # 步骤3: 审核通过
            response = self.client.post(
                f'/admin/api/achievement-review/{pending_item.id}/approve-with-data',
                json={},
                content_type='application/json'
            )
            
            if response.status_code != 200:
                steps.append(StepResult("大创", "审核通过", "HTTP 200", f"HTTP {response.status_code}", False, ""))
                result.passed = False
                return result
            
            data = json.loads(response.data)
            if not data.get('success'):
                steps.append(StepResult("大创", "审核通过", "success=True", f"success=False", False, data.get('message', '')))
                result.passed = False
                return result
            
            # 验证文件已删除
            file_deleted = self._verify_file_not_exists(review_file_path)
            steps.append(StepResult(
                "大创", "审核通过-文件删除",
                "review/文件已删除",
                "文件已删除" if file_deleted else "文件仍存在",
                file_deleted,
                f"原路径={review_file_path}",
                self._get_log_snippet()
            ))
            if not file_deleted:
                result.passed = False
            
            # 验证数据入库
            innovation_manager = self.app_context.get_innovation_project_manager()
            projects = innovation_manager.query_projects(filter_obj=None)
            matching_project = None
            for project in projects:
                # 大创项目不存储文件路径，所以只要找到最新的项目即可
                matching_project = project
                break
            
            if matching_project:
                result.final_record_id = matching_project.id
                steps.append(StepResult(
                    "大创", "审核通过-入库",
                    "innovation_projects表中有新记录",
                    "有新记录",
                    True,
                    f"项目ID={matching_project.id}"
                ))
            else:
                steps.append(StepResult("大创", "审核通过-入库", "innovation_projects表中有新记录", "无新记录", False, ""))
                result.passed = False
            
        except Exception as e:
            import traceback
            steps.append(StepResult("大创", "异常", "无异常", str(e), False, traceback.format_exc()))
            result.passed = False
        
        return result
    
    def test_laboratory_image_management(self, image_path: Path) -> CategoryResult:
        """测试实验室图片管理（上传、查看、删除）"""
        result = CategoryResult(category="实验室图片", file_path=str(image_path))
        steps = result.steps
        
        try:
            self._login_as_admin()
            
            # 获取或创建实验室
            lab_id = self._get_laboratory_id()
            if not lab_id:
                steps.append(StepResult("实验室图片", "获取实验室", "有实验室ID", "无实验室ID", False, ""))
                result.passed = False
                return result
            
            # 步骤1: 上传图片
            upload_file = self._create_upload_file(image_path)
            # 重置stream位置
            upload_file.stream.seek(0)
            # Flask test_client文件上传：使用data参数，传递(file_obj, filename)元组
            response = self.client.post(
                f'/admin/laboratories/{lab_id}/images/upload',
                data={'image': (upload_file, upload_file.filename)}
            )
            
            if response.status_code != 200:
                steps.append(StepResult("实验室图片", "上传图片", "HTTP 200", f"HTTP {response.status_code}", False, ""))
                result.passed = False
                return result
            
            data = json.loads(response.data)
            if not data.get('success'):
                steps.append(StepResult("实验室图片", "上传图片", "success=True", f"success=False", False, data.get('message', '')))
                result.passed = False
                return result
            
            image_path_relative = data.get('image_path', '')
            result.final_file_location = image_path_relative
            
            # 验证文件存在
            file_exists = self._verify_file_exists(image_path_relative)
            steps.append(StepResult(
                "实验室图片", "上传图片-文件",
                "文件存在于laboratories/{lab_id}/photos/",
                "存在" if file_exists else "不存在",
                file_exists,
                f"路径={image_path_relative}",
                self._get_log_snippet()
            ))
            if not file_exists:
                result.passed = False
                return result
            
            # 步骤2: 查看图片
            # 从image_path中提取文件名
            filename = Path(image_path_relative).name if image_path_relative else None
            if filename:
                view_response = self.client.get(f'/admin/files/laboratory/{filename}')
                steps.append(StepResult(
                    "实验室图片", "查看图片",
                    "HTTP 200, Content-Type=image/jpeg",
                    f"HTTP {view_response.status_code}, Content-Type={view_response.content_type}",
                    view_response.status_code == 200 and 'image' in view_response.content_type,
                    f"响应长度={len(view_response.data)}",
                    ""
                ))
                if view_response.status_code != 200 or 'image' not in view_response.content_type:
                    result.passed = False
                # 必须显式 close：test_client 下 send_file 打开的文件句柄不会自动释放，不 close 会导致后续删除 PermissionError
                view_response.close()
            
            # 步骤3: 删除图片
            delete_response = self.client.post(
                f'/admin/laboratories/{lab_id}/images/delete',
                json={'image_path': image_path_relative},
                content_type='application/json'
            )
            
            if delete_response.status_code != 200:
                steps.append(StepResult("实验室图片", "删除图片", "HTTP 200", f"HTTP {delete_response.status_code}", False, ""))
                result.passed = False
            else:
                delete_data = json.loads(delete_response.data)
                if delete_data.get('success'):
                    # 验证文件已删除（view 已 close，句柄已释放）
                    file_deleted = self._verify_file_not_exists(image_path_relative)
                    steps.append(StepResult(
                        "实验室图片", "删除图片-文件",
                        "文件已删除",
                        "已删除" if file_deleted else "仍存在",
                        file_deleted,
                        f"原路径={image_path_relative}",
                        ""
                    ))
                    if not file_deleted:
                        result.passed = False
                else:
                    steps.append(StepResult("实验室图片", "删除图片", "success=True", f"success=False", False, delete_data.get('message', '')))
                    result.passed = False
            
        except Exception as e:
            import traceback
            steps.append(StepResult("实验室图片", "异常", "无异常", str(e), False, traceback.format_exc()))
            result.passed = False
        
        return result
    
    def test_laboratory_download_management(self, file_path: Path) -> CategoryResult:
        """测试实验室下载文件管理（上传、查看、删除）"""
        result = CategoryResult(category="实验室下载", file_path=str(file_path))
        steps = result.steps
        
        try:
            self._login_as_admin()
            
            # 获取或创建实验室
            lab_id = self._get_laboratory_id()
            if not lab_id:
                steps.append(StepResult("实验室下载", "获取实验室", "有实验室ID", "无实验室ID", False, ""))
                result.passed = False
                return result
            
            # 步骤1: 上传文件
            upload_file = self._create_upload_file(file_path)
            # 重置stream位置
            upload_file.stream.seek(0)
            # Flask test_client文件上传：使用data参数，传递(file_obj, filename)元组
            response = self.client.post(
                f'/admin/laboratories/{lab_id}/downloads/upload',
                data={
                    'file': (upload_file, upload_file.filename),
                    'file_title': '测试下载文件',
                    'is_public': 'true'
                }
            )
            
            if response.status_code != 200:
                steps.append(StepResult("实验室下载", "上传文件", "HTTP 200", f"HTTP {response.status_code}", False, ""))
                result.passed = False
                return result
            
            data = json.loads(response.data)
            if not data.get('success'):
                steps.append(StepResult("实验室下载", "上传文件", "success=True", f"success=False", False, data.get('message', '')))
                result.passed = False
                return result
            
            file_path_relative = data.get('file_path', '')
            download_id = data.get('download_id')
            result.final_file_location = file_path_relative
            result.final_record_id = download_id
            
            # 验证文件存在
            file_exists = self._verify_file_exists(file_path_relative)
            steps.append(StepResult(
                "实验室下载", "上传文件-文件",
                "文件存在于laboratories/{lab_id}/downloads/",
                "存在" if file_exists else "不存在",
                file_exists,
                f"路径={file_path_relative}",
                self._get_log_snippet()
            ))
            if not file_exists:
                result.passed = False
                return result
            
            # 步骤2: 查看/下载文件
            if download_id:
                view_response = self.client.get(f'/admin/laboratories/{lab_id}/downloads/{download_id}/file')
                steps.append(StepResult(
                    "实验室下载", "下载文件",
                    "HTTP 200",
                    f"HTTP {view_response.status_code}",
                    view_response.status_code == 200,
                    f"响应长度={len(view_response.data)}",
                    ""
                ))
                if view_response.status_code != 200:
                    result.passed = False
                # 必须显式 close：test_client 下 send_file 打开的文件句柄不会自动释放，不 close 会导致后续删除 PermissionError
                view_response.close()
            
            # 步骤3: 删除文件
            if download_id:
                delete_response = self.client.delete(f'/admin/laboratories/{lab_id}/downloads/{download_id}')
                
                if delete_response.status_code != 200:
                    steps.append(StepResult("实验室下载", "删除文件", "HTTP 200", f"HTTP {delete_response.status_code}", False, ""))
                    result.passed = False
                else:
                    delete_data = json.loads(delete_response.data)
                    if delete_data.get('success'):
                        # 验证文件已删除（view 已 close，句柄已释放）
                        file_deleted = self._verify_file_not_exists(file_path_relative)
                        steps.append(StepResult(
                            "实验室下载", "删除文件-文件",
                            "文件已删除",
                            "已删除" if file_deleted else "仍存在",
                            file_deleted,
                            f"原路径={file_path_relative}",
                            ""
                        ))
                        if not file_deleted:
                            result.passed = False
                    else:
                        steps.append(StepResult("实验室下载", "删除文件", "success=True", f"success=False", False, delete_data.get('message', '')))
                        result.passed = False
            
        except Exception as e:
            import traceback
            steps.append(StepResult("实验室下载", "异常", "无异常", str(e), False, traceback.format_exc()))
            result.passed = False
        
        return result
    
    def test_other_file_management(self, file_path: Path) -> CategoryResult:
        """测试其他文件管理（查看、下载、编辑）
        
        通过 POST /admin/other-files/upload 直接创建 other_files 记录，
        再测试查看、下载、编辑 API。（提交到实验室会写入 laboratory_downloads，不是 other_files）
        """
        result = CategoryResult(category="其他文件管理", file_path=str(file_path))
        steps = result.steps
        
        try:
            self._login_as_admin()
            
            lab_id = self._get_laboratory_id()
            
            # 通过 other-files/upload 直接创建 other_files 记录
            upload_file = self._create_upload_file(file_path)
            upload_file.stream.seek(0)
            form_data = {'file': (upload_file, upload_file.filename)}
            if lab_id:
                form_data['laboratory_id'] = str(lab_id)
            form_data['description'] = '测试其他文件'
            
            response = self.client.post(
                '/admin/other-files/upload',
                data=form_data,
                follow_redirects=False
            )
            
            if response.status_code != 302:
                steps.append(StepResult("其他文件管理", "创建文件记录", "HTTP 302 重定向", f"HTTP {response.status_code}", False, ""))
                result.passed = False
                return result
            
            # 解析重定向 URL 获取 file_id: .../other-files/<file_id>
            import re
            location = response.headers.get('Location', '')
            m = re.search(r'/admin/other-files/(\d+)', location)
            if not m:
                steps.append(StepResult("其他文件管理", "解析file_id", "重定向含 file_id", f"Location={location}", False, ""))
                result.passed = False
                return result
            
            file_id = int(m.group(1))
            result.final_record_id = file_id
            
            # 获取 file_path 用于后续校验（可选）
            with self.app.app_context():
                other_mgr = self.app_context.get_other_file_manager()
                obj = other_mgr.get_file_by_id(file_id)
                result.final_file_location = obj.file_path if obj else ""
            
            steps.append(StepResult("其他文件管理", "创建文件记录", "上传成功", f"file_id={file_id}", True, ""))
            
            # 步骤1: 查看文件详情
            view_response = self.client.get(f'/admin/other-files/{file_id}')
            if view_response.status_code == 200:
                html_content = view_response.get_data(as_text=True)
                download_url_in_page = f'/admin/other-files/{file_id}/download' in html_content
                steps.append(StepResult(
                    "其他文件管理", "查看文件详情",
                    "页面包含下载URL",
                    "包含" if download_url_in_page else "不包含",
                    download_url_in_page,
                    f"详情页面状态码={view_response.status_code}",
                    ""
                ))
                if not download_url_in_page:
                    result.passed = False
            else:
                steps.append(StepResult("其他文件管理", "查看文件详情", "HTTP 200", f"HTTP {view_response.status_code}", False, ""))
                result.passed = False
            
            # 步骤2: 下载文件
            download_response = self.client.get(f'/admin/other-files/{file_id}/download')
            steps.append(StepResult(
                "其他文件管理", "下载文件",
                "HTTP 200",
                f"HTTP {download_response.status_code}",
                download_response.status_code == 200,
                f"响应长度={len(download_response.data)}",
                ""
            ))
            if download_response.status_code != 200:
                result.passed = False
            download_response.close()  # send_file 句柄释放
            
            # 步骤3: 编辑文件
            edit_response = self.client.post(
                f'/admin/other-files/{file_id}/edit',
                data={
                    'file_name': '修改后的文件名',
                    'description': '测试描述',
                    'laboratory_id': str(lab_id) if lab_id else ''
                }
            )
            
            if edit_response.status_code in [200, 302]:  # 可能是重定向
                # 验证数据库记录已更新
                with self.app.app_context():
                    other_mgr = self.app_context.get_other_file_manager()
                    updated_file = other_mgr.get_file_by_id(file_id)
                    if updated_file and updated_file.file_name == '修改后的文件名':
                        steps.append(StepResult(
                            "其他文件管理", "编辑文件",
                            "文件信息已更新",
                            "已更新",
                            True,
                            f"新文件名={updated_file.file_name}",
                            ""
                        ))
                    else:
                        steps.append(StepResult("其他文件管理", "编辑文件", "文件信息已更新", "未更新", False, ""))
                        result.passed = False
            else:
                steps.append(StepResult("其他文件管理", "编辑文件", "HTTP 200/302", f"HTTP {edit_response.status_code}", False, ""))
                result.passed = False
            
        except Exception as e:
            import traceback
            steps.append(StepResult("其他文件管理", "异常", "无异常", str(e), False, traceback.format_exc()))
            result.passed = False
        
        return result
    
    def test_file_import_file_access(self, file_path: Path) -> CategoryResult:
        """测试文件导入过程中的文件访问"""
        result = CategoryResult(category="文件导入访问", file_path=str(file_path))
        steps = result.steps
        
        try:
            self._login_as_admin()
            
            # 步骤1: 上传文件（文件在temp_upload目录）
            upload_file = self._create_upload_file(file_path)
            response = self.client.post(
                '/admin/file-import/upload',
                data={
                    'files': [(upload_file, upload_file.filename)],
                    'use_ocr_cache': '1',
                    'use_llm_cache': '1'
                }
            )
            
            if response.status_code != 200:
                steps.append(StepResult("文件导入访问", "上传文件", "HTTP 200", f"HTTP {response.status_code}", False, ""))
                result.passed = False
                return result
            
            data = json.loads(response.data)
            if not data.get('success'):
                steps.append(StepResult("文件导入访问", "上传文件", "success=True", f"success=False", False, data.get('message', '')))
                result.passed = False
                return result
            
            import_session_id = data.get('import_session_id')
            
            # 查找pending记录获取文件路径
            with self.app.app_context():
                pending_manager = self.app_context.get_pending_achievement_manager()
                from backend.models.pending_achievement import PendingAchievementFilter
                
                filter_obj = PendingAchievementFilter(
                    achievement_type='other',
                    status='pending',
                    import_session_id=import_session_id,
                    limit=1000
                )
                pending_items = pending_manager.query_pending(filter_obj)
                
                if not pending_items:
                    steps.append(StepResult("文件导入访问", "查找pending记录", "记录存在", "记录不存在", False, ""))
                    result.passed = False
                    return result
                
                pending_item = pending_items[0]
                temp_file_path = pending_item.file_path
            
            # 步骤2: 访问temp_upload中的文件
            if temp_file_path and temp_file_path.startswith('temp_upload/'):
                access_response = self.client.get(f'/admin/file-import/file/{temp_file_path}')
                steps.append(StepResult(
                    "文件导入访问", "访问temp_upload文件",
                    "HTTP 200",
                    f"HTTP {access_response.status_code}",
                    access_response.status_code == 200,
                    f"响应长度={len(access_response.data)}, Content-Type={access_response.content_type}",
                    ""
                ))
                if access_response.status_code != 200:
                    result.passed = False
                access_response.close()  # send_file 句柄释放
                
                # 步骤3: 提交审核后访问review文件
                submit_response = self.client.post(
                    '/admin/file-import/api/submit',
                    json={
                        'item_id': pending_item.id,
                        'force_submit': True
                    },
                    content_type='application/json'
                )
                
                if submit_response.status_code == 200:
                    # 重新查询获取review路径
                    with self.app.app_context():
                        updated_pending = pending_manager.get_pending_by_id(pending_item.id)
                        if updated_pending and updated_pending.file_path.startswith('review/'):
                            review_file_path = updated_pending.file_path
                            review_access_response = self.client.get(f'/admin/file-import/file/{review_file_path}')
                            steps.append(StepResult(
                                "文件导入访问", "访问review文件",
                                "HTTP 200",
                                f"HTTP {review_access_response.status_code}",
                                review_access_response.status_code == 200,
                                f"响应长度={len(review_access_response.data)}, Content-Type={review_access_response.content_type}",
                                ""
                            ))
                            if review_access_response.status_code != 200:
                                result.passed = False
                            review_access_response.close()  # send_file 句柄释放
                        else:
                            # 如果文件路径不是review/，可能是移动失败，记录详细信息
                            actual_path = updated_pending.file_path if updated_pending else "None"
                            steps.append(StepResult(
                                "文件导入访问", "查找review文件路径",
                                "路径存在且以review/开头",
                                f"路径={actual_path}",
                                False,
                                f"文件可能未成功移动到review目录"
                            ))
                            result.passed = False
                else:
                    steps.append(StepResult("文件导入访问", "提交审核", "HTTP 200", f"HTTP {submit_response.status_code}", False, ""))
                    result.passed = False
            
        except Exception as e:
            import traceback
            steps.append(StepResult("文件导入访问", "异常", "无异常", str(e), False, traceback.format_exc()))
            result.passed = False
        
        return result
    
    def test_laboratory_edit_cover_image(self, image_path: Path) -> CategoryResult:
        """测试实验室编辑功能中的封面图片上传"""
        result = CategoryResult(category="实验室编辑封面", file_path=str(image_path))
        steps = result.steps
        
        try:
            self._login_as_admin()
            
            # 获取或创建实验室
            lab_id = self._get_laboratory_id()
            if not lab_id:
                steps.append(StepResult("实验室编辑封面", "获取实验室", "有实验室ID", "无实验室ID", False, ""))
                result.passed = False
                return result
            
            # 步骤1: 编辑实验室并上传封面图片
            upload_file = self._create_upload_file(image_path)
            upload_file.stream.seek(0)
            
            # Flask test_client文件上传：使用data参数，传递(file_obj, filename)元组
            response = self.client.post(
                f'/admin/laboratories/{lab_id}/edit',
                data={
                    'cover_image': (upload_file, upload_file.filename),
                    'name': '测试实验室（编辑封面）',
                    'description': '测试封面图片上传'
                }
            )
            
            if response.status_code not in [200, 302]:
                steps.append(StepResult("实验室编辑封面", "编辑实验室", "HTTP 200/302", f"HTTP {response.status_code}", False, ""))
                result.passed = False
                return result
            
            # 步骤2: 验证封面图片已保存
            with self.app.app_context():
                laboratory_manager = self.app_context.get_laboratory_manager()
                lab = laboratory_manager.get_laboratory_by_id(lab_id)
                
                if lab and lab.cover_image:
                    cover_path = lab.cover_image
                    result.final_file_location = cover_path
                    
                    # 验证文件存在（封面图片存储在static目录）
                    # cover_path格式：images/laboratory_covers/{filename}
                    from flask import current_app
                    static_folder = Path(current_app.static_folder)
                    cover_file_path = static_folder / cover_path
                    file_exists = cover_file_path.exists()
                    
                    steps.append(StepResult(
                        "实验室编辑封面", "封面图片保存",
                        "文件存在于static/images/laboratory_covers/",
                        "存在" if file_exists else "不存在",
                        file_exists,
                        f"路径={cover_path}, 绝对路径={cover_file_path}",
                        self._get_log_snippet()
                    ))
                    if not file_exists:
                        result.passed = False
                else:
                    steps.append(StepResult("实验室编辑封面", "封面图片保存", "cover_image字段有值", "cover_image字段为空", False, ""))
                    result.passed = False
            
        except Exception as e:
            import traceback
            steps.append(StepResult("实验室编辑封面", "异常", "无异常", str(e), False, traceback.format_exc()))
            result.passed = False
        
        return result
    
    def run_all_tests(self):
        """运行所有测试"""
        test_files = self._pick_test_files()
        if not test_files:
            print("未找到测试文件")
            return
        
        # 基础流转测试
        category_map = {
            "奖状": self.test_award_flow,
            "专利": self.test_patent_flow,
            "软著": self.test_software_flow,
            "其他": self.test_other_flow,
            "大创": self.test_innovation_flow,
        }
        
        for category, file_path in test_files.items():
            print(f"\n测试类别: {category}, 文件: {file_path.name}")
            if category in category_map:
                try:
                    result = category_map[category](file_path)
                    self.results.append(result)
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    self.results.append(CategoryResult(
                        category=category,
                        file_path=str(file_path),
                        steps=[StepResult(category, "异常", "-", str(e), False, "")],
                        passed=False
                    ))
        
        # 实验室图片管理测试（使用其他类型的图片）
        if "其他" in test_files:
            print(f"\n测试类别: 实验室图片, 文件: {test_files['其他'].name}")
            try:
                result = self.test_laboratory_image_management(test_files['其他'])
                self.results.append(result)
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.results.append(CategoryResult(
                    category="实验室图片",
                    file_path=str(test_files['其他']),
                    steps=[StepResult("实验室图片", "异常", "-", str(e), False, "")],
                    passed=False
                ))
        
        # 实验室下载文件管理测试（使用其他类型的文件）
        if "其他" in test_files:
            print(f"\n测试类别: 实验室下载, 文件: {test_files['其他'].name}")
            try:
                result = self.test_laboratory_download_management(test_files['其他'])
                self.results.append(result)
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.results.append(CategoryResult(
                    category="实验室下载",
                    file_path=str(test_files['其他']),
                    steps=[StepResult("实验室下载", "异常", "-", str(e), False, "")],
                    passed=False
                ))
        
        # 其他文件管理测试（使用其他类型的文件）
        if "其他" in test_files:
            print(f"\n测试类别: 其他文件管理, 文件: {test_files['其他'].name}")
            try:
                result = self.test_other_file_management(test_files['其他'])
                self.results.append(result)
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.results.append(CategoryResult(
                    category="其他文件管理",
                    file_path=str(test_files['其他']),
                    steps=[StepResult("其他文件管理", "异常", "-", str(e), False, "")],
                    passed=False
                ))
        
        # 文件导入过程文件访问测试（使用其他类型的文件）
        if "其他" in test_files:
            print(f"\n测试类别: 文件导入访问, 文件: {test_files['其他'].name}")
            try:
                result = self.test_file_import_file_access(test_files['其他'])
                self.results.append(result)
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.results.append(CategoryResult(
                    category="文件导入访问",
                    file_path=str(test_files['其他']),
                    steps=[StepResult("文件导入访问", "异常", "-", str(e), False, "")],
                    passed=False
                ))
        
        # 实验室编辑封面图片测试（使用其他类型的图片）
        if "其他" in test_files:
            print(f"\n测试类别: 实验室编辑封面, 文件: {test_files['其他'].name}")
            try:
                result = self.test_laboratory_edit_cover_image(test_files['其他'])
                self.results.append(result)
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.results.append(CategoryResult(
                    category="实验室编辑封面",
                    file_path=str(test_files['其他']),
                    steps=[StepResult("实验室编辑封面", "异常", "-", str(e), False, "")],
                    passed=False
                ))
    
    def generate_report(self) -> Path:
        """生成HTML测试报告"""
        report_dir = project_root / "tests" / "report"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / "文件流转验证.html"
        
        # 构建HTML
        rows = []
        for cr in self.results:
            for s in cr.steps:
                status = "通过" if s.passed else "失败"
                cls = "pass" if s.passed else "fail"
                log_display = f'<pre style="font-size: 10px; max-height: 100px; overflow: auto;">{s.log_snippet}</pre>' if s.log_snippet else ""
                tr = f'''
                <tr>
                    <td>{cr.category}</td>
                    <td>{Path(cr.file_path).name}</td>
                    <td>{s.step}</td>
                    <td>{s.expected}</td>
                    <td>{s.actual}</td>
                    <td class="{cls}">{status}</td>
                    <td>{s.detail}</td>
                    <td>{log_display}</td>
                </tr>
                '''
                rows.append(tr)
        
        all_passed = all(r.passed for r in self.results)
        total_tests = sum(len(r.steps) for r in self.results)
        passed_tests = sum(sum(1 for s in r.steps if s.passed) for r in self.results)
        
        html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <title>文件流转验证报告</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 24px; background: #f5f5f5; }}
    .container {{ background: white; padding: 24px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
    h1 {{ color: #333; margin-top: 0; }}
    .summary {{ background: #f9f9f9; padding: 16px; border-radius: 4px; margin-bottom: 24px; }}
    .summary-item {{ margin: 8px 0; }}
    table {{ border-collapse: collapse; width: 100%; background: white; }}
    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
    th {{ background: #f5f5f5; font-weight: bold; }}
    .pass {{ color: green; font-weight: bold; }}
    .fail {{ color: red; font-weight: bold; }}
    .meta {{ color: #666; }}
    pre {{ margin: 0; white-space: pre-wrap; word-wrap: break-word; }}
  </style>
</head>
<body>
  <div class="container">
    <h1>文件流转验证报告</h1>
    <div class="summary">
      <div class="summary-item"><strong>测试概览:</strong> 总计 {total_tests} 项，通过 {passed_tests} 项，失败 {total_tests - passed_tests} 项</div>
      <div class="summary-item"><strong>整体结果:</strong> <span class="{'pass' if all_passed else 'fail'}">{"全部通过" if all_passed else "存在失败"}</span></div>
      <div class="summary-item"><strong>Files根目录:</strong> <code>{self.files_root}</code></div>
    </div>
    <table>
      <thead>
        <tr>
          <th>类别</th>
          <th>测试文件</th>
          <th>步骤</th>
          <th>预期</th>
          <th>实际</th>
          <th>结果</th>
          <th>备注</th>
          <th>日志片段</th>
        </tr>
      </thead>
      <tbody>
        {''.join(rows)}
      </tbody>
    </table>
  </div>
</body>
</html>
'''
        
        report_path.write_text(html, encoding='utf-8')
        return report_path


def main():
    """主函数"""
    print("=" * 60)
    print("文件流转API测试")
    print("=" * 60)
    
    tester = FileFlowTester()
    tester.run_all_tests()
    
    # 生成报告
    report_path = tester.generate_report()
    print(f"\n报告已生成: {report_path}")
    
    # 自动打开浏览器
    try:
        webbrowser.open(f'file://{report_path.absolute()}')
        print("已在浏览器中打开报告")
    except Exception as e:
        print(f"打开浏览器失败: {e}")
    
    # 统计结果
    failed = sum(1 for r in tester.results if not r.passed)
    total = len(tester.results)
    print(f"\n测试完成: {total - failed}/{total} 个类别通过")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())


def test_file_flow_integration():
    """pytest 入口（T31-T34 批次4）：文件流转 API 全流程集成测试。

    依赖真实库与业务文件（CI 无库环境自动 skip）。运行结束恢复工作目录，
    避免模块级 os.chdir 污染其它用例。
    """
    import os as _os
    from tests.fixtures.schemas import require_real_db
    require_real_db()
    import pytest as _pytest
    # T71-①：本测试是重流程集成（依赖真实库+业务文件+外部服务），改为显式门控收集，
    # 避免资产齐备后自动真跑拖累全量基线。手动运行：
    #   AWARDIE_RUN_FILE_FLOW=1 python -m pytest tests/test_files.py::test_file_flow_integration -v
    if _os.environ.get("AWARDIE_RUN_FILE_FLOW") != "1":
        _pytest.skip("文件流转集成测试为显式门控：设 AWARDIE_RUN_FILE_FLOW=1 启用")
    original_cwd = _os.getcwd()
    try:
        tester = FileFlowTester()
        assets = tester._pick_test_files()
        if not assets:
            _pytest.skip("缺少 images/测试图片 测试资产（CI/新环境无本地图片）")
        assert tester.run_all_tests(), "文件流转流程存在失败步骤，详见上方输出"
    finally:
        _os.chdir(original_cwd)
