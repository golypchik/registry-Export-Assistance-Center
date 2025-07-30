from django.db import models
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from django.utils.safestring import mark_safe
from django.db.models.signals import pre_delete
from django.dispatch import receiver
import os
import logging
import pandas as pd
from django.utils.functional import cached_property
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.conf import settings
from django.core.files.base import ContentFile
import qrcode
from io import BytesIO
logger = logging.getLogger(__name__)

class ISOStandard(models.Model):
    standard_name = models.CharField(max_length=100, verbose_name="Стандарт ИСО")
    description = models.TextField(verbose_name="Расшифровка стандарта")
    certificate_number_prefix = models.CharField(max_length=50, verbose_name="Префикс в сертификате")
    certificate_standard_name = models.CharField(max_length=255, verbose_name="Наименование стандарта в сертификате")
    
    def __str__(self):
        return self.standard_name
    
    class Meta:
        verbose_name = "Стандарт ИСО"
        verbose_name_plural = "Стандарты ИСО"
        ordering = ['standard_name']


class Certificate(models.Model):
    STATUS_CHOICES = [
        ('active', 'Действителен'),
        ('inspection_failed', 'Действие сертификата приостановлено, не пройден инспекционный контроль'),
        ('expired', 'Действие сертификата приостановлено, истек срок действия'),
        ('revoked', 'Отозван'),
        ('pending', 'В ожидании'),
    ]
    
    INSPECTION_STATUS_CHOICES = [
        ('pending', 'Ожидается в будущем'),
        ('passed', 'Пройден'),
        ('failed', 'Не пройден'),
    ]
    
    name = models.CharField('Наименование организации', max_length=255)
    inn = models.CharField('ИНН организации', max_length=255)
    address = models.TextField('Адрес организации')
    
    certificate_number_part = models.CharField(max_length=5, unique=True, verbose_name="Номер сертификата (часть)")

    iso_standard = models.ForeignKey(ISOStandard, on_delete=models.CASCADE, verbose_name='Стандарт ISO')
    iso_standard_name = models.CharField(max_length=255, verbose_name='Наименование стандарта в сертификате', blank=True)
    quality_management_system = models.TextField('Система менеджмента качества')
    start_date = models.DateField('Дата начала действия')
    expiry_date = models.DateField('Дата окончания действия')
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default='active')
    
    first_inspection_date = models.DateField('Дата 1-го инспекционного контроля', null=True, blank=True)
    first_inspection_status = models.CharField('Статус 1-го инспекционного контроля', 
                                              max_length=10, 
                                              choices=INSPECTION_STATUS_CHOICES, 
                                              default='pending')
    
    second_inspection_date = models.DateField('Дата 2-го инспекционного контроля', null=True, blank=True)
    second_inspection_status = models.CharField('Статус 2-го инспекционного контроля', 
                                               max_length=10, 
                                               choices=INSPECTION_STATUS_CHOICES, 
                                               default='pending')
    
    file1 = models.FileField('Файл сертификата', upload_to='certificates/', null=True, blank=True)
    file1_psd = models.FileField(upload_to='certificates/', blank=True, null=True, verbose_name="Сертификат (PSD)")
    file2 = models.FileField('Файл приложения', upload_to='certificates/', null=True, blank=True)
    file2_psd = models.FileField(upload_to='permissions/', null=True, blank=True, verbose_name="Разрешение (PSD)")
    file3 = models.FileField('Дополнительный файл', upload_to='certificates/', null=True, blank=True)
    
    # Удаляем дублирующиеся поля для очистки файлов - оставляем только clear_*
    clear_file1 = models.BooleanField(default=False)
    clear_file1_psd = models.BooleanField(default=False)
    clear_file2 = models.BooleanField(default=False)
    clear_file2_psd = models.BooleanField(default=False)
    clear_file3 = models.BooleanField(default=False)
    
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    updated_at = models.DateTimeField('Дата обновления', auto_now=True)
    
    validity_period = models.IntegerField(choices=[(1, '1 год'), (2, '2 года'), (3, '3 года')], default=1, verbose_name="Срок действия")
    client_email = models.EmailField(blank=True, null=True, verbose_name="Email клиента")
    notifications_enabled = models.BooleanField(default=False, verbose_name="Уведомления подключены")
    certification_area = models.TextField(verbose_name="Область сертификации")
    qr_code = models.ImageField(upload_to='qr_codes/', blank=True, null=True, verbose_name='QR-код')

    
    @cached_property
    def full_certificate_number(self):
        iso_code = self.iso_standard.certificate_number_prefix
        return f"№SMK.{self.certificate_number_part}{iso_code}"

    def clean(self):
        super().clean()
        if Certificate.objects.filter(certificate_number_part=self.certificate_number_part).exclude(pk=self.pk).exists():
            raise ValidationError({'certificate_number_part': "Этот номер сертификата уже занят."})

    @classmethod
    def get_next_number(cls):
        last_cert = cls.objects.order_by('-certificate_number_part').first()
        if not last_cert:
            return "01001"
        last_num = int(last_cert.certificate_number_part)
        return f"{last_num + 1:05d}"
    
    def needs_notification(self):
        if not self.notifications_enabled:
            return False
        
        today = timezone.now().date()
        days_until_expiry = (self.expiry_date - today).days
        
        return days_until_expiry in [30, 15]

    def __str__(self):
        return f"{self.name} - {self.full_certificate_number}"
    
    def calculate_status(self):
        today = timezone.now().date()
        
        if self.expiry_date < today:
            return 'expired'
        
        if self.second_inspection_date and self.second_inspection_date < today:
            if self.second_inspection_status == 'failed':
                return 'inspection_failed'
        
        if self.first_inspection_date and self.first_inspection_date < today:
            if self.first_inspection_status == 'failed':
                return 'inspection_failed'
        
        return 'active'
    
    def _delete_file_if_exists(self, file_field):
        """Безопасное удаление файла"""
        if file_field:
            try:
                if os.path.isfile(file_field.path):
                    os.remove(file_field.path)
            except (ValueError, OSError) as e:
                logger.warning(f"Не удалось удалить файл {file_field}: {e}")
    
    def _handle_file_clearing(self):
        """Обработка очистки файлов"""
        if self.clear_file1:
            self._delete_file_if_exists(self.file1)
            self.file1 = None
            self.clear_file1 = False
            
        if self.clear_file1_psd:
            self._delete_file_if_exists(self.file1_psd)
            self.file1_psd = None
            self.clear_file1_psd = False
            
        if self.clear_file2:
            self._delete_file_if_exists(self.file2)
            self.file2 = None
            self.clear_file2 = False
            
        if self.clear_file2_psd:
            self._delete_file_if_exists(self.file2_psd)
            self.file2_psd = None
            self.clear_file2_psd = False
            
        if self.clear_file3:
            self._delete_file_if_exists(self.file3)
            self.file3 = None
            self.clear_file3 = False
    
    
    
    def _generate_qr_code(self):
        """Генерирует QR-код с логотипом и прозрачным фоном"""
        try:
            import qrcode
            from PIL import Image, ImageDraw
            from django.conf import settings
            from django.core.files.base import ContentFile
            from io import BytesIO
            import os
            
            # Создаем QR-код
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_H,  # Высокий уровень коррекции для логотипа
                box_size=10,
                border=4,
            )
            
            # URL для QR-кода
            url = f"{settings.SITE_URL}/certificate/{self.id}/"
            qr.add_data(url)
            qr.make(fit=True)
            
            # Создаем изображение QR-кода с прозрачным фоном
            qr_img = qr.make_image(fill_color="black", back_color="white")
            qr_img = qr_img.convert("RGBA")
            
            # Делаем белый фон прозрачным
            data = qr_img.getdata()
            new_data = []
            for item in data:
                # Если пиксель белый (255, 255, 255), делаем его прозрачным
                if item[0] == 255 and item[1] == 255 and item[2] == 255:
                    new_data.append((255, 255, 255, 0))  # Прозрачный
                else:
                    new_data.append(item)  # Оставляем как есть
            
            qr_img.putdata(new_data)
            
            # Загружаем логотип
            logo_path = os.path.join(settings.BASE_DIR, 'certificates', 'static', 'certificates', 'img', 'company_logo.png')
            if os.path.exists(logo_path):
                logo = Image.open(logo_path)
                
                # Вычисляем размер логотипа (увеличиваем до 1/3 от размера QR-кода)
                qr_width, qr_height = qr_img.size
                logo_size = min(qr_width, qr_height) // 3
                
                # Изменяем размер логотипа
                logo = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
                
                # Если логотип не имеет альфа-канала, добавляем его
                if logo.mode != 'RGBA':New-Item -Path ".gitignore" -ItemType File
                    logo = logo.convert('RGBA')
                
                # Создаем белый квадратный фон для логотипа
                padding = 10
                logo_bg_size = logo_size + (padding * 2)
                logo_bg = Image.new('RGBA', (logo_bg_size, logo_bg_size), (255, 255, 255, 255))
                
                # Вычисляем позицию для размещения логотипа в центре QR-кода
                logo_bg_pos = ((qr_width - logo_bg_size) // 2, (qr_height - logo_bg_size) // 2)
                logo_pos = (padding, padding)
                
                # Накладываем белый квадратный фон на QR-код
                qr_img.paste(logo_bg, logo_bg_pos, logo_bg)
                
                # Накладываем логотип на белый фон
                logo_final_pos = (logo_bg_pos[0] + logo_pos[0], logo_bg_pos[1] + logo_pos[1])
                qr_img.paste(logo, logo_final_pos, logo)
            
            # Сохраняем QR-код
            buffer = BytesIO()
            qr_img.save(buffer, format='PNG')
            buffer.seek(0)
            
            filename = f'qr_code_{self.id}.png'
            self.qr_code.save(filename, ContentFile(buffer.getvalue()), save=False)
            
            return True
            
        except Exception as e:
            print(f"Ошибка при генерации QR-кода: {e}")
            return False
    
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        
        # Устанавливаем название стандарта
        if not self.iso_standard_name and self.iso_standard:
            self.iso_standard_name = self.iso_standard.certificate_standard_name
        
        # Устанавливаем даты инспекций для новых сертификатов
        if is_new:
            self.first_inspection_date = self.start_date + relativedelta(years=1)
            self.second_inspection_date = self.start_date + relativedelta(years=2)
        
        # Обновляем статус
        self.status = self.calculate_status()
        
        # Обрабатываем очистку файлов
        self._handle_file_clearing()
        
        # Сохраняем объект
        super().save(*args, **kwargs)
        
        # Генерируем QR-код для новых сертификатов или если он отсутствует
        if is_new or not self.qr_code:
            if self._generate_qr_code():
                super().save(update_fields=['qr_code'])
    def delete(self, *args, **kwargs):
        """Удаление сертификата с очисткой всех связанных файлов"""
        # Удаление файлов сертификата
        self._delete_file_if_exists(self.file1)
        self._delete_file_if_exists(self.file1_psd)
        self._delete_file_if_exists(self.file2)
        self._delete_file_if_exists(self.file2_psd)
        self._delete_file_if_exists(self.file3)
        self._delete_file_if_exists(self.qr_code)
        

        # Удаление файлов аудиторов
        for auditor in self.auditors.all():
            auditor.delete()  # Это вызовет метод delete() аудитора

        # Удаление пустых папок
        self._remove_empty_folders()

        super().delete(*args, **kwargs)

    def _remove_empty_folders(self):
        """Удаление пустых папок"""
        folders = ['certificates', 'permissions', 'audit_files', 'qr_codes', 'audit_images']
        for folder in folders:
            folder_path = os.path.join(settings.MEDIA_ROOT, folder)
            try:
                if os.path.exists(folder_path) and not os.listdir(folder_path):
                    os.rmdir(folder_path)
            except OSError as e:
                logger.warning(f"Не удалось удалить папку {folder_path}: {e}")

    def generate_audit_number(self):
        """Генерация номера аудита"""
        audits_count = self.auditors.count()
        iso_code = self.iso_standard.certificate_number_prefix
        return f"№AUD.{audits_count + 1:02d}{iso_code}"
    
    class Meta:
        verbose_name = 'Сертификат'
        verbose_name_plural = 'Сертификаты'
        ordering = ['-created_at']


class Auditor(models.Model):
    certificate = models.ForeignKey(Certificate, on_delete=models.CASCADE, related_name='auditors')
    full_name = models.CharField(max_length=255, verbose_name="ФИО аудитора")
    audit_file = models.FileField(upload_to='audit_files/', null=True, blank=True, verbose_name="Файл аудита")
    audit_file_psd = models.FileField(upload_to='audit_files/', null=True, blank=True, verbose_name="Файл аудита (PSD)")
    audit_number = models.CharField(max_length=20, blank=True, verbose_name="Номер аудита")
    generated_audit_image = models.ImageField(upload_to='audit_images/', blank=True, null=True, verbose_name="Сгенерированное изображение аудита")

    def __str__(self):
        return f"{self.full_name} - {self.certificate.full_certificate_number}"

    def _delete_file_if_exists(self, file_field):
        """Безопасное удаление файла"""
        if file_field:
            try:
                if os.path.isfile(file_field.path):
                    os.remove(file_field.path)
            except (ValueError, OSError) as e:
                logger.warning(f"Не удалось удалить файл {file_field}: {e}")

    def save(self, *args, **kwargs):
        if not self.audit_number:
            self.audit_number = self.certificate.generate_audit_number()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Удаление аудитора с очисткой файлов"""
        self._delete_file_if_exists(self.audit_file)
        self._delete_file_if_exists(self.audit_file_psd)
        self._delete_file_if_exists(self.generated_audit_image)
        super().delete(*args, **kwargs)

    class Meta:
        verbose_name = 'Аудитор'
        verbose_name_plural = 'Аудиторы'
        ordering = ['full_name']


# Сигналы для автоматической очистки файлов при удалении
@receiver(pre_delete, sender=Certificate)
def certificate_delete_files(sender, instance, **kwargs):
    """Сигнал для удаления файлов при удалении сертификата"""
    # Этот сигнал можно использовать как дополнительную защиту
    # если метод delete() по какой-то причине не сработает
    pass

@receiver(pre_delete, sender=Auditor)
def auditor_delete_files(sender, instance, **kwargs):
    """Сигнал для удаления файлов при удалении аудитора"""
    # Этот сигнал можно использовать как дополнительную защиту
    # если метод delete() по какой-то причине не сработает
    pass    