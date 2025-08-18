"""cert_checker URL Configuration"""

# Стандартные импорты Python
import os
import sys

# Добавляем путь к проекту в PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Импорты Django
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve

# Создаем views для главного приложения
from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('certificates.urls')),
]

# Обслуживание файлов
if settings.DEBUG:
    # В режиме разработки
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
else:
    # В продакшене - защищенное обслуживание медиа файлов
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', views.protected_media, name='media'),
    ]
    # Статические файлы обслуживаются через WhiteNoise
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)