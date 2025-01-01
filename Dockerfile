# Builder stage
FROM --platform=$BUILDPLATFORM python:3.12.8-slim-bookworm AS builder

LABEL \
    org.opencontainers.image.title="Meter Reader" \
    org.opencontainers.image.description="Efficiently reads analog using advanced object detection." \
    org.opencontainers.image.url="https://github.com/yonz2/meterreader2" \
    org.opencontainers.image.source="https://github.com/yonz2/meterreader2" \
    org.opencontainers.image.vendor="Yonz" \
    org.opencontainers.image.licenses="MIT" \
    org.opencontainers.image.version="1.0.0" \
    org.opencontainers.image.created="2025-01-01T14:51:19Z" \
    org.opencontainers.image.revision="abcdefg" \
    org.opencontainers.image.documentation="https://github.com/your-github-username/meterreader/blob/main/README.md" \
    maintainer="Yonz <yonz@me.com>"

WORKDIR /usr/src/app

RUN apt update && apt upgrade -y && \
    apt install --no-install-recommends -y curl wget && \
    rm -rf /var/lib/apt/lists/*

ENV PIP_ROOT_USER_ACTION=ignore


COPY requirements.txt .
# Install the more complex libraries "manually" to ensure they are installed correctly
RUN python -m pip install --upgrade pip && \
    python -m pip install -r requirements.txt && \
    python -m pip install hypercorn==0.17.3  # Install hypercorn explicitly && \
    python -m pip install numpy && \
    python -m pip install opencv-contrib-python-headless && \    
    python -m pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu && \
    python -m pip install torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cpu && \
    # python -m pip install roboflow && \
    python -m pip install ultralytics
  
# Final stage
FROM --platform=$BUILDPLATFORM python:3.12.8-slim-bookworm

WORKDIR /usr/src/app
EXPOSE 8099

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/hypercorn /usr/local/bin/hypercorn


# Copy application files ... ignoring file patterns defined in .dockerignore
COPY . .

RUN adduser --disabled-password --gecos "" appuser 
RUN chown -R appuser /usr/src/app

USER appuser

CMD ["hypercorn", "--bind", "0.0.0.0:8099", "server:app"]