"""
清理奖状数据脚本
功能：
通过菜单选择要清理的项目：
1. 删除奖状（包括关联表记录）
2. 删除奖状模板（自动产生的）
3. 删除奖状模板（全部）
4. 删除OCR缓存
5. 删除LLM缓存
6. 删除奖状图片
7. 删除所有活动

使用方法：
    python tools/clean_all.py

注意：此操作不可逆，请谨慎使用！

执行顺序说明：
- 如果同时选择了清理活动和奖状，会先执行奖状清理，再执行活动清理
- 清理活动时会先删除活动与奖状的关联（activity_awards），再删除活动本身
- 这样可以确保先清空活动中的奖状关联，再删除活动

缓存说明：
- OCR缓存：基于图片hash值，如果图片已删除且不重新导入相同图片，缓存无用
- LLM缓存：基于prompt+文本hash值，如果图片已删除，对应的OCR文本也不会再出现，缓存无用
- 建议：如果完全重新开始，建议也清理缓存；如果可能重新导入相同图片，可保留缓存
"""
import sqlite3
import logging
import shutil
from pathlib import Path
from typing import Dict
import sys

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_database_path():
    """获取主数据库路径"""
    db_path = project_root / "database" / "competitions.db"
    if not db_path.exists():
        raise FileNotFoundError(f"数据库文件不存在: {db_path}")
    return db_path


def get_ocr_cache_path():
    """获取OCR缓存数据库路径"""
    db_path = project_root / "database" / "ocr_cache.db"
    return db_path


def get_extract_cache_path():
    """获取LLM提取缓存数据库路径"""
    db_path = project_root / "database" / "extract_cache.db"
    return db_path


def get_images_dir():
    """获取图片目录路径"""
    images_dir = project_root / "files" / "images"
    return images_dir


def count_awards(db_path: Path) -> int:
    """统计奖状数量"""
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM awards")
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except Exception as e:
        logger.error(f"统计奖状数量失败: {e}")
        return 0


def count_images(images_dir: Path) -> int:
    """统计图片文件数量"""
    if not images_dir.exists():
        return 0
    try:
        # 统计所有图片文件
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif']
        count = 0
        for ext in image_extensions:
            count += len(list(images_dir.glob(f"*{ext}")))
            count += len(list(images_dir.glob(f"*{ext.upper()}")))
        return count
    except Exception as e:
        logger.error(f"统计图片数量失败: {e}")
        return 0


def count_templates(db_path: Path) -> int:
    """
    统计奖状模板数量

    注意：award_templates 表已废弃，模板现在存储在 competitions.db 的 templates 表中
    此函数保留用于兼容性，但返回0
    """
    logger.info("award_templates 表已废弃，模板已迁移至 competitions.db 的 templates 表")
    return 0


def count_cache() -> Dict[str, int]:
    """统计缓存数量"""
    ocr_count = 0
    extract_count = 0
    
    # 统计 OCR 缓存
    try:
        ocr_cache_path = get_ocr_cache_path()
        if ocr_cache_path.exists():
            conn = sqlite3.connect(str(ocr_cache_path))
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM ocr_cache")
            ocr_count = cursor.fetchone()[0]
            conn.close()
    except Exception as e:
        logger.error(f"统计OCR缓存数量失败: {e}")
    
    # 统计 LLM 提取缓存
    try:
        extract_cache_path = get_extract_cache_path()
        if extract_cache_path.exists():
            conn = sqlite3.connect(str(extract_cache_path))
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM extract_cache")
            extract_count = cursor.fetchone()[0]
            conn.close()
    except Exception as e:
        logger.error(f"统计LLM提取缓存数量失败: {e}")
    
    return {"ocr": ocr_count, "extract": extract_count}


def count_templates_by_type(db_path: Path) -> Dict[str, int]:
    """
    统计奖状模板数量（自动和手动分开）

    注意：award_templates 表已废弃，模板现在存储在 competitions.db 的 templates 表中
    此函数保留用于兼容性
    """
    logger.info("award_templates 表已废弃，模板已迁移至 competitions.db 的 templates 表")
    return {"auto": 0, "manual": 0}


def count_activities(db_path: Path) -> int:
    """统计活动数量"""
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        # 检查表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='competition_activities'")
        if cursor.fetchone():
            cursor.execute("SELECT COUNT(*) FROM competition_activities")
            count = cursor.fetchone()[0]
        else:
            count = 0
        conn.close()
        return count
    except Exception as e:
        logger.error(f"统计活动数量失败: {e}")
        return 0


def count_pending_achievements(db_path: Path) -> int:
    """统计待审核记录数量（仅 status='submit'，与管理员「待审核」页一致）"""
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pending_achievements'")
        if cursor.fetchone():
            cursor.execute("SELECT COUNT(*) FROM pending_achievements WHERE status = ?", ("submit",))
            count = cursor.fetchone()[0]
        else:
            count = 0
        conn.close()
        return count
    except Exception as e:
        logger.error(f"统计待审核记录数量失败: {e}")
        return 0


def clean_awards(db_path: Path) -> int:
    """
    删除所有奖状记录（包括关联表）
    
    Returns:
        int: 删除的奖状数量
    """
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # 1. 删除关联表记录
        logger.info("正在删除关联表记录...")
        cursor.execute("DELETE FROM award_student_winners")
        deleted_student_winners = cursor.rowcount
        
        cursor.execute("DELETE FROM award_teacher_winners")
        deleted_teacher_winners = cursor.rowcount
        
        cursor.execute("DELETE FROM award_supervisors")
        deleted_supervisors = cursor.rowcount
        
        cursor.execute("DELETE FROM award_related_students")
        deleted_related_students = cursor.rowcount
        
        logger.info(f"   - award_student_winners: {deleted_student_winners} 条")
        logger.info(f"   - award_teacher_winners: {deleted_teacher_winners} 条")
        logger.info(f"   - award_supervisors: {deleted_supervisors} 条")
        logger.info(f"   - award_related_students: {deleted_related_students} 条")
        
        # 2. 删除主表记录
        logger.info("正在删除奖状主表记录...")
        cursor.execute("DELETE FROM awards")
        deleted_awards = cursor.rowcount
        logger.info(f"   - awards: {deleted_awards} 条")
        
        conn.commit()
        conn.close()
        
        logger.info(f"删除奖状完成：共删除 {deleted_awards} 条奖状记录")
        return deleted_awards
        
    except Exception as e:
        logger.error(f"删除奖状失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 0


def clean_templates(db_path: Path, manual_only: bool = False, delete_all: bool = False) -> int:
    """
    删除奖状模板

    注意：award_templates 表已废弃，此函数不再执行任何操作
    模板管理请使用 competitions.db 中的 templates 表

    Args:
        db_path: 数据库路径（不再使用）
        manual_only: 是否只删除手动编辑的模板（不再使用）
        delete_all: 是否删除所有模板（不再使用）

    Returns:
        int: 始终返回 0
    """
    logger.info("award_templates 表已废弃，此函数不再执行任何操作")
    logger.info("模板管理请使用 backend.extract.template.TemplateManager 操作 competitions.db/templates 表")
    return 0


def clean_ocr_cache() -> int:
    """删除OCR缓存"""
    try:
        from backend.ocr.core.cache_db import CacheDB
        ocr_cache_path = get_ocr_cache_path()
        
        if not ocr_cache_path.exists():
            logger.info("OCR缓存数据库不存在，跳过删除")
            return 0
        
        cache_db = CacheDB(str(ocr_cache_path))
        deleted_count = cache_db.delete_ocr_cache()
        logger.info(f"删除OCR缓存完成：共删除 {deleted_count} 条")
        return deleted_count
    except Exception as e:
        logger.error(f"删除OCR缓存失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 0


def clean_extract_cache() -> int:
    """删除LLM提取缓存"""
    try:
        from backend.extract.llm.cache_db import ExtractCacheDB
        extract_cache_path = get_extract_cache_path()
        
        if not extract_cache_path.exists():
            logger.info("LLM提取缓存数据库不存在，跳过删除")
            return 0
        
        cache_db = ExtractCacheDB(str(extract_cache_path))
        # 删除所有缓存（传入 None 表示删除全部）
        deleted_count = cache_db.delete(None)
        logger.info(f"删除LLM提取缓存完成：共删除 {deleted_count} 条")
        return deleted_count
    except Exception as e:
        logger.error(f"删除LLM提取缓存失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 0


def clean_award_images(images_dir: Path) -> int:
    """删除奖状图片文件"""
    if not images_dir.exists():
        logger.info("图片目录不存在，跳过图片删除")
        return 0
    
    try:
        # 统计删除前的文件数
        image_count = count_images(images_dir)
        
        if image_count == 0:
            logger.info("图片目录中没有图片文件，跳过删除")
            return 0
        
        logger.info(f"正在删除图片文件目录: {images_dir}")
        
        # 删除目录中的所有文件
        deleted_count = 0
        for file_path in images_dir.iterdir():
            if file_path.is_file():
                file_path.unlink()
                deleted_count += 1
                logger.debug(f"已删除: {file_path}")
        
        logger.info(f"删除图片文件完成：共删除 {deleted_count} 个文件")
        return deleted_count
        
    except Exception as e:
        logger.error(f"删除图片文件失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 0


def clean_orphaned_files() -> int:
    """清理files目录下的所有文件"""
    try:
        files_dir = project_root / "files"

        if not files_dir.exists():
            logger.info("files 目录不存在，跳过删除")
            return 0

        # 统计文件数量和大小
        total_count = 0
        total_size = 0
        for item in files_dir.rglob("*"):
            if item.is_file():
                total_count += 1
                total_size += item.stat().st_size

        if total_count == 0:
            logger.info("files 目录中没有文件，跳过删除")
            return 0

        logger.info(f"正在清理 files 目录: {files_dir}")
        logger.info(f"发现 {total_count} 个文件，总大小：{total_size / (1024*1024):.2f} MB")

        # 删除所有文件和子目录
        deleted_count = 0
        for item in files_dir.rglob("*"):
            try:
                if item.is_file():
                    item.unlink()
                    deleted_count += 1
                    logger.debug(f"已删除文件: {item.relative_to(files_dir)}")
                elif item.is_dir() and item != files_dir:
                    # 删除空目录（如果目录为空，rmdir会成功）
                    try:
                        item.rmdir()
                        logger.debug(f"已删除目录: {item.relative_to(files_dir)}")
                    except OSError:
                        # 目录不为空，稍后会处理
                        pass
            except Exception as e:
                logger.warning(f"删除 {item} 失败: {e}")

        logger.info(f"清理 files 目录完成：共删除 {deleted_count} 个文件")
        return deleted_count

    except Exception as e:
        logger.error(f"清理 files 目录失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 0


def clean_activities(db_path: Path) -> int:
    """
    删除所有活动记录（包括关联表）
    执行顺序：先删除活动与奖状的关联，再删除活动本身
    
    Returns:
        int: 删除的活动数量
    """
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # 检查表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='competition_activities'")
        if not cursor.fetchone():
            conn.close()
            logger.info("competition_activities 表不存在，跳过")
            return 0
        
        # 1. 先删除活动与奖状的关联（将奖状从活动中清空）
        logger.info("正在删除活动与奖状的关联...")
        cursor.execute("DELETE FROM activity_awards")
        deleted_activity_awards = cursor.rowcount
        logger.info(f"   - activity_awards: {deleted_activity_awards} 条")
        
        # 2. 删除活动与学生的关联
        logger.info("正在删除活动与学生的关联...")
        cursor.execute("DELETE FROM activity_students")
        deleted_activity_students = cursor.rowcount
        logger.info(f"   - activity_students: {deleted_activity_students} 条")
        
        # 3. 删除活动与教师的关联
        logger.info("正在删除活动与教师的关联...")
        cursor.execute("DELETE FROM activity_teachers")
        deleted_activity_teachers = cursor.rowcount
        logger.info(f"   - activity_teachers: {deleted_activity_teachers} 条")
        
        # 4. 删除活动主表记录
        logger.info("正在删除活动主表记录...")
        cursor.execute("DELETE FROM competition_activities")
        deleted_activities = cursor.rowcount
        logger.info(f"   - competition_activities: {deleted_activities} 条")
        
        conn.commit()
        conn.close()
        
        logger.info(f"删除活动完成：共删除 {deleted_activities} 条活动记录")
        return deleted_activities

    except Exception as e:
        logger.error(f"删除活动失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 0


def clean_pending_achievements(db_path: Path) -> int:
    """
    删除待审核记录：仅删除 status='submit' 的记录（与管理员「待审核」页展示一致）。
    不删除 status='pending' 的未提交记录。

    Returns:
        int: 删除的记录数量
    """
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pending_achievements'")
        if not cursor.fetchone():
            conn.close()
            logger.info("pending_achievements 表不存在，跳过")
            return 0

        logger.info("正在删除待审核记录（仅已提交 status=submit）...")
        cursor.execute("DELETE FROM pending_achievements WHERE status = ?", ("submit",))
        deleted_count = cursor.rowcount
        logger.info(f"   - pending_achievements (submit): {deleted_count} 条")

        conn.commit()
        conn.close()

        logger.info(f"删除待审核记录完成：共删除 {deleted_count} 条记录")
        return deleted_count

    except Exception as e:
        logger.error(f"删除待审核记录失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 0


def clean_all_awards(db_path: Path, images_dir: Path, confirm: bool = False, clean_cache: bool = False, clean_templates: bool = False) -> bool:
    """
    清理所有奖状
    
    Args:
        db_path: 数据库路径
        images_dir: 图片目录路径
        confirm: 是否已确认（安全措施）
        clean_cache: 是否清理缓存
        clean_templates: 是否清理模板（默认False，因为模板独立于奖状存在）
    
    Returns:
        bool: 是否成功
    """
    if not confirm:
        logger.error("需要确认才能执行清理操作！请设置 confirm=True")
        return False
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # 1. 删除关联表记录
        logger.info("正在删除关联表记录...")
        cursor.execute("DELETE FROM award_student_winners")
        deleted_student_winners = cursor.rowcount
        
        cursor.execute("DELETE FROM award_teacher_winners")
        deleted_teacher_winners = cursor.rowcount
        
        cursor.execute("DELETE FROM award_supervisors")
        deleted_supervisors = cursor.rowcount
        
        cursor.execute("DELETE FROM award_related_students")
        deleted_related_students = cursor.rowcount
        
        logger.info(f"   - award_student_winners: {deleted_student_winners} 条")
        logger.info(f"   - award_teacher_winners: {deleted_teacher_winners} 条")
        logger.info(f"   - award_supervisors: {deleted_supervisors} 条")
        logger.info(f"   - award_related_students: {deleted_related_students} 条")
        
        # 2. 删除奖状模板表记录（可选）
        # 注意：award_templates 表已废弃，不再删除
        # 模板现在存储在 competitions.db 的 templates 表中
        if clean_templates:
            logger.info("award_templates 表已废弃，跳过删除")
            logger.info("如需清理模板，请使用 backend.extract.template.TemplateManager 操作 competitions.db/templates 表")
        else:
            logger.info("跳过奖状模板删除（模板已迁移至 competitions.db 的 templates 表）")
        
        # 3. 删除主表记录
        logger.info("正在删除奖状主表记录...")
        cursor.execute("DELETE FROM awards")
        deleted_awards = cursor.rowcount
        logger.info(f"   - awards: {deleted_awards} 条")
        
        # 提交事务
        conn.commit()
        conn.close()
        
        logger.info("数据库清理完成")
        
        # 4. 删除图片文件
        if images_dir.exists():
            logger.info(f"正在删除图片文件目录: {images_dir}")
            try:
                # 统计删除前的文件数
                image_count = count_images(images_dir)
                
                # 删除目录中的所有文件
                for file_path in images_dir.iterdir():
                    if file_path.is_file():
                        file_path.unlink()
                        logger.debug(f"已删除: {file_path}")
                
                logger.info(f"已删除 {image_count} 个图片文件")
            except Exception as e:
                logger.error(f"删除图片文件失败: {e}")
                # 图片删除失败不影响整体操作
        else:
            logger.info("图片目录不存在，跳过图片删除")
        
        # 5. 清理缓存（可选）
        if clean_cache:
            logger.info("正在清理缓存...")
            try:
                deleted_ocr = clean_ocr_cache()
                logger.info(f"   - OCR缓存: {deleted_ocr} 条")
                
                deleted_extract = clean_extract_cache()
                logger.info(f"   - LLM提取缓存: {deleted_extract} 条")
                
                logger.info("缓存清理完成")
            except Exception as e:
                logger.error(f"清理缓存失败: {e}")
                # 缓存清理失败不影响整体操作
        
        logger.info("=" * 60)
        logger.info("所有奖状清理完成！")
        logger.info("=" * 60)
        logger.info(f"   - 删除奖状记录: {deleted_awards} 条")
        logger.info(f"   - 删除关联记录: {deleted_student_winners + deleted_teacher_winners + deleted_supervisors + deleted_related_students} 条")
        if clean_templates:
            logger.info("   - 模板记录: 0 条（已废弃的表）")
        else:
            logger.info("   - 模板记录已保留（模板独立于奖状存在）")
        if clean_cache:
            logger.info("   - OCR 和 LLM 缓存已清理")
        else:
            logger.info("   - OCR 和 LLM 缓存已保留")
        
        return True
        
    except Exception as e:
        logger.error(f"清理奖状失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def show_menu(selected_items: set) -> None:
    """显示菜单"""
    menu_items = [
        ("1", "删除奖状（包括所有关联记录）", "awards"),
        ("2", "删除奖状模板（自动产生的）", "templates_auto"),
        ("3", "删除奖状模板（全部）", "templates_all"),
        ("4", "删除OCR缓存", "cache_ocr"),
        ("5", "删除LLM缓存", "cache_extract"),
        ("6", "删除奖状图片", "images"),
        ("7", "删除待审核（仅已提交，与管理员页一致）", "pending_achievements"),
        ("8", "清理files目录（推荐）", "clean_files"),
        ("0", "完成选择，开始清理", "done"),
        ("q", "退出", "quit")
    ]

    print("\n" + "=" * 60)
    print("清理菜单 - 请选择要清理的项目（可多选）")
    print("=" * 60)

    for key, desc, item_id in menu_items:
        marker = "✓" if item_id in selected_items else " "
        print(f"  [{marker}] {key}. {desc}")

    print("=" * 60)


def main():
    """主函数"""
    print("=" * 60)
    print("清理奖状数据工具")
    print("=" * 60)
    print()
    print("警告：此操作不可恢复，请谨慎选择！")
    print()
    
    try:
        db_path = get_database_path()
        images_dir = get_images_dir()
        
        # 统计当前数据
        award_count = count_awards(db_path)
        image_count = count_images(images_dir)
        cache_stats = count_cache()
        template_stats = count_templates_by_type(db_path)
        template_total = count_templates(db_path)
        activity_count = count_activities(db_path)
        pending_count = count_pending_achievements(db_path)

        # 显示当前数据统计
        print("当前数据统计：")
        print(f"  - 奖状数量: {award_count}")
        print(f"  - 奖状模板（自动）: {template_stats['auto']}")
        print(f"  - 奖状模板（手动）: {template_stats['manual']}")
        print(f"  - 奖状模板（总计）: {template_total}")
        print(f"  - OCR缓存数量: {cache_stats['ocr']}")
        print(f"  - LLM提取缓存数量: {cache_stats['extract']}")
        print(f"  - 图片文件数量: {image_count}")
        print(f"  - 活动数量: {activity_count}")
        print(f"  - 待审核记录数量: {pending_count}")
        print()

        # 检查是否有可清理的数据
        has_data = (award_count > 0 or template_stats['auto'] > 0 or template_stats['manual'] > 0 or
                   cache_stats['ocr'] > 0 or cache_stats['extract'] > 0 or image_count > 0 or activity_count > 0 or pending_count > 0)
        
        if not has_data:
            print("没有可清理的数据。")
            return
        
        # 菜单选择循环
        selected_items = set()
        
        while True:
            show_menu(selected_items)
            
            try:
                choice = input("\n请选择 (输入数字/0完成/q退出): ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\n\n操作已取消")
                return
            
            if choice == 'q':
                print("\n操作已取消")
                return
            
            elif choice == '0':
                if not selected_items:
                    print("\n警告：未选择任何清理项目，请至少选择一项")
                    continue
                break
            
            elif choice == '1':
                if 'awards' in selected_items:
                    selected_items.remove('awards')
                    print("已取消选择：删除奖状")
                else:
                    selected_items.add('awards')
                    print("已选择：删除奖状")
            
            elif choice == '2':
                if 'templates_auto' in selected_items:
                    selected_items.remove('templates_auto')
                    print("已取消选择：删除奖状模板（自动产生的）")
                else:
                    selected_items.add('templates_auto')
                    print("已选择：删除奖状模板（自动产生的）")
            
            elif choice == '3':
                if 'templates_all' in selected_items:
                    selected_items.remove('templates_all')
                    print("已取消选择：删除奖状模板（全部）")
                else:
                    selected_items.add('templates_all')
                    print("已选择：删除奖状模板（全部）")
            
            elif choice == '4':
                if 'cache_ocr' in selected_items:
                    selected_items.remove('cache_ocr')
                    print("已取消选择：删除OCR缓存")
                else:
                    selected_items.add('cache_ocr')
                    print("已选择：删除OCR缓存")
            
            elif choice == '5':
                if 'cache_extract' in selected_items:
                    selected_items.remove('cache_extract')
                    print("已取消选择：删除LLM缓存")
                else:
                    selected_items.add('cache_extract')
                    print("已选择：删除LLM缓存")
            
            elif choice == '6':
                if 'images' in selected_items:
                    selected_items.remove('images')
                    print("已取消选择：删除奖状图片")
                else:
                    selected_items.add('images')
                    print("已选择：删除奖状图片")
            
            elif choice == '7':
                if 'pending_achievements' in selected_items:
                    selected_items.remove('pending_achievements')
                    print("已取消选择：删除待审核")
                else:
                    selected_items.add('pending_achievements')
                    print("已选择：删除待审核")

            elif choice == '8':
                if 'clean_files' in selected_items:
                    selected_items.remove('clean_files')
                    print("已取消选择：清理files目录")
                else:
                    selected_items.add('clean_files')
                    print("已选择：清理files目录")

            else:
                print("错误：无效选择，请重新输入")

        # 显示最终确认
        print("\n" + "=" * 60)
        print("已选择的清理项目：")
        for item_id in sorted(selected_items):
            item_names = {
                'awards': '删除奖状',
                'templates_auto': '删除奖状模板（自动产生的）',
                'templates_all': '删除奖状模板（全部）',
                'cache_ocr': '删除OCR缓存',
                'cache_extract': '删除LLM缓存',
                'images': '删除奖状图片',
                'pending_achievements': '删除待审核',
                'clean_files': '清理files目录'
            }
            print(f"  - {item_names.get(item_id, item_id)}")
        print("=" * 60)

        # 如果同时选择了活动和奖状，提示执行顺序
        if 'activities' in selected_items and 'awards' in selected_items:
            print("\n注意：将先执行奖状清理，再执行活动清理（先清空活动中的奖状关联，再删除活动）")
        
        # 最终确认
        print("\n警告：此操作不可恢复！")
        try:
            confirm = input("确认执行清理？(输入 'YES' 确认): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n操作已取消")
            return
        
        if confirm != 'YES':
            print("\n操作已取消")
            return
        
        # 执行清理
        print("\n开始清理...")
        print("-" * 60)
        
        results = {}
        
        # 如果同时选择了活动和奖状，先执行奖状清理
        # 这样可以先清空活动中的奖状关联，再删除活动
        if 'awards' in selected_items:
            results['awards'] = clean_awards(db_path)
        
        if 'templates_auto' in selected_items:
            results['templates_auto'] = clean_templates(db_path, manual_only=False, delete_all=False)
        
        if 'templates_all' in selected_items:
            results['templates_all'] = clean_templates(db_path, manual_only=False, delete_all=True)
        
        if 'cache_ocr' in selected_items:
            results['cache_ocr'] = clean_ocr_cache()
        
        if 'cache_extract' in selected_items:
            results['cache_extract'] = clean_extract_cache()
        
        if 'images' in selected_items:
            results['images'] = clean_award_images(images_dir)

        if 'pending_achievements' in selected_items:
            results['pending_achievements'] = clean_pending_achievements(db_path)

        if 'clean_files' in selected_items:
            results['clean_files'] = clean_orphaned_files()

        # 最后执行活动清理（如果选择了）
        # 这样确保先清空活动中的奖状关联，再删除活动
        if 'activities' in selected_items:
            results['activities'] = clean_activities(db_path)

        # 显示清理结果
        print("\n" + "=" * 60)
        print("清理完成！")
        print("=" * 60)
        print("清理结果：")

        item_names = {
            'awards': '奖状记录',
            'templates_auto': '奖状模板（自动）',
            'templates_all': '奖状模板（全部）',
            'cache_ocr': 'OCR缓存',
            'cache_extract': 'LLM缓存',
            'images': '图片文件',
            'pending_achievements': '待审核记录',
            'clean_files': 'files目录文件',
            'activities': '活动记录',
            'orphaned_files': '孤儿文件'
        }
        
        for item_id, count in results.items():
            print(f"  - {item_names.get(item_id, item_id)}: {count} 条/个")
        
        print("=" * 60)
            
    except FileNotFoundError as e:
        logger.error(f"文件未找到: {e}")
        print(f"错误: {e}")
    except Exception as e:
        logger.error(f"执行失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        print(f"错误: {e}")


if __name__ == "__main__":
    main()

