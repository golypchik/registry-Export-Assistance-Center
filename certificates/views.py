from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, FileResponse
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Q
from django.urls import reverse
from django.contrib import messages
from django.core.files.base import ContentFile
from .models import Certificate, ISOStandard, Auditor
from .tasks import send_notifications_task
from .forms import CertificateForm, AuditorFormSet
from .utils import generate_certificate_image, generate_permission_image, generate_audit_image
from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404
import os
def delete_certificate(request, certificate_id):
    certificate = get_object_or_404(Certificate, id=certificate_id)
    
    if request.method == 'POST':
        certificate.delete()  # Используем метод delete модели, который уже обрабатывает удаление файлов
        messages.success(request, 'Сертификат успешно удален.')
        return redirect('admin_certificates')
    
    return render(request, 'certificates/admin/certificate_confirm_delete.html', {
        'certificate': certificate
    })

def generate_audit_preview(request, certificate_id, auditor_id):
    certificate = get_object_or_404(Certificate, id=certificate_id)
    auditor = get_object_or_404(Auditor, id=auditor_id, certificate=certificate)
    
    if not auditor.audit_number:
        iso_code = certificate.iso_standard.certificate_number_prefix
        auditor_index = list(certificate.auditors.all()).index(auditor) + 1
        auditor.audit_number = f"№AUD.{auditor_index:02d}.{iso_code}"
        auditor.save()

    image = generate_audit_image(certificate, auditor, auditor.audit_number)
    
    response = HttpResponse(content_type="image/png")
    image.save(response, "PNG")
    return response

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
        
        query = Q()
        
        if len(parts) == 3 and parts[0].upper() == 'SMK':
            query |= Q(certificate_number_part__iexact=parts[1])
        else:
            query |= Q(certificate_number_part__icontains=search_query)
        
        # Добавляем prefetch_related для загрузки связанных файлов
        certificates = Certificate.objects.filter(query).prefetch_related('auditors')
        
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

def certificate_detail(request, certificate_id):
    certificate = get_object_or_404(Certificate, id=certificate_id)
    
    # Обновляем статус сертификата
    current_status = certificate.calculate_status()
    if certificate.status != current_status:
        certificate.status = current_status
        certificate.save(update_fields=['status'])
    
    # Используем существующий шаблон search_results для отображения
    return render(request, 'certificates/search_results.html', {
        'certificates': [certificate],
        'search_query': certificate.certificate_number_part,
        'is_detail_view': True
    })

def trigger_notifications(request):
    send_notifications_task.delay()
    return HttpResponse("Notifications task triggered")


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
    """Скачивание файлов сертификата"""
    certificate = get_object_or_404(Certificate, id=certificate_id)
    
    file_field = None
    filename = None
    
    if file_num == 1 and certificate.file1:
        file_field = certificate.file1
        filename = f"certificate_{certificate.certificate_number_part}.{file_field.name.split('.')[-1]}"
    elif file_num == 2 and certificate.file2:
        file_field = certificate.file2
        filename = f"permission_{certificate.certificate_number_part}.{file_field.name.split('.')[-1]}"
    elif file_num == 3 and certificate.file3:
        file_field = certificate.file3
        filename = f"additional_{certificate.certificate_number_part}.{file_field.name.split('.')[-1]}"
    
    if not file_field:
        raise Http404("Файл не найден")
    
    try:
        with open(file_field.path, 'rb') as f:
            response = HttpResponse(f.read(), content_type='application/octet-stream')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
    except FileNotFoundError:
        raise Http404("Файл не найден на сервере")

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
        if file_field in ['file1', 'file2', 'file3']:
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