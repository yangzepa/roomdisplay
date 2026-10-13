FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends fonts-nanum fonts-nanum-extra \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
ENV DATA_DIR=/data TZ=Asia/Seoul
EXPOSE 8070
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8070", "--timeout-keep-alive", "330"]
