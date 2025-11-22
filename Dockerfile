# 使用官方Python 3.11 slim镜像作为基础镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=Asia/Shanghai

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY src/ ./src/
COPY run.py .
COPY scheduler.py .

# 创建日志目录
RUN mkdir -p logs

# 设置权限
RUN chmod +x run.py scheduler.py

# 默认命令（手动运行模式）
CMD ["python", "run.py"]
