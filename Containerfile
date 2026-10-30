FROM docker.io/library/python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir --timeout 120 --retries 10 --index-url https://download.pytorch.org/whl/cpu torch && pip install --no-cache-dir --timeout 120 --retries 10 --index-url https://pypi.org/simple --extra-index-url https://download.pytorch.org/whl/cpu --no-deps sentence-transformers && pip install --no-cache-dir --timeout 120 --retries 10 --index-url https://pypi.org/simple -r requirements.txt

COPY backend/ ./backend/

EXPOSE 8000

CMD ["python", "backend/manage.py", "runserver", "0.0.0.0:8000"]
