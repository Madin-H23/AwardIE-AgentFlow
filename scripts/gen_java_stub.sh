#!/bin/bash
# 生成 AI Worker 的 Java gRPC stub(protoc 无法处理中文路径,proto 在 ASCII 短路径下编译)
set -e
# localRepository 动态解析(2026-09-03 迁 D 盘后 ~/.m2 硬编码失效)
M2=$(env -u HTTP_PROXY -u HTTPS_PROXY mvn -B help:evaluate -Dexpression=settings.localRepository -q -DforceStdout 2>/dev/null | tail -1)
PROTOC=$(ls "$M2/com/google/protobuf/protoc/3.25.3/protoc-"*windows-x86_64.exe | head -1)
GRPCGEN=$(ls "$M2/io/grpc/protoc-gen-grpc-java/1.64.0/protoc-gen-grpc-java-"*windows-x86_64.exe | head -1)
STUB_TARGET="D:/Develop/AI 应用开发/AI应用开发项目/AwardIE-AgentFlow/awardie-backend/src/main/java/awardie/ai"
rm -rf /c/temp/protoc-work/java
mkdir -p /c/temp/protoc-work/java
cp "D:/Develop/AI 应用开发/AI应用开发项目/AwardIE-AgentFlow/ai_worker/protos/ai_service.proto" /c/temp/protoc-work/
cd /c/temp/protoc-work
"$PROTOC" -I. --java_out=./java --plugin=protoc-gen-grpc-java="$GRPCGEN" --grpc-java_out=./java ai_service.proto
find java -name '*.java'
mkdir -p "$STUB_TARGET"
cp java/awardie/ai/*.java "$STUB_TARGET/"
echo "stub 拷入完成"
