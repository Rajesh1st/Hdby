FROM python:3.10-slim

WORKDIR /app

COPY . .

RUN apt-get update && apt-get install -y wget unzip chromium chromium-driver \
    && pip install --no-cache-dir -r requirements.txt

ENV PATH="/usr/lib/chromium/:${PATH}"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
