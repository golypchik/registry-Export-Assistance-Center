from celery import shared_task
from .utils import send_notification

@shared_task
def send_notifications_task():
    return send_notification()