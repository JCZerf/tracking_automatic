FROM mcr.microsoft.com/playwright/python:v1.60.0-noble

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

COPY requirements.txt ./
COPY solver/requirements_ocr.txt ./solver/requirements_ocr.txt
RUN pip install --no-cache-dir --requirement requirements.txt

COPY --chown=pwuser:pwuser api ./api
COPY --chown=pwuser:pwuser bot ./bot
COPY --chown=pwuser:pwuser solver ./solver
COPY --chown=pwuser:pwuser main.py ./main.py

RUN mkdir -p /home/pwuser/.paddlex && chown -R pwuser:pwuser /home/pwuser/.paddlex

USER pwuser

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
