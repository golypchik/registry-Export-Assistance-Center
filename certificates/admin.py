from django.contrib import admin
from django.utils.html import format_html, mark_safe
from django.http import HttpResponse, HttpResponseRedirect
from django.conf import settings
from .models import Certificate, ISOStandard, Auditor
import re
import os
import logging
from django.core.files.base import ContentFile
from django import forms
from .forms import CertificateAdminForm

logger = logging.getLogger(__name__)
def get_file_preview(file):
    if file:
        if file.name.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
            return format_html('<img src="{}" style="max-height: 100px;" />', file.url)
        elif file.name.lower().endswith('.pdf'):
            return format_html('<a href="{}" target="_blank">Просмотреть PDF</a>', file.url)
        elif file.name.lower().endswith('.psd'):
            return format_html('<a href="{}" target="_blank">Скачать PSD</a>', file.url)
        else:
            return format_html('<a href="{}" target="_blank">Скачать файл</a>', file.url)
    return "Нет файла"

class AuditorInline(admin.TabularInline):
    model = Auditor
    extra = 1
    fields = ('full_name', 'audit_file', 'audit_file_preview')
    readonly_fields = ('audit_file_preview',)

    def audit_file_preview(self, instance):
        return get_file_preview(instance.audit_file)
    audit_file_preview.short_description = "Предпросмотр файла аудита"

class CertificateAdminForm(forms.ModelForm):
    class Meta:
        model = Certificate
        fields = '__all__'
        exclude = ['auditor_certificate', 'file1', 'file2']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['identifier_type'].widget = forms.RadioSelect(choices=Certificate.IDENTIFIER_TYPE_CHOICES)
        self.fields['identifier_value'].widget = forms.TextInput(attrs={'size': '20'})

@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    form = CertificateAdminForm
    inlines = [AuditorInline]
    list_display = ('name', 'full_certificate_number', 'display_identifier_info', 'iso_standard', 'iso_standard_name', 'status', 
                    'first_inspection_status', 'second_inspection_status',
                    'start_date', 'expiry_date', 'notifications_enabled')
    list_filter = ('status', 'iso_standard', 'identifier_type', 'first_inspection_status', 'second_inspection_status', 'notifications_enabled')
    search_fields = ('name', 'certificate_number_part', 'identifier_value', 'inn')
    date_hierarchy = 'created_at'
    
    def display_identifier_info(self, obj):
        return f"{obj.display_identifier_label}: {obj.display_identifier}"
    display_identifier_info.short_description = "Идентификатор"

    exclude = ('additional_files',)
    
    fieldsets = (
        ('Информация об организации', {
            'fields': ('name', 'identifier_type', 'identifier_value', 'address')
        }),
        ('Информация о сертификате', {
            'fields': ('certificate_number_part', 'iso_standard', 'iso_standard_name', 'quality_management_system', 
                      'start_date', 'expiry_date', 'status', 'validity_period', 'certification_area')
        }),
        ('Инспекционный контроль', {
            'fields': ('first_inspection_date', 'first_inspection_status',
                      'second_inspection_date', 'second_inspection_status')
        }),
        ('Файлы', {
            'fields': (
                'permissions_preview',
                'uploaded_permission',
                'uploaded_permission_signed',
                'certificates_preview',
                'uploaded_certificate',
                'uploaded_certificate_signed',
                'qr_code',
                'auditors_certificates_preview',
            )
        }),
        ('Уведомления', {
            'fields': ('client_email', 'notifications_enabled')
        }),
    )
    
    readonly_fields = ('permissions_preview', 'certificates_preview', 
                       'auditors_certificates_preview', 'qr_code')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "iso_standard":
            kwargs["queryset"] = ISOStandard.objects.all().order_by('standard_name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        # Сохраняем модель
        super().save_model(request, obj, form, change)
        
        # Очищаем данные дублирования из сессии после успешного сохранения
        if 'duplicate_certificate_data' in request.session:
            del request.session['duplicate_certificate_data']
            logger.info("Данные дублирования очищены из сессии")

    def save_formset(self, request, form, formset, change):
        """Сохранение формсета аудиторов"""
        instances = formset.save(commit=False)
        
        for instance in instances:
            if not instance.pk:  # Новый аудитор
                instance.save()  # Сохраняем для получения ID
                
                # Генерируем номер аудита если его нет
                if not instance.audit_number:
                    instance.audit_number = form.instance.generate_audit_number()
            
            instance.save()
        
        # Удаляем отмеченные для удаления объекты
        for obj in formset.deleted_objects:
            obj.delete()
        
        formset.save_m2m()

    def duplicate_certificates(self, request, queryset):
        """Действие для дублирования сертификатов"""
        if queryset.count() != 1:
            self.message_user(request, "Пожалуйста, выберите только один сертификат для дублирования.")
            return
        
        certificate = queryset.first()
        return HttpResponseRedirect(f'/admin/certificates/certificate/add/?duplicate_from={certificate.id}')
    
    duplicate_certificates.short_description = "Дублировать сертификат"

    
    def get_urls(self):
        """Добавляем URL для регенерации QR-кода, получения данных ISO стандарта и регенерации сертификатов"""
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:object_id>/regenerate-qr/',
                self.admin_site.admin_view(self.regenerate_qr_view),
                name='certificates_certificate_regenerate_qr',
            ),
            path(
                '<int:object_id>/regenerate-certificates/',
                self.admin_site.admin_view(self.regenerate_certificates_view),
                name='certificates_certificate_regenerate_certificates',
            ),
            path(
                'get-iso-standard/<int:standard_id>/',
                self.admin_site.admin_view(self.get_iso_standard_data),
                name='certificates_certificate_get_iso_standard',
            ),
        ]
        return custom_urls + urls
    
    def get_iso_standard_data(self, request, standard_id):
        """Получение данных ISO стандарта по ID"""
        from django.http import JsonResponse
        from django.shortcuts import get_object_or_404
        
        try:
            iso_standard = get_object_or_404(ISOStandard, pk=standard_id)
            return JsonResponse({
                'status': 'success',
                'data': {
                    'certificate_standard_name': iso_standard.certificate_standard_name,
                    'certificate_number_prefix': iso_standard.certificate_number_prefix,
                    'description': iso_standard.description,
                }
            })
        except Exception as e:
            logger.error(f"Ошибка при получении данных ISO стандарта: {e}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
    def regenerate_qr_view(self, request, object_id):
        """Представление для регенерации QR-кода"""
        from django.http import JsonResponse
        from django.shortcuts import get_object_or_404
        
        if request.method == 'POST':
            try:
                certificate = get_object_or_404(Certificate, pk=object_id)
                
                # Удаляем старый QR-код
                if certificate.qr_code:
                    certificate._delete_file_if_exists(certificate.qr_code)
                    certificate.qr_code = None
                
                # Генерируем новый QR-код
                if certificate._generate_qr_code():
                    certificate.save(update_fields=['qr_code'])
                    return JsonResponse({'status': 'success', 'message': 'QR-код успешно сгенерирован'})
                else:
                    return JsonResponse({'status': 'error', 'message': 'Ошибка при генерации QR-кода'}, status=500)
                    
            except Exception as e:
                logger.error(f"Ошибка при регенерации QR-кода: {e}")
                return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
        
        return JsonResponse({'status': 'error', 'message': 'Метод не поддерживается'}, status=405)
    
    def regenerate_certificates_view(self, request, object_id):
        """Представление для ручной регенерации сертификатов"""
        from django.http import JsonResponse
        from django.shortcuts import get_object_or_404
        from .certificate_generator import generate_all_certificates
        
        if request.method == 'POST':
            try:
                certificate = get_object_or_404(Certificate, pk=object_id)
                
                # Проверяем наличие QR-кода
                if not certificate.qr_code:
                    return JsonResponse({'status': 'error', 'message': 'Сначала необходимо создать QR-код'}, status=400)
                
                # Генерируем все сертификаты
                if generate_all_certificates(certificate):
                    return JsonResponse({'status': 'success', 'message': 'Все сертификаты успешно сгенерированы'})
                else:
                    return JsonResponse({'status': 'error', 'message': 'Ошибка при генерации сертификатов'}, status=500)
                    
            except Exception as e:
                logger.error(f"Ошибка при регенерации сертификатов: {e}")
                return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
        
        return JsonResponse({'status': 'error', 'message': 'Метод не поддерживается'}, status=405)
    
    
    def get_form(self, request, obj=None, **kwargs):
        """Переопределяем get_form для поддержки дублирования"""
        form_class = super().get_form(request, obj, **kwargs)
        
        # Если это дублирование и данные есть в сессии
        if not obj and 'duplicate_certificate_data' in request.session:
            try:
                duplicate_data = request.session['duplicate_certificate_data']
                logger.info(f"Загружаем данные дублирования из сессии: {duplicate_data.get('name', 'Unknown')}")
                
                # Создаем кастомный класс формы с предзаполненными данными
                class DuplicateForm(form_class):
                    def __init__(self, *args, **kwargs):
                        super().__init__(*args, **kwargs)
                        if not self.instance.pk:  # Только для новых объектов
                            self.initial.update({
                                'name': duplicate_data.get('name'),
                                'identifier_type': duplicate_data.get('identifier_type'),
                                'identifier_value': duplicate_data.get('identifier_value'),
                                'inn': duplicate_data.get('inn'),
                                'address': duplicate_data.get('address'),
                                'certificate_number_part': duplicate_data.get('certificate_number_part'),
                                'iso_standard': duplicate_data.get('iso_standard_id'),
                                'iso_standard_name': duplicate_data.get('iso_standard_name'),
                                'quality_management_system': duplicate_data.get('quality_management_system'),
                                'start_date': duplicate_data.get('start_date'),
                                'expiry_date': duplicate_data.get('expiry_date'),
                                'status': duplicate_data.get('status'),
                                'first_inspection_date': duplicate_data.get('first_inspection_date'),
                                'first_inspection_status': duplicate_data.get('first_inspection_status'),
                                'second_inspection_date': duplicate_data.get('second_inspection_date'),
                                'second_inspection_status': duplicate_data.get('second_inspection_status'),
                                'validity_period': duplicate_data.get('validity_period'),
                                'client_email': duplicate_data.get('client_email'),
                                'notifications_enabled': duplicate_data.get('notifications_enabled'),
                                'certification_area': duplicate_data.get('certification_area'),
                            })
                            logger.info("Форма предзаполнена данными дублирования")
                
                return DuplicateForm
                
            except Exception as e:
                logger.error(f"Ошибка при предзаполнении формы: {str(e)}")
        
        return form_class
    
    def add_view(self, request, form_url='', extra_context=None):
        """Переопределяем add_view для поддержки дублирования"""
        duplicate_from_id = request.GET.get('duplicate_from')
        
        if duplicate_from_id:
            try:
                logger.info(f"Дублирование сертификата с ID: {duplicate_from_id}")
                
                # Получаем сертификат для дублирования
                original_certificate = Certificate.objects.get(pk=duplicate_from_id)
                logger.info(f"Найден оригинальный сертификат: {original_certificate.name}")
                
                # Собираем данные аудиторов
                auditors_data = []
                for auditor in original_certificate.auditors.all():
                    auditors_data.append({
                        'full_name': auditor.full_name,
                    })
                
                logger.info(f"Найдено {len(auditors_data)} аудиторов для дублирования")
                
                # Сохраняем данные в сессии
                request.session['duplicate_certificate_data'] = {
                    'name': original_certificate.name,
                    'identifier_type': original_certificate.identifier_type,
                    'identifier_value': original_certificate.identifier_value,
                    'inn': original_certificate.inn,
                    'address': original_certificate.address,
                    'certificate_number_part': Certificate.get_next_number(),
                    'iso_standard_id': original_certificate.iso_standard.id,
                    'iso_standard_name': original_certificate.iso_standard_name,
                    'quality_management_system': original_certificate.quality_management_system,
                    'start_date': original_certificate.start_date.isoformat(),
                    'expiry_date': original_certificate.expiry_date.isoformat(),
                    'status': 'pending',  # Новый сертификат в статусе "В ожидании"
                    'first_inspection_date': original_certificate.first_inspection_date.isoformat() if original_certificate.first_inspection_date else None,
                    'first_inspection_status': original_certificate.first_inspection_status,
                    'second_inspection_date': original_certificate.second_inspection_date.isoformat() if original_certificate.second_inspection_date else None,
                    'second_inspection_status': original_certificate.second_inspection_status,
                    'validity_period': original_certificate.validity_period,
                    'client_email': original_certificate.client_email,
                    'notifications_enabled': original_certificate.notifications_enabled,
                    'certification_area': original_certificate.certification_area,
                    'auditors': auditors_data,
                }
                
                logger.info("Данные сохранены в сессии")
                
            except Certificate.DoesNotExist:
                logger.error(f"Сертификат с ID {duplicate_from_id} не найден")
            except Exception as e:
                logger.error(f"Ошибка при дублировании: {str(e)}")
        
        return super().add_view(request, form_url, extra_context)
    
    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        """Переопределяем changeform_view для поддержки дублирования аудиторов"""
        # Если это дублирование и данные есть в сессии
        if not object_id and 'duplicate_certificate_data' in request.session:
            try:
                duplicate_data = request.session['duplicate_certificate_data']
                auditors_data = duplicate_data.get('auditors', [])
                
                if auditors_data:
                    logger.info(f"Найдено {len(auditors_data)} аудиторов для дублирования")
                    
                    # Добавляем данные аудиторов в extra_context
                    if extra_context is None:
                        extra_context = {}
                    
                    # Преобразуем данные в JSON для JavaScript
                    import json
                    extra_context['duplicate_auditors'] = json.dumps(auditors_data)
                    logger.info("Данные аудиторов добавлены в контекст")
                
            except Exception as e:
                logger.error(f"Ошибка при подготовке данных аудиторов: {str(e)}")
        
        return super().changeform_view(request, object_id, form_url, extra_context)
    
    def qr_code(self, obj):
        """Отображение QR-кода в админке с возможностью регенерации"""
        if obj.qr_code:
            return format_html(
                '<div style="text-align: center;">'
                '<img src="{}" style="max-width:100px; max-height:100px; border: 1px solid #ddd; border-radius: 4px;" /><br>'
                '<small>QR-код с логотипом</small><br>'
                '<a href="javascript:void(0)" onclick="regenerateQR({})" style="font-size: 11px; color: #007cba;">Перегенерировать</a>'
                '</div>'
                '<script>'
                'function regenerateQR(certId) {{'
                '    if(confirm("Перегенерировать QR-код?")) {{'
                '        fetch("/admin/certificates/certificate/" + certId + "/regenerate-qr/", {{'
                '            method: "POST",'
                '            headers: {{'
                '                "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]").value,'
                '                "Content-Type": "application/json"'
                '            }}'
                '        }}).then(response => {{'
                '            if(response.ok) {{'
                '                location.reload();'
                '            }} else {{'
                '                alert("Ошибка при генерации QR-кода");'
                '            }}'
                '        }});'
                '    }}'
                '}}'
                '</script>', 
                obj.qr_code.url, obj.pk
            )
        return format_html(
            '<div style="text-align: center; color: #666;">'
            'QR-код не сгенерирован<br>'
            '<a href="javascript:void(0)" onclick="regenerateQR({})" style="font-size: 11px; color: #007cba;">Сгенерировать</a>'
            '</div>'
            '<script>'
            'function regenerateQR(certId) {{'
            '    fetch("/admin/certificates/certificate/" + certId + "/regenerate-qr/", {{'
            '        method: "POST",'
            '        headers: {{'
            '            "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]").value,'
            '            "Content-Type": "application/json"'
            '        }}'
            '    }}).then(response => {{'
            '        if(response.ok) {{'
            '            location.reload();'
            '        }} else {{'
            '            alert("Ошибка при генерации QR-кода");'
            '        }}'
            '    }});'
            '}}'
            '</script>', 
            obj.pk
        )
    qr_code.short_description = 'QR-код'

    def certificates_preview(self, obj):
        """Превью сертификатов с возможностью замены загруженными файлами"""
        if not obj.pk:
            return "Сохраните сертификат для просмотра"
        
        html_parts = []
        html_parts.append('<div style="display: flex; flex-direction: column; gap: 10px;">')
        html_parts.append('<h4 style="margin: 0 0 10px 0; color: #333;">Сертификат соответствия</h4>')
        
        # Сертификат (без подписей) - приоритет: uploaded > generated
        cert_image = obj.get_certificate_image(with_signatures=False)
        if cert_image:
            source_text = "📤 Загружен" if obj.uploaded_certificate else "🤖 Сгенерирован"
            html_parts.append(
                '<div style="border: 1px solid #ddd; padding: 10px; border-radius: 4px; background: #f9f9f9;">'
                '<strong style="color: #0073aa;">✓ Без подписей:</strong> <span style="font-size: 11px; color: #666;">({})</span><br>'
                '<a href="{}" target="_blank">'
                '<img src="{}" style="max-width: 150px; cursor: pointer; margin-top: 5px; border: 1px solid #ccc;" '
                'title="Нажмите для открытия в полном размере" onerror="this.style.display=\'none\'; this.nextSibling.style.display=\'block\';">'
                '</a>'
                '<span style="display:none; color: red;">Ошибка загрузки изображения</span><br>'
                '<a href="{}" download style="font-size: 11px; color: #0073aa;">⬇ Скачать</a>'
                '</div>'.format(
                    source_text,
                    cert_image.url,
                    cert_image.url,
                    cert_image.url
                )
            )
        else:
            html_parts.append('<div style="border: 1px solid #ddd; padding: 10px; border-radius: 4px; background: #fff3cd;">'
                            '<strong>⚠ Без подписей:</strong> Не сгенерирован. Загрузите файл ниже.</div>')
        
        # Сертификат (с подписями) - приоритет: uploaded > generated
        cert_signed_image = obj.get_certificate_image(with_signatures=True)
        if cert_signed_image:
            source_text = "📤 Загружен" if obj.uploaded_certificate_signed else "🤖 Сгенерирован"
            html_parts.append(
                '<div style="border: 1px solid #ddd; padding: 10px; border-radius: 4px; background: #f9f9f9;">'
                '<strong style="color: #0073aa;">✓ С подписями:</strong> <span style="font-size: 11px; color: #666;">({})</span><br>'
                '<a href="{}" target="_blank">'
                '<img src="{}" style="max-width: 150px; cursor: pointer; margin-top: 5px; border: 1px solid #ccc;" '
                'title="Нажмите для открытия в полном размере" onerror="this.style.display=\'none\'; this.nextSibling.style.display=\'block\';">'
                '</a>'
                '<span style="display:none; color: red;">Ошибка загрузки изображения</span><br>'
                '<a href="{}" download style="font-size: 11px; color: #0073aa;">⬇ Скачать</a>'
                '</div>'.format(
                    source_text,
                    cert_signed_image.url,
                    cert_signed_image.url,
                    cert_signed_image.url
                )
            )
        else:
            html_parts.append('<div style="border: 1px solid #ddd; padding: 10px; border-radius: 4px; background: #fff3cd;">'
                            '<strong>⚠ С подписями:</strong> Не сгенерирован. Загрузите файл ниже.</div>')
        
        html_parts.append('</div>')
        result_html = ''.join(html_parts)
        return format_html(result_html)
    certificates_preview.short_description = 'Сертификаты соответствия (просмотр)'
    
    def permissions_preview(self, obj):
        """Превью разрешений с возможностью замены загруженными файлами"""
        if not obj.pk:
            return "Сохраните сертификат для просмотра"
        
        html_parts = []
        html_parts.append('<div style="display: flex; flex-direction: column; gap: 10px;">')
        html_parts.append('<h4 style="margin: 0 0 10px 0; color: #333;">Разрешение на применение знака</h4>')
        
        # Разрешение (без подписей) - приоритет: uploaded > generated
        perm_image = obj.get_permission_image(with_signatures=False)
        if perm_image:
            source_text = "📤 Загружено" if obj.uploaded_permission else "🤖 Сгенерировано"
            html_parts.append(
                '<div style="border: 1px solid #ddd; padding: 10px; border-radius: 4px; background: #f0f8ff;">'
                '<strong style="color: #28a745;">✓ Без подписей:</strong> <span style="font-size: 11px; color: #666;">({})</span><br>'
                '<a href="{}" target="_blank">'
                '<img src="{}" style="max-width: 150px; cursor: pointer; margin-top: 5px; border: 1px solid #ccc;" '
                'title="Нажмите для открытия в полном размере" onerror="this.style.display=\'none\'; this.nextSibling.style.display=\'block\';">'
                '</a>'
                '<span style="display:none; color: red;">Ошибка загрузки изображения</span><br>'
                '<a href="{}" download style="font-size: 11px; color: #28a745;">⬇ Скачать</a>'
                '</div>'.format(
                    source_text,
                    perm_image.url,
                    perm_image.url,
                    perm_image.url
                )
            )
        else:
            html_parts.append('<div style="border: 1px solid #ddd; padding: 10px; border-radius: 4px; background: #fff3cd;">'
                            '<strong>⚠ Без подписей:</strong> Не сгенерировано. Загрузите файл ниже.</div>')
        
        # Разрешение (с подписями) - приоритет: uploaded > generated
        perm_signed_image = obj.get_permission_image(with_signatures=True)
        if perm_signed_image:
            source_text = "📤 Загружено" if obj.uploaded_permission_signed else "🤖 Сгенерировано"
            html_parts.append(
                '<div style="border: 1px solid #ddd; padding: 10px; border-radius: 4px; background: #f0f8ff;">'
                '<strong style="color: #28a745;">✓ С подписями:</strong> <span style="font-size: 11px; color: #666;">({})</span><br>'
                '<a href="{}" target="_blank">'
                '<img src="{}" style="max-width: 150px; cursor: pointer; margin-top: 5px; border: 1px solid #ccc;" '
                'title="Нажмите для открытия в полном размере" onerror="this.style.display=\'none\'; this.nextSibling.style.display=\'block\';">'
                '</a>'
                '<span style="display:none; color: red;">Ошибка загрузки изображения</span><br>'
                '<a href="{}" download style="font-size: 11px; color: #28a745;">⬇ Скачать</a>'
                '</div>'.format(
                    source_text,
                    perm_signed_image.url,
                    perm_signed_image.url,
                    perm_signed_image.url
                )
            )
        else:
            html_parts.append('<div style="border: 1px solid #ddd; padding: 10px; border-radius: 4px; background: #fff3cd;">'
                            '<strong>⚠ С подписями:</strong> Не сгенерировано. Загрузите файл ниже.</div>')
        
        html_parts.append('</div>')
        result_html = ''.join(html_parts)
        return format_html(result_html)
    permissions_preview.short_description = 'Разрешения на знак (просмотр)'
    
    def auditors_certificates_preview(self, obj):
        """Предпросмотр всех сертификатов аудиторов"""
        if not obj.pk:
            return "Сохраните сертификат для просмотра"
        
        auditors = obj.auditors.all()
        
        if not auditors:
            return "Нет аудиторов"
        
        result_html = '<div style="display: flex; flex-direction: column; gap: 15px;">'
        
        for auditor in auditors:
            result_html += format_html(
                '<div style="border: 2px solid #2b2b2b; padding: 15px; border-radius: 8px; background: #1a1a1a;">'
                '<h3 style="margin-top: 0; color: #4a9eff;">{}</h3>',
                auditor.full_name
            )
            
            # Сгенерированный аудит (без подписей)
            if auditor.generated_audit:
                result_html += format_html(
                    '<div style="margin-bottom: 10px;">'
                    '<strong style="color: #ccc;">Без подписей:</strong><br>'
                    '<a href="{}" target="_blank">'
                    '<img src="{}" style="max-width: 150px; cursor: pointer; margin-top: 5px; border: 1px solid #444;" title="Нажмите для открытия в полном размере">'
                    '</a><br>'
                    '<a href="{}" download style="font-size: 11px; color: #4a9eff;">Скачать</a>'
                    '</div>',
                    auditor.generated_audit.url,
                    auditor.generated_audit.url,
                    auditor.generated_audit.url
                )
            else:
                result_html += '<div style="margin-bottom: 10px; color: #888;">Без подписей: Не сгенерирован</div>'
            
            # Сгенерированный аудит (с подписями)
            if auditor.generated_audit_signed:
                result_html += format_html(
                    '<div>'
                    '<strong style="color: #ccc;">С подписями:</strong><br>'
                    '<a href="{}" target="_blank">'
                    '<img src="{}" style="max-width: 150px; cursor: pointer; margin-top: 5px; border: 1px solid #444;" title="Нажмите для открытия в полном размере">'
                    '</a><br>'
                    '<a href="{}" download style="font-size: 11px; color: #4a9eff;">Скачать</a>'
                    '</div>',
                    auditor.generated_audit_signed.url,
                    auditor.generated_audit_signed.url,
                    auditor.generated_audit_signed.url
                )
            else:
                result_html += '<div style="color: #888;">С подписями: Не сгенерирован</div>'
            
            result_html += '</div>'
        
        result_html += '</div>'
        return format_html(result_html)
    auditors_certificates_preview.short_description = 'Сертификаты аудиторов'

    actions = ['duplicate_certificates']

    class Media:
        js = ('certificates/js/preview.js',)

@admin.register(ISOStandard)
class ISOStandardAdmin(admin.ModelAdmin):
    list_display = ('standard_name', 'description', 'certificate_number_prefix')
    search_fields = ('standard_name', 'description')
    ordering = ('standard_name',)

class AuditorAdminForm(forms.ModelForm):
    clear_audit_file = forms.BooleanField(required=False, label='Очистить файл аудита')

    class Meta:
        model = Auditor
        fields = '__all__'

@admin.register(Auditor)
class AuditorAdmin(admin.ModelAdmin):
    form = AuditorAdminForm
    list_display = ('full_name', 'certificate', 'audit_number', 'audit_file_preview')
    list_filter = ('certificate__iso_standard', 'certificate__status')
    search_fields = ('full_name', 'certificate__name', 'certificate__certificate_number_part')
    readonly_fields = ('audit_file_preview_with_generated', 'audit_number')
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('certificate', 'full_name', 'audit_number')
        }),
        ('Файлы', {
            'fields': ('audit_file', 'audit_file_preview_with_generated', 
                      'uploaded_audit', 'uploaded_audit_signed',
                      'clear_audit_file')
        }),
    )

    def audit_file_preview(self, obj):
        """Предпросмотр файла аудита для списка"""
        return get_file_preview(obj.audit_file)
    audit_file_preview.short_description = 'Предпросмотр файла аудита'
    
    def audit_file_preview_with_generated(self, obj):
        """Предпросмотр файла аудита с возможностью замены загруженными файлами"""
        if not obj.pk:
            return "Сохраните аудитора для просмотра файлов"
        
        result_html = '<div style="display: flex; flex-direction: column; gap: 10px;">'
        
        # Аудит (без подписей) - приоритет: uploaded > generated
        audit_image = obj.get_audit_image(with_signatures=False)
        if audit_image:
            source_text = "📤 Загружен" if obj.uploaded_audit else "🤖 Сгенерирован"
            result_html += format_html(
                '<div style="border: 1px solid #ddd; padding: 10px; border-radius: 4px;">'
                '<strong>Без подписей:</strong> <span style="font-size: 11px; color: #666;">({})</span><br>'
                '<a href="{}" target="_blank">'
                '<img src="{}" style="max-width: 150px; cursor: pointer; margin-top: 5px;" title="Нажмите для открытия в полном размере">'
                '</a><br>'
                '<a href="{}" download style="font-size: 11px;">Скачать</a>'
                '</div>',
                source_text,
                audit_image.url,
                audit_image.url,
                audit_image.url
            )
        else:
            result_html += '<div style="border: 1px solid #ddd; padding: 10px; border-radius: 4px;">Без подписей: Не сгенерирован. Загрузите файл ниже.</div>'
        
        # Аудит (с подписями) - приоритет: uploaded > generated
        audit_signed_image = obj.get_audit_image(with_signatures=True)
        if audit_signed_image:
            source_text = "📤 Загружен" if obj.uploaded_audit_signed else "🤖 Сгенерирован"
            result_html += format_html(
                '<div style="border: 1px solid #ddd; padding: 10px; border-radius: 4px;">'
                '<strong>С подписями:</strong> <span style="font-size: 11px; color: #666;">({})</span><br>'
                '<a href="{}" target="_blank">'
                '<img src="{}" style="max-width: 150px; cursor: pointer; margin-top: 5px;" title="Нажмите для открытия в полном размере">'
                '</a><br>'
                '<a href="{}" download style="font-size: 11px;">Скачать</a>'
                '</div>',
                source_text,
                audit_signed_image.url,
                audit_signed_image.url,
                audit_signed_image.url
            )
        else:
            result_html += '<div style="border: 1px solid #ddd; padding: 10px; border-radius: 4px;">С подписями: Не сгенерирован. Загрузите файл ниже.</div>'
        
        result_html += '</div>'
        return format_html(result_html)
    audit_file_preview_with_generated.short_description = 'Предпросмотр'

    def save_model(self, request, obj, form, change):
        """Сохранение модели аудитора с обработкой очистки файлов"""
        # Обрабатываем очистку файлов
        if form.cleaned_data.get('clear_audit_file') and obj.audit_file:
            obj.audit_file.delete(save=False)
            obj.audit_file = None

        # Генерируем номер аудита если его нет
        if not obj.audit_number and obj.certificate:
            obj.audit_number = obj.certificate.generate_audit_number()

        super().save_model(request, obj, form, change)