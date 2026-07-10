"""
批量抽取准确率评测脚本

对测试奖状图片集批量跑 OCR+LLM 抽取,统计:
1. 抽取成功率(能成功返回结构化数据的比例)
2. 字段级准确率(正确字段数 / 总字段数)
3. 竞赛名/获奖人/奖项级别 三个核心字段的准确率

ground truth 来自文件名编码(如"2024数据安全-李杰-省赛-二等奖")。
结果输出到 output/eval_report.json 供简历引用。

用法:
    unset ALL_PROXY
    python tools/evaluate_extraction.py
"""
import sys
import json
import re
import logging
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# ==================== Ground Truth 解析 ====================
# 文件名编码了答案,格式: {年份}{竞赛关键词}-{人名}-{级别}-{奖项}.ext
# 如: 2024数据安全-李杰-省赛-二等奖.jpg

AWARD_LEVELS = ["特等奖", "一等奖", "二等奖", "三等奖", "金奖", "银奖", "铜奖", "优秀奖"]
COMP_LEVELS = ["国赛", "省赛", "校赛", "国际赛", "国家级", "省级"]


def parse_ground_truth(filename: str) -> dict:
    """从文件名解析 ground truth(竞赛关键词/人名/级别/奖项)。"""
    name = Path(filename).stem  # 去扩展名
    truth = {"filename": filename, "raw": name}

    # 提取奖项级别
    for level in AWARD_LEVELS:
        if level in name:
            truth["award_level"] = level
            break

    # 提取竞赛级别
    for level in COMP_LEVELS:
        if level in name:
            truth["competition_level"] = level
            break

    # 提取年份
    m = re.match(r"^(\d{4})", name)
    if m:
        truth["year"] = int(m.group(1))

    # 竞赛关键词:去掉年份/级别/奖项/人名后的核心词
    core = name
    if m:
        core = core[len(m.group(1)):]
    for level in AWARD_LEVELS + COMP_LEVELS:
        core = core.replace(level, "")
    # 按分隔符拆,第一段通常是竞赛关键词
    parts = re.split(r"[-_\-\s]+", core)
    parts = [p for p in parts if p and len(p) >= 2]
    if parts:
        truth["competition_keyword"] = parts[0]

    return truth


def _normalize(s) -> str:
    """归一化字符串用于比对(去空格/标点/统一大小写)。"""
    if s is None:
        return ""
    s = str(s)
    # 去常见标点和空格
    for ch in " \t\n\r.,、，。;；:：()（）[]【】\"'""''":
        s = s.replace(ch, "")
    return s.lower()


def _keyword_match(keyword: str, text: str) -> bool:
    """竞赛关键词是否包含在抽取结果中(模糊匹配)。"""
    keyword = _normalize(keyword)
    text = _normalize(text)
    if not keyword or not text:
        return False
    # 双向包含(关键词在文本中,或文本核心词在关键词中)
    return keyword in text or (len(keyword) >= 3 and keyword[:3] in text)


def score_extraction(truth: dict, extracted: dict) -> dict:
    """
    对单条抽取结果打分。

    返回:
        {field: correct_bool, ...} 各字段是否正确
    """
    scores = {}

    # 1. 竞赛名(关键词模糊匹配)
    if "competition_keyword" in truth:
        comp_name = extracted.get("competition_name", "")
        scores["competition_name"] = _keyword_match(truth["competition_keyword"], comp_name)

    # 2. 奖项级别(精确匹配,容错"二等奖"vs"二等")
    if "award_level" in truth:
        ext_level = _normalize(extracted.get("award_level", ""))
        tru_level = _normalize(truth["award_level"])
        scores["award_level"] = tru_level in ext_level or ext_level in tru_level

    # 3. 竞赛级别(国赛/省赛)
    if "competition_level" in truth:
        ext_cl = _normalize(extracted.get("competition_level", ""))
        tru_cl = _normalize(truth["competition_level"])
        # "国家级" vs "国赛" 容错
        if tru_cl.startswith("国") and ext_cl.startswith("国"):
            scores["competition_level"] = True
        elif tru_cl.startswith("省") and ext_cl.startswith("省"):
            scores["competition_level"] = True
        else:
            scores["competition_level"] = tru_cl in ext_cl

    # 4. 年份
    if "year" in truth:
        ext_year = extracted.get("year")
        scores["year"] = str(ext_year) == str(truth["year"])

    return scores


# ==================== 批量评测 ====================

def evaluate_folder(folder: str, ctx, label: str) -> dict:
    """评测一个文件夹内所有奖状图片。"""
    folder_path = Path(folder)
    if not folder_path.exists():
        return {"label": label, "error": f"文件夹不存在: {folder}"}

    images = sorted([f for f in folder_path.iterdir()
                     if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".jfif")])

    results = []
    fw = ctx.extract_framework

    for img in images:
        truth = parse_ground_truth(img.name)
        logger.info("评测: %s", img.name)
        try:
            extract_result = fw.extract(str(img), use_ocr_cache=True, use_llm_cache=True)
            status = str(extract_result.status)
            if "SUCCESS" in status:
                extracted = extract_result.data or {}
                scores = score_extraction(truth, extracted)
                results.append({
                    "filename": img.name,
                    "status": "success",
                    "truth": truth,
                    "extracted": {k: extracted.get(k) for k in
                                  ["competition_name", "award_level", "competition_level", "year", "winner_name"]},
                    "scores": scores,
                })
            else:
                results.append({
                    "filename": img.name,
                    "status": "failed",
                    "error": extract_result.error_message,
                    "truth": truth,
                })
        except Exception as e:
            results.append({
                "filename": img.name,
                "status": "error",
                "error": str(e)[:200],
                "truth": truth,
            })

    # 统计
    stats = _compute_stats(results, label)
    return {"label": label, "results": results, "stats": stats}


def _compute_stats(results: list, label: str) -> dict:
    """计算统计指标。"""
    total = len(results)
    success = [r for r in results if r["status"] == "success"]
    failed = [r for r in results if r["status"] != "success"]

    # 字段级准确率(只统计成功的)
    field_correct = {}
    field_total = {}
    for r in success:
        for field, correct in r.get("scores", {}).items():
            field_total[field] = field_total.get(field, 0) + 1
            if correct:
                field_correct[field] = field_correct.get(field, 0) + 1

    field_accuracy = {}
    all_correct_fields = 0
    all_total_fields = 0
    for field in field_total:
        acc = field_correct.get(field, 0) / field_total[field] if field_total[field] else 0
        field_accuracy[field] = round(acc * 100, 1)
        all_correct_fields += field_correct.get(field, 0)
        all_total_fields += field_total[field]

    overall_field_acc = round(all_correct_fields / all_total_fields * 100, 1) if all_total_fields else 0
    success_rate = round(len(success) / total * 100, 1) if total else 0

    return {
        "label": label,
        "total": total,
        "success_count": len(success),
        "failed_count": len(failed),
        "success_rate": success_rate,
        "field_accuracy": field_accuracy,
        "overall_field_accuracy": overall_field_acc,
        "failed_details": [{"filename": f["filename"], "error": f.get("error", "")[:80]} for f in failed],
    }


def main():
    from config.loader import get_config
    from backend.agent.tools.context import ToolContext

    config_loader = get_config()
    ctx = ToolContext(config_loader)

    print("=" * 60)
    print("批量抽取准确率评测")
    print("=" * 60)

    all_stats = []

    # 中文奖状
    print("\n>>> 评测中文奖状...")
    cn_result = evaluate_folder("tests/test_images/award/chinese", ctx, "中文奖状")
    all_stats.append(cn_result["stats"])
    _print_stats(cn_result["stats"])

    # 英文奖状
    print("\n>>> 评测英文奖状...")
    en_result = evaluate_folder("tests/test_images/award/english", ctx, "英文奖状")
    all_stats.append(en_result["stats"])
    _print_stats(en_result["stats"])

    # 汇总
    print("\n" + "=" * 60)
    print("汇总")
    print("=" * 60)
    total_success = sum(s["success_count"] for s in all_stats)
    total_all = sum(s["total"] for s in all_stats)
    # 加权字段准确率
    weighted_acc = sum(s["overall_field_accuracy"] * s["success_count"] for s in all_stats) / total_success if total_success else 0
    print(f"总图片数: {total_all}")
    print(f"成功抽取: {total_success} ({round(total_success/total_all*100,1)}%)")
    print(f"加权字段级准确率: {round(weighted_acc,1)}%")

    # 落盘
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    report = {
        "summary": {
            "total_images": total_all,
            "success_count": total_success,
            "success_rate": round(total_success / total_all * 100, 1),
            "weighted_field_accuracy": round(weighted_acc, 1),
        },
        "details": all_stats,
        "full_results": {
            "chinese": cn_result["results"],
            "english": en_result["results"],
        },
    }
    report_path = output_dir / "eval_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n详细报告已保存: {report_path}")


def _print_stats(stats: dict):
    """打印单组统计。"""
    print(f"\n--- {stats['label']} ({stats['total']}张) ---")
    print(f"  成功: {stats['success_count']}/{stats['total']} ({stats['success_rate']}%)")
    print(f"  字段级准确率(综合): {stats['overall_field_accuracy']}%")
    for field, acc in stats["field_accuracy"].items():
        print(f"    {field}: {acc}%")
    if stats["failed_details"]:
        print(f"  失败: {stats['failed_details']}")


if __name__ == "__main__":
    main()
