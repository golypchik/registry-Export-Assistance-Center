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
from django.shortcuts import render, get_object_or_404
from django.http import Http404
from .models import Certificate
import logging

logger = logging.getLogger(__name__)

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
    certificates = []
    
    if search_query:
        try:
            # Расширенный поиск по нескольким полям
            certificates = Certificate.objects.filter(
                Q(certificate_number_part__icontains=search_query) |
                Q(name__icontains=search_query) |
                Q(inn__icontains=search_query) |
                Q(full_certificate_number__icontains=search_query)
            ).select_related('iso_standard').prefetch_related('auditors').distinct()
            
            # Обновляем статусы найденных сертификатов
            for certificate in certificates:
                current_status = certificate.calculate_status()
                if certificate.status != current_status:
                    certificate.status = current_status
                    certificate.save(update_fields=['status'])
                    
        except Exception as e:
            logger.error(f"Ошибка при поиске сертификатов: {e}")
            certificates = []
    
    return render(request, 'certificates/search_results.html', {
        'certificates': certificates,
        'search_query': search_query
    })

def certificate_detail(request, certificate_id):
    try:
        certificate = get_object_or_404(Certificate, id=certificate_id)
        
        # Обновляем статус сертификата
        current_status = certificate.calculate_status()
        if certificate.status != current_status:
            certificate.status = current_status
            certificate.save(update_fields=['status'])
        
        return render(request, 'certificates/search_results.html', {
            'certificates': [certificate],
            'search_query': certificate.certificate_number_part,
            'is_detail_view': True
        })
    except Exception as e:
        logger.error(f"Ошибка при получении сертификата {certificate_id}: {e}")
        raise Http404("Сертификат не найден")

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
    certificate = get_object_or_404(Certificate, id=certificate_id)
    
    file_mapping = {
        1: certificate.file1,
        2: certificate.file2,
        3: certificate.file3
    }
    
    file = file_mapping.get(file_num)
    if not file:
        return HttpResponse("Файл не найден", status=404)
    
    try:
        response = FileResponse(file.open(), as_attachment=True, filename=file.name.split('/')[-1])
        return response
    except Exception as e:
        logger.error(f"Ошибка при скачивании файла: {e}")
        return HttpResponse("Ошибка при скачивании файла", status=500)

def download_auditor_file(request, certificate_id, auditor_id, file_type):
    """Скачивание файлов аудитора"""
    certificate = get_object_or_404(Certificate, id=certificate_id)
    auditor = get_object_or_404(Auditor, id=auditor_id, certificate=certificate)
    
    file_mapping = {
        'audit_file1': auditor.audit_file1,
        'audit_file2': auditor.audit_file2,
        'audit_file3': auditor.audit_file3,
        'audit_image1': auditor.audit_image1,
        'audit_image2': auditor.audit_image2,
        'audit_image3': auditor.audit_image3,
    }
    
    file = file_mapping.get(file_type)
    if not file:
        return HttpResponse("Файл не найден", status=404)
    
    try:
        response = FileResponse(file.open(), as_attachment=True, filename=file.name.split('/')[-1])
        return response
    except Exception as e:
        logger.error(f"Ошибка при скачивании файла аудитора: {e}")
        return HttpResponse("Ошибка при скачивании файла", status=500)

@login_required
def admin_certificates(request):
    # Получаем параметры фильтрации и поиска
    search_query = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status', '')
    iso_filter = request.GET.get('iso_standard', '')
    
    # Базовый queryset
    certificates = Certificate.objects.select_related('iso_standard').prefetch_related('auditors')
    
    # Применяем поиск
    if search_query:
        certificates = certificates.filter(
            Q(certificate_number_part__icontains=search_query) |
            Q(name__icontains=search_query) |
            Q(inn__icontains=search_query) |
            Q(full_certificate_number__icontains=search_query)
        )
    
    # Применяем фильтр по статусу
    if status_filter:
        certificates = certificates.filter(status=status_filter)
    
    # Применяем фильтр по ISO стандарту
    if iso_filter:
        certificates = certificates.filter(iso_standard_id=iso_filter)
    
    # Сортировка
    certificates = certificates.order_by('-created_at')
    
    # Обновляем статусы сертификатов
    for certificate in certificates:
        current_status = certificate.calculate_status()
        if certificate.status != current_status:
            certificate.status = current_status
            certificate.save(update_fields=['status'])
    
    # Получаем данные для фильтров
    iso_standards = ISOStandard.objects.all().order_by('standard_name')
    status_choices = Certificate.STATUS_CHOICES
    
    context = {
        'certificates': certificates,
        'iso_standards': iso_standards,
        'status_choices': status_choices,
        'current_search': search_query,
        'current_status': status_filter,
        'current_iso': iso_filter,
    }
    
    return render(request, 'certificates/admin/certificate_list.html', context)

@login_required
def manage_inspections(request, certificate_id):
    certificate = get_object_or_404(Certificate, id=certificate_id)
    
    if request.method == 'POST':
        for inspection in ['first', 'second']:
            status_key = f'{inspection}_inspection_status'
            date_key = f'{inspection}_inspection_date'
            
            if status_key in request.POST:
                new_status = request.POST.get(status_key)
                setattr(certificate, status_key, new_status)
                
                # Если статус изменился на "пройден", устанавливаем текущую дату
                if new_status == 'passed' and date_key in request.POST:
                    date_value = request.POST.get(date_key)
                    if date_value:
                        setattr(certificate, date_key, date_value)
                    else:
                        setattr(certificate, date_key, timezone.now().date())
        
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
    
    # Статистика по ISO стандартам
    iso_stats = {}
    for iso_standard in ISOStandard.objects.all():
        iso_stats[iso_standard.standard_name] = Certificate.objects.filter(iso_standard=iso_standard).count()
    
    # Статистика по инспекционным контролям
    inspection_stats = {
        'first_passed': Certificate.objects.filter(first_inspection_status='passed').count(),
        'first_failed': Certificate.objects.filter(first_inspection_status='failed').count(),
        'first_pending': Certificate.objects.filter(first_inspection_status='pending').count(),
        'second_passed': Certificate.objects.filter(second_inspection_status='passed').count(),
        'second_failed': Certificate.objects.filter(second_inspection_status='failed').count(),
        'second_pending': Certificate.objects.filter(second_inspection_status='pending').count(),
    }
    
    # Статистика по месяцам (последние 12 месяцев)
    from django.utils import timezone
    from datetime import datetime, timedelta
    import calendar
    
    monthly_stats = []
    current_date = timezone.now().date()
    
    for i in range(12):
        month_start = current_date.replace(day=1) - timedelta(days=i*30)
        month_start = month_start.replace(day=1)
        if month_start.month == 12:
            month_end = month_start.replace(year=month_start.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            month_end = month_start.replace(month=month_start.month + 1, day=1) - timedelta(days=1)
        
        count = Certificate.objects.filter(
            created_at__date__gte=month_start,
            created_at__date__lte=month_end
        ).count()
        
        monthly_stats.append({
            'month': calendar.month_name[month_start.month],
            'year': month_start.year,
            'count': count
        })
    
    monthly_stats.reverse()  # Показываем от старых к новым
    
    context = {
        'total_certificates': total_certificates,
        'status_counts': status_counts,
        'iso_stats': iso_stats,
        'inspection_stats': inspection_stats,
        'monthly_stats': monthly_stats,
    }
    
    return render(request, 'certificates/admin/statistics.html', context)

@login_required
def edit_certificate(request, certificate_id):
    certificate = get_object_or_404(Certificate, id=certificate_id)
    
    if request.method == 'POST':
        form = CertificateForm(request.POST, request.FILES, instance=certificate)
        formset = AuditorFormSet(request.POST, request.FILES, instance=certificate)
        
        if form.is_valid() and formset.is_valid():
            certificate = form.save()
            
            # Сохраняем аудиторов
            auditors = formset.save(commit=False)
            for auditor in auditors:
                auditor.certificate = certificate
                auditor.save()
            
            # Удаляем аудиторов, которые были помечены для удаления
            for auditor in formset.deleted_objects:
                auditor.delete()
            
            formset.save_m2m()
            
            messages.success(request, 'Сертификат успешно обновлен.')
            return redirect('admin_certificates')
    else:
        form = CertificateForm(instance=certificate)
        formset = AuditorFormSet(instance=certificate)
    
    return render(request, 'certificates/admin/certificate_form.html', {
        'form': form,
        'formset': formset,
        'certificate': certificate,
        'title': 'Редактировать сертификат'
    })

def generate_certificate_preview(request, certificate_id):
    certificate = get_object_or_404(Certificate, id=certificate_id)
    
    # Генерируем изображение сертификата
    image = generate_certificate_image(certificate)
    
    response = HttpResponse(content_type="image/png")
    image.save(response, "PNG")
    return response

def generate_permission_preview(request, certificate_id):
    certificate = get_object_or_404(Certificate, id=certificate_id)
    
    # Генерируем изображение разрешения
    image = generate_permission_image(certificate)
    
    response = HttpResponse(content_type="image/png")
    image.save(response, "PNG")
    return response

@login_required
def bulk_update_statuses(request):
    """Массовое обновление статусов сертификатов"""
    if request.method == 'POST':
        updated_count = 0
        certificates = Certificate.objects.all()
        
        for certificate in certificates:
            old_status = certificate.status
            new_status = certificate.calculate_status()
            
            if old_status != new_status:
                certificate.status = new_status
                certificate.save(update_fields=['status'])
                updated_count += 1
        
        messages.success(request, f'Обновлено статусов: {updated_count} из {certificates.count()}')
        return redirect('admin_certificates')
    
    return render(request, 'certificates/admin/bulk_update_confirm.html')

@login_required
def export_certificates(request):
    """Экспорт сертификатов в Excel"""
    import pandas as pd
    from django.http import HttpResponse
    from io import BytesIO
    
    # Получаем все сертификаты
    certificates = Certificate.objects.select_related('iso_standard').all()
    
    # Подготавливаем данные для экспорта
    data = []
    for cert in certificates:
        data.append({
            'Номер сертификата': cert.full_certificate_number,
            'Наименование организации': cert.name,
            'ИНН': cert.inn,
            'Стандарт': cert.iso_standard.standard_name if cert.iso_standard else '',
            'Статус': cert.get_status_display(),
            'Дата начала': cert.start_date.strftime('%d.%m.%Y') if cert.start_date else '',
            'Дата окончания': cert.expiry_date.strftime('%d.%m.%Y') if cert.expiry_date else '',
            'Первый контроль': cert.get_first_inspection_status_display(),
            'Дата первого контроля': cert.first_inspection_date.strftime('%d.%m.%Y') if cert.first_inspection_date else '',
            'Второй контроль': cert.get_second_inspection_status_display(),
            'Дата второго контроля': cert.second_inspection_date.strftime('%d.%m.%Y') if cert.second_inspection_date else '',
            'Дата создания': cert.created_at.strftime('%d.%m.%Y %H:%M') if cert.created_at else '',
        })
    
    # Создаем DataFrame
    df = pd.DataFrame(data)
    
    # Создаем Excel файл в памяти
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Сертификаты', index=False)
    
    output.seek(0)
    
    # Возвращаем файл
    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="certificates_export.xlsx"'
    
    return response

def qr_redirect(request, certificate_id):
    """Перенаправление по QR коду"""
    try:
        certificate = get_object_or_404(Certificate, id=certificate_id)
        return redirect('certificate_detail', certificate_id=certificate.id)
    except Exception as e:
        logger.error(f"Ошибка при переходе по QR коду: {e}")
        return redirect('index')

@login_required
def certificate_history(request, certificate_id):
    """История изменений сертификата"""
    certificate = get_object_or_404(Certificate, id=certificate_id)
    
    # Здесь можно добавить логику для отслеживания истории изменений
    # Например, используя django-simple-history или создав собственную модель для логирования
    
    context = {
        'certificate': certificate,
        # 'history': certificate.history.all() if hasattr(certificate, 'history') else []
    }
    
    return render(request, 'certificates/admin/certificate_history.html', context)

def api_certificate_status(request, certificate_id):
    """API для получения статуса сертификата"""
    try:
        certificate = get_object_or_404(Certificate, id=certificate_id)
        
        # Обновляем статус
        current_status = certificate.calculate_status()
        if certificate.status != current_status:
            certificate.status = current_status
            certificate.save(update_fields=['status'])
        
        data = {
            'id': certificate.id,
            'certificate_number': certificate.full_certificate_number,
            'name': certificate.name,
            'inn': certificate.inn,
            'status': certificate.status,
            'status_display': certificate.get_status_display(),
            'start_date': certificate.start_date.isoformat() if certificate.start_date else None,
            'expiry_date': certificate.expiry_date.isoformat() if certificate.expiry_date else None,
            'iso_standard': certificate.iso_standard.standard_name if certificate.iso_standard else None,
        }
        
        return JsonResponse(data)
        
    except Exception as e:
        logger.error(f"Ошибка в API получения статуса сертификата: {e}")
        return JsonResponse({'error': 'Сертификат не найден'}, status=404)

from django.http import JsonResponse

def api_search_certificates(request):
    """API для поиска сертификатов"""
    search_query = request.GET.get('q', '').strip()
    
    if not search_query:
        return JsonResponse({'certificates': []})
    
    try:
        certificates = Certificate.objects.filter(
            Q(certificate_number_part__icontains=search_query) |
            Q(name__icontains=search_query) |
            Q(inn__icontains=search_query) |
            Q(full_certificate_number__icontains=search_query)
        ).select_related('iso_standard')[:10]  # Ограничиваем результат
        
        data = []
        for cert in certificates:
            data.append({
                'id': cert.id,
                'certificate_number': cert.full_certificate_number,
                'name': cert.name,
                'inn': cert.inn,
                'status': cert.get_status_display(),
                'iso_standard': cert.iso_standard.standard_name if cert.iso_standard else '',
            })
        
        return JsonResponse({'certificates': data})
        
    except Exception as e:
        logger.error(f"Ошибка в API поиска сертификатов: {e}")
        return JsonResponse({'error': 'Ошибка поиска'}, status=500)


def api_certificate_autocomplete(request):
    """API для автодополнения при поиске сертификатов"""
    search_query = request.GET.get('term', '').strip()
    
    if not search_query or len(search_query) < 2:
        return JsonResponse({'suggestions': []})
    
    try:
        # Поиск по различным полям с ограничением результатов
        certificates = Certificate.objects.filter(
            Q(certificate_number_part__icontains=search_query) |
            Q(name__icontains=search_query) |
            Q(inn__icontains=search_query) |
            Q(full_certificate_number__icontains=search_query)
        ).select_related('iso_standard')[:5]
        
        suggestions = []
        for cert in certificates:
            suggestions.append({
                'label': f"{cert.full_certificate_number} - {cert.name}",
                'value': cert.full_certificate_number,
                'id': cert.id,
                'name': cert.name,
                'inn': cert.inn,
                'status': cert.get_status_display()
            })
        
        return JsonResponse({'suggestions': suggestions})
        
    except Exception as e:
        logger.error(f"Ошибка в API автодополнения: {e}")
        return JsonResponse({'suggestions': []})

@login_required
def certificate_notifications(request):
    """Управление уведомлениями для сертификатов"""
    from datetime import datetime, timedelta
    
    # Сертификаты, которые скоро истекают (в течение 30 дней)
    expiring_soon = Certificate.objects.filter(
        expiry_date__lte=timezone.now().date() + timedelta(days=30),
        expiry_date__gte=timezone.now().date(),
        status='active'
    ).select_related('iso_standard')
    
    # Сертификаты с просроченными инспекциями
    overdue_inspections = Certificate.objects.filter(
        Q(first_inspection_status='pending', first_inspection_date__lt=timezone.now().date()) |
        Q(second_inspection_status='pending', second_inspection_date__lt=timezone.now().date())
    ).select_related('iso_standard')
    
    # Истекшие сертификаты
    expired_certificates = Certificate.objects.filter(
        expiry_date__lt=timezone.now().date(),
        status__in=['active', 'pending']
    ).select_related('iso_standard')
    
    context = {
        'expiring_soon': expiring_soon,
        'overdue_inspections': overdue_inspections,
        'expired_certificates': expired_certificates,
    }
    
    return render(request, 'certificates/admin/notifications.html', context)

@login_required
def send_manual_notification(request, certificate_id):
    """Отправка уведомления вручную для конкретного сертификата"""
    certificate = get_object_or_404(Certificate, id=certificate_id)
    
    if request.method == 'POST':
        notification_type = request.POST.get('notification_type')
        
        try:
            # Здесь можно добавить логику отправки уведомлений
            # Например, через Celery task
            from .tasks import send_single_notification_task
            send_single_notification_task.delay(certificate.id, notification_type)
            
            messages.success(request, f'Уведомление отправлено для сертификата {certificate.full_certificate_number}')
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления: {e}")
            messages.error(request, 'Ошибка при отправке уведомления')
        
        return redirect('certificate_notifications')
    
    return render(request, 'certificates/admin/send_notification.html', {
        'certificate': certificate
    })

@login_required
def certificate_reports(request):
    """Генерация отчетов по сертификатам"""
    from datetime import datetime, timedelta
    from django.db.models import Count
    
    # Отчет по статусам
    status_report = Certificate.objects.values('status').annotate(
        count=Count('id')
    ).order_by('status')
    
    # Отчет по ISO стандартам
    iso_report = Certificate.objects.values(
        'iso_standard__standard_name'
    ).annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Отчет по месяцам создания (последние 12 месяцев)
    monthly_report = []
    current_date = timezone.now().date()
    
    for i in range(12):
        month_start = current_date.replace(day=1) - timedelta(days=i*30)
        month_start = month_start.replace(day=1)
        
        if month_start.month == 12:
            month_end = month_start.replace(year=month_start.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            month_end = month_start.replace(month=month_start.month + 1, day=1) - timedelta(days=1)
        
        count = Certificate.objects.filter(
            created_at__date__gte=month_start,
            created_at__date__lte=month_end
        ).count()
        
        monthly_report.append({
            'month': month_start.strftime('%B %Y'),
            'count': count,
            'month_start': month_start,
            'month_end': month_end
        })
    
    monthly_report.reverse()
    
    # Отчет по инспекциям
    inspection_report = {
        'first_passed': Certificate.objects.filter(first_inspection_status='passed').count(),
        'first_failed': Certificate.objects.filter(first_inspection_status='failed').count(),
        'first_pending': Certificate.objects.filter(first_inspection_status='pending').count(),
        'second_passed': Certificate.objects.filter(second_inspection_status='passed').count(),
        'second_failed': Certificate.objects.filter(second_inspection_status='failed').count(),
        'second_pending': Certificate.objects.filter(second_inspection_status='pending').count(),
    }
    
    context = {
        'status_report': status_report,
        'iso_report': iso_report,
        'monthly_report': monthly_report,
        'inspection_report': inspection_report,
        'total_certificates': Certificate.objects.count(),
    }
    
    return render(request, 'certificates/admin/reports.html', context)

@login_required
def import_certificates(request):
    """Импорт сертификатов из Excel файла"""
    if request.method == 'POST' and request.FILES.get('excel_file'):
        try:
            import pandas as pd
            excel_file = request.FILES['excel_file']
            
            # Читаем Excel файл
            df = pd.read_excel(excel_file)
            
            imported_count = 0
            error_count = 0
            errors = []
            
            for index, row in df.iterrows():
                try:
                    # Проверяем обязательные поля
                    if pd.isna(row.get('certificate_number_part')) or pd.isna(row.get('name')):
                        errors.append(f"Строка {index + 2}: отсутствуют обязательные поля")
                        error_count += 1
                        continue
                    
                    # Создаем или обновляем сертификат
                    certificate, created = Certificate.objects.get_or_create(
                        certificate_number_part=str(row['certificate_number_part']).strip(),
                        defaults={
                            'name': str(row['name']).strip(),
                            'inn': str(row.get('inn', '')).strip(),
                            'start_date': pd.to_datetime(row.get('start_date')).date() if not pd.isna(row.get('start_date')) else None,
                            'expiry_date': pd.to_datetime(row.get('expiry_date')).date() if not pd.isna(row.get('expiry_date')) else None,
                            'status': str(row.get('status', 'pending')).strip(),
                        }
                    )
                    
                    if created:
                        imported_count += 1
                    
                except Exception as e:
                    errors.append(f"Строка {index + 2}: {str(e)}")
                    error_count += 1
            
            if imported_count > 0:
                messages.success(request, f'Импортировано {imported_count} сертификатов')
            
            if error_count > 0:
                messages.warning(request, f'Ошибок при импорте: {error_count}')
                for error in errors[:10]:  # Показываем только первые 10 ошибок
                    messages.error(request, error)
            
        except Exception as e:
            logger.error(f"Ошибка при импорте сертификатов: {e}")
            messages.error(request, f'Ошибка при импорте: {str(e)}')
        
        return redirect('admin_certificates')
    
    return render(request, 'certificates/admin/import_certificates.html')

def health_check(request):
    """Проверка состояния системы"""
    try:
        # Проверяем подключение к базе данных
        Certificate.objects.count()
        
        # Проверяем Celery (если используется)
        from django.core.cache import cache
        cache.set('health_check', 'ok', 10)
        cache_status = cache.get('health_check') == 'ok'
        
        status = {
            'database': 'ok',
            'cache': 'ok' if cache_status else 'error',
            'timestamp': timezone.now().isoformat(),
        }
        
        return JsonResponse(status)
        
    except Exception as e:
        logger.error(f"Ошибка при проверке состояния: {e}")
        return JsonResponse({
            'database': 'error',
            'error': str(e),
            'timestamp': timezone.now().isoformat(),
        }, status=500)

@login_required
def certificate_backup(request):
    """Создание резервной копии сертификатов"""
    if request.method == 'POST':
        try:
            import json
            from django.core import serializers
            
            # Сериализуем все сертификаты
            certificates_data = serializers.serialize('json', Certificate.objects.all())
            iso_standards_data = serializers.serialize('json', ISOStandard.objects.all())
            auditors_data = serializers.serialize('json', Auditor.objects.all())
            
            backup_data = {
                'certificates': json.loads(certificates_data),
                'iso_standards': json.loads(iso_standards_data),
                'auditors': json.loads(auditors_data),
                'backup_date': timezone.now().isoformat(),
            }
            
            # Создаем JSON файл
            response = HttpResponse(
                json.dumps(backup_data, ensure_ascii=False, indent=2),
                content_type='application/json'
            )
            response['Content-Disposition'] = f'attachment; filename="certificates_backup_{timezone.now().strftime("%Y%m%d_%H%M%S")}.json"'
            
            return response
            
        except Exception as e:
            logger.error(f"Ошибка при создании резервной копии: {e}")
            
            messages.error(request, f'Ошибка при создании резервной копии: {str(e)}')
            return redirect('admin_certificates')
    
    return render(request, 'certificates/admin/backup.html')

@login_required
def certificate_restore(request):
    """Восстановление сертификатов из резервной копии"""
    if request.method == 'POST' and request.FILES.get('backup_file'):
        try:
            import json
            from django.core import serializers
            
            backup_file = request.FILES['backup_file']
            backup_data = json.load(backup_file)
            
            restored_count = 0
            error_count = 0
            
            # Восстанавливаем ISO стандарты
            if 'iso_standards' in backup_data:
                for obj_data in backup_data['iso_standards']:
                    try:
                        for deserialized_object in serializers.deserialize('json', json.dumps([obj_data])):
                            deserialized_object.save()
                            restored_count += 1
                    except Exception as e:
                        logger.error(f"Ошибка при восстановлении ISO стандарта: {e}")
                        error_count += 1
            
            # Восстанавливаем сертификаты
            if 'certificates' in backup_data:
                for obj_data in backup_data['certificates']:
                    try:
                        for deserialized_object in serializers.deserialize('json', json.dumps([obj_data])):
                            deserialized_object.save()
                            restored_count += 1
                    except Exception as e:
                        logger.error(f"Ошибка при восстановлении сертификата: {e}")
                        error_count += 1
            
            # Восстанавливаем аудиторов
            if 'auditors' in backup_data:
                for obj_data in backup_data['auditors']:
                    try:
                        for deserialized_object in serializers.deserialize('json', json.dumps([obj_data])):
                            deserialized_object.save()
                            restored_count += 1
                    except Exception as e:
                        logger.error(f"Ошибка при восстановлении аудитора: {e}")
                        error_count += 1
            
            if restored_count > 0:
                messages.success(request, f'Восстановлено {restored_count} объектов')
            
            if error_count > 0:
                messages.warning(request, f'Ошибок при восстановлении: {error_count}')
            
        except Exception as e:
            logger.error(f"Ошибка при восстановлении из резервной копии: {e}")
            messages.error(request, f'Ошибка при восстановлении: {str(e)}')
        
        return redirect('admin_certificates')
    
    return render(request, 'certificates/admin/restore.html')

@login_required
def certificate_audit_log(request):
    """Журнал аудита действий с сертификатами"""
    # Здесь можно реализовать логику для отображения журнала аудита
    # Если используется django-simple-history или собственная система логирования
    
    context = {
        'audit_logs': [],  # Заменить на реальные данные аудита
    }
    
    return render(request, 'certificates/admin/audit_log.html', context)

@login_required
def certificate_settings(request):
    """Настройки системы сертификатов"""
    if request.method == 'POST':
        # Обработка настроек
        settings_data = {
            'notification_days_before_expiry': request.POST.get('notification_days_before_expiry', 30),
            'auto_update_statuses': request.POST.get('auto_update_statuses') == 'on',
            'email_notifications': request.POST.get('email_notifications') == 'on',
        }
        
        # Сохраняем настройки (можно использовать django-constance или собственную модель)
        try:
            from django.core.cache import cache
            cache.set('certificate_settings', settings_data, None)  # Бессрочно
            messages.success(request, 'Настройки сохранены')
        except Exception as e:
            logger.error(f"Ошибка при сохранении настроек: {e}")
            messages.error(request, 'Ошибка при сохранении настроек')
        
        return redirect('certificate_settings')
    
    # Загружаем текущие настройки
    try:
        from django.core.cache import cache
        settings_data = cache.get('certificate_settings', {
            'notification_days_before_expiry': 30,
            'auto_update_statuses': True,
            'email_notifications': True,
        })
    except:
        settings_data = {
            'notification_days_before_expiry': 30,
            'auto_update_statuses': True,
            'email_notifications': True,
        }
    
    return render(request, 'certificates/admin/settings.html', {
        'settings': settings_data
    })

@login_required
def regenerate_qr_code(request, certificate_id):
    """Регенерация QR-кода для сертификата"""
    if request.method == 'POST':
        try:
            certificate = get_object_or_404(Certificate, id=certificate_id)
            
            # Регенерируем QR-код
            if certificate._generate_qr_code():
                certificate.save(update_fields=['qr_code'])
                return JsonResponse({'success': True})
            else:
                return JsonResponse({'success': False, 'error': 'Ошибка генерации QR-кода'})
                
        except Exception as e:
            logger.error(f"Ошибка при регенерации QR-кода: {e}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Метод не поддерживается'})

def certificate_qr_view(request, certificate_id):
    """Отображение QR-кода сертификата"""
    certificate = get_object_or_404(Certificate, id=certificate_id)
    
    if not certificate.qr_code:
        # Генерируем QR-код если его нет
        if certificate._generate_qr_code():
            certificate.save(update_fields=['qr_code'])
    
    if certificate.qr_code:
        try:
            with open(certificate.qr_code.path, 'rb') as f:
                response = HttpResponse(f.read(), content_type="image/png")
                response['Content-Disposition'] = f'inline; filename="qr_code_{certificate.id}.png"'
                return response
        except FileNotFoundError:
            # Если файл не найден, регенерируем
            if certificate._generate_qr_code():
                certificate.save(update_fields=['qr_code'])
                with open(certificate.qr_code.path, 'rb') as f:
                    response = HttpResponse(f.read(), content_type="image/png")
                    response['Content-Disposition'] = f'inline; filename="qr_code_{certificate.id}.png"'
                    return response
    
    # Если QR-код не удалось создать, возвращаем ошибку 404
    raise Http404("QR-код не найден")

@login_required
def certificate_templates(request):
    """Управление шаблонами сертификатов"""
    # Здесь можно реализовать управление шаблонами для генерации сертификатов
    
    context = {
        'templates': [],  # Список доступных шаблонов
    }
    
    return render(request, 'certificates/admin/templates.html', context)

@login_required
def certificate_bulk_actions(request):
    """Массовые действия с сертификатами"""
    if request.method == 'POST':
        action = request.POST.get('action')
        certificate_ids = request.POST.getlist('certificate_ids')
        
        if not certificate_ids:
            messages.error(request, 'Не выбраны сертификаты для обработки')
            return redirect('admin_certificates')
        
        certificates = Certificate.objects.filter(id__in=certificate_ids)
        
        try:
            if action == 'update_statuses':
                updated_count = 0
                for certificate in certificates:
                    old_status = certificate.status
                    new_status = certificate.calculate_status()
                    if old_status != new_status:
                        certificate.status = new_status
                        certificate.save(update_fields=['status'])
                        updated_count += 1
                
                messages.success(request, f'Обновлено статусов: {updated_count}')
                
            elif action == 'regenerate_qr':
                regenerated_count = 0
                for certificate in certificates:
                    if certificate._generate_qr_code():
                        certificate.save(update_fields=['qr_code'])
                        regenerated_count += 1
                
                messages.success(request, f'Регенерировано QR-кодов: {regenerated_count}')
                
            elif action == 'export_selected':
                # Экспорт выбранных сертификатов
                import pandas as pd
                from io import BytesIO
                
                data = []
                for cert in certificates:
                    data.append({
                        'Номер сертификата': cert.full_certificate_number,
                        'Наименование организации': cert.name,
                        'ИНН': cert.inn,
                        'Статус': cert.get_status_display(),
                        'Дата начала': cert.start_date.strftime('%d.%m.%Y') if cert.start_date else '',
                        'Дата окончания': cert.expiry_date.strftime('%d.%m.%Y') if cert.expiry_date else '',
                    })
                
                df = pd.DataFrame(data)
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, sheet_name='Выбранные сертификаты', index=False)
                
                output.seek(0)
                
                response = HttpResponse(
                    output.getvalue(),
                    content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )
                response['Content-Disposition'] = 'attachment; filename="selected_certificates.xlsx"'
                return response
                
            elif action == 'delete_selected':
                deleted_count = certificates.count()
                certificates.delete()
                messages.success(request, f'Удалено сертификатов: {deleted_count}')
                
            else:
                messages.error(request, 'Неизвестное действие')
                
        except Exception as e:
            logger.error(f"Ошибка при выполнении массового действия {action}: {e}")
            messages.error(request, f'Ошибка при выполнении действия: {str(e)}')
        
        return redirect('admin_certificates')
    
    return redirect('admin_certificates')


def certificate_public_api(request):
    """Публичный API для проверки сертификатов"""
    if request.method == 'GET':
        certificate_number = request.GET.get('number', '').strip()
        
        if not certificate_number:
            return JsonResponse({'error': 'Номер сертификата не указан'}, status=400)
        
        try:
            certificate = Certificate.objects.filter(
                Q(certificate_number_part__iexact=certificate_number) |
                Q(full_certificate_number__iexact=certificate_number)
            ).select_related('iso_standard').first()
            
            if not certificate:
                return JsonResponse({'error': 'Сертификат не найден'}, status=404)
            
            data = {
                'certificate_number': certificate.full_certificate_number,
                'name': certificate.name,
                'inn': certificate.inn,
                'status': certificate.get_status_display(),
                'status_code': certificate.status,
                'iso_standard': certificate.iso_standard.standard_name if certificate.iso_standard else '',
                'start_date': certificate.start_date.strftime('%d.%m.%Y') if certificate.start_date else None,
                'expiry_date': certificate.expiry_date.strftime('%d.%m.%Y') if certificate.expiry_date else None,
                'first_inspection_status': certificate.get_first_inspection_status_display(),
                'second_inspection_status': certificate.get_second_inspection_status_display(),
                'is_valid': certificate.status == 'active',
            }
            
            return JsonResponse(data)
            
        except Exception as e:
            logger.error(f"Ошибка в публичном API: {e}")
            return JsonResponse({'error': 'Внутренняя ошибка сервера'}, status=500)
    
    return JsonResponse({'error': 'Метод не поддерживается'}, status=405)

@login_required
def certificate_statistics(request):
    """Статистика по сертификатам"""
    from django.db.models import Count, Q
    from datetime import datetime, timedelta
    
    # Общая статистика
    total_certificates = Certificate.objects.count()
    active_certificates = Certificate.objects.filter(status='active').count()
    expired_certificates = Certificate.objects.filter(status='expired').count()
    revoked_certificates = Certificate.objects.filter(status='revoked').count()
    
    # Статистика по инспекциям
    first_inspections_passed = Certificate.objects.filter(first_inspection_status='passed').count()
    first_inspections_failed = Certificate.objects.filter(first_inspection_status='failed').count()
    second_inspections_passed = Certificate.objects.filter(second_inspection_status='passed').count()
    second_inspections_failed = Certificate.objects.filter(second_inspection_status='failed').count()
    
    # Сертификаты, истекающие в ближайшие 30 дней
    expiring_soon = Certificate.objects.filter(
        expiry_date__lte=timezone.now().date() + timedelta(days=30),
        expiry_date__gte=timezone.now().date(),
        status='active'
    ).count()
    
    # Статистика по ISO стандартам
    iso_stats = Certificate.objects.values(
        'iso_standard__standard_name'
    ).annotate(
        count=Count('id')
    ).order_by('-count')[:10]
    
    context = {
        'total_certificates': total_certificates,
        'active_certificates': active_certificates,
        'expired_certificates': expired_certificates,
        'revoked_certificates': revoked_certificates,
        'first_inspections_passed': first_inspections_passed,
        'first_inspections_failed': first_inspections_failed,
        'second_inspections_passed': second_inspections_passed,
        'second_inspections_failed': second_inspections_failed,
        'expiring_soon': expiring_soon,
        'iso_stats': iso_stats,
    }
    
    return render(request, 'certificates/admin/statistics.html', context)
