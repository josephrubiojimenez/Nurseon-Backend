# Use a lightweight Python base image
FROM python:3.10-slim

# Install system dependencies required for Tesseract OCR
RUN apt-get update && apt-get install -y tesseract-ocr libgl1 && rm -rf /var/lib/apt/lists/*

# Set up the internal app directory
WORKDIR /app

# Install Python package requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all local backend files into the container
COPY . .

# Expose Render's standard web service port
EXPOSE 10000

# Fire up the FastAPI app using Uvicorn
CMD ["uvicorn", "Nurseon:app", "--host", "0.0.0.0", "--port", "10000"]