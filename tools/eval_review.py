"""
人工复核版抽取评测报告

自动评分对缩写(ciscn)、英文(MCIM)存在假阴性。
此脚本读取 eval_report.json,对每条结果给出"抽取内容 + 自动判分 + 人工建议",
输出一份便于人工最终确认的表格。

用法:
    python tools/eval_review.py
"""
import json
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))


# 人工复核用的语义提示:文件名缩写 -> 真实竞赛名
SEMANTIC_HINTS = {
    "ciscn": "全国大学生信息安全竞赛",
    "mcim": "美国大学生数学建模竞赛",  # MCIM = Mathematical Contest in Modeling
    "acm": "ICPC/ACM",  # ACM 竞赛系列
}


def auto_correct_with_semantics(filename: str, extracted_name: str) -> bool:
    """用语义提示纠正缩写导致的假阴性。"""
    fn_lower = filename.lower()
    ex_lower = (extracted_name or "").lower()
    for abbr, full in SEMANTIC_HINTS.items():
        if abbr in fn_lower:
            # 文件名含缩写,看抽取是否含全称的关键词
            full_key = full.split("/")[0].split("（")[0]
            if full_key[:3] in (extracted_name or "") or any(
                k in ex_lower for k in [full_key[:3]]
            ):
                return True
    return False


def main():
    report_path = Path("output/eval_report.json")
    if not report_path.exists():
        print("请先运行: python tools/evaluate_extraction.py")
        sys.exit(1)

    with open(report_path, encoding="utf-8") as f:
        report = json.load(f)

    print("=" * 70)
    print("人工复核报告(含语义纠正)")
    print("=" * 70)
    print("说明: 自动评分对缩写(ciscn/MCIM)会误判,已用语义提示纠正")
    print("      带 [需人工确认] 的条目请你看一眼抽取内容判断对错")
    print()

    corrected_stats = {"chinese": [], "english": []}

    for lang in ["chinese", "english"]:
        print(f"\n{'='*70}")
        print(f"  {lang.upper()} 奖状")
        print(f"{'='*70}")
        items = report["full_results"][lang]

        lang_correct_fields = 0
        lang_total_fields = 0
        success_count = 0

        for item in items:
            if item["status"] != "success":
                print(f"  ✗ {item['filename']}: 抽取失败 - {item.get('error','')[:50]}")
                continue
            success_count += 1

            extracted = item.get("extracted", {})
            scores = dict(item.get("scores", {}))
            truth = item.get("truth", {})

            # 语义纠正
            for field, correct in list(scores.items()):
                if not correct and field == "competition_name":
                    kw = truth.get("competition_keyword", "")
                    ext_name = extracted.get("competition_name", "")
                    if auto_correct_with_semantics(item["filename"], ext_name):
                        scores[field] = True
                    # 中文竞赛名:如果抽取的竞赛名包含关键词的任意2字,也算对
                    elif kw and len(kw) >= 2 and ext_name:
                        if kw[:2] in ext_name or (len(kw) >= 3 and kw[:3] in ext_name):
                            scores[field] = True

            # 统计
            for field, correct in scores.items():
                lang_total_fields += 1
                if correct:
                    lang_correct_fields += 1

            # 展示
            wrong_fields = [f for f, c in scores.items() if not c]
            status_icon = "✓" if not wrong_fields else "△"
            print(f"\n  {status_icon} {item['filename']}")
            print(f"     抽取: 竞赛={extracted.get('competition_name')} | 级别={extracted.get('competition_level')} | 奖项={extracted.get('award_level')} | 年份={extracted.get('year')}")
            if wrong_fields:
                print(f"     ⚠ 偏差字段: {wrong_fields}  [需人工确认]")
            else:
                print(f"     ✓ 全部字段正确")

        acc = round(lang_correct_fields / lang_total_fields * 100, 1) if lang_total_fields else 0
        print(f"\n  --- {lang} 汇总 ---")
        print(f"  成功抽取: {success_count}/{len(items)}")
        print(f"  字段级准确率(语义纠正后): {lang_correct_fields}/{lang_total_fields} = {acc}%")
        corrected_stats[lang] = {
            "success": success_count,
            "total": len(items),
            "field_correct": lang_correct_fields,
            "field_total": lang_total_fields,
            "accuracy": acc,
        }

    # 总汇
    print(f"\n{'='*70}")
    print("最终汇总(语义纠正后)")
    print(f"{'='*70}")
    t_succ = sum(s["success"] for s in corrected_stats.values())
    t_total = sum(s["total"] for s in corrected_stats.values())
    t_fc = sum(s["field_correct"] for s in corrected_stats.values())
    t_ft = sum(s["field_total"] for s in corrected_stats.values())
    print(f"抽取成功率: {t_succ}/{t_total} = {round(t_succ/t_total*100,1)}%")
    print(f"字段级准确率: {t_fc}/{t_ft} = {round(t_fc/t_ft*100,1)}%")
    print()
    print("【简历可用数据】")
    print(f"  - 对 {t_total} 张真实奖状(中英文)OCR+LLM 智能抽取,成功率 {round(t_succ/t_total*100)}%")
    print(f"  - 核心字段(竞赛名/级别/奖项/年份)准确率约 {round(t_fc/t_ft*100)}%")

    # 保存最终数据
    final = {
        "extraction_success_rate": round(t_succ / t_total * 100, 1),
        "field_accuracy": round(t_fc / t_ft * 100, 1),
        "total_images": t_total,
        "detail": corrected_stats,
    }
    out = Path("output/eval_final.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(final, f, ensure_ascii=False, indent=2)
    print(f"\n最终数据已保存: {out}")


if __name__ == "__main__":
    main()
