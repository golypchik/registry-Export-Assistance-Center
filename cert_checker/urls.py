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
def verification_file(request, filename):
    """Обслуживание файлов верификации поисковых систем"""
    try:
        # Путь к файлам верификации
        verification_dir = os.path.join(settings.STATIC_ROOT, 'verification')
        file_path = os.path.join(verification_dir, filename)
        
        # Проверяем существование файла
        if os.path.exists(file_path) and os.path.isfile(file_path):
            # Определяем content-type по расширению
            if filename.endswith('.xml'):
                content_type = 'application/xml'
            else:
                content_type = 'text/html'
            
            return FileResponse(open(file_path, 'rb'), content_type=content_type)
        else:
            raise Http404("Файл верификации не найден")
    except Exception as e:
        raise Http404(f"Ошибка при обслуживании файла верификации: {e}")

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('certificates.urls')),
    path('robots.txt', robots_txt, name='robots_txt'),
    
    # Файлы верификации поисковых систем (Google)
    re_path(r'^google(?P<filename>[a-f0-9]+)\.html$', verification_file, name='google_verification'),
    
    # Файлы верификации поисковых систем (Яндекс)
    re_path(r'^yandex_(?P<filename>[a-f0-9]+)\.html$', verification_file, name='yandex_verification'),
    
    # Файлы верификации поисковых систем (Bing)
    re_path(r'^BingSiteAuth\.xml$', verification_file, {'filename': 'BingSiteAuth.xml'}, name='bing_verification'),
    
    # Дополнительные файлы верификации (на случай других форматов)
    re_path(r'^(?P<filename>google[a-f0-9]+\.html)$', verification_file, name='google_verification_alt'),
    re_path(r'^(?P<filename>yandex_[a-f0-9]+\.html)$', verification_file, name='yandex_verification_alt'),
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