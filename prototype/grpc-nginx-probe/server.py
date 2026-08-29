"""探针 P1 gRPC server:两个 server-streaming 方法。

StreamDeltas: 快流,默认 20 个 delta、间隔 200ms、载荷 1KB/100KB 交替。
StreamSlow:  慢流,默认 3 个 delta、间隔 35s,用于验证 read timeout 断流。
"""
import datetime
import sys
import time
from concurrent import futures

import grpc

import streamer_pb2
import streamer_pb2_grpc


class Streamer(streamer_pb2_grpc.StreamerServicer):
    def _gen(self, request, context):
        for i in range(request.count):
            if context.is_active() is False:
                return
            yield streamer_pb2.Delta(
                seq=i,
                ts=datetime.datetime.now().isoformat(timespec="milliseconds"),
                payload=b"x" * request.payload_bytes,
            )
            time.sleep(request.interval_ms / 1000)

    def StreamDeltas(self, request, context):
        yield from self._gen(request, context)

    def StreamSlow(self, request, context):
        yield from self._gen(request, context)


def serve(port):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=8))
    streamer_pb2_grpc.add_StreamerServicer_to_server(Streamer(), server)
    server.add_insecure_port(f"127.0.0.1:{port}")
    server.start()
    print(f"gRPC server on 127.0.0.1:{port}", flush=True)
    server.wait_for_termination()


if __name__ == "__main__":
    serve(int(sys.argv[1]) if len(sys.argv) > 1 else 50051)
