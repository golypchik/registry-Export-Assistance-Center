"""
Management команда для тестирования генерации сертификатов
"""
from django.core.management.base import BaseCommand
from certificates.models import Certificate
from certificates.certificate_generator import generate_all_certificates
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Тестирование генерации сертификатов для существующих сертификатов'

    def add_arguments(self, parser):
        parser.add_argument(
            '--certificate-id',
            type=int,
            help='ID сертификата для генерации',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Генерировать для всех сертификатов',
        )

    def handle(self, *args, **options):
        certificate_id = options.get('certificate_id')
        generate_all = options.get('all')

        if certificate_id:
            try:
                certificate = Certificate.objects.get(pk=certificate_id)
                self.stdout.write(f'Генерация сертификатов для: {certificate.name}')
                
                if not certificate.qr_code:
                    self.stdout.write(self.style.WARNING('QR-код отсутствует. Генерирую...'))
                    if certificate._generate_qr_code():
                        certificate.save(update_fields=['qr_code'])
                        self.stdout.write(self.style.SUCCESS('QR-код создан'))
                    else:
                        self.stdout.write(self.style.ERROR('Не удалось создать QR-код'))
                        return
                
                if generate_all_certificates(certificate):
                    self.stdout.write(self.style.SUCCESS('✓ Все сертификаты успешно сгенерированы!'))
                    self.stdout.write(f'  - Сертификат (без подписей): {certificate.generated_certificate}')
                    self.stdout.write(f'  - Сертификат (с подписями): {certificate.generated_certificate_signed}')
                    self.stdout.write(f'  - Разрешение (без подписей): {certificate.generated_permission}')
                    self.stdout.write(f'  - Разрешение (с подписями): {certificate.generated_permission_signed}')
                    
                    for auditor in certificate.auditors.all():
                        self.stdout.write(f'  - Аудит для {auditor.full_name} (без подписей): {auditor.generated_audit}')
                        self.stdout.write(f'  - Аудит для {auditor.full_name} (с подписями): {auditor.generated_audit_signed}')
                else:
                    self.stdout.write(self.style.ERROR('✗ Ошибка при генерации сертификатов'))
                    
            except Certificate.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Сертификат с ID {certificate_id} не найден'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Ошибка: {e}'))
                logger.exception("Ошибка при генерации сертификатов")
                
        elif generate_all:
            certificates = Certificate.objects.all()
            total = certificates.count()
            self.stdout.write(f'Найдено сертификатов: {total}')
            
            success_count = 0
            error_count = 0
            
            for i, certificate in enumerate(certificates, 1):
                self.stdout.write(f'[{i}/{total}] Обработка: {certificate.name}')
                
                try:
                    if not certificate.qr_code:
                        self.stdout.write(self.style.WARNING('  QR-код отсутствует. Генерирую...'))
                        if certificate._generate_qr_code():
                            certificate.save(update_fields=['qr_code'])
                    
                    if generate_all_certificates(certificate):
                        self.stdout.write(self.style.SUCCESS('  ✓ Успешно'))
                        success_count += 1
                    else:
                        self.stdout.write(self.style.ERROR('  ✗ Ошибка'))
                        error_count += 1
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'  ✗ Ошибка: {e}'))
                    error_count += 1
                    logger.exception(f"Ошибка при генерации для {certificate.name}")
            
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS(f'Успешно: {success_count}'))
            if error_count > 0:
                self.stdout.write(self.style.ERROR(f'Ошибок: {error_count}'))
                
        else:
            self.stdout.write(self.style.WARNING('Укажите --certificate-id=ID или --all'))
            self.stdout.write('')
            self.stdout.write('Примеры использования:')
            self.stdout.write('  python manage.py test_certificate_generation --certificate-id=1')
            self.stdout.write('  python manage.py test_certificate_generation --all')


