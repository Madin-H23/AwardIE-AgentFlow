"""真 AI Worker 冒烟(架构票《AI Worker extract/prompt RPC 扩展》验收;本地手动,不进 CI)。

前置:
    1. PG 5433 在线(取 templates.sample_image_blob 作真实样本图)
    2. Worker 已起:D:/venvs/awardie/Scripts/python.exe ai_worker/server.py(默认 50060)

用法:
    D:/venvs/awardie/Scripts/python.exe scripts/smoke_worker_rpc.py [--port 50060]

验收口径:Health ok;GeneratePrompt code=0 且 prompt 非空(纯本地拼装,秒回);
ExtractTemplate code=0 且 data_json/ocr_text 非空(真 OCR+LLM,30-120s)。
"""
import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "ai_worker" / "protos"))

import grpc  # noqa: E402
import ai_service_pb2 as pb  # noqa: E402
import ai_service_pb2_grpc as pb_grpc  # noqa: E402


def fetch_sample_image() -> bytes:
    import psycopg2
    conn = psycopg2.connect(host="127.0.0.1", port=5433, dbname="awardie_dev",
                            user="postgres", password="postgres")
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT sample_image_blob FROM templates "
                        "WHERE sample_image_blob IS NOT NULL ORDER BY id DESC LIMIT 1")
            row = cur.fetchone()
        if not row or not row[0]:
            raise SystemExit("templates 表无样本图:先经 templates create 页创建一个模板")
        return bytes(row[0])
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=50060)
    args = parser.parse_args()
    failures = []

    channel = grpc.insecure_channel(f"127.0.0.1:{args.port}")
    grpc.channel_ready_future(channel).result(timeout=10)
    stub = pb_grpc.AiServiceStub(channel)

    health = stub.Health(pb.HealthRequest(), timeout=10)
    print(f"[Health] ok={health.ok} version={health.version} langgraph={health.langgraph_available}")
    if not health.ok:
        failures.append("health")

    rule = {
        "keywords": ["蓝桥杯"],
        "sample_extracted": {},
        "default_fields": {},
        "llm_fields": {},
        "min_length": 5,
        "max_length": 200,
        "language": "zh",
        "need_translate": False,
    }
    prompt_resp = stub.GeneratePrompt(pb.GeneratePromptRequest(
        template_rule_json=json.dumps(rule, ensure_ascii=False),
        sample_text="2024年蓝桥杯大赛省级一等奖 张三",
        trace_id="smoke-prompt",
    ), timeout=30)
    print(f"[GeneratePrompt] code={prompt_resp.code} prompt_len={len(prompt_resp.prompt)}")
    print(f"  prompt 头 80 字: {prompt_resp.prompt[:80]!r}")
    if prompt_resp.code != 0 or not prompt_resp.prompt:
        failures.append("generate_prompt")

    image = fetch_sample_image()
    print(f"[ExtractTemplate] 样本图 {len(image)} bytes,真 OCR+LLM 约需 30-120s ……")
    extract_resp = stub.ExtractTemplate(pb.ExtractTemplateRequest(
        image=image,
        filename="smoke.jpg",
        template_rule_json="{}",
        use_ocr_cache=True,
        use_llm_cache=True,
        trace_id="smoke-extract",
    ), timeout=300)
    print(f"[ExtractTemplate] code={extract_resp.code} message={extract_resp.message}")
    if extract_resp.code == 0:
        data = json.loads(extract_resp.data_json)
        print(f"  data_json 键: {sorted(data.keys())}")
        print(f"  ocr_text 长度: {len(extract_resp.ocr_text)}")
        if not data or not extract_resp.ocr_text:
            failures.append("extract_template_content")
    else:
        failures.append("extract_template")

    channel.close()
    if failures:
        print(f"SMOKE FAIL: {failures}")
        return 1
    print("SMOKE PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
