# AwardIE-AgentFlow 生产镜像（部署设计 §1）
FROM python:3.11-slim

WORKDIR /app

# 系统依赖（OpenCV/Paddle 头文件）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libglib2.0-0 libgl1 curl \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖（CPU 版：PaddlePaddle 固定版本避开 3.3.x bug）
COPY requirements-cpu.txt .
RUN pip install --no-cache-dir -r requirements-cpu.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 应用代码
COPY app/ app/
COPY backend/ backend/
COPY config/ config/
COPY scripts/ scripts/
COPY run.py .

# 数据卷挂载点（SQLite 三库 + chroma + files）
VOLUME ["/app/database", "/app/files", "/app/logs"]

ENV FLASK_ENV=production PYTHONUNBUFFERED=1
EXPOSE 5001

HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=60s \
    CMD curl -sf http://localhost:5001/assistant/health || exit 1

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5001", "--timeout", "120", "--graceful-timeout", "30", "run:app"]
