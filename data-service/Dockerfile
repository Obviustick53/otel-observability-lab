FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py migrate.py ./
COPY migrations ./migrations

EXPOSE 8002
HEALTHCHECK --interval=10s --timeout=3s --retries=5 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8002/health', timeout=2)"
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
