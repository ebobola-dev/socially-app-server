FROM python:3.13.3-slim

WORKDIR /app

RUN apt update && apt install -y \
    build-essential \
    libffi-dev \
    libssl-dev \
    cargo \
    gcc \
    python3-dev \
    default-libmysqlclient-dev \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

ENV TZ=${TZ}

COPY . .

RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir cryptography

EXPOSE ${SERVER_PORT}

RUN chmod +x /wait-for-it.sh /entrypoint.sh

CMD ["/entrypoint.sh"]