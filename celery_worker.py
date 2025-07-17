import os
from celery import Celery
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from app import db, Recording, User, Speaker
from app import generate_summary_task as app_generate_summary_task
from app import transcribe_audio_task as app_transcribe_audio_task

celery = Celery(__name__, broker=os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
                backend=os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'))

def create_flask_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('SQLALCHEMY_DATABASE_URI', 'sqlite:////data/instance/transcriptions.db')
    app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_FOLDER', '/data/uploads')
    app.config['MAX_CONTENT_LENGTH'] = 250 * 1024 * 1024  # 250MB max file size
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default-dev-key-change-in-production')
    db.init_app(app)
    return app

@celery.task
def transcribe_audio_task(recording_id, filepath, filename_for_asr, start_time):
    app = create_flask_app()
    with app.app_context():
        app_transcribe_audio_task(app.app_context(), recording_id, filepath, filename_for_asr, start_time)

@celery.task
def generate_summary_task(recording_id, start_time):
    app = create_flask_app()
    with app.app_context():
        app_generate_summary_task(app.app_context(), recording_id, start_time)
