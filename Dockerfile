FROM python:3.10-slim

# Install system dependencies required for standard image handling (OpenCV/Pillow)
RUN apt-get update && apt-get install -y \
    libgl1 \
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Set up the internal app directory
WORKDIR /app

# Install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all local backend files
COPY . .

# web service port
EXPOSE 10000

#  FastAPI app using Uvicorn with trusted proxy headers
CMD ["uvicorn", "Nurseon:app", "--host", "0.0.0.0", "--port", "10000", "--proxy-headers", "--forwarded-allow-ips=*"]