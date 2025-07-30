"""cert_checker URL Configuration"""

# Стандартные импорты Python
import os
import sys

# Добавляем путь к проекту в PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Импорты Django
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from certificates import views as certificate_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('certificates.urls')),
    path('trigger-notifications/', certificate_views.trigger_notifications, name='trigger_notifications'),
    path('certificate/<int:certificate_id>/delete-file/', certificate_views.delete_certificate_file, name='delete_certificate_file'),
    
]

# Добавляем обработку медиа-файлов в режиме разработки
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    
