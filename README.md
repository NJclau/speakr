# Speakr

Speakr is an audio transcription and summarization app.

**The FastAPI version is the default and maintained version of the application.**

## Running the Application

### FastAPI (Recommended)

1.  **Set up the environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```

2.  **Run the application with Docker Compose:**
    ```bash
    cd speakr_fastapi
    docker-compose up -d
    uvicorn app.main:app --reload
    ```
