FROM python:3.11-slim

WORKDIR /app

COPY watcher/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY watcher/ .

CMD ["python", "watcher.py"]
