import sqlite3
import re
import logging
from pathlib import Path

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def normalize_name(name):
    """
    规范化竞赛名称：
    1. 去除所有非中文字符、非英文字符、非数字（即去除符号、空格等）
    2. 转换为小写
    """
    if not name:
        return ""
    # 替换掉所有非字母、非数字、非中文的字符
    # \u4e00-\u9fa5 是中文字符范围
    # a-zA-Z0-9 是英文字母和数字
    # [^\u4e00-\u9fa5a-zA-Z0-9] 匹配所有非上述字符
    cleaned = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', '', name)
    return cleaned.lower()

def update_tags():
    project_root = Path(__file__).parents[3] # rebuild/tools/赛事等级标记/update_tags.py -> tools -> rebuild -> root
    db_path = project_root / "rebuild/database/competitions.db"
    
    whitelist_file = Path(__file__).parent / "白名单赛事.txt"
    watchlist_file = Path(__file__).parent / "观察目录.txt"
    
    if not db_path.exists():
        logger.error(f"数据库不存在: {db_path}")
        return
        
    # 读取名单并规范化
    whitelist_names = set()
    if whitelist_file.exists():
        with open(whitelist_file, "r", encoding="utf-8") as f:
            for line in f:
                name = line.strip()
                if name:
                    whitelist_names.add(normalize_name(name))
        logger.info(f"读取到白名单赛事: {len(whitelist_names)} 个")
    else:
        logger.warning(f"白名单文件不存在: {whitelist_file}")

    watchlist_names = set()
    if watchlist_file.exists():
        with open(watchlist_file, "r", encoding="utf-8") as f:
            for line in f:
                name = line.strip()
                if name:
                    watchlist_names.add(normalize_name(name))
        logger.info(f"读取到观察目录赛事: {len(watchlist_names)} 个")
    else:
        logger.warning(f"观察目录文件不存在: {watchlist_file}")

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 获取所有竞赛
        cursor.execute("SELECT id, competition_name FROM competitions")
        competitions = cursor.fetchall()
        
        updated_white = 0
        updated_watch = 0
        
        for comp in competitions:
            comp_id = comp['id']
            comp_name = comp['competition_name']
            norm_name = normalize_name(comp_name)
            
            is_white = 0
            is_watch = 0
            
            # 匹配逻辑：
            # 这里简单使用精确匹配规范化后的名称。
            # 如果需要模糊匹配（如包含），可以调整逻辑。
            # 根据需求："忽略所有的符号，比如引号，波折号，大小写" -> 这就是规范化后的精确匹配
            
            # 另外，txt 中的名称可能是全称，数据库中的也可能是全称。
            # 但有时候会有“部分匹配”的情况？
            # 比如数据库是 "蓝桥杯全国软件和信息技术专业人才大赛"，名单是 "蓝桥杯全国软件和信息技术专业人才大赛" -> 匹配
            # 比如数据库是 "蓝桥杯"，名单是 "蓝桥杯全国软件和信息技术专业人才大赛" -> 不匹配？
            # 通常名单是官方全称。我们先尝试全称匹配。
            # 如果名单中的名称包含在数据库名称中，或者反之？
            # 为了更稳健，我们检查：名单名称 是否 == 数据库名称 (规范化后)
            # 或者：名单名称 是否 包含在 数据库名称 中 (规范化后) -> 这样 "蓝桥杯" (DB) 很难匹配 "蓝桥杯全国..." (List)
            # 反之 "蓝桥杯全国..." (DB) 可以匹配 "蓝桥杯" (List)
            # 但这里的名单列表看起来都很长，是全称。
            
            # 让我们遍历名单进行匹配
            
            # 优化：直接判断
            if norm_name in whitelist_names:
                is_white = 1
            else:
                # 尝试模糊匹配：如果名单中的名字出现在数据库名字中，或者数据库名字出现在名单中？
                # 考虑到名单较长，通常是规范名称。
                for w_name in whitelist_names:
                    # 如果规范化后的名单名称 包含 规范化后的数据库名称 (DB: 蓝桥杯, List: 蓝桥杯大赛 -> List包含DB? 不对)
                    # 通常 DB 里的名字可能比较杂。
                    # 如果 DB: "第十五届蓝桥杯...", List: "蓝桥杯..." -> DB 包含 List
                    if w_name in norm_name:
                        is_white = 1
                        break
            
            if norm_name in watchlist_names:
                is_watch = 1
            else:
                for w_name in watchlist_names:
                    if w_name in norm_name:
                        is_watch = 1
                        break
            
            if is_white or is_watch:
                cursor.execute(
                    "UPDATE competitions SET white_list = ?, watch_list = ? WHERE id = ?",
                    (is_white, is_watch, comp_id)
                )
                if is_white: updated_white += 1
                if is_watch: updated_watch += 1
                logger.info(f"更新竞赛 [{comp_name}]: White={is_white}, Watch={is_watch}")
        
        conn.commit()
        logger.info(f"更新完成。白名单: {updated_white}, 观察名单: {updated_watch}")
        
    except sqlite3.Error as e:
        logger.error(f"数据库操作失败: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    update_tags()
