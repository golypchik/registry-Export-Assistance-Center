from __future__ import absolute_import, unicode_literals
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cert_checker.settings')

app = Celery('cert_checker')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.conf.timezone = 'Europe/Moscow'

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')