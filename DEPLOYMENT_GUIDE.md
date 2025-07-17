# Deployment Guide

## Flask (Legacy)

The legacy Flask application can be deployed using Gunicorn.

```bash
gunicorn -w 4 'app:app'
```

## FastAPI (New)

The new FastAPI application can be deployed using Uvicorn with Gunicorn as a process manager.

```bash
cd speakr_fastapi
gunicorn -k uvicorn.workers.UvicornWorker -w 4 app.main:app
```
