FROM python:3.11-slim

# Instala ffmpeg y otras dependencias
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instala yt-dlp desde fuente (más reciente que pip)
RUN pip install --no-cache-dir yt-dlp

WORKDIR /app

# Copia requirements e instala
COPY scripts/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia código de la API
COPY src/ .
COPY scripts/cookies.txt /app/scripts/cookies.txt

# Puerto
EXPOSE 8080

# Comando de inicio
CMD ["python", "api.py"]
