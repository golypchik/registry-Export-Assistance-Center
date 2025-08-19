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
from django.http import HttpResponse, FileResponse, Http404
from django.views.decorators.http import require_GET
from django.views.generic import TemplateView
from django.contrib.sitemaps.views import sitemap
from django.views.static import serve
# Импорт views из приложения certificates
from certificates import views

# Импорт sitemaps
try:
    from certificates.sitemaps import StaticViewSitemap, CertificateSitemap
    sitemaps = {
        'static': StaticViewSitemap,
        'certificates': CertificateSitemap,
    }
except ImportError:
    # Если файл sitemaps.py не существует, используем пустой словарь
    sitemaps = {}

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
        "Crawl-delay: 1",
        "",
        "User-agent: Yandex", 
        "Allow: /",
        "Crawl-delay: 1",
        "",
        "User-agent: Bingbot",
        "Allow: /",
        "Crawl-delay: 1",
        "",
        "# Запрещаем индексацию административных разделов",
        "Disallow: /admin/",
        "Disallow: /media/private/",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")

@require_GET
def google_verification(request):
    """Обслуживание файла верификации Google"""
    file_path = os.path.join(settings.BASE_DIR, 'googlec0ac4a089806bf02.html')
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return HttpResponse(content, content_type='text/html')
    raise Http404("Google verification file not found")

@require_GET
def yandex_verification(request):
    """Обслуживание файла верификации Яндекс"""
    file_path = os.path.join(settings.BASE_DIR, 'yandex_77e8b3f69934cd66.html')
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return HttpResponse(content, content_type='text/html')
    raise Http404("Yandex verification file not found")

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('certificates.urls')),
    path('robots.txt', robots_txt, name='robots_txt'),
    
    # Файлы верификации поисковых систем
    path('googlec0ac4a089806bf02.html', google_verification, name='google_verification'),
    path('yandex_77e8b3f69934cd66.html', yandex_verification, name='yandex_verification'),
]

# Добавляем sitemap только если sitemaps определены
if sitemaps:
    urlpatterns.append(
        path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap')
    )
else:
    # Fallback sitemap
    urlpatterns.append(
        path('sitemap.xml', TemplateView.as_view(template_name='sitemap.xml', content_type='application/xml'))
    )

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