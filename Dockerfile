# RAG QA 系统 Docker 镜像
# 双进程启动：FastAPI 后端(8000) + Streamlit 前端(8501)
FROM python:3.11-slim

WORKDIR /app

# 先装依赖（利用 Docker 层缓存，代码变更时不必重复安装）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 拷贝项目代码
COPY . .

# 确保持久化目录存在
RUN mkdir -p db/chroma_db

# 暴露后端与前端端口
EXPOSE 8000 8501

# 启动脚本：后台起 uvicorn，前台起 streamlit
CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port 8000 & streamlit run frontend.py --server.port 8501 --server.address 0.0.0.0"]