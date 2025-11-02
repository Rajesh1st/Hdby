FROM python:3.11-slim

# Install Chrome & dependencies
RUN apt-get update && apt-get install -y \
    wget unzip gnupg \
    chromium chromium-driver \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PATH="/usr/lib/chromium:/usr/bin:$PATH"
ENV PORT=8000

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
