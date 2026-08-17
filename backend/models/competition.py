import sqlite3
import re
import logging
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from pathlib import Path

# 配置日志
logger = logging.getLogger(__name__)

# 缺失竞赛ID常量：当查询不到竞赛时使用此值代替None
# 使用一个特别大的值（2^31 - 1，即INT32_MAX）来表示缺失的竞赛
MISSING_COMPETITION_ID = 2147483647

@dataclass
class Competition:
    """竞赛类"""
    id: int                                         # 竞赛ID (Database Primary Key)
    name: str                                       # 竞赛官方名称
    time_range: Optional[str] = None                # 竞赛举办时间范围描述（原始字符串）
    description: Optional[str] = None               # 竞赛简介
    is_white_list: bool = False                     # 是否为白名单赛事 (高含金量/官方认可)
    is_watch_list: bool = False                     # 是否为观察名单赛事 (考察期)
    grade_category: Optional[str] = None            # 学院判定等级 (如 A类, B类)
    aliases: List[str] = field(default_factory=list)# 竞赛别名列表 (用于模糊匹配)
    related_activities: Optional[List[Any]] = None  # 关联的参赛活动列表，暂设为 None
    reference_materials: Optional[List[Any]] = None  # 竞赛相关参考资料，暂设为 None
    start_month: Optional[int] = None                # 竞赛开始月份（1-12，已解析）
    end_month: Optional[int] = None                  # 竞赛结束月份（1-12，已解析）
    is_auto_added: bool = False                      # 是否为程序自动添加（True=程序添加，False=手工添加）
    official_website: Optional[str] = None           # 官网链接
    organizer: Optional[str] = None                  # 主办单位
    participant_requirements: Optional[str] = None   # 参赛要求

    @staticmethod
    def _chinese_to_arabic_month(chinese_text: str) -> Optional[int]:
        """
        将中文月份数字转换为阿拉伯数字（1-12）
        
        Args:
            chinese_text: 中文数字文本（如"一"、"十二"等，不包含"月"字）
        
        Returns:
            对应的阿拉伯数字（1-12），如果无法转换返回None
        """
        chinese_month_map = {
            '一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6,
            '七': 7, '八': 8, '九': 9, '十': 10, '十一': 11, '十二': 12
        }
        text = chinese_text.strip()
        return chinese_month_map.get(text)

    @staticmethod
    def _normalize_month_text(month_text: str) -> Optional[int]:
        """
        规范化月份文本，支持中文数字和阿拉伯数字
        
        Args:
            month_text: 月份文本（可能是中文数字或阿拉伯数字，可能包含"月"字）
        
        Returns:
            对应的阿拉伯数字（1-12），如果无法转换返回None
        """
        if not month_text:
            return None
        text = month_text.replace('月', '').strip()
        if text.isdigit():
            month_num = int(text)
            if 1 <= month_num <= 12:
                return month_num
            return None
        return Competition._chinese_to_arabic_month(text)

    @staticmethod
    def _parse_time_range(time_range_str: Optional[str]) -> Tuple[int, int]:
        """
        解析时间范围字符串，返回开始月份和结束月份
        
        Args:
            time_range_str: 时间范围字符串（如"4-10月"、"五月"等）
        
        Returns:
            Tuple[int, int]: (start_month, end_month)
            如果解析失败，返回默认值 (1, 11)
        """
        default_start = 1
        default_end = 11
        
        if not time_range_str:
            return default_start, default_end
        
        time_range_raw = time_range_str.replace(' ', '').replace('到', '-')
        
        if '-' in time_range_raw:
            # 处理范围格式（如"4-10月"、"四月-十月"等）
            parts = time_range_raw.split('-', 1)
            start_month_text = parts[0].strip()
            end_month_text = parts[1].strip()
            
            start_month = Competition._normalize_month_text(start_month_text)
            end_month = Competition._normalize_month_text(end_month_text)
            
            if start_month is None or end_month is None:
                logger.warning(f"时间范围解析失败: {time_range_str}")
                return default_start, default_end
            
            if not (1 <= start_month <= 12) or not (1 <= end_month <= 12):
                logger.warning(f"时间范围不合法: {time_range_str}")
                return default_start, default_end
            
            return start_month, end_month
        else:
            # 处理单个数字格式（如"5月"、"五月"等）
            month_int = Competition._normalize_month_text(time_range_raw)
            
            if month_int is None:
                logger.warning(f"时间范围解析失败: {time_range_str}")
                return default_start, default_end
            
            if not (1 <= month_int <= 12):
                logger.warning(f"时间范围不合法: {time_range_str}")
                return default_start, default_end
            
            # 以当前数字为中心，向前后各扩展一个月，处理月份回绕
            start_month = month_int - 1
            end_month = month_int + 1
            if start_month < 1:
                start_month = 12
            if end_month > 12:
                end_month = 1
            
            return start_month, end_month

    @classmethod
    def from_db_row(cls, row: sqlite3.Row) -> 'Competition':
        """从数据库行构建对象"""
        # 解析 alias_list (假设是以逗号或换行分隔的字符串)
        alias_str = row['alias_list'] or ""
        aliases = [
            a.strip()
            for a in re.split(r'[;,，；\n]', alias_str)
            if a.strip()
        ]

        # 解析时间范围
        time_range_str = row['competition_time']
        start_month, end_month = cls._parse_time_range(time_range_str)

        # 处理 is_auto_added 字段（兼容旧数据库，如果字段不存在则默认为 False）
        is_auto_added = False
        if 'is_auto_added' in row.keys():
            is_auto_added = bool(row['is_auto_added'])

        # 获取官网链接（如果存在）
        official_website = None
        if 'official_website' in row.keys():
            official_website = row['official_website']

        # 获取主办单位（如果存在）
        organizer = None
        if 'organizer' in row.keys():
            organizer = row['organizer']

        # 获取参赛要求（如果存在）
        participant_requirements = None
        if 'participant_requirements' in row.keys():
            participant_requirements = row['participant_requirements']

        return cls(
            id=row['id'],
            name=row['competition_name'],
            time_range=time_range_str,
            description=row['brief_description'],
            is_white_list=bool(row['white_list']),
            is_watch_list=bool(row['watch_list']),
            grade_category=row['grade_category'],
            aliases=aliases,
            start_month=start_month,
            end_month=end_month,
            is_auto_added=is_auto_added,
            official_website=official_website,
            organizer=organizer,
            participant_requirements=participant_requirements
        )

class CompetitionManager:
    """竞赛管理类"""
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            logger.error(f"数据库文件不存在: {self.db_path}")
            # 可以在这里抛出异常，或者保持空状态
            
        self.competitions: List[Competition] = []
        self._load_data()

    def _get_db_connection(self):
        from backend.utils.db_connection import get_connection

        return get_connection(self.db_path)

    def _load_data(self):
        """从数据库加载数据"""
        if not self.db_path.exists():
            return

        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()

            # 加载 Competitions
            cursor.execute("SELECT * FROM competitions")
            comp_rows = cursor.fetchall()

            self.competitions = []
            for row in comp_rows:
                comp = Competition.from_db_row(row)
                self.competitions.append(comp)

            logger.info(f"成功加载 {len(self.competitions)} 个竞赛信息")
            
        except sqlite3.Error as e:
            logger.error(f"加载竞赛数据失败: {e}")
        finally:
            if 'conn' in locals():
                conn.close()

    def _normalize_text(self, text: str) -> str:
        """
        规范化文本用于匹配：
        去除所有非中文、非字母、非数字字符，并转为小写
        """
        if not text:
            return ""
        # 确保 text 是字符串类型
        if not isinstance(text, str):
            text = str(text)
        # 保留 中文(\u4e00-\u9fa5)、字母(a-zA-Z)、数字(0-9)
        cleaned = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', '', text)
        return cleaned.lower()

    def get_competition_by_id(self, comp_id: int) -> Optional[Competition]:
        """根据ID获取竞赛（先查内存）"""
        for comp in self.competitions:
            if comp.id == comp_id:
                return comp
        return None

    def get_competition_by_id_from_db(self, comp_id: int) -> Optional[Competition]:
        """
        从数据库按 ID 加载竞赛；若找到则加入内存列表并返回。
        用于奖状列表等场景中，展示尚未在内存列表中的竞赛（如本请求内新建的竞赛）。
        """
        if comp_id is None:
            return None
        try:
            conn = self._get_db_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM competitions WHERE id = ?", (int(comp_id),))
                row = cursor.fetchone()
                if row is None:
                    return None
                comp = Competition.from_db_row(row)
                if comp and not any(c.id == comp.id for c in self.competitions):
                    self.competitions.append(comp)
                return comp
            finally:
                conn.close()
        except (sqlite3.Error, TypeError, ValueError) as e:
            logger.warning("从数据库加载竞赛失败 comp_id=%s: %s", comp_id, e)
            return None
    
    def get_competition_name_by_id(self, comp_id: int) -> Optional[str]:
        """
        根据竞赛ID获取竞赛名称（便捷方法）
        
        Args:
            comp_id: 竞赛ID
        
        Returns:
            竞赛名称，如果找不到返回 None
        """
        comp = self.get_competition_by_id(comp_id)
        return comp.name if comp else None

    def get_competition_id_by_name(self, competition_name: str) -> int:
        """
        通过竞赛名称获取竞赛ID，如果找不到则自动添加竞赛
        
        :param competition_name: 竞赛名称（必须是非空字符串）
        :return: 竞赛ID（永远返回合法的竞赛ID，不会返回缺失值）
        :raises: ValueError 如果 competition_name 为空或不是字符串
        """
        # 参数验证：如果为空或不是字符串，抛出异常
        if not competition_name:
            raise ValueError("competition_name 不能为空")
        if not isinstance(competition_name, str):
            raise ValueError(f"competition_name 必须是字符串类型，当前类型: {type(competition_name)}")
        
        competition_name = competition_name.strip()
        if not competition_name:
            raise ValueError("competition_name 不能为空字符串")
        
        # 先尝试匹配现有竞赛
        comp = self.match_competition(competition_name)
        if comp:
            return comp.id
        
        # 如果找不到，自动添加竞赛（程序添加）
        logger.info(f"未找到竞赛 '{competition_name}'，自动添加为新竞赛（程序添加）")
        new_id = self.add_competition(
            name=competition_name,
            is_auto_added=True
        )
        
        if new_id is None:
            raise RuntimeError(f"自动添加竞赛 '{competition_name}' 失败")
        
        return new_id

    PLACEHOLDER_COMPETITION_NAME = "待补充"

    def get_or_create_placeholder_competition_id(self) -> int:
        """
        获取或创建占位竞赛（名称固定为「待补充」），用于 competition_name 为空时的奖状入库。
        竞赛表 competition_name UNIQUE，故全局仅一条。
        """
        comp = self.match_competition(self.PLACEHOLDER_COMPETITION_NAME)
        if comp:
            return comp.id
        logger.info(f"创建占位竞赛「{self.PLACEHOLDER_COMPETITION_NAME}」")
        new_id = self.add_competition(
            name=self.PLACEHOLDER_COMPETITION_NAME,
            is_auto_added=True
        )
        if new_id is None:
            raise RuntimeError(f"创建占位竞赛「{self.PLACEHOLDER_COMPETITION_NAME}」失败")
        return new_id

    @staticmethod
    def is_missing_competition_id(comp_id: Optional[int]) -> bool:
        """
        检查竞赛ID是否为缺失值
        :param comp_id: 竞赛ID
        :return: 如果是缺失值返回True，否则返回False
        """
        return comp_id is None or comp_id == MISSING_COMPETITION_ID

    def match_competition(self, query_name: str) -> Optional[Competition]:
        """
        竞赛匹配：
        匹配竞赛名称或别名（忽略符号、大小写、空格）
        """
        if not query_name:
            return None
        
        # 确保是字符串类型
        if not isinstance(query_name, str):
            query_name = str(query_name).strip()
            if not query_name:
                return None
            
        norm_query = self._normalize_text(query_name)
        
        # 优先级 1: 精确匹配 (名称或别名)
        for comp in self.competitions:
            # 1. 匹配主名称
            if self._normalize_text(comp.name) == norm_query:
                return comp
            
            # 2. 匹配别名
            for alias in comp.aliases:
                if self._normalize_text(alias) == norm_query:
                    return comp
                    
        # 优先级 2: 包含别名匹配 (输入字符串包含别名)
        # 寻找匹配长度最长的别名，以避免短关键词误判
        best_match: Optional[Competition] = None
        max_len = 0
        
        for comp in self.competitions:
            # 检查名称和别名
            candidates = [comp.name] + comp.aliases
            for cand in candidates:
                norm_cand = self._normalize_text(cand)
                if not norm_cand:
                    continue
                
                # 如果输入包含别名 (例如: 输入 "2024蓝桥杯省赛" 包含 "蓝桥杯")
                if norm_cand in norm_query:
                    # 记录匹配长度，取最长匹配
                    if len(norm_cand) > max_len:
                        max_len = len(norm_cand)
                        best_match = comp
                        
        if best_match:
            return best_match
            
        return None

    def associate_competition_from_template(
        self, template_id: int, template_manager: Any
    ) -> Optional[Competition]:
        """
        从模板的 default_fields 中获取 competition_name 并匹配竞赛
        
        Args:
            template_id: 模板ID
            template_manager: 模板管理器实例
            
        Returns:
            匹配到的 Competition 对象，如果未匹配到则返回 None
        """
        if not template_id or not template_manager:
            return None
        
        try:
            template = template_manager.get_template(template_id)
            if template and template.default_fields:
                template_competition_name = template.default_fields.get('competition_name')
                if template_competition_name:
                    matched_competition = self.match_competition(template_competition_name)
                    
                    return matched_competition
        except Exception as e:
            logger.warning(f"从模板获取竞赛失败: {e}", exc_info=True)
        
        return None

    def associate_competition_from_name(
        self, competition_name: str
    ) -> Optional[Competition]:
        """
        通过 competition_name 匹配竞赛（封装 match_competition）
        
        Args:
            competition_name: 竞赛名称
            
        Returns:
            匹配到的 Competition 对象，如果未匹配到则返回 None
        """
        if not competition_name:
            return None
        
        return self.match_competition(competition_name)

    def add_alias(self, comp_id: int, new_alias: str) -> bool:
        """添加竞赛别名并同步到数据库"""
        comp = self.get_competition_by_id(comp_id)
        if not comp:
            logger.warning(f"找不到竞赛 ID: {comp_id}")
            return False
            
        if new_alias in comp.aliases:
            logger.info(f"别名 '{new_alias}' 已存在")
            return True # 视为成功
            
        # 更新内存
        comp.aliases.append(new_alias)
        
        # 同步数据库
        return self._sync_aliases_to_db(comp)

    def update_aliases(self, comp_id: int, aliases: List[str]) -> bool:
        """更新竞赛别名列表（覆盖）"""
        comp = self.get_competition_by_id(comp_id)
        if not comp:
            return False
            
        comp.aliases = aliases
        return self._sync_aliases_to_db(comp)

    def _sync_aliases_to_db(self, comp: Competition) -> bool:
        """将别名列表同步回数据库"""
        # 将列表转换为逗号分隔字符串
        alias_str = ",".join(comp.aliases)
        
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                "UPDATE competitions SET alias_list = ? WHERE id = ?",
                (alias_str, comp.id)
            )
            conn.commit()
            logger.info(f"已更新竞赛 [{comp.name}] 的别名列表")
            return True
        except sqlite3.Error as e:
            logger.error(f"更新数据库别名失败: {e}")
            return False
        finally:
            if 'conn' in locals():
                conn.close()

    def add_competition(self, 
                       name: str, 
                       alias_list: str = "",
                       official_website: str = "",
                       organizer: str = "",
                       competition_time: str = "",
                       participant_requirements: str = "",
                       grade_category: str = "",
                       brief_description: str = "",
                       white_list: bool = False,
                       watch_list: bool = False,
                       is_auto_added: bool = False) -> Optional[int]:
        """
        添加新竞赛
        
        :param name: 竞赛名称
        :param alias_list: 别名列表（逗号分隔）
        :param official_website: 官网链接
        :param organizer: 主办单位
        :param competition_time: 举办时间范围
        :param participant_requirements: 参赛要求
        :param grade_category: 竞赛等级分类
        :param brief_description: 简介
        :param white_list: 是否白名单赛事
        :param watch_list: 是否观察名单赛事
        :param is_auto_added: 是否为程序自动添加（True=程序添加，False=手工添加）
        :return: 新添加的竞赛ID，如果失败返回None
        """
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            # 检查 is_auto_added 字段是否存在，如果不存在则先添加字段
            cursor.execute("PRAGMA table_info(competitions)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'is_auto_added' not in columns:
                logger.warning("数据库表 competitions 中缺少 is_auto_added 字段，请运行迁移脚本")
                # 如果字段不存在，使用默认值 False（手工添加）
                is_auto_added_value = 0
            else:
                is_auto_added_value = 1 if is_auto_added else 0
            
            cursor.execute("""
                INSERT INTO competitions (
                    competition_name, alias_list, official_website, organizer,
                    competition_time, participant_requirements, grade_category,
                    brief_description, white_list, watch_list, is_auto_added
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                name, alias_list, official_website, organizer,
                competition_time, participant_requirements, grade_category,
                brief_description, 1 if white_list else 0, 1 if watch_list else 0,
                is_auto_added_value
            ))
            conn.commit()
            new_id = cursor.lastrowid
            
            # 更新内存
            aliases = [a.strip() for a in re.split(r'[;,，；\n]', alias_list) if a.strip()]
            start_month, end_month = Competition._parse_time_range(competition_time)
            new_comp = Competition(
                id=new_id,
                name=name,
                time_range=competition_time,
                description=brief_description,
                is_white_list=white_list,
                is_watch_list=watch_list,
                grade_category=grade_category,
                aliases=aliases,
                start_month=start_month,
                end_month=end_month,
                is_auto_added=is_auto_added
            )
            self.competitions.append(new_comp)
            add_type = "程序自动添加" if is_auto_added else "手工添加"
            logger.info(f"已添加新竞赛: {name} (ID: {new_id}, {add_type})")
            return new_id
        except sqlite3.Error as e:
            logger.error(f"添加竞赛失败: {e}")
            return None
        finally:
            if 'conn' in locals():
                conn.close()
    
    def update_competition(self, 
                          comp_id: int,
                          name: str = None,
                          alias_list: str = None,
                          official_website: str = None,
                          organizer: str = None,
                          competition_time: str = None,
                          participant_requirements: str = None,
                          grade_category: str = None,
                          brief_description: str = None,
                          white_list: bool = None,
                          watch_list: bool = None) -> bool:
        """更新竞赛信息"""
        comp = self.get_competition_by_id(comp_id)
        if not comp:
            logger.warning(f"找不到竞赛 ID: {comp_id}")
            return False
        
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            # 构建更新字段
            updates = []
            values = []
            
            if name is not None:
                updates.append("competition_name = ?")
                values.append(name)
                comp.name = name
            
            if alias_list is not None:
                updates.append("alias_list = ?")
                values.append(alias_list)
                comp.aliases = [a.strip() for a in re.split(r'[;,，；\n]', alias_list) if a.strip()]
            
            if official_website is not None:
                updates.append("official_website = ?")
                values.append(official_website)
            
            if organizer is not None:
                updates.append("organizer = ?")
                values.append(organizer)
            
            if competition_time is not None:
                updates.append("competition_time = ?")
                values.append(competition_time)
                comp.time_range = competition_time
                # 重新解析时间范围
                comp.start_month, comp.end_month = Competition._parse_time_range(competition_time)
            
            if participant_requirements is not None:
                updates.append("participant_requirements = ?")
                values.append(participant_requirements)
            
            if grade_category is not None:
                updates.append("grade_category = ?")
                values.append(grade_category)
                comp.grade_category = grade_category
            
            if brief_description is not None:
                updates.append("brief_description = ?")
                values.append(brief_description)
                comp.description = brief_description
            
            if white_list is not None:
                updates.append("white_list = ?")
                values.append(1 if white_list else 0)
                comp.is_white_list = white_list
            
            if watch_list is not None:
                updates.append("watch_list = ?")
                values.append(1 if watch_list else 0)
                comp.is_watch_list = watch_list
            
            if not updates:
                return True  # 没有需要更新的字段
            
            values.append(comp_id)
            sql = f"UPDATE competitions SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(sql, values)
            conn.commit()
            
            logger.info(f"已更新竞赛 ID: {comp_id}")
            return True
        except sqlite3.Error as e:
            logger.error(f"更新竞赛失败: {e}")
            return False
        finally:
            if 'conn' in locals():
                conn.close()

    def find_all_references(self, comp_id: int, db_path: Optional[str] = None) -> Dict[str, int]:
        """
        查找所有引用该竞赛的实体
        
        Args:
            comp_id: 竞赛ID
            db_path: 数据库路径（如果为None，使用self.db_path）
        
        Returns:
            包含各类引用统计的字典，格式：{"awards": count, "templates": count, ...}
        """
        if db_path is None:
            db_path = self.db_path
        
        stats = {
            "awards": 0,
            "templates": 0,  # 预留，如果将来有模板表
        }
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # 检查 awards 表
            cursor.execute("SELECT COUNT(*) FROM awards WHERE competition_id = ?", (comp_id,))
            stats["awards"] = cursor.fetchone()[0]
            
            # 预留：检查其他可能的引用表
            # cursor.execute("SELECT COUNT(*) FROM award_templates WHERE competition_id = ?", (comp_id,))
            # stats["templates"] = cursor.fetchone()[0]
            
            conn.close()
        except sqlite3.Error as e:
            logger.error(f"查询竞赛引用失败: {e}")
        
        return stats
    
    def can_delete_competition(self, comp_id: int, db_path: Optional[str] = None) -> Tuple[bool, Dict[str, int], str]:
        """
        检查竞赛是否可以删除
        
        Args:
            comp_id: 竞赛ID
            db_path: 数据库路径（如果为None，使用self.db_path）
        
        Returns:
            (是否可以删除, 引用统计字典, 错误消息)
        """
        # 检查竞赛是否存在
        comp = self.get_competition_by_id(comp_id)
        if not comp:
            return False, {}, f"竞赛 ID {comp_id} 不存在"
        
        # 查找所有引用
        refs = self.find_all_references(comp_id, db_path)
        
        # 统计总引用数
        total_refs = sum(refs.values())
        
        if total_refs > 0:
            # 构建详细的错误消息
            ref_details = []
            if refs["awards"] > 0:
                ref_details.append(f"{refs['awards']} 个奖状")
            if refs["templates"] > 0:
                ref_details.append(f"{refs['templates']} 个模板")
            
            error_msg = f"无法删除竞赛「{comp.name}」（ID: {comp_id}），存在关联数据：{', '.join(ref_details)}"
            return False, refs, error_msg
        
        return True, refs, ""
    
    def delete_competition(self, comp_id: int, force: bool = False) -> Tuple[bool, str]:
        """
        删除竞赛

        Args:
            comp_id: 竞赛ID
            force: 是否强制删除（即使有关联数据也删除，危险操作）

        Returns:
            (是否成功, 错误消息)
        """
        # 检查是否可以删除
        can_delete, refs, error_msg = self.can_delete_competition(comp_id)

        if not can_delete and not force:
            logger.warning(f"拒绝删除竞赛 ID {comp_id}: {error_msg}")
            return False, error_msg

        if not can_delete and force:
            logger.warning(f"强制删除竞赛 ID {comp_id}，将删除 {refs.get('awards', 0)} 个关联奖状")
            # 注意：强制删除时，关联的奖状仍然保留 competition_id，但竞赛已不存在
            # 这会导致数据不一致，建议在业务层处理关联数据的清理

        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()

            # 删除竞赛本身
            cursor.execute("DELETE FROM competitions WHERE id = ?", (comp_id,))
            conn.commit()

            # 更新内存
            comp = self.get_competition_by_id(comp_id)
            if comp:
                self.competitions.remove(comp)

            logger.info(f"已删除竞赛 ID: {comp_id}")
            return True, "删除成功"
        except sqlite3.Error as e:
            error_msg = f"删除竞赛失败: {e}"
            logger.error(error_msg)
            return False, error_msg
        finally:
            if 'conn' in locals():
                conn.close()

    def is_white_list_competion(self, competition_name: str) -> bool:
        """
        检查竞赛是否在白名单中（支持别名匹配）
        
        Args:
            competition_name: 竞赛名称（可以是主名称或别名）
        
        Returns:
            bool: 如果竞赛在白名单中返回 True，否则返回 False
        """
        if not competition_name:
            return False
        
        # 使用 match_competition 方法匹配竞赛（支持别名）
        comp = self.match_competition(competition_name)
        if comp:
            return comp.is_white_list
        
        return False

    def is_watch_list_competion(self, competition_name: str) -> bool:
        """
        检查竞赛是否在观察名单中（支持别名匹配）
        
        Args:
            competition_name: 竞赛名称（可以是主名称或别名）
        
        Returns:
            bool: 如果竞赛在观察名单中返回 True，否则返回 False
        """
        if not competition_name:
            return False
        
        # 使用 match_competition 方法匹配竞赛（支持别名）
        comp = self.match_competition(competition_name)
        if comp:
            return comp.is_watch_list
        
        return False

    def get_competition_time_range(self, competition_name: str) -> Tuple[List[int], bool]:
        """
        获取竞赛的举办时间范围（兼容方法，推荐直接访问 competition.start_month 和 end_month）
        
        Args:
            competition_name: 竞赛名称
        
        Returns:
            Tuple[List[int], bool]: (月份范围, 是否成功)
            - 如果成功解析时间范围，返回 (月份列表, True)
            - 如果使用默认值，返回 ([1, 11], False)
        
        Note:
            推荐直接使用 competition.start_month 和 competition.end_month 属性
        """
        comp = self.match_competition(competition_name)
        if not comp:
            logger.warning(f"竞赛 {competition_name} 未找到")
            return [1, 11], False
        
        if comp.start_month is None or comp.end_month is None:
            logger.warning(f"竞赛 {competition_name} 没有解析到时间范围")
            return [1, 11], False
        
        return [comp.start_month, comp.end_month], True