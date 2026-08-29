"""AI Worker 冒烟脚本(goal #4 验收):Health / Extract / ExtractAndReview / Ask。

用法(D:\\venvs\\awardie):
    python ai_worker/client_smoke.py [port] [sample_file]
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "protos"))

import grpc  # noqa: E402

import ai_service_pb2 as pb  # noqa: E402
import ai_service_pb2_grpc as pb_grpc  # noqa: E402


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else "50060"
    sample = sys.argv[2] if len(sys.argv) > 2 else "files/agent_upload/14094a2d_--.jpg"
    target = f"127.0.0.1:{port}"
    channel = grpc.insecure_channel(target)
    stub = pb_grpc.AiServiceStub(channel)

    # 1. Health
    h = stub.Health(pb.HealthRequest(), timeout=10)
    print(f"[1/4] Health: ok={h.ok} version={h.version} langgraph={h.langgraph_available}")
    assert h.ok, "Health 未通过"

    # 2. Extract(unary,真实样例)
    t0 = time.monotonic()
    r = stub.Extract(pb.ExtractRequest(file_path=sample, use_ocr_cache=True, use_llm_cache=True), timeout=180)
    print(f"[2/4] Extract: code={r.code} status={r.status} doc_type={r.doc_type} "
          f"confidence={r.confidence:.2f} 耗时={time.monotonic()-t0:.1f}s")
    if r.code != 0:
        print(f"      ⚠ 非零返回: {r.message[:120]}")
    else:
        data = json.loads(r.data_json)
        keys = list(data.keys())[:6]
        print(f"      data keys: {keys}")

    # 3. ExtractAndReview(流式)
    t0 = time.monotonic()
    nodes, deltas, final = [], [], None
    for evt in stub.ExtractAndReview(pb.ExtractRequest(file_path=sample), timeout=300):
        which = evt.WhichOneof("event")
        if which == "node":
            nodes.append(evt.node.node)
        elif which == "delta":
            deltas.append(evt.delta.text)
        else:
            final = evt.final
    print(f"[3/4] ExtractAndReview: 节点={nodes} delta数={len(deltas)} 耗时={time.monotonic()-t0:.1f}s")
    assert final is not None, "未收到终态"
    print(f"      decision={final.decision} code={final.code} issues={final.issues_json[:80]}")
    print(f"      suggestion={final.suggestion[:80]}")
    print(f"      disclaimer={final.disclaimer[:30]}")
    assert final.code == 0 and final.decision in ("pass", "reject", "need_manual"), "审核终态异常"

    # 4. Ask(流式)
    t0 = time.monotonic()
    answer_parts, afinal = [], None
    for evt in stub.Ask(pb.AskRequest(question="挑战杯是几类竞赛?"), timeout=180):
        which = evt.WhichOneof("event")
        if which == "delta":
            answer_parts.append(evt.delta.text)
        elif which == "final":
            afinal = evt.final
    answer = "".join(answer_parts) or (afinal.answer if afinal else "")
    print(f"[4/4] Ask: 流式 {len(answer_parts)} 段共 {len(answer)} 字,耗时={time.monotonic()-t0:.1f}s")
    print(f"      answer 前 60 字: {answer[:60]}")
    assert afinal is not None and afinal.code == 0, "问答终态异常"

    print("\n✅ 冒烟全部通过")


if __name__ == "__main__":
    main()
