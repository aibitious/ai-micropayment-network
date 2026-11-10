FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DB_PATH=/data/404.sqlite3
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && useradd -u 10001 -m app && mkdir -p /data && chown 10001:10001 /data
COPY agent404 /app/agent404
USER 10001:10001
EXPOSE 8080
CMD ["uvicorn", "agent404.mcp_server:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1", "--no-access-log"]
