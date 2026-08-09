FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# СТАВИМ torch ТОЛЬКО для CPU (без CUDA), чтобы не качать 2GB nvidia-библиотек
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
RUN mkdir -p uploads

# Кэшируем модель LaBSE в образе
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('cointegrated/LaBSE-en-ru')"

EXPOSE 8081

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8081", "--workers", "1"]