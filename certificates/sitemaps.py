from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from .models import Certificate

class StaticViewSitemap(Sitemap):
    """Sitemap для статических страниц"""
    priority = 0.5
    changefreq = 'daily'

    def items(self):
        return ['index', 'search']

    def location(self, item):
        return reverse(item)

class CertificateSitemap(Sitemap):
    """Sitemap для сертификатов"""
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        return Certificate.objects.filter(status='active')

    def lastmod(self, obj):
        return obj.updated_at if hasattr(obj, 'updated_at') else obj.created_at

    def location(self, obj):
        return reverse('certificate_detail', args=[obj.certificate_number])