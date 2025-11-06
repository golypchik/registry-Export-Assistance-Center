from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from datetime import timedelta
import logging
import traceback
from django.conf import settings
from django.core.files.base import ContentFile
from PIL import Image
from io import BytesIO
import os

logger = logging.getLogger(__name__)

def send_notification(certificate=None, recipient_type=None, notification_type=None):
    """Отправляет уведомления о сертификатах"""
    admin_email = getattr(settings, 'ADMIN_EMAIL', "info@export-center.ru")
    today = timezone.now().date()

    if certificate and recipient_type and notification_type:
        return send_single_notification(certificate, recipient_type, notification_type, admin_email)
    else:
        return send_mass_notifications(admin_email, today)

def send_single_notification(cert, recipient_type, notification_type, admin_email):
    """Отправляет одиночное уведомление"""
    context = {
        'client_name': cert.name,
        'standard': cert.iso_standard,
        'certification_area': getattr(cert, 'quality_management_system', ''),
        'expiry_date': cert.expiry_date.strftime('%d.%m.%Y'),
        'full_certificate_number': cert.full_certificate_number,
        'start_date': cert.start_date.strftime('%d.%m.%Y'),
        'inn': cert.display_identifier,
        'first_inspection_date': cert.first_inspection_date.strftime('%d.%m.%Y') if cert.first_inspection_date else 'Не назначена',
        'second_inspection_date': cert.second_inspection_date.strftime('%d.%m.%Y') if cert.second_inspection_date else 'Не назначена',
    }

    try:
        if recipient_type == 'admin':
            subject = f"Уведомление о сертификате {cert.full_certificate_number}"
            
            # Определяем шаблон в зависимости от типа уведомления
            if notification_type == 'expiry_warning':
                template_name = 'certificates/emails/admin_expiry_warning.txt'
            elif notification_type == 'inspection_reminder':
                template_name = 'certificates/emails/admin_inspection_reminder.txt'
            elif notification_type == 'status_change':
                template_name = 'certificates/emails/admin_status_change.txt'
            else:
                template_name = 'certificates/emails/admin_notification.txt'
            
            try:
                message = render_to_string(template_name, context)
            except Exception:
                # Fallback к простому тексту если шаблон не найден
                message = f"""
Уведомление о сертификате {cert.full_certificate_number}

Организация: {cert.name}
{cert.display_identifier_label}: {cert.display_identifier}
Стандарт: {cert.iso_standard}
Срок действия: с {cert.start_date.strftime('%d.%m.%Y')} по {cert.expiry_date.strftime('%d.%m.%Y')}
Тип уведомления: {notification_type}

С уважением,
Система управления сертификатами
                """
            
            send_mail(subject, message, admin_email, [admin_email], fail_silently=False)
            logger.info(f"Admin notification sent for certificate {cert.full_certificate_number}")
            return 1
            
        elif recipient_type == 'client' and hasattr(cert, 'client_email') and cert.client_email:
            subject = f"Уведомление о вашем сертификате {cert.full_certificate_number}"
            
            # Определяем шаблон для клиента
            if notification_type == 'expiry_warning':
                template_name = 'certificates/emails/client_expiry_warning.txt'
            elif notification_type == 'inspection_reminder':
                template_name = 'certificates/emails/client_inspection_reminder.txt'
            elif notification_type == 'status_change':
                template_name = 'certificates/emails/client_status_change.txt'
            else:
                template_name = 'certificates/emails/client_notification.txt'
            
            try:
                message = render_to_string(template_name, context)
            except Exception:
                # Fallback к простому тексту если шаблон не найден
                message = f"""
Уважаемые коллеги!

Уведомляем Вас о статусе сертификата {cert.full_certificate_number}

Организация: {cert.name}
{cert.display_identifier_label}: {cert.display_identifier}
Стандарт: {cert.iso_standard}
Срок действия: с {cert.start_date.strftime('%d.%m.%Y')} по {cert.expiry_date.strftime('%d.%m.%Y')}

Для получения подробной информации обратитесь к администратору системы.

С уважением,
Система добровольной сертификации "Export Quality System"
                """
            
            send_mail(subject, message, admin_email, [cert.client_email], fail_silently=False)
            logger.info(f"Client notification sent for certificate {cert.full_certificate_number}")
            return 1
        else:
            logger.warning(f"Invalid recipient type or missing client email for certificate {cert.full_certificate_number}")
            return 0
            
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления для сертификата {cert.full_certificate_number}: {str(e)}")
        logger.error(traceback.format_exc())
        return 0

def send_mass_notifications(admin_email, today):
    """Отправляет массовые уведомления"""
    from .models import Certificate  # Отложенный импорт для избежания циркулярного импорта
    certificates = Certificate.objects.filter(notifications_enabled=True)
    logger.info(f"Found {certificates.count()} certificates with notifications enabled")
    notifications_sent = 0

    for cert in certificates:
        try:
            expiry_date = cert.expiry_date
            days_until_expiry = (expiry_date - today).days
            logger.info(f"Processing certificate {cert.full_certificate_number}, days until expiry: {days_until_expiry}")
            
            # Уведомления о скором истечении срока действия
            if days_until_expiry in [30, 15, 7, 1]:
                notification_type = 'expiry_warning'
                notifications_sent += send_single_notification(cert, 'admin', notification_type, admin_email)
                if hasattr(cert, 'client_email') and cert.client_email:
                    notifications_sent += send_single_notification(cert, 'client', notification_type, admin_email)
            
            # Уведомления о предстоящих инспекционных контролях
            if cert.first_inspection_date:
                days_until_first_inspection = (cert.first_inspection_date - today).days
                if days_until_first_inspection in [30, 15, 7]:
                    notification_type = 'inspection_reminder'
                    notifications_sent += send_single_notification(cert, 'admin', notification_type, admin_email)
                    if hasattr(cert, 'client_email') and cert.client_email:
                        notifications_sent += send_single_notification(cert, 'client', notification_type, admin_email)
            
            if cert.second_inspection_date:
                days_until_second_inspection = (cert.second_inspection_date - today).days
                if days_until_second_inspection in [30, 15, 7]:
                    notification_type = 'inspection_reminder'
                    notifications_sent += send_single_notification(cert, 'admin', notification_type, admin_email)
                    if hasattr(cert, 'client_email') and cert.client_email:
                        notifications_sent += send_single_notification(cert, 'client', notification_type, admin_email)
            
            # Автоматическое изменение статуса просроченных сертификатов
            if days_until_expiry < 0 and cert.status == 'active':
                cert.status = 'expired'
                cert.save()
                notification_type = 'status_change'
                notifications_sent += send_single_notification(cert, 'admin', notification_type, admin_email)
                logger.info(f"Certificate {cert.full_certificate_number} status changed to expired")
                
        except Exception as e:
            logger.error(f"Error processing certificate {cert.full_certificate_number}: {str(e)}")
            continue

    logger.info(f"Total notifications sent: {notifications_sent}")
    return notifications_sent


def compress_image(image_file, max_size_mb=1, quality=85):
    """
    Сжимает изображение до указанного размера в МБ, сохраняя приемлемое качество
    
    Args:
        image_file: Django UploadedFile object или file path
        max_size_mb: максимальный размер в мегабайтах (по умолчанию 1 МБ)
        quality: качество JPEG (10-95, по умолчанию 85)
    
    Returns:
        ContentFile object или None если сжатие не требуется
    """
    try:
        # Проверяем размер файла
        max_size_bytes = max_size_mb * 1024 * 1024
        
        if hasattr(image_file, 'size'):
            current_size = image_file.size
        else:
            current_size = os.path.getsize(image_file)
        
        # Если файл меньше лимита, возвращаем None
        if current_size <= max_size_bytes:
            logger.info(f"File size {current_size/1024/1024:.2f}MB is within limit {max_size_mb}MB")
            return None
        
        logger.info(f"Compressing image: {current_size/1024/1024:.2f}MB -> target: {max_size_mb}MB")
        
        # Открываем изображение
        if hasattr(image_file, 'read'):
            image_file.seek(0)
            image = Image.open(image_file)
        else:
            image = Image.open(image_file)
        
        # Конвертируем в RGB если нужно (для JPEG)
        if image.mode not in ('RGB', 'RGBA'):
            if image.mode == 'P' and 'transparency' in image.info:
                image = image.convert('RGBA')
            else:
                image = image.convert('RGB')
        
        # Начальные параметры
        current_quality = quality
        scale_factor = 1.0
        compressed_data = None
        
        # Итеративное сжатие
        for attempt in range(10):  # максимум 10 попыток
            # Масштабируем изображение если нужно
            if scale_factor < 1.0:
                new_width = int(image.width * scale_factor)
                new_height = int(image.height * scale_factor)
                scaled_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            else:
                scaled_image = image
            
            # Сжимаем с текущим качеством
            buffer = BytesIO()
            
            # Определяем формат сохранения
            format_name = 'JPEG'
            save_kwargs = {'format': format_name, 'quality': current_quality, 'optimize': True}
            
            # Для изображений с прозрачностью используем PNG
            if scaled_image.mode == 'RGBA':
                format_name = 'PNG'
                save_kwargs = {'format': format_name, 'optimize': True}
            
            scaled_image.save(buffer, **save_kwargs)
            compressed_size = buffer.tell()
            
            logger.info(f"Attempt {attempt+1}: Quality {current_quality}, Scale {scale_factor:.2f}, Size: {compressed_size/1024/1024:.2f}MB")
            
            # Если размер подходит, сохраняем результат
            if compressed_size <= max_size_bytes:
                compressed_data = buffer.getvalue()
                break
            
            # Уменьшаем качество или размер для следующей попытки
            if current_quality > 20:
                current_quality = max(20, current_quality - 10)
            else:
                scale_factor = max(0.5, scale_factor - 0.1)
        
        if compressed_data:
            # Определяем расширение файла
            extension = '.jpg' if format_name == 'JPEG' else '.png'
            
            # Создаем ContentFile
            compressed_file = ContentFile(compressed_data)
            
            # Оригинальное имя файла
            original_name = getattr(image_file, 'name', 'compressed_image')
            if hasattr(image_file, 'name') and image_file.name:
                name_parts = os.path.splitext(image_file.name)
                compressed_name = f"{name_parts[0]}_compressed{extension}"
            else:
                compressed_name = f"compressed_image{extension}"
            
            compressed_file.name = compressed_name
            
            final_size = len(compressed_data)
            logger.info(f"Successfully compressed: {current_size/1024/1024:.2f}MB -> {final_size/1024/1024:.2f}MB (reduction: {((current_size-final_size)/current_size*100):.1f}%)")
            
            return compressed_file
        else:
            logger.warning("Failed to compress image within size limit")
            return None
            
    except Exception as e:
        logger.error(f"Error compressing image: {str(e)}")
        logger.error(traceback.format_exc())
        return None