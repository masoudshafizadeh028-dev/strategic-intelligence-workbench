# TODO: ایمیج را با digest پین کن (مثلاً python:3.12-slim@sha256:<digest>)؛ digest معتبر در دسترس نبود، تگ شناور نگه داشته شد.
# کانتکست بیلد ریشه‌ی مخزن است (نگاه کن به docker-compose.yml: context: .).
# پس همه‌ی مسیرهای COPY نسبی به ریشه‌اند.
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PERSHIAA_DATA_DIR=/data
COPY hub/core.py hub/dashboard.html hub/config.yaml ./
COPY doctrine/doctrine_engine.py ./doctrine_engine.py
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python3 -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/health')"
CMD ["python3", "core.py", "--serve", "--port", "8000", "--host", "0.0.0.0"]
