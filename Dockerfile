FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .

RUN pip install --no-cache-dir . && \
    pip install --no-cache-dir ".[dev]" && \
    rm -rf /root/.cache

COPY . .

RUN pip install --no-cache-dir -e . && \
    rm -rf /root/.cache

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
