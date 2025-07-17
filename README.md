# Speakr

Speakr is an audio transcription and summarization app.

## Running the Application

### Flask (Legacy)

1.  **Set up the environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```

2.  **Run the application:**
    ```bash
    flask run
    ```

### FastAPI (New)

1.  **Set up the environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    pip install fastapi uvicorn
    ```

2.  **Run the application:**
    ```bash
    cd speakr_fastapi
    uvicorn app.main:app --reload
    ```
