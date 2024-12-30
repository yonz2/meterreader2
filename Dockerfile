FROM python:3.12.8-slim-bookworm

WORKDIR /usr/src/app
EXPOSE 8099

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1
RUN apt update && apt upgrade -y && apt install curl iputils-ping net-tools dnsutils -y

RUN python -V && pip install --upgrade pip

# Install pip requirements
COPY requirements.txt .
RUN python -m pip install -r requirements.txt

# Creates a non-root user with an explicit UID and adds permission to access the /app folder
# For more info, please refer to https://aka.ms/vscode-docker-python-configure-containers
RUN adduser --disabled-password --gecos "" appuser
# RUN adduser -u 1000 --disabled-password --gecos "" appuser

# copy files to app directory
COPY  *.py *.md *.yaml .
COPY predicter ./predicter
COPY helpers ./helpers

RUN ls -la ./*
RUN chown -R appuser /usr/src/app

USER appuser

# During debugging, this entry point will be overridden. For more information, please refer to https://aka.ms/vscode-docker-python-debug
CMD ["hypercorn", "--bind", "0.0.0.0:8099", "server:app"] 
