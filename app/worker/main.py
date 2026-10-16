from app.core.config import Settings
from app.worker.celery_app import create_celery_app

celery_app = create_celery_app(Settings())
