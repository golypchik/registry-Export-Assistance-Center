from django.core.management.base import BaseCommand
from certificates.models import Certificate
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Обновляет статусы сертификатов на основе дат и инспекционных контролей'

    def handle(self, *args, **options):
        today = timezone.now().date()
        certificates = Certificate.objects.all()
        updated_count = 0
        
        for certificate in certificates:
            old_status = certificate.status
            new_status = certificate.calculate_status()
            
            if old_status != new_status:
                certificate.status = new_status
                certificate.save(update_fields=['status'])
                updated_count += 1
                self.stdout.write(self.style.SUCCESS(
                    f'Обновлен статус сертификата {certificate.full_certificate_number}: {old_status} -> {new_status}'
                ))
        
        self.stdout.write(self.style.SUCCESS(f'Обновлено {updated_count} сертификатов из {certificates.count()}'))