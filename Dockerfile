# Usamos Python 3.11 oficial y estable
FROM python:3.11-slim

# Establecemos carpeta de trabajo
WORKDIR /app

# Copiamos archivos
COPY requirements.txt .
COPY bot.py .
COPY strategy.py .

# Instalamos dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Comando para iniciar
CMD ["python", "bot.py"]

