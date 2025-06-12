# user_service/Dockerfile
FROM python:3.10-slim
WORKDIR /app

# Salin requirements.txt dari root context
COPY requirements.txt . 

RUN pip install --no-cache-dir -r requirements.txt

# Salin kode aplikasi dari subdirektori user_service di dalam context
COPY user_service/. . 

EXPOSE 5001
CMD ["python", "app.py"]