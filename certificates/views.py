from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, FileResponse, Http404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q
from django.urls import reverse
from django.contrib import messages
from django.core.files.base import ContentFile
from .models import Certificate, ISOStandard, Auditor
from .tasks import send_notifications_task
from .forms import CertificateForm, AuditorFormSet
import os
from django.conf import settings
from django.views.static import serve

def protected_media(request, path):
    """
    Обслуживание медиа файлов с контролем доступа
    """
    import os
    from django.http import Http404, FileResponse
    
    # Проверяем, что путь безопасен (предотвращаем directory traversal атаки)
    if '..' in path or path.startswith('/'):
        raise Http404("Недопустимый путь к файлу")
    
    # Полный путь к файлу
    file_path = os.path.join(settings.MEDIA_ROOT, path)
    
    # Проверяем, что файл существует и находится в MEDIA_ROOT
    if not os.path.exists(file_path) or not os.path.commonpath([settings.MEDIA_ROOT, file_path]) == settings.MEDIA_ROOT:
        raise Http404("Файл не найден")
    
    # Публичные файлы (сертификаты, QR-коды) - доступны всем
    public_paths = ['certificates/', 'qr_codes/', 'permissions/', 'audit_files/', 'audit_images/',
                    'generated_certificates/', 'generated_permissions/', 'generated_audits/']
    is_public = any(path.startswith(pub_path) for pub_path in public_paths)
    
    # Приватные файлы требуют авторизации
    if not is_public and not request.user.is_authenticated:
        from django.contrib.auth.views import redirect_to_login
        return redirect_to_login(request.get_full_path())
    
    try:
        # Получаем информацию о файле для оптимизации
        import mimetypes
        file_size = os.path.getsize(file_path)
        content_type = mimetypes.guess_type(file_path)[0] or 'application/octet-stream'
        
        # Используем FileResponse для лучшей производительности
        response = FileResponse(open(file_path, 'rb'), content_type=content_type)
        
        # Добавляем заголовки для кеширования публичных файлов
        if is_public:
            response['Cache-Control'] = 'public, max-age=2592000, immutable'  # 30 дней + immutable
            response['ETag'] = f'"{hash(path + str(os.path.getmtime(file_path)))}"'
            response['Expires'] = (timezone.now() + timedelta(days=30)).strftime('%a, %d %b %Y %H:%M:%S GMT')
        else:
            response['Cache-Control'] = 'private, max-age=3600'  # 1 час для приватных
            
        # Добавляем размер файла для лучшей производительности
        response['Content-Length'] = str(file_size)
        
        return response
    except (IOError, OSError):
        raise Http404("Ошибка при чтении файла")    
def delete_certificate(request, certificate_id):
    certificate = get_object_or_404(Certificate, id=certificate_id)
    
    if request.method == 'POST':
        certificate.delete()  # Используем метод delete модели, который уже обрабатывает удаление файлов
        messages.success(request, 'Сертификат успешно удален.')
        return redirect('admin_certificates')
    
    return render(request, 'certificates/admin/certificate_confirm_delete.html', {
        'certificate': certificate
    })

@login_required
def add_certificate(request):
    if request.method == 'POST':
        form = CertificateForm(request.POST, request.FILES)
        formset = AuditorFormSet(request.POST, request.FILES)
        
        if form.is_valid() and formset.is_valid():
            certificate = form.save()
            
            # Сохраняем аудиторов
            auditors = formset.save(commit=False)
            for auditor in auditors:
                auditor.certificate = certificate
                auditor.save()
            formset.save_m2m()
            
            messages.success(request, 'Сертификат успешно добавлен.')
            return redirect('admin_certificates')
    else:
        form = CertificateForm()
        formset = AuditorFormSet()
    
    return render(request, 'certificates/admin/certificate_form.html', {
        'form': form,
        'formset': formset,
        'title': 'Добавить сертификат'
    })

def index(request):
    return render(request, 'certificates/index.html')

def search_results(request):
    search_query = request.GET.get('search_query', '').strip()
    
    if search_query:
        if search_query.startswith('№'):
            search_query = search_query[1:]
        
        parts = search_query.split('.')
        
        # Проверяем правильный формат номера сертификата: SMK.XXXXX.ISO
        if len(parts) == 3 and parts[0].upper() == 'SMK':
            # Точный поиск по номеру сертификата из полного формата
            query = Q(certificate_number_part__iexact=parts[1])
        elif search_query.isdigit() and len(search_query) == 5:
            # Если введено ровно 5 цифр - точный поиск по номеру сертификата
            query = Q(certificate_number_part__iexact=search_query)
        else:
            # Любой другой запрос - ничего не ищем (убран поиск по ИНН/УНП)
            query = Q(pk__in=[])  # Пустой результат
        
        certificates = Certificate.objects.filter(query)
        
        for certificate in certificates:
            current_status = certificate.calculate_status()
            if certificate.status != current_status:
                certificate.status = current_status
                certificate.save(update_fields=['status'])
    else:
        certificates = Certificate.objects.none()
    
    return render(request, 'certificates/search_results.html', {
        'certificates': certificates,
        'search_query': search_query
    })

def trigger_notifications(request):
    send_notifications_task.delay()
    return HttpResponse("Notifications task triggered")

def certificate_detail(request, certificate_id):
    certificate = get_object_or_404(Certificate, id=certificate_id)
    
    # Обновляем статус сертификата
    current_status = certificate.calculate_status()
    if certificate.status != current_status:
        certificate.status = current_status
        certificate.save(update_fields=['status'])
    
    # Используем тот же шаблон, что и для результатов поиска
    context = {
        'certificates': [certificate],  # Передаем как список для совместимости с шаблоном
        'search_query': certificate.full_certificate_number,  # Показываем номер сертификата
    }
    return render(request, 'certificates/search_results.html', context)

def permission_detail(request, certificate_id):
    certificate = get_object_or_404(Certificate, id=certificate_id)
    context = {
        'certificate': certificate,
    }
    return render(request, 'certificates/permission_template.html', context)

def audit_detail(request, certificate_id, auditor_id):
    certificate = get_object_or_404(Certificate, id=certificate_id)
    auditor = get_object_or_404(Auditor, id=auditor_id, certificate=certificate)
    context = {
        'certificate': certificate,
        'auditor': auditor,
    }
    return render(request, 'certificates/audit_template.html', context)

def download_file(request, certificate_id, file_num):
    certificate = get_object_or_404(Certificate, id=certificate_id)
    
    file_mapping = {
        1: certificate.file1,
        2: certificate.file2,
        3: certificate.auditor_certificate
    }
    
    file = file_mapping.get(file_num)
    if not file:
        return HttpResponse("Файл не найден", status=404)
    
    response = FileResponse(file.open(), as_attachment=True, filename=file.name.split('/')[-1])
    return response

@login_required
def admin_certificates(request):
    certificates = Certificate.objects.all().order_by('-created_at')
    
    for certificate in certificates:
        current_status = certificate.calculate_status()
        if certificate.status != current_status:
            certificate.status = current_status
            certificate.save(update_fields=['status'])
    
    return render(request, 'certificates/admin/certificate_list.html', {
        'certificates': certificates
    })

@login_required
def manage_inspections(request, certificate_id):
    certificate = get_object_or_404(Certificate, id=certificate_id)
    
    if request.method == 'POST':
        for inspection in ['first', 'second']:
            status_key = f'{inspection}_inspection_status'
            if status_key in request.POST:
                setattr(certificate, status_key, request.POST.get(status_key))
                if getattr(certificate, status_key) == 'passed':
                    setattr(certificate, f'{inspection}_inspection_date', timezone.now().date())
        
        certificate.status = certificate.calculate_status()
        certificate.save()
        
        messages.success(request, 'Инспекционные контроли обновлены.')
        return redirect('admin_certificates')
    
    return render(request, 'certificates/admin/manage_inspections.html', {
        'certificate': certificate
    })

@login_required
def certificate_statistics(request):
    total_certificates = Certificate.objects.count()
    
    status_counts = {
        'active': Certificate.objects.filter(status='active').count(),
        'inspection_failed': Certificate.objects.filter(status='inspection_failed').count(),
        'expired': Certificate.objects.filter(status='expired').count(),
        'revoked': Certificate.objects.filter(status='revoked').count(),
        'pending': Certificate.objects.filter(status='pending').count(),
    }
    
    inspection_counts = {
        'first': {status: Certificate.objects.filter(first_inspection_status=status).count() for status in ['passed', 'failed', 'pending']},
        'second': {status: Certificate.objects.filter(second_inspection_status=status).count() for status in ['passed', 'failed', 'pending']},
    }
    
    iso_stats = {iso.standard_name: Certificate.objects.filter(iso_standard=iso).count() for iso in ISOStandard.objects.all()}
    
    context = {
        'total_certificates': total_certificates,
        'status_counts': status_counts,
        'inspection_counts': inspection_counts,
        'iso_stats': iso_stats,
    }
    
    return render(request, 'certificates/admin/statistics.html', context)

@login_required
def edit_certificate(request, certificate_id=None):
    if certificate_id:
        certificate = get_object_or_404(Certificate, id=certificate_id)
        title = 'Редактировать сертификат'
    else:
        certificate = None
        title = 'Добавить сертификат'

    if request.method == 'POST':
        form = CertificateForm(request.POST, request.FILES, instance=certificate)
        formset = AuditorFormSet(request.POST, request.FILES, instance=certificate)
        
        if form.is_valid() and formset.is_valid():
            certificate = form.save()
            
            # Обработка аудиторов
            auditors = formset.save(commit=False)
            for auditor in auditors:
                if not auditor.pk:  # Если это новый аудитор
                    auditor.certificate = certificate
                auditor.save()
            
            # Удаление аудиторов, отмеченных для удаления
            for obj in formset.deleted_objects:
                obj.delete()
            
            formset.save_m2m()
            
            if certificate_id:
                messages.success(request, 'Сертификат успешно обновлен.')
            else:
                messages.success(request, 'Сертификат успешно добавлен.')
            
            return redirect('admin_certificates')
    else:
        form = CertificateForm(instance=certificate)
        formset = AuditorFormSet(instance=certificate)

    # Получаем предпросмотры для аудиторов
    audit_previews = []
    if certificate:
        for auditor in certificate.auditors.all():
            if auditor.audit_file:
                audit_previews.append({
                    'auditor': auditor,
                    'preview_url': reverse('generate_audit_preview', args=[certificate.id, auditor.id])
                })

    return render(request, 'certificates/admin/certificate_form.html', {
        'form': form,
        'formset': formset,
        'certificate': certificate,
        'title': title,
        'audit_previews': audit_previews,
    })

@login_required
def delete_certificate_file(request, certificate_id):
    certificate = get_object_or_404(Certificate, id=certificate_id)
    if request.method == 'POST':
        file_field = request.POST.get('file_field')
        if file_field in ['file1', 'file2', 'auditor_certificate']:
            file_obj = getattr(certificate, file_field)
            if file_obj:
                file_obj.delete()
                setattr(certificate, file_field, None)
                certificate.save()
                messages.success(request, f'Файл {file_field} успешно удален.')
        return redirect('edit_certificate', certificate_id=certificate.id)
    
    return render(request, 'certificates/admin/delete_certificate_file.html', {
        'certificate': certificate
    })