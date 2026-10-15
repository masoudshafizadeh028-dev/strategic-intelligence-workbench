# TODO: ایمیج را با digest پین کن (مثلاً python:3.12-slim@sha256:<digest>)؛ digest معتبر در دسترس نبود، تگ شناور نگه داشته شد.
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PERSHIAA_DATA_DIR=/data
# وابستگی‌های اختیاری OCR: اگر نصب نشوند، سرویس با stdlib بالا می‌آید
RUN apt-get update && apt-get install -y --no-install-recommends \
      tesseract-ocr tesseract-ocr-fas poppler-utils \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt || echo "نصب وابستگی‌های اختیاری ناموفق — حالت stdlib فعال می‌ماند"
COPY . .
EXPOSE 8001
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python3 -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8001/api/health')"
CMD ["python3", "api.py", "--port", "8001", "--host", "0.0.0.0"]
