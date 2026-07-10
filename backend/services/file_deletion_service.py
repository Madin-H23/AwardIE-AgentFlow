"""
业务对象文件删除服务

封装业务对象的文件清理逻辑
"""
from pathlib import Path
from typing import Optional, Dict

from .unified_file_manager import get_unified_file_manager, FileType, LabFileType
from .file_exceptions import FileNotFoundError, OperationFailedError


class FileDeletionService:
    """业务对象文件删除服务"""
    
    def __init__(self):
        """初始化删除服务"""
        self.file_manager = get_unified_file_manager()
    
    def delete_award_image(self, image_hash: str) -> bool:
        """删除奖状图片文件"""
        try:
            file_path = self.file_manager.find_file(FileType.AWARD, image_hash)
            file_path.unlink()
            return True
        except FileNotFoundError:
            return False  # 文件已不存在
        except Exception:
            raise OperationFailedError(f"删除奖状图片失败: {image_hash}")
    
    def delete_patent_file(self, file_path_str: str) -> bool:
        """删除专利文件"""
        if not file_path_str:
            return False
        
        try:
            full_path = self.file_manager.files_root / file_path_str
            if full_path.exists():
                full_path.unlink()
                return True
            return False
        except Exception:
            raise OperationFailedError(f"删除专利文件失败: {file_path_str}")
    
    def delete_software_file(self, file_path_str: str) -> bool:
        """删除软著文件"""
        if not file_path_str:
            return False
        
        try:
            full_path = self.file_manager.files_root / file_path_str
            if full_path.exists():
                full_path.unlink()
                return True
            return False
        except Exception:
            raise OperationFailedError(f"删除软著文件失败: {file_path_str}")
    
    def delete_laboratory_files(self, lab_id: int) -> Dict[str, int]:
        """删除实验室所有文件"""
        results = {'covers': 0, 'downloads': 0, 'photos': 0, 'errors': []}
        
        for lab_file_type in LabFileType:
            try:
                results[lab_file_type.value] = self._delete_lab_files_by_type(lab_id, lab_file_type)
            except Exception as e:
                results['errors'].append(f"删除{lab_file_type.value}失败: {e}")
        
        return results
    
    def _delete_lab_files_by_type(self, lab_id: int, lab_file_type: LabFileType) -> int:
        """删除特定类型的实验室文件"""
        type_dir_key = self.file_manager.directories["laboratories"][lab_file_type.value]
        type_dir = self.file_manager.files_root / type_dir_key
        
        if not type_dir.exists():
            return 0
        
        deleted_count = 0
        pattern = f"lab_{lab_id}_"
        
        for file_path in type_dir.rglob('*'):
            if file_path.is_file() and pattern in file_path.name:
                try:
                    file_path.unlink()
                    deleted_count += 1
                except Exception as e:
                    raise OperationFailedError(f"删除实验室文件失败 {file_path}: {e}")
        
        return deleted_count


# 全局实例
_file_deletion_service: Optional[FileDeletionService] = None


def get_file_deletion_service() -> FileDeletionService:
    """获取文件删除服务实例"""
    global _file_deletion_service
    
    if _file_deletion_service is None:
        _file_deletion_service = FileDeletionService()
    
    return _file_deletion_service