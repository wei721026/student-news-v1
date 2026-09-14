FROM python:3.12-slim
WORKDIR /app
COPY publisher/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY publisher/ /app/publisher/
ENV PORT=8080
CMD exec gunicorn --bind :$PORT --workers 2 --threads 4 --timeout 120 publisher.app:app
