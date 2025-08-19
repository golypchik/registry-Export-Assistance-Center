from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from django.utils import timezone
from .models import Certificate

class StaticViewSitemap(Sitemap):
    """Sitemap для статических страниц"""
    priority = 0.8
    changefreq = 'weekly'
    protocol = 'https'

    def items(self):
        return ['search_certificates']

    def location(self, item):
        try:
            return reverse(item)
        except:
            return '/'

class CertificateSitemap(Sitemap):
    """Sitemap для сертификатов"""
    changefreq = 'daily'
    priority = 0.9
    protocol = 'https'
    limit = 1000

    def items(self):
        try:
            return Certificate.objects.filter(
                status__in=['active', 'valid', 'issued']
            ).order_by('-id')[:500]  # Ограничиваем количество
        except:
            return []

    def lastmod(self, obj):
        try:
            return getattr(obj, 'updated_at', timezone.now())
        except:
            return timezone.now()

    def location(self, obj):
        try:
            return f'/certificate/{obj.pk}/'
        except:
            return '/'