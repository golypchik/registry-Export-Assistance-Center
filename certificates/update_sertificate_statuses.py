from django.core.management.base import BaseCommand
from certificates.models import Certificate
from django.utils import timezone

class Command(BaseCommand):
    help = 'Обновляет статусы всех сертификатов на основе текущей даты'

    def handle(self, *args, **options):
        today = timezone.now().date()
        certificates = Certificate.objects.all()
        updated_count = 0
        
        for certificate in certificates:
            old_status = certificate.status
            old_first_status = certificate.first_inspection_status
            old_second_status = certificate.second_inspection_status
            
            # Проверка первого инспекционного контроля
            if certificate.first_inspection_date and today >= certificate.first_inspection_date and certificate.first_inspection_status == 'pending':
                certificate.first_inspection_status = 'failed'
                certificate.status = 'inspection_failed'
                certificate.save(update_fields=['first_inspection_status', 'status'])
                updated_count += 1
                self.stdout.write(self.style.WARNING(
                    f'Сертификат {certificate.full_certificate_number}: первый инспекционный контроль просрочен, статус изменен на "не пройден"'
                ))
            
            # Проверка второго инспекционного контроля
            elif certificate.second_inspection_date and today >= certificate.second_inspection_date and certificate.second_inspection_status == 'pending':
                certificate.second_inspection_status = 'failed'
                certificate.status = 'inspection_failed'
                certificate.save(update_fields=['second_inspection_status', 'status'])
                updated_count += 1
                self.stdout.write(self.style.WARNING(
                    f'Сертификат {certificate.full_certificate_number}: второй инспекционный контроль просрочен, статус изменен на "не пройден"'
                ))
            
            # Проверка срока действия
            elif today > certificate.expiry_date and certificate.status != 'expired':
                certificate.status = 'expired'
                certificate.save(update_fields=['status'])
                updated_count += 1
                self.stdout.write(self.style.WARNING(
                    f'Сертификат {certificate.full_certificate_number}: срок действия истек'
                ))
            
            # Общее обновление статуса
            else:
                new_status = certificate.calculate_status()
                if new_status != certificate.status:
                    certificate.status = new_status
                    certificate.save(update_fields=['status'])
                    updated_count += 1
                    self.stdout.write(self.style.SUCCESS(
                        f'Сертификат {certificate.full_certificate_number}: статус обновлен с "{old_status}" на "{new_status}"'
                    ))
        
        self.stdout.write(self.style.SUCCESS(f'Обновлено {updated_count} сертификатов'))