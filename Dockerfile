# Use official Python runtime
FROM python:3.11-slim

# Install ffmpeg (needed for video/audio processing)
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first (better cache layer)
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the code (this brings bot.py inside the container)
COPY . .

# Set environment variables (Railway will inject your BOT_TOKEN automatically)
ENV PYTHONUNBUFFERED=1

# Run your bot
CMD ["python", "bot.py"]
