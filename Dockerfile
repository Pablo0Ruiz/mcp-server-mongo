# Imagen base de Python
FROM python:3.11-slim

# Directorio de trabajo
WORKDIR /app

# Copiar dependencias
COPY requirements.txt .

# Instalar dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código del servidor
COPY src/mongo/MongoMcp.py .

# Puerto expuesto
EXPOSE 8000

# Variables de entorno por defecto
ENV PORT=8000
ENV HOST=0.0.0.0

# Comando de inicio
CMD ["python", "MongoMcp.py"]