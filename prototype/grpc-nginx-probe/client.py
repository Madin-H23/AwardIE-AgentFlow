"""探针 P1 client:测量每个 delta 的到达间隔,判断透传是否被缓冲。

用法: client.py <target:port> <method:deltas|slow> [count] [interval_ms]
判定: 快流下相邻 delta 间隔中位数应接近 interval_ms;
      若间隔全部趋近 0 且总时长被压缩,说明被代理缓冲"憋成一阵"。
"""
import statistics
import sys
import time

import grpc

import streamer_pb2
import streamer_pb2_grpc


def run(target, method, count, interval_ms):
    channel = grpc.insecure_channel(target)
    grpc.channel_ready_future(channel).result(timeout=10)
    stub = streamer_pb2_grpc.StreamerStub(channel)
    req = streamer_pb2.StreamReq(count=count, interval_ms=interval_ms, payload_bytes=1024)

    rpc = stub.StreamDeltas if method == "deltas" else stub.StreamSlow
    t0 = time.monotonic()
    arrivals = []
    try:
        for delta in rpc(req, timeout=300):
            arrivals.append((delta.seq, time.monotonic() - t0))
    except grpc.RpcError as e:
        print(f"RPC 终止: code={e.code().name} details={e.details()}")
        if not arrivals:
            return 2

    gaps = [arrivals[i + 1][1] - arrivals[i][1] for i in range(len(arrivals) - 1)]
    total = arrivals[-1][1] if arrivals else 0
    print(f"target={target} method={method} 收到 {len(arrivals)}/{count} 个 delta, 总时长 {total:.2f}s")
    if gaps:
        med = statistics.median(gaps)
        p95 = sorted(gaps)[int(len(gaps) * 0.95)]
        print(f"间隔中位数 {med*1000:.0f}ms | p95 {p95*1000:.0f}ms | 首包 {arrivals[0][1]*1000:.0f}ms")
        print("间隔序列(ms):", [f"{g*1000:.0f}" for g in gaps])
        # 判定:间隔中位数应接近 interval_ms;若 < 1/3 说明被缓冲
        expected = interval_ms / 1000
        if med < expected / 3:
            print(f"结论: ✗ 疑似被缓冲(中位数 {med*1000:.0f}ms << {interval_ms}ms)")
            return 1
        print(f"结论: ✓ 逐条透传正常(中位数 {med*1000:.0f}ms ≈ {interval_ms}ms)")
    return 0


if __name__ == "__main__":
    target = sys.argv[1]
    method = sys.argv[2] if len(sys.argv) > 2 else "deltas"
    count = int(sys.argv[3]) if len(sys.argv) > 3 else 20
    interval_ms = int(sys.argv[4]) if len(sys.argv) > 4 else 200
    sys.exit(run(target, method, count, interval_ms))
