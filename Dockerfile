FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt requirements-production.txt ./
RUN pip install -r requirements-production.txt
COPY . .
RUN DJANGO_DEBUG=0 DJANGO_SECRET_KEY=build-only-placeholder python manage.py collectstatic --noinput
RUN useradd --create-home --uid 10001 foodloop && mkdir -p /data/media && chown -R foodloop:foodloop /app /data
USER foodloop
EXPOSE 8000
CMD ["python", "scripts/serve.py"]
