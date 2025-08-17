# Use official Python runtime
FROM python:3.11-slim

# Install system deps (ffmpeg needed for yt-dlp audio)
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Set workdir
WORKDIR /app

# Copy dependencies
COPY requirements.txt .

# Install Python deps
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Expose port (Render assigns PORT dynamically)
EXPOSE 8000

# Run the bot
CMD ["python", "bot.py"]
