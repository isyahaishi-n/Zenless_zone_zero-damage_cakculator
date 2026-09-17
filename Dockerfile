# Dockerfile — jalur A: backend Python tetap proses panjang (Fly.io/Render/Railway/VPS).
# Pakai deploy/serve_public.py (bind 0.0.0.0 + hormati $PORT); server.py TIDAK diubah.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080 \
    HOST=0.0.0.0

WORKDIR /app
COPY . .

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s \
  CMD python -c "import urllib.request,os;urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8080')+'/api/data',timeout=4)"

CMD ["python", "deploy/serve_public.py"]
