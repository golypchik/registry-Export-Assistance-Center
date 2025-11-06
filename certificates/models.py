
from django.conf import settings
import os
import logging
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.functional import cached_property
from django.db.models.signals import pre_delete, post_save
from django.dispatch import receiver
from dateutil.relativedelta import relativedelta
from .utils import compress_image

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


class CertificateISOStandard(models.Model):
    """Промежуточная модель для связи сертификата с несколькими ISO стандартами"""
    certificate = models.ForeignKey('Certificate', on_delete=models.CASCADE, related_name='certificate_standards')
    iso_standard = models.ForeignKey(ISOStandard, on_delete=models.CASCADE, verbose_name='Стандарт ISO')
    order = models.PositiveIntegerField(default=0, verbose_name='Порядок отображения')
    
    class Meta:
        verbose_name = 'Стандарт ISO сертификата'
        verbose_name_plural = 'Стандарты ISO сертификата'
        ordering = ['order']
        unique_together = ['certificate', 'iso_standard']
    
    def __str__(self):
        return f"{self.certificate.name} - {self.iso_standard.standard_name}"


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
    
    IDENTIFIER_TYPE_CHOICES = [
        ('inn', 'ИНН'),
        ('unp', 'УНП'),
    ]
    
    name = models.CharField('Наименование организации', max_length=255)
    identifier_type = models.CharField('Тип идентификатора', max_length=3, choices=IDENTIFIER_TYPE_CHOICES, default='inn')
    identifier_value = models.CharField('Номер идентификатора', max_length=255, default='')
    inn = models.CharField('ИНН организации', max_length=255, blank=True, null=True)  # Оставляем для совместимости, будет удалено после миграции
    address = models.TextField('Адрес организации')
    
    certificate_number_part = models.CharField(max_length=5, unique=True, verbose_name="Номер сертификата (часть)")

    # Множественные стандарты ISO через промежуточную модель
    iso_standards = models.ManyToManyField(
        ISOStandard, 
        through='CertificateISOStandard',
        verbose_name='Стандарты ISO',
        related_name='certificates'
    )
    
    # Оставляем старые поля для обратной совместимости и миграции
    iso_standard = models.ForeignKey(ISOStandard, on_delete=models.SET_NULL, verbose_name='Стандарт ISO (устаревшее)', blank=True, null=True)
    iso_standard_name = models.CharField(max_length=255, verbose_name='Наименование стандарта в сертификате', blank=True)
    quality_management_system = models.TextField('Область сертификации')
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
    file2 = models.FileField('Файл приложения', upload_to='certificates/', null=True, blank=True)
    auditor_certificate = models.FileField('Сертификат аудитора', upload_to='certificates/', null=True, blank=True)
    
    # Удаляем дублирующиеся поля для очистки файлов - оставляем только clear_*
    clear_file1 = models.BooleanField(default=False)
    clear_file2 = models.BooleanField(default=False)
    clear_auditor_certificate = models.BooleanField(default=False)
    
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    updated_at = models.DateTimeField('Дата обновления', auto_now=True)
    
    validity_period = models.IntegerField(choices=[(1, '1 год'), (2, '2 года'), (3, '3 года')], default=1, verbose_name="Срок действия")
    client_email = models.EmailField(blank=True, null=True, verbose_name="Email клиента")
    notifications_enabled = models.BooleanField(default=False, verbose_name="Уведомления подключены")
    qr_code = models.ImageField(upload_to='qr_codes/', blank=True, null=True, verbose_name='QR-код')
    
    # Автоматически генерируемые изображения сертификатов
    generated_certificate = models.ImageField(upload_to='generated_certificates/', blank=True, null=True, verbose_name='Сертификат (без подписей)')
    generated_certificate_signed = models.ImageField(upload_to='generated_certificates/', blank=True, null=True, verbose_name='Сертификат (с подписями)')
    generated_permission = models.ImageField(upload_to='generated_permissions/', blank=True, null=True, verbose_name='Разрешение (без подписей)')
    generated_permission_signed = models.ImageField(upload_to='generated_permissions/', blank=True, null=True, verbose_name='Разрешение (с подписями)')
    
    # Ручная загрузка сертификатов (заменяют автоматически сгенерированные)
    uploaded_certificate = models.ImageField(upload_to='uploaded_certificates/', blank=True, null=True, verbose_name='Загруженный сертификат (без подписей)')
    uploaded_certificate_signed = models.ImageField(upload_to='uploaded_certificates/', blank=True, null=True, verbose_name='Загруженный сертификат (с подписями)')
    uploaded_permission = models.ImageField(upload_to='uploaded_permissions/', blank=True, null=True, verbose_name='Загруженное разрешение (без подписей)')
    uploaded_permission_signed = models.ImageField(upload_to='uploaded_permissions/', blank=True, null=True, verbose_name='Загруженное разрешение (с подписями)')

    
    @cached_property
    def full_certificate_number(self):
        """Возвращает полный номер сертификата с префиксами всех стандартов"""
        # Получаем все стандарты для определения окончания номера
        all_standards = self.get_all_iso_standards()
        
        # Если 2 или более стандартов - используем .IMS
        if len(all_standards) >= 2:
            return f"№SMK.{self.certificate_number_part}.IMS"
        
        # Если один стандарт - используем его код
        if len(all_standards) == 1:
            iso_code = all_standards[0].certificate_number_prefix
            return f"№SMK.{self.certificate_number_part}{iso_code}"
        
        # Обратная совместимость со старым полем
        elif self.iso_standard:
            iso_code = self.iso_standard.certificate_number_prefix
            return f"№SMK.{self.certificate_number_part}{iso_code}"
        
        return f"№SMK.{self.certificate_number_part}"
    
    def get_first_iso_standard(self):
        """Возвращает первый ISO стандарт (для номера сертификата)"""
        first_cert_standard = self.certificate_standards.first()
        return first_cert_standard.iso_standard if first_cert_standard else None
    
    def get_all_iso_standards(self):
        """Возвращает все ISO стандарты в правильном порядке"""
        return [cs.iso_standard for cs in self.certificate_standards.all()]
    
    def get_iso_standards_display(self):
        """Возвращает строку со всеми стандартами для отображения (каждый с новой строки)"""
        standards = self.get_all_iso_standards()
        if standards:
            return '\n'.join([std.certificate_standard_name for std in standards])
        # Обратная совместимость
        elif self.iso_standard:
            return self.iso_standard.certificate_standard_name
        return self.iso_standard_name or ''
    
    @property
    def display_identifier(self):
        """Возвращает значение идентификатора"""
        return self.identifier_value or self.inn or ''
    
    @property
    def display_identifier_label(self):
        """Возвращает подпись для идентификатора (ИНН или УНП)"""
        return dict(self.IDENTIFIER_TYPE_CHOICES).get(self.identifier_type, 'ИНН')
    
    @property 
    def inn_display(self):
        """Для обратной совместимости - возвращает значение идентификатора"""
        return self.display_identifier
    
    def get_certificate_image(self, with_signatures=False):
        """Возвращает изображение сертификата с приоритетом: uploaded > generated"""
        if with_signatures:
            return self.uploaded_certificate_signed or self.generated_certificate_signed
        else:
            return self.uploaded_certificate or self.generated_certificate
    
    def get_permission_image(self, with_signatures=False):
        """Возвращает изображение разрешения с приоритетом: uploaded > generated"""
        if with_signatures:
            return self.uploaded_permission_signed or self.generated_permission_signed
        else:
            return self.uploaded_permission or self.generated_permission
    
    @property
    def display_certificate_signed(self):
        """Для использования в шаблонах - сертификат с подписями с приоритетом"""
        return self.get_certificate_image(with_signatures=True)
    
    @property
    def display_certificate(self):
        """Для использования в шаблонах - сертификат без подписей с приоритетом"""
        return self.get_certificate_image(with_signatures=False)
    
    @property
    def display_permission_signed(self):
        """Для использования в шаблонах - разрешение с подписями с приоритетом"""
        return self.get_permission_image(with_signatures=True)
    
    @property
    def display_permission(self):
        """Для использования в шаблонах - разрешение без подписей с приоритетом"""
        return self.get_permission_image(with_signatures=False)

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
            
        if self.clear_file2:
            self._delete_file_if_exists(self.file2)
            self.file2 = None
            self.clear_file2 = False
            
        if self.clear_auditor_certificate:
            self._delete_file_if_exists(self.auditor_certificate)
            self.auditor_certificate = None
            self.clear_auditor_certificate = False
    
    def _compress_images(self):
        """Сжимает изображения больше 1 МБ до приемлемого размера"""
        # Список полей с изображениями для сжатия
        image_fields = ['file1', 'file2', 'auditor_certificate', 'qr_code',
                        'generated_certificate', 'generated_certificate_signed',
                        'generated_permission', 'generated_permission_signed',
                        'uploaded_certificate', 'uploaded_certificate_signed',
                        'uploaded_permission', 'uploaded_permission_signed']
        
        for field_name in image_fields:
            field = getattr(self, field_name, None)
            if field and hasattr(field, 'file') and field.file:
                try:
                    # Проверяем, является ли файл изображением по расширению
                    if field.name:
                        file_extension = field.name.lower().split('.')[-1]
                        image_extensions = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff', 'webp']
                        
                        if file_extension in image_extensions:
                            logger.info(f"Checking image {field.name} for compression...")
                            
                            # Сжимаем изображение
                            compressed_file = compress_image(field, max_size_mb=1)
                            
                            if compressed_file:
                                # Удаляем старый файл
                                if field.name:
                                    field.delete(save=False)
                                
                                # Сохраняем сжатое изображение
                                field.save(compressed_file.name, compressed_file, save=False)
                                logger.info(f"Successfully compressed and replaced {field_name}")
                            else:
                                logger.info(f"Image {field.name} is already within size limit")
                        else:
                            logger.info(f"Skipping non-image file: {field.name}")
                            
                except Exception as e:
                    logger.error(f"Error compressing image {field_name}: {str(e)}")
                    # Продолжаем работу даже если одно изображение не удалось сжать
                    continue
    
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
            
            # Создаем изображение QR-кода с серым цветом вместо черного
            qr_img = qr.make_image(fill_color=(150, 150, 150), back_color="white")
            qr_img = qr_img.convert("RGBA")
            
            # Делаем белый фон прозрачным и QR-код на 20% прозрачным (альфа 80%)
            data = qr_img.getdata()
            new_data = []
            for item in data:
                # Если пиксель белый (255, 255, 255), делаем его полностью прозрачным
                if item[0] == 255 and item[1] == 255 and item[2] == 255:
                    new_data.append((255, 255, 255, 0))  # Полностью прозрачный
                else:
                    # Серые пиксели делаем на 20% прозрачными (80% непрозрачности = альфа 204)
                    new_data.append((item[0], item[1], item[2], 204))
            
            qr_img.putdata(new_data)
            
            # Загружаем логотип Центра Содействия Экспорту
            logo_path = os.path.join(settings.BASE_DIR, 'templates', 'background', 'logo2.png')
            logger.info(f"Проверка логотипа для QR-кода: {logo_path}")
            logger.info(f"Файл существует: {os.path.exists(logo_path)}")
            
            if os.path.exists(logo_path):
                logger.info("Начинаем добавление логотипа в QR-код")
                logo = Image.open(logo_path)
                logger.info(f"Логотип загружен, размер: {logo.size}, режим: {logo.mode}")
                
                # Вычисляем размер логотипа (увеличиваем до 1/3 от размера QR-кода)
                qr_width, qr_height = qr_img.size
                logo_size = min(qr_width, qr_height) // 3
                logger.info(f"QR-код размер: {qr_width}x{qr_height}, размер логотипа: {logo_size}x{logo_size}")
                
                # Изменяем размер логотипа
                logo = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
                
                # Если логотип не имеет альфа-канала, добавляем его
                if logo.mode != 'RGBA':
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
                logger.info("Логотип успешно добавлен в QR-код")
            else:
                logger.warning(f"Файл логотипа не найден: {logo_path}")
            
            # Сохраняем QR-код
            buffer = BytesIO()
            qr_img.save(buffer, format='PNG')
            buffer.seek(0)
            
            filename = f'qr_code_{self.id}.png'
            self.qr_code.save(filename, ContentFile(buffer.getvalue()), save=False)
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при генерации QR-кода: {e}", exc_info=True)
            print(f"Ошибка при генерации QR-кода: {e}")
            return False
    
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        
        # Миграция данных из старого поля inn в новые поля
        if self.inn and not self.identifier_value:
            self.identifier_value = self.inn
            self.identifier_type = 'inn'
        
        # Устанавливаем название стандарта (обновляем при каждом сохранении)
        # Теперь используем все стандарты через get_iso_standards_display()
        # Но это можно сделать только после сохранения, так как нужен доступ к M2M
        # Поэтому обновляем iso_standard_name в post_save сигнале или после добавления стандартов
        if self.iso_standard:
            # Обратная совместимость - если используется старое поле
            self.iso_standard_name = self.iso_standard.certificate_standard_name
        
        # Устанавливаем даты инспекций для новых сертификатов
        if is_new:
            self.first_inspection_date = self.start_date + relativedelta(years=1)
            self.second_inspection_date = self.start_date + relativedelta(years=2)
        
        # Обновляем статус
        self.status = self.calculate_status()
        
        # Обрабатываем очистку файлов
        self._handle_file_clearing()
        
        # Сжимаем изображения перед сохранением
        self._compress_images()
        
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
        self._delete_file_if_exists(self.file2)
        self._delete_file_if_exists(self.auditor_certificate)
        self._delete_file_if_exists(self.qr_code)
        
        # Удаление сгенерированных файлов
        self._delete_file_if_exists(self.generated_certificate)
        self._delete_file_if_exists(self.generated_certificate_signed)
        self._delete_file_if_exists(self.generated_permission)
        self._delete_file_if_exists(self.generated_permission_signed)
        
        # Удаление загруженных вручную файлов
        self._delete_file_if_exists(self.uploaded_certificate)
        self._delete_file_if_exists(self.uploaded_certificate_signed)
        self._delete_file_if_exists(self.uploaded_permission)
        self._delete_file_if_exists(self.uploaded_permission_signed)
        

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
        
        # Получаем все стандарты для определения окончания номера
        all_standards = self.get_all_iso_standards()
        
        # Если 2 или более стандартов - используем .IMS
        if len(all_standards) >= 2:
            iso_code = ".IMS"
        # Если один стандарт - используем его код
        elif len(all_standards) == 1:
            iso_code = all_standards[0].certificate_number_prefix
        # Обратная совместимость со старым полем
        elif self.iso_standard:
            iso_code = self.iso_standard.certificate_number_prefix
        else:
            iso_code = ""
        
        return f"№AUD.{audits_count + 1:02d}{iso_code}"
    
    class Meta:
        verbose_name = 'Сертификат'
        verbose_name_plural = 'Сертификаты'
        ordering = ['-certificate_number_part']  # Сортировка по номеру (от новых к старым)


class Auditor(models.Model):
    certificate = models.ForeignKey(Certificate, on_delete=models.CASCADE, related_name='auditors')
    full_name = models.CharField(max_length=255, verbose_name="ФИО аудитора")
    audit_file = models.FileField(upload_to='audit_files/', null=True, blank=True, verbose_name="Файл аудита")
    audit_number = models.CharField(max_length=20, blank=True, verbose_name="Номер аудита")
    generated_audit_image = models.ImageField(upload_to='audit_images/', blank=True, null=True, verbose_name="Сгенерированное изображение аудита")
    
    # Автоматически генерируемые изображения аудита
    generated_audit = models.ImageField(upload_to='generated_audits/', blank=True, null=True, verbose_name='Аудит (без подписей)')
    generated_audit_signed = models.ImageField(upload_to='generated_audits/', blank=True, null=True, verbose_name='Аудит (с подписями)')
    
    # Ручная загрузка сертификатов аудитора (заменяют автоматически сгенерированные)
    uploaded_audit = models.ImageField(upload_to='uploaded_audits/', blank=True, null=True, verbose_name='Загруженный аудит (без подписей)')
    uploaded_audit_signed = models.ImageField(upload_to='uploaded_audits/', blank=True, null=True, verbose_name='Загруженный аудит (с подписями)')

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

    def _compress_images(self):
        """Сжимает изображения больше 1 МБ до приемлемого размера"""
        # Список полей с изображениями для сжатия
        image_fields = ['audit_file', 'generated_audit_image',
                        'generated_audit', 'generated_audit_signed',
                        'uploaded_audit', 'uploaded_audit_signed']
        
        for field_name in image_fields:
            field = getattr(self, field_name, None)
            if field and hasattr(field, 'file') and field.file:
                try:
                    # Проверяем, является ли файл изображением по расширению
                    if field.name:
                        file_extension = field.name.lower().split('.')[-1]
                        image_extensions = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff', 'webp']
                        
                        if file_extension in image_extensions:
                            logger.info(f"Checking auditor image {field.name} for compression...")
                            
                            # Сжимаем изображение
                            compressed_file = compress_image(field, max_size_mb=1)
                            
                            if compressed_file:
                                # Удаляем старый файл
                                if field.name:
                                    field.delete(save=False)
                                
                                # Сохраняем сжатое изображение
                                field.save(compressed_file.name, compressed_file, save=False)
                                logger.info(f"Successfully compressed and replaced auditor {field_name}")
                            else:
                                logger.info(f"Auditor image {field.name} is already within size limit")
                        else:
                            logger.info(f"Skipping non-image auditor file: {field.name}")
                            
                except Exception as e:
                    logger.error(f"Error compressing auditor image {field_name}: {str(e)}")
                    # Продолжаем работу даже если одно изображение не удалось сжать
                    continue

    def save(self, *args, **kwargs):
        if not self.audit_number:
            self.audit_number = self.certificate.generate_audit_number()
        
        # Сжимаем изображения перед сохранением
        self._compress_images()
        
        super().save(*args, **kwargs)

    def get_audit_image(self, with_signatures=False):
        """Возвращает изображение аудита с приоритетом: uploaded > generated"""
        if with_signatures:
            return self.uploaded_audit_signed or self.generated_audit_signed
        else:
            return self.uploaded_audit or self.generated_audit
    
    @property
    def display_audit_signed(self):
        """Для использования в шаблонах - аудит с подписями с приоритетом"""
        return self.get_audit_image(with_signatures=True)
    
    @property
    def display_audit(self):
        """Для использования в шаблонах - аудит без подписей с приоритетом"""
        return self.get_audit_image(with_signatures=False)

    def delete(self, *args, **kwargs):
        """Удаление аудитора с очисткой файлов"""
        self._delete_file_if_exists(self.audit_file)
        self._delete_file_if_exists(self.generated_audit_image)
        self._delete_file_if_exists(self.generated_audit)
        self._delete_file_if_exists(self.generated_audit_signed)
        self._delete_file_if_exists(self.uploaded_audit)
        self._delete_file_if_exists(self.uploaded_audit_signed)
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


@receiver(post_save, sender=Certificate)
def generate_certificate_images(sender, instance, created, **kwargs):
    """
    Автоматически генерирует изображения сертификатов после сохранения
    НЕ генерирует сразу, так как M2M связи еще не сохранены
    """
    # Проверяем, что это не рекурсивный вызов
    if kwargs.get('update_fields'):
        # Если update_fields указаны, это скорее всего наш собственный вызов save()
        # Проверяем, не обновляем ли мы только generated поля
        update_fields = kwargs.get('update_fields', [])
        if any(field.startswith('generated_') for field in update_fields):
            return
    
    # Проверяем, есть ли QR-код (он генерируется первым)
    if not instance.qr_code:
        logger.info(f"QR-код еще не создан для сертификата {instance.id}, пропускаем генерацию")
        return
    
    # Если есть старое поле iso_standard (для обратной совместимости), генерируем сразу
    if instance.iso_standard and not instance.certificate_standards.exists():
        from .certificate_generator import generate_all_certificates
        try:
            logger.info(f"Найден старый стандарт для {instance.name}, генерируем сертификаты")
            generate_all_certificates(instance)
        except Exception as e:
            logger.error(f"Ошибка при генерации сертификатов: {e}", exc_info=True)
    else:
        # НЕ генерируем здесь - будет генерация в m2m_changed сигнале
        logger.info(f"Сертификат {instance.name} (ID: {instance.id}) сохранен, ожидаем сохранения ISO стандартов")


# ПРИМЕЧАНИЕ: Сигнал m2m_changed НЕ работает для промежуточных моделей (through)
# когда данные сохраняются через inline формы в админке.
# Поэтому генерация вызывается вручную в save_formset метода CertificateAdmin


@receiver(post_save, sender=Auditor)
def generate_auditor_images(sender, instance, created, **kwargs):
    """
    Автоматически генерирует изображения аудита после сохранения аудитора
    """
    # Проверяем, что это не рекурсивный вызов
    if kwargs.get('update_fields'):
        update_fields = kwargs.get('update_fields', [])
        if any(field.startswith('generated_') for field in update_fields):
            return
    
    # Проверяем, есть ли QR-код у сертификата
    if not instance.certificate.qr_code:
        logger.info(f"QR-код еще не создан для сертификата, пропускаем генерацию аудита")
        return
    
    # Импортируем генератор
    from .certificate_generator import generate_audit_certificate
    
    try:
        logger.info(f"Запуск генерации аудита для {instance.full_name}")
        
        # Генерируем аудит без подписей
        audit_file = generate_audit_certificate(instance.certificate, instance, with_signatures=False)
        if audit_file:
            filename = f'audit_{instance.id}.png'
            instance.generated_audit.save(filename, audit_file, save=False)
        
        # Генерируем аудит с подписями
        audit_signed_file = generate_audit_certificate(instance.certificate, instance, with_signatures=True)
        if audit_signed_file:
            filename = f'audit_{instance.id}_signed.png'
            instance.generated_audit_signed.save(filename, audit_signed_file, save=False)
        
        # Сохраняем с указанием update_fields чтобы избежать рекурсии
        instance.save(update_fields=['generated_audit', 'generated_audit_signed'])
        
    except Exception as e:
        logger.error(f"Ошибка при автоматической генерации аудита: {e}", exc_info=True)    