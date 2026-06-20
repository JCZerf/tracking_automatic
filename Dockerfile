FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install --yes --no-install-recommends libgl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
COPY solver/requirements_ocr.txt ./solver/requirements_ocr.txt
RUN pip install --no-cache-dir --requirement requirements.txt

RUN useradd --create-home --uid 1000 appuser

COPY --chown=appuser:appuser api ./api
COPY --chown=appuser:appuser bot ./bot
COPY --chown=appuser:appuser solver ./solver
COPY --chown=appuser:appuser main.py ./main.py

RUN mkdir -p /home/appuser/.paddlex && chown -R appuser:appuser /home/appuser/.paddlex

USER appuser

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
