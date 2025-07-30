from django.contrib import admin
from django.utils.html import format_html
from django.http import HttpResponse
from django.conf import settings
from .models import Certificate, ISOStandard, Auditor
from .utils import generate_certificate_image, generate_permission_image, generate_audit_image
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
    delete_file1 = forms.BooleanField(required=False, label='Удалить файл сертификата')
    delete_file1_psd = forms.BooleanField(required=False, label='Удалить файл сертификата (PSD)')
    delete_file2 = forms.BooleanField(required=False, label='Удалить файл разрешения')
    delete_file2_psd = forms.BooleanField(required=False, label='Удалить файл разрешения (PSD)')
    delete_file3 = forms.BooleanField(required=False, label='Удалить дополнительный файл')

    class Meta:
        model = Certificate
        fields = '__all__'

@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    form = CertificateAdminForm
    inlines = [AuditorInline]
    list_display = ('name', 'full_certificate_number', 'inn', 'iso_standard', 'iso_standard_name', 'status', 
                    'first_inspection_status', 'second_inspection_status', 'download_psd_link',
                    'start_date', 'expiry_date', 'notifications_enabled')
    list_filter = ('status', 'iso_standard', 'first_inspection_status', 'second_inspection_status', 'notifications_enabled')
    search_fields = ('name', 'certificate_number_part', 'inn')
    date_hierarchy = 'created_at'
    
    def download_psd_link(self, obj):
        if obj.file1_psd:
            return format_html('<a href="{}">Скачать PSD</a>', obj.file1_psd.url)
        return "Нет PSD"
    download_psd_link.short_description = "PSD файл"

    exclude = ('additional_files',)
    
    fieldsets = (
        ('Информация об организации', {
            'fields': ('name', 'inn', 'address')
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
                ('file1', 'file1_preview', 'file1_psd'),
                ('file2', 'file2_preview', 'file2_psd'),
                ('file3', 'file3_preview'),
                'qr_code'
            )
        }),
        ('Уведомления', {
            'fields': ('client_email', 'notifications_enabled')
        }),
    )
    
    readonly_fields = ('file1_preview', 'file2_preview', 'file3_preview', 'iso_standard_name', 'qr_code')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "iso_standard":
            kwargs["queryset"] = ISOStandard.objects.all().order_by('standard_name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        # Флаги для отслеживания, были ли файлы удалены
        file1_deleted = form.cleaned_data.get('delete_file1', False)
        file1_psd_deleted = form.cleaned_data.get('delete_file1_psd', False)
        file2_deleted = form.cleaned_data.get('delete_file2', False)
        file2_psd_deleted = form.cleaned_data.get('delete_file2_psd', False)
        file3_deleted = form.cleaned_data.get('delete_file3', False)
    
        # Удаляем файлы, если отмечены для удаления
        if file1_deleted and obj.file1:
            obj.file1.delete(save=False)
            obj.file1 = None
    
        if file1_psd_deleted and obj.file1_psd:
            obj.file1_psd.delete(save=False)
            obj.file1_psd = None
    
        if file2_deleted and obj.file2:
            obj.file2.delete(save=False)
            obj.file2 = None
    
        if file2_psd_deleted and obj.file2_psd:
            obj.file2_psd.delete(save=False)
            obj.file2_psd = None

        if file3_deleted and obj.file3:
            obj.file3.delete(save=False)
            obj.file3 = None
    
        # Сохраняем модель
        super().save_model(request, obj, form, change)
    
        # Генерируем документы только если они не были удалены и не были загружены пользователем
        self._generate_documents_if_needed(obj, form, file1_deleted, file1_psd_deleted, 
                                         file2_deleted, file2_psd_deleted)

    def _generate_documents_if_needed(self, obj, form, file1_deleted, file1_psd_deleted, 
                                    file2_deleted, file2_psd_deleted):
        """Генерирует документы только при необходимости"""
        
        # Генерируем сертификат (PNG)
        if not file1_deleted and not obj.file1 and 'file1' not in form.changed_data:
            self._generate_certificate(obj)
    
        # Генерируем сертификат (PSD)
        if not file1_psd_deleted and not obj.file1_psd and 'file1_psd' not in form.changed_data:
            self._generate_certificate_psd(obj)
    
        # Генерируем разрешение (PNG)
        if not file2_deleted and not obj.file2 and 'file2' not in form.changed_data:
            self._generate_permission(obj)
    
        # Генерируем разрешение (PSD)
        if not file2_psd_deleted and not obj.file2_psd and 'file2_psd' not in form.changed_data:
            self._generate_permission_psd(obj)
    
        obj.save()

    def _generate_certificate(self, obj):
        """Генерирует PNG сертификат"""
        try:
            certificate_images = generate_certificate_image(obj)
            if isinstance(certificate_images, dict):
                png_image = certificate_images.get('png')
                if png_image:
                    obj.file1.save(f'certificates/certificate_{obj.id}.png', png_image, save=False)
        except Exception as e:
            # Логируем ошибку, но не прерываем процесс
            print(f"Ошибка генерации сертификата PNG для {obj.id}: {e}")

    def _generate_certificate_psd(self, obj):
        """Генерирует PSD сертификат"""
        try:
            certificate_images = generate_certificate_image(obj)
            if isinstance(certificate_images, dict):
                psd_image = certificate_images.get('psd')
                if psd_image:
                    obj.file1_psd.save(f'certificates/certificate_{obj.id}.psd', psd_image, save=False)
        except Exception as e:
            print(f"Ошибка генерации сертификата PSD для {obj.id}: {e}")

    def _generate_permission(self, obj):
        """Генерирует PNG разрешение"""
        try:
            permission_images = generate_permission_image(obj)
            if isinstance(permission_images, dict):
                png_image = permission_images.get('png')
                if png_image:
                    obj.file2.save(f'permissions/permission_{obj.id}.png', png_image, save=False)
        except Exception as e:
            print(f"Ошибка генерации разрешения PNG для {obj.id}: {e}")

    def _generate_permission_psd(self, obj):
        """Генерирует PSD разрешение"""
        try:
            permission_images = generate_permission_image(obj)
            if isinstance(permission_images, dict):
                psd_image = permission_images.get('psd')
                if psd_image:
                    obj.file2_psd.save(f'permissions/permission_{obj.id}.psd', psd_image, save=False)
        except Exception as e:
            print(f"Ошибка генерации разрешения PSD для {obj.id}: {e}")

    def save_formset(self, request, form, formset, change):
        """Сохранение формсета аудиторов с генерацией файлов"""
        instances = formset.save(commit=False)
        
        for instance in instances:
            if not instance.pk:  # Новый аудитор
                instance.save()  # Сохраняем для получения ID
                
                # Генерируем номер аудита если его нет
                if not instance.audit_number:
                    instance.audit_number = form.instance.generate_audit_number()
                
                # Генерируем файлы аудита
                self._generate_audit_files(form.instance, instance)
            
            instance.save()
        
        # Удаляем отмеченные для удаления объекты
        for obj in formset.deleted_objects:
            obj.delete()
        
        formset.save_m2m()

    def _generate_audit_files(self, certificate, auditor):
        """Генерирует файлы аудита для аудитора"""
        try:
            if not auditor.audit_file or not auditor.audit_file_psd:
                audit_images = generate_audit_image(certificate, auditor, auditor.audit_number)
                if isinstance(audit_images, dict):
                    png_image = audit_images.get('png')
                    psd_image = audit_images.get('psd')
                    
                    if png_image and not auditor.audit_file:
                        auditor.audit_file.save(
                            f'audit_files/audit_{certificate.id}_{auditor.id}.png', 
                            png_image, 
                            save=False
                        )
                    
                    if psd_image and not auditor.audit_file_psd:
                        auditor.audit_file_psd.save(
                            f'audit_files/audit_{certificate.id}_{auditor.id}.psd', 
                            psd_image, 
                            save=False
                        )
        except Exception as e:
            print(f"Ошибка генерации файлов аудита для аудитора {auditor.id}: {e}")

    def download_psd(self, request, queryset):
        """Действие для скачивания PSD файлов"""
        if queryset.count() != 1:
            self.message_user(request, "Пожалуйста, выберите только один сертификат.")
            return
    
        certificate = queryset.first()
        if not certificate.file1_psd:
            self.message_user(request, "PSD файл не найден для этого сертификата.")
            return
            
        try:
            # Получаем содержимое PSD файла
            psd_content = certificate.file1_psd.read()
            
            # Создаем HTTP ответ для скачивания
            response = HttpResponse(psd_content, content_type='application/octet-stream')
            filename = os.path.basename(certificate.file1_psd.name)
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
            
        except Exception as e:
            self.message_user(request, f"Ошибка при скачивании PSD файла: {e}")
    
    download_psd.short_description = "Скачать PSD файл"

    
    def get_urls(self):
        """Добавляем URL для регенерации QR-кода"""
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:object_id>/regenerate-qr/',
                self.admin_site.admin_view(self.regenerate_qr_view),
                name='certificates_certificate_regenerate_qr',
            ),
        ]
        return custom_urls + urls
    
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

    def file1_preview(self, obj):
        """Предпросмотр файла сертификата"""
        return get_file_preview(obj.file1)
    file1_preview.short_description = 'Предпросмотр'
    
    def file2_preview(self, obj):
        """Предпросмотр файла разрешения"""
        return get_file_preview(obj.file2)
    file2_preview.short_description = 'Предпросмотр'
    
    def file3_preview(self, obj):
        """Предпросмотр дополнительного файла"""
        return get_file_preview(obj.file3)
    file3_preview.short_description = 'Предпросмотр'

    actions = ['download_psd']

    class Media:
        js = ('certificates/js/preview.js',)

@admin.register(ISOStandard)
class ISOStandardAdmin(admin.ModelAdmin):
    list_display = ('standard_name', 'description', 'certificate_number_prefix')
    search_fields = ('standard_name', 'description')
    ordering = ('standard_name',)

class AuditorAdminForm(forms.ModelForm):
    clear_audit_file = forms.BooleanField(required=False, label='Очистить файл аудита')
    clear_audit_file_psd = forms.BooleanField(required=False, label='Очистить файл аудита (PSD)')

    class Meta:
        model = Auditor
        fields = '__all__'

@admin.register(Auditor)
class AuditorAdmin(admin.ModelAdmin):
    form = AuditorAdminForm
    list_display = ('full_name', 'certificate', 'audit_number', 'audit_file_preview')
    list_filter = ('certificate__iso_standard', 'certificate__status')
    search_fields = ('full_name', 'certificate__name', 'certificate__certificate_number_part')
    readonly_fields = ('audit_file_preview', 'audit_number')
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('certificate', 'full_name', 'audit_number')
        }),
        ('Файлы аудита', {
            'fields': ('audit_file', 'audit_file_psd', 'audit_file_preview', 
                        'clear_audit_file', 'clear_audit_file_psd')
        }),
    )

    def audit_file_preview(self, obj):
        """Предпросмотр файла аудита"""
        return get_file_preview(obj.audit_file)
    audit_file_preview.short_description = 'Предпросмотр файла аудита'

    def save_model(self, request, obj, form, change):
        """Сохранение модели аудитора с обработкой очистки файлов"""
        # Обрабатываем очистку файлов
        if form.cleaned_data.get('clear_audit_file') and obj.audit_file:
            obj.audit_file.delete(save=False)
            obj.audit_file = None
            
        if form.cleaned_data.get('clear_audit_file_psd') and obj.audit_file_psd:
            obj.audit_file_psd.delete(save=False)
            obj.audit_file_psd = None

        # Генерируем номер аудита если его нет
        if not obj.audit_number and obj.certificate:
            obj.audit_number = obj.certificate.generate_audit_number()

        super().save_model(request, obj, form, change)

        # Генерируем файлы аудита если они отсутствуют
        if obj.certificate and (not obj.audit_file or not obj.audit_file_psd):
            self._generate_audit_files_for_auditor(obj)

    def _generate_audit_files_for_auditor(self, auditor):
        """Генерирует файлы аудита для конкретного аудитора"""
        try:
            audit_images = generate_audit_image(auditor.certificate, auditor, auditor.audit_number)
            if isinstance(audit_images, dict):
                png_image = audit_images.get('png')
                psd_image = audit_images.get('psd')
                
                if png_image and not auditor.audit_file:
                    auditor.audit_file.save(
                        f'audit_files/audit_{auditor.certificate.id}_{auditor.id}.png',
                        png_image,
                        save=False
                    )
                
                if psd_image and not auditor.audit_file_psd:
                    auditor.audit_file_psd.save(
                        f'audit_files/audit_{auditor.certificate.id}_{auditor.id}.psd',
                        psd_image,
                        save=False
                    )
                
                auditor.save()
                
        except Exception as e:
            print(f"Ошибка генерации файлов аудита для аудитора {auditor.id}: {e}")