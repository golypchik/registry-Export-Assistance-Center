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

# Импорт views из приложения certificates
from certificates import views
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse
from django.views.decorators.http import require_GET
from django.views.generic import TemplateView

@require_GET
def robots_txt(request):
    lines = [
        "User-agent: *",
        "Allow: /",
        "",
        f"Sitemap: {request.build_absolute_uri('/sitemap.xml')}",
        "",
        "# Дополнительные директивы для поисковых систем",
        "User-agent: Googlebot",
        "Allow: /",
        "",
        "User-agent: Yandex", 
        "Allow: /",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('certificates.urls')),
    path('robots.txt', robots_txt),
    path('sitemap.xml', TemplateView.as_view(template_name='sitemap.xml', content_type='application/xml')),
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