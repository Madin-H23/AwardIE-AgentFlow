#!/bin/bash
# 生成 v3 的 AI Worker Java gRPC stub(批7)
#
# 与 v2 scripts/gen_java_stub.sh 的差异:
#   1. 输入是 v3 自己的 proto 副本(src/main/proto/ai_service.proto,已加 java_package
#      选项落到 cn.iocoder.yudao.module.business.framework.grpc.awardie.ai);
#      v2 生成物在顶层 awardie.ai 包,不符合 v3 包规范,故重生成而非复制;
#   2. 输出落到 v3 business 模块的 grpc 包目录。
#
# proto 的 package awardie.ai **不可改**:它决定 wire 完整方法路径,
# 现存 Python Worker 按该契约实现。
#
# 工具版本与 v2 一致(protoc 3.25.3 / grpc-java 1.64.0),避免生成物版本漂移。
# 契约变更后重跑本脚本;生成物为机器产物,勿手工编辑。
set -e

# localRepository 动态解析(2026-09-03 迁 D 盘后 ~/.m2 硬编码失效)
M2=$(env -u HTTP_PROXY -u HTTPS_PROXY mvn -B help:evaluate -Dexpression=settings.localRepository -q -DforceStdout 2>/dev/null | tail -1)
PROTOC=$(ls "$M2/com/google/protobuf/protoc/3.25.3/protoc-"*windows-x86_64.exe | head -1)
GRPCGEN=$(ls "$M2/io/grpc/protoc-gen-grpc-java/1.64.0/protoc-gen-grpc-java-"*windows-x86_64.exe | head -1)

REPO="D:/Develop/AI 应用开发/AI应用开发项目/AwardIE-AgentFlow"
STUB_TARGET="$REPO/awardie-v3/yudao-module-business/src/main/java/cn/iocoder/yudao/module/business/framework/grpc/awardie/ai"

# protoc 无法处理中文路径,复制到 ASCII 短路径下编译
rm -rf /c/temp/protoc-work/v3
mkdir -p /c/temp/protoc-work/v3/java
cp "$REPO/awardie-v3/yudao-module-business/src/main/proto/ai_service.proto" /c/temp/protoc-work/v3/
cd /c/temp/protoc-work/v3
"$PROTOC" -I. --java_out=./java --plugin=protoc-gen-grpc-java="$GRPCGEN" --grpc-java_out=./java ai_service.proto
find java -name '*.java'

mkdir -p "$STUB_TARGET"
cp java/cn/iocoder/yudao/module/business/framework/grpc/awardie/ai/*.java "$STUB_TARGET/"
echo "stub 拷入完成: $STUB_TARGET"
