# TODO: ایمیج را با digest پین کن (مثلاً python:3.12-slim@sha256:<digest>)؛ digest معتبر در دسترس نبود، تگ شناور نگه داشته شد.
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PERSHIAA_DATA_DIR=/data
COPY . .
RUN pip install --no-cache-dir fastapi uvicorn[standard] pydantic || echo "حالت stdlib فعال می‌ماند"
EXPOSE 8002
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python3 -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8002/api/health')"
CMD ["python3", "app.py", "--host", "0.0.0.0", "--port", "8002"]
