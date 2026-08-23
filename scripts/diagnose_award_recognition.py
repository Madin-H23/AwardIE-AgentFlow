"""
诊断奖状识别问题

分析为什么奖状无法识别为奖状类型
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(project_root))

from backend.ocr import OCREngine
from backend.extract.template.matcher import TypeMatcher, TemplateMatcher
from config.loader import get_config_loader

def diagnose_award_recognition(image_path: str):
    """诊断奖状识别问题"""
    print("=" * 60)
    print("奖状识别诊断")
    print("=" * 60)
    
    # 1. 加载配置
    config_loader = get_config_loader()
    config = config_loader.load_config()
    
    # 2. 执行OCR
    print("\n[步骤1] 执行OCR识别...")
    ocr_engine = OCREngine.from_config_loader(config_loader)
    ocr_text, _ = ocr_engine.get_text(image_path, use_cache=True, is_precise=True)
    
    if not ocr_text:
        print("❌ OCR识别失败，无法获取文本")
        return
    
    print(f"✓ OCR识别成功")
    print(f"  文本长度: {len(ocr_text)} 字符")
    print(f"  文本预览（前200字符）: {ocr_text[:200]}...")
    
    # 3. 加载类型匹配规则
    print("\n[步骤2] 加载类型匹配规则...")
    config_dir = project_root / "backend" / "extract" / "config"
    TemplateMatcher.load_configs(str(config_dir))
    
    # 4. 执行类型匹配
    print("\n[步骤3] 执行类型匹配...")
    doc_type = TypeMatcher.match(ocr_text)
    print(f"  匹配结果: {doc_type}")
    
    if doc_type == "other":
        print("\n❌ 类型匹配失败，返回 'other'")
        print("\n[诊断] 分析失败原因...")
        
        # 检查文本长度
        from backend.extract.template.utils import clean_text
        clean_text_input = clean_text(ocr_text)
        text_len = len(clean_text_input)
        print(f"  清理后文本长度: {text_len} 字符")
        
        # 检查award规则
        import json
        type_rules_file = config_dir / "type_rules.json"
        with open(type_rules_file, 'r', encoding='utf-8') as f:
            rules = json.load(f)
        
        award_rules = rules.get("award", {})
        min_length = award_rules.get("min_length", 0)
        print(f"  award类型最小长度要求: {min_length} 字符")
        
        if text_len < min_length:
            print(f"  ❌ 文本长度不足: {text_len} < {min_length}")
        else:
            print(f"  ✓ 文本长度满足要求: {text_len} >= {min_length}")
        
        # 检查排除关键词
        exclude_keywords = award_rules.get("exclude_keywords", [])
        found_excludes = []
        for keyword in exclude_keywords:
            if keyword in clean_text_input:
                found_excludes.append(keyword)
        
        if found_excludes:
            print(f"  ❌ 包含排除关键词: {found_excludes}")
        else:
            print(f"  ✓ 不包含排除关键词")
        
        # 检查条件
        conditions = award_rules.get("conditions", [])
        print(f"\n  检查匹配条件（共{len(conditions)}个）...")
        matched_conditions = []
        for idx, condition in enumerate(conditions):
            cond_type = condition.get("type")
            if cond_type == "contains":
                keyword = condition.get("keyword", "")
                case_insensitive = condition.get("case_insensitive", False)
                if case_insensitive:
                    matched = keyword.lower() in clean_text_input.lower()
                else:
                    matched = keyword in clean_text_input
                if matched:
                    matched_conditions.append(f"条件{idx+1}: 包含'{keyword}'")
            elif cond_type == "and":
                keywords = condition.get("keywords", [])
                matched = all(kw in clean_text_input for kw in keywords)
                if matched:
                    matched_conditions.append(f"条件{idx+1}: 同时包含{keywords}")
        
        if matched_conditions:
            print(f"  ✓ 匹配到的条件:")
            for cond in matched_conditions:
                print(f"    - {cond}")
        else:
            print(f"  ❌ 没有匹配到任何条件")
            print(f"\n  提示: 需要满足以下任一条件:")
            for idx, condition in enumerate(conditions[:5]):  # 只显示前5个
                cond_type = condition.get("type")
                if cond_type == "contains":
                    keyword = condition.get("keyword", "")
                    print(f"    - 包含关键词: '{keyword}'")
                elif cond_type == "and":
                    keywords = condition.get("keywords", [])
                    print(f"    - 同时包含: {keywords}")
    else:
        print(f"\n✓ 类型匹配成功，识别为: {doc_type}")
    
    # 5. 检查关键词匹配（框架层面）
    print("\n[步骤4] 检查框架层面的关键词匹配...")
    from backend.extract.extractors.award import AwardExtractor
    award_config = config.get("extract", {}).get("award", {})
    from backend.extract.template import TemplateManager
    db_path = str(config_loader.get_path("database", "competitions_db"))
    template_manager = TemplateManager(
        db_path=db_path,
        base_fields_map={},
        config_dir=str(config_dir) if config_dir.exists() else None
    )
    extractor = AwardExtractor(award_config, template_manager=template_manager)
    
    matches = extractor.matches_keywords(ocr_text)
    print(f"  关键词匹配结果: {matches}")
    if matches:
        print(f"  ✓ 框架层面匹配成功，会使用 AwardExtractor")
    else:
        print(f"  ❌ 框架层面匹配失败，不会使用 AwardExtractor")
        print(f"  检查的关键词: {extractor.keywords[:10]}...")  # 只显示前10个
    
    print("\n" + "=" * 60)
    print("诊断完成")
    print("=" * 60)


if __name__ == "__main__":
    import sys
    import os
    # 设置UTF-8编码
    if sys.platform == 'win32':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    
    if len(sys.argv) < 2:
        print("使用方法: python diagnose_award_recognition.py <图片路径>")
        print("示例: python diagnose_award_recognition.py images/测试图片/奖状/2025一带一路邓明豪.jpg")
        sys.exit(1)
    
    image_path = sys.argv[1]
    if not Path(image_path).exists():
        print(f"错误: 文件不存在: {image_path}")
        sys.exit(1)
    
    diagnose_award_recognition(image_path)
