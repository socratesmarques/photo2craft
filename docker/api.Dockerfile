FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /srv/photo2craft
COPY apps/api/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && useradd -m -u 10001 app
COPY shared/ shared/
COPY apps/api/app/ apps/api/app/
RUN mkdir data && chown -R app:app data
USER app
ENV DATA_DIR=/srv/photo2craft/data
WORKDIR /srv/photo2craft/apps/api
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--limit-concurrency", "16"]
