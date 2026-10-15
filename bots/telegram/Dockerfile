# TODO: ایمیج را با digest پین کن (مثلاً python:3.12-slim@sha256:<digest>)؛ digest معتبر در دسترس نبود، تگ شناور نگه داشته شد.
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt || echo "Telethon نصب نشد؛ فقط selftest در دسترس است"
COPY downloader.py .
ENTRYPOINT ["python3", "downloader.py"]
CMD ["--selftest"]
