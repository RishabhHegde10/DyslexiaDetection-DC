FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1
ENV RUN_ENV=docker

WORKDIR /app

# Install dependencies first for Docker caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all project files
COPY . .

# Expose standard gRPC port
EXPOSE 50051

# Default command if not specified
CMD ["python", "k8s_prediction_server.py"]
