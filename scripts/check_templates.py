"""查询模板ID 36和50的配置，并测试教师证书的OCR文本匹配"""
import sqlite3
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.extract.template import TemplateManager
from config.loader import get_config_loader

project_root = Path(__file__).parent.parent
db_path = project_root / "database" / "competitions.db"

# 查询模板配置
conn = sqlite3.connect(str(db_path))
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=" * 60)
print("查询模板配置")
print("=" * 60)

templates_info = {}
for template_id in [36, 50]:
    row = cur.execute("SELECT id, keywords, default_fields, template_type FROM templates WHERE id=?", (template_id,)).fetchone()
    if row:
        keywords = json.loads(row["keywords"]) if row["keywords"] else []
        default_fields = json.loads(row["default_fields"]) if row["default_fields"] else {}
        templates_info[template_id] = {
            "keywords": keywords,
            "default_fields": default_fields,
            "type": row['template_type']
        }
        print(f"\n模板 ID {template_id}:")
        print(f"  类型: {row['template_type']}")
        print(f"  关键词 ({len(keywords)}个): {keywords}")
        print(f"  默认字段: {json.dumps(default_fields, ensure_ascii=False, indent=4)}")
        print(f"  显示名称: {default_fields.get('competition_name', 'N/A')} ({default_fields.get('granted_role', 'N/A')})")
    else:
        print(f"\n模板 ID {template_id}: 不存在")

conn.close()

# 测试教师证书的OCR文本（模拟）
print("\n" + "=" * 60)
print("测试OCR文本匹配")
print("=" * 60)

# 模拟教师证书的OCR文本（根据图片描述）
test_ocr = """荣誉证书
Certificate of Honor
福州大学至诚学院 陈亦萍
指导 林俊杰
2024年新华三杯全国大学生数字技术大赛
福建 省赛/三等奖,获得[优秀指导教师]称号
特发此证,以此鼓励
新华三集团 总裁
华三技术有限公司
签发日期 2025年04月"""

print(f"\n测试OCR文本（前200字符）:\n{test_ocr[:200]}...")

# 加载模板管理器并测试匹配
config_loader = get_config_loader()
config = config_loader.load_config()

base_fields_map = {}
for doc_type in ["award", "patent", "software"]:
    fields_file = project_root / "backend" / "extract" / "prompts" / f"{doc_type}_fields.json"
    if fields_file.exists():
        with open(fields_file, "r", encoding="utf-8") as f:
            base_fields_map[doc_type] = json.load(f)

config_dir = project_root / "backend" / "extract" / "config"
template_manager = TemplateManager(
    db_path=str(db_path),
    base_fields_map=base_fields_map,
    config_dir=str(config_dir) if config_dir.exists() else None
)

# 测试匹配
from backend.extract.template.matcher import TemplateMatcher
from backend.extract.template.utils import clean_text

default_prompts = {"award": "默认奖状提示词"}
match_result = TemplateMatcher.match_full(test_ocr, template_manager.templates, default_prompts)

print(f"\n匹配结果:")
print(f"  类型: {match_result.type}")
if match_result.template:
    print(f"  模板ID: {match_result.template.template_id}")
    print(f"  模板名称: {match_result.template.get_display_name()}")
    print(f"  相似度: {match_result.similarity:.3f}")
    print(f"  角色: {match_result.template.default_fields.get('granted_role', 'N/A')}")
else:
    print(f"  未匹配到模板")

# 检查每个模板的关键词匹配情况
print(f"\n关键词匹配详情:")
for template_id in [36, 50]:
    template = next((t for t in template_manager.templates if t.template_id == template_id), None)
    if template:
        matched = template.match_by_keywords(test_ocr)
        print(f"  模板 {template_id} ({template.get_display_name()}): {'✓ 匹配' if matched else '✗ 不匹配'}")
        for kw in template.keywords:
            clean_kw = clean_text(kw)
            clean_ocr = clean_text(test_ocr)
            found = clean_kw in clean_ocr
            print(f"    - '{kw}' (清理后: '{clean_kw}'): {'✓' if found else '✗'}")
