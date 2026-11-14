FROM python:3.11-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 tesseract-ocr tesseract-ocr-vie tesseract-ocr-lao tesseract-ocr-eng tesseract-ocr-tha tesseract-ocr-chi-sim tesseract-ocr-kor tesseract-ocr-spa tesseract-ocr-fra tesseract-ocr-deu fonts-nanum && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr-frk tesseract-ocr-script-frak && rm -rf /var/lib/apt/lists/*
RUN apt-get update && apt-get install -y --no-install-recommends fonts-wqy-zenhei fonts-noto-core fonts-symbola fonts-hanazono && rm -rf /var/lib/apt/lists/*
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr-jpn tesseract-ocr-khm tesseract-ocr-rus tesseract-ocr-ind tesseract-ocr-msa tesseract-ocr-mya tesseract-ocr-hin tesseract-ocr-ita tesseract-ocr-por tesseract-ocr-nld tesseract-ocr-ara && rm -rf /var/lib/apt/lists/*
COPY app ./app
COPY tests ./tests
COPY prepare_model.py .
RUN useradd --create-home --uid 10001 appuser
RUN mkdir -p /data && chown appuser:appuser /data
USER appuser
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--limit-concurrency", "12"]

FROM runtime AS preparer
USER root
ENV HF_HUB_OFFLINE=0 TRANSFORMERS_OFFLINE=0
COPY requirements-local.txt .
RUN pip install --no-cache-dir -r requirements-local.txt
RUN pip install --no-cache-dir torch==2.7.0 --index-url https://download.pytorch.org/whl/cpu
ENTRYPOINT ["python", "prepare_model.py"]
