FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/output /app/received_links

CMD ["sh", "-c", "python -c 'from db_functions import create_database; create_database()' && python spotseek_queue_handler.py & python spotseek.py & python -m http.server ${PORT:-8000}"]
