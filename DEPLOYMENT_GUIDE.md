# Deployment Guide

The new FastAPI application can be deployed using Uvicorn with Gunicorn as a process manager.

```bash
cd speakr_fastapi
gunicorn -k uvicorn.workers.UvicornWorker -w 4 app.main:app
```
