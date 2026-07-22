FROM python:3.12-slim

WORKDIR /app

# libsndfile for soundfile; ffmpeg for mp3/aiff decoding
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src
COPY configs ./configs

RUN pip install --no-cache-dir ".[audio,viz]"

EXPOSE 8000
CMD ["uvicorn", "dancelab.api.main:app", "--host", "127.0.0.1", "--port", "8000"]
