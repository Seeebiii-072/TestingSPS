FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt /app/email_worker/requirements.txt
RUN pip install --no-cache-dir -r /app/email_worker/requirements.txt
COPY . /app/email_worker
ENV PYTHONPATH=/app
CMD ["python", "-m", "email_worker.main"]
