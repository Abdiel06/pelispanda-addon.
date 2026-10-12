# Usamos un sistema operativo de Microsoft que ya trae Chromium preinstalado
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Creamos una carpeta en la nube
WORKDIR /app

# Copiamos todos tus archivos a la nube
COPY . /app/

# Instalamos las librerías
RUN pip install --no-cache-dir -r requirements.txt

# Le decimos a la nube que escuche en este puerto
EXPOSE 5000

# Encendemos el servidor en modo Producción
CMD gunicorn --bind 0.0.0.0:${PORT:-5000} addon:app --timeout 120