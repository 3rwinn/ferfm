# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory in the container
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
# Copy only requirements first to leverage Docker cache
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip
# Install CPU-only torch and dependent packages first, using PyTorch index as extra
RUN pip install --no-cache-dir torch sentence-transformers transformers --extra-index-url https://download.pytorch.org/whl/cpu
# Install the rest of the requirements
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . /app/

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application using gunicorn (or use manage.py runserver for development)
# For development, we often run this command via docker-compose instead.
CMD ["gunicorn", "core.wsgi:application", "--bind", "0.0.0.0:8000"]
# For simple development testing:
# CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"] 