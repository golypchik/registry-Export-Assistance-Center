from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from datetime import timedelta
from .models import Certificate
import logging
import traceback
from django.conf import settings
from django.core.files.base import ContentFile
from PIL import Image, ImageDraw, ImageFont
import qrcode
from io import BytesIO
import os
from django.urls import reverse
from psd_tools import PSDImage
# Добавить в начало файла после импортов

def create_qr_with_logo(data, logo_path=None, transparent_bg=True):
    """Создает QR-код с логотипом и прозрачным фоном"""
    try:
        # Создание QR-кода
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,  # Высокий уровень коррекции для логотипа
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)
        
        # Создание изображения QR-кода
        if transparent_bg:
            qr_img = qr.make_image(fill_color="black", back_color=None)
            qr_img = qr_img.convert("RGBA")
            # Делаем белый фон прозрачным
            datas = qr_img.getdata()
            newData = []
            for item in datas:
                if item[0] == 255 and item[1] == 255 and item[2] == 255:  # белый цвет
                    newData.append((255, 255, 255, 0))  # прозрачный
                else:
                    newData.append(item)
            qr_img.putdata(newData)
        else:
            qr_img = qr.make_image(fill_color="black", back_color="white")
            qr_img = qr_img.convert("RGBA")
        
        # Добавление логотипа если указан путь
        if logo_path and os.path.exists(logo_path):
            try:
                logo = Image.open(logo_path)
                logo = logo.convert("RGBA")
                
                # Размер логотипа (не более 30% от размера QR-кода)
                qr_width, qr_height = qr_img.size
                logo_size = min(qr_width, qr_height) // 4
                logo = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
                
                # Создание белого фона для логотипа
                logo_bg = Image.new('RGBA', (logo_size + 20, logo_size + 20), (255, 255, 255, 255))
                logo_bg.paste(logo, (10, 10), logo)
                
                # Позиционирование в центре
                logo_pos = ((qr_width - logo_bg.size[0]) // 2, (qr_height - logo_bg.size[1]) // 2)
                qr_img.paste(logo_bg, logo_pos, logo_bg)
                
            except Exception as e:
                logger.error(f"Не удалось добавить логотип: {str(e)}")

        return qr_img
        
    except Exception as e:
        logger.error(f"Ошибка при создании QR-кода с логотипом: {str(e)}")
        return None
logger = logging.getLogger(__name__)

def generate_certificate_image(certificate, file1_cleared=False, file1_psd_cleared=False):
    """Генерирует изображения сертификата (PNG и PSD)"""
    if file1_cleared and file1_psd_cleared:
        return None

    result = {}
    
    try:
        if not file1_cleared or not file1_psd_cleared:
            psd_path = os.path.join(settings.BASE_DIR, 'static', 'certificates', 'img', 'certificate_background.psd')
            
            if not os.path.exists(psd_path):
                logger.error(f"PSD template not found: {psd_path}")
                return None
                
            psd = PSDImage.open(psd_path)
            
            # Генерация QR-кода с логотипом
            url = settings.SITE_URL + reverse('certificate_detail', args=[certificate.id])
            logo_path = os.path.join(settings.BASE_DIR, 'certificates', 'static', 'certificates', 'img', 'company_logo.png')
            qr_img = create_qr_with_logo(url, logo_path, transparent_bg=True)
            
            if not qr_img:
                # Fallback к обычному QR-коду
                qr = qrcode.QRCode(version=1, box_size=10, border=5)
                qr.add_data(url)
                qr.make(fit=True)
                qr_img = qr.make_image(fill_color="black", back_color="white")
            
            replace_dict = {
                '%%CERTIFICATE_NUMBER%%': certificate.full_certificate_number,
                '%%ORGANIZATION_NAME%%': certificate.name,
                '%%INN%%': certificate.inn,
                '%%ADDRESS%%': certificate.address,
                '%%QUALITY_MANAGEMENT_SYSTEM%%': certificate.quality_management_system,
                '%%ISO_STANDARD%%': certificate.iso_standard_name or str(certificate.iso_standard),
                '%%START_DATE%%': certificate.start_date.strftime('%d.%m.%Y'),
                '%%EXPIRY_DATE%%': certificate.expiry_date.strftime('%d.%m.%Y'),
            }
            
            # Обработка текстовых слоев
            for layer in psd:
                if layer.kind == 'type':
                    try:
                        if hasattr(layer, 'text') and layer.text is not None:
                            original_text = layer.text.value
                            new_text = original_text
                            for key, value in replace_dict.items():
                                if key in original_text:
                                    new_text = new_text.replace(key, str(value))
                            
                            if new_text != original_text:
                                layer.text.value = new_text
                                logger.info(f"Successfully updated text in layer: {layer.name}")
                    except Exception as e:
                        logger.error(f"Error updating text in layer {layer.name}: {str(e)}")
                
                elif layer.name == '%%QR%%':
                    try:
                        # Логика для замены QR-кода требует дополнительной реализации
                        logger.info("QR code layer found")
                    except Exception as e:
                        logger.error(f"Error adding QR code: {str(e)}")

            # Сохранение PSD
            if not file1_psd_cleared:
                psd_buffer = BytesIO()
                psd.save(psd_buffer)
                psd_buffer.seek(0)
                result['psd'] = ContentFile(psd_buffer.getvalue(), name=f'certificate_{certificate.id}.psd')

            # Сохранение PNG
            if not file1_cleared:
                png_image = psd.composite()
                png_buffer = BytesIO()
                png_image.save(png_buffer, format='PNG')
                png_buffer.seek(0)
                result['png'] = ContentFile(png_buffer.getvalue(), name=f'certificate_{certificate.id}.png')

    except Exception as e:
        logger.error(f"Error generating certificate image: {str(e)}")
        return None

    return result

def generate_permission_image(certificate, file2_cleared=False, file2_psd_cleared=False):
    """Генерирует изображения разрешения (PNG и PSD)"""
    if file2_cleared and file2_psd_cleared:
        return None

    result = {}
    
    try:
        if not file2_cleared or not file2_psd_cleared:
            psd_path = os.path.join(settings.BASE_DIR, 'static', 'certificates', 'img', 'permission_background.psd')
            
            if not os.path.exists(psd_path):
                logger.error(f"PSD template not found: {psd_path}")
                return None
                
            psd = PSDImage.open(psd_path)
            
            # Генерация QR-кода с логотипом
            url = settings.SITE_URL + reverse('permission_detail', args=[certificate.id])
            logo_path = os.path.join(settings.BASE_DIR, 'certificates', 'static', 'certificates', 'img', 'company_logo.png')
            qr_img = create_qr_with_logo(url, logo_path, transparent_bg=True)
            
            if not qr_img:
                # Fallback к обычному QR-коду
                qr = qrcode.QRCode(version=1, box_size=10, border=5)
                qr.add_data(url)
                qr.make(fit=True)
                qr_img = qr.make_image(fill_color="black", back_color="white")
            
            replace_dict = {
                '%%CERTIFICATE_NUMBER%%': certificate.full_certificate_number,
                '%%ORGANIZATION_NAME%%': certificate.name,
                '%%INN%%': certificate.inn,
                '%%ADDRESS%%': certificate.address,
            }
            
            # Обработка текстовых слоев
            for layer in psd:
                if layer.kind == 'type':
                    try:
                        if hasattr(layer, 'text') and layer.text is not None:
                            original_text = layer.text.value
                            new_text = original_text
                            for key, value in replace_dict.items():
                                if key in original_text:
                                    new_text = new_text.replace(key, str(value))
                            
                            if new_text != original_text:
                                layer.text.value = new_text
                                logger.info(f"Successfully updated text in layer: {layer.name}")
                    except Exception as e:
                        logger.error(f"Error updating text in layer {layer.name}: {str(e)}")
                
                elif layer.name == '%%QR%%':
                    try:
                        logger.info("QR code layer found for permission")
                    except Exception as e:
                        logger.error(f"Error adding QR code: {str(e)}")

            # Сохранение PSD
            if not file2_psd_cleared:
                psd_buffer = BytesIO()
                psd.save(psd_buffer)
                psd_buffer.seek(0)
                result['psd'] = ContentFile(psd_buffer.getvalue(), name=f'permission_{certificate.id}.psd')

            # Сохранение PNG
            if not file2_cleared:
                png_image = psd.composite()
                png_buffer = BytesIO()
                png_image.save(png_buffer, format='PNG')
                png_buffer.seek(0)
                result['png'] = ContentFile(png_buffer.getvalue(), name=f'permission_{certificate.id}.png')

    except Exception as e:
        logger.error(f"Error generating permission image: {str(e)}")
        return None

    return result

def generate_audit_image(certificate, auditor, audit_number, audit_file_cleared=False, audit_file_psd_cleared=False):
    """Генерирует изображения аудита (PNG и PSD)"""
    if audit_file_cleared and audit_file_psd_cleared:
        return None

    result = {}
    
    try:
        if not audit_file_cleared or not audit_file_psd_cleared:
            psd_path = os.path.join(settings.BASE_DIR, 'static', 'certificates', 'img', 'audit_background.psd')
            
            if not os.path.exists(psd_path):
                logger.error(f"PSD template not found: {psd_path}")
                return None
                
            psd = PSDImage.open(psd_path)
            
            # Генерация QR-кода с логотипом
            url = settings.SITE_URL + reverse('audit_detail', args=[certificate.id, auditor.id])
            logo_path = os.path.join(settings.BASE_DIR, 'certificates', 'static', 'certificates', 'img', 'company_logo.png')
            qr_img = create_qr_with_logo(url, logo_path, transparent_bg=True)
            
            if not qr_img:
                # Fallback к обычному QR-коду
                qr = qrcode.QRCode(version=1, box_size=10, border=5)
                qr.add_data(url)
                qr.make(fit=True)
                qr_img = qr.make_image(fill_color="black", back_color="white")
            
            replace_dict = {
                '%%AUDIT_NUMBER%%': audit_number,
                '%%AUDIT_NAME%%': auditor.full_name,
                '%%ISO_STANDARD%%': str(certificate.iso_standard),
                '%%START_DATE%%': certificate.start_date.strftime('%d.%m.%Y'),
                '%%EXPIRY_DATE%%': certificate.expiry_date.strftime('%d.%m.%Y'),
            }
            
            # Обработка текстовых слоев
            for layer in psd:
                if layer.kind == 'type':
                    try:
                        if hasattr(layer, 'text') and layer.text is not None:
                            original_text = layer.text.value
                            new_text = original_text
                            for key, value in replace_dict.items():
                                if key in original_text:
                                    new_text = new_text.replace(key, str(value))
                            
                            if new_text != original_text:
                                layer.text.value = new_text
                                logger.info(f"Successfully updated text in layer: {layer.name}")
                    except Exception as e:
                        logger.error(f"Error updating text in layer {layer.name}: {str(e)}")
                
                elif layer.name == '%%QR%%':
                    try:
                        logger.info("QR code layer found for audit")
                    except Exception as e:
                        logger.error(f"Error adding QR code: {str(e)}")

            # Сохранение PSD
            if not audit_file_psd_cleared:
                psd_buffer = BytesIO()
                psd.save(psd_buffer)
                psd_buffer.seek(0)
                result['psd'] = ContentFile(psd_buffer.getvalue(), name=f'audit_{certificate.id}_{auditor.id}.psd')

            # Сохранение PNG
            if not audit_file_cleared:
                png_image = psd.composite()
                png_buffer = BytesIO()
                png_image.save(png_buffer, format='PNG')
                png_buffer.seek(0)
                result['png'] = ContentFile(png_buffer.getvalue(), name=f'audit_{certificate.id}_{auditor.id}.png')

    except Exception as e:
        logger.error(f"Error generating audit image: {str(e)}")
        return None

    return result

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
        'certification_area': getattr(cert, 'certification_area', ''),
        'expiry_date': cert.expiry_date.strftime('%d.%m.%Y'),
        'full_certificate_number': cert.full_certificate_number,
        'start_date': cert.start_date.strftime('%d.%m.%Y'),
        'inn': cert.inn,
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
ИНН: {cert.inn}
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
ИНН: {cert.inn}
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