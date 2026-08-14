# ============================================================
# Dockerfile for Hugging Face Spaces (Docker SDK)
# Python 3.9, matching this bot's tested/required version.
# ============================================================
FROM python:3.9-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    TZ="Asia/Dhaka" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=7860

# ffmpeg + mediainfo for encoding/metadata, build-essential for any
# packages that need to compile native extensions during pip install.
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends \
        ffmpeg \
        mediainfo \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# Hugging Face Spaces' Dev Mode requires a non-root user with UID 1000.
RUN useradd -m -u 1000 user

WORKDIR /app

# Install dependencies first (as root, so pip can write to system site-
# packages) -- this keeps Docker's layer cache working: requirements.txt
# only changes rarely, so this layer is reused across most rebuilds.
COPY requirements.txt .
RUN python3 -m pip install --no-cache-dir --upgrade pip \
    && pip3 install --no-cache-dir -r requirements.txt

# Now copy the rest of the app and hand ownership to the non-root user.
COPY --chown=user:user . .
RUN chmod +x run.sh \
    && mkdir -p VideoEncoder/downloads VideoEncoder/encodes \
    && chown -R user:user VideoEncoder/downloads VideoEncoder/encodes

USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

# Hugging Face Spaces (Docker SDK) routes traffic to this port and uses
# it to tell whether the container started successfully. The bot itself
# doesn't need this for Telegram -- see VideoEncoder/core/health.py for
# the tiny status server that satisfies this requirement.
EXPOSE 7860

CMD ["bash", "run.sh"]
