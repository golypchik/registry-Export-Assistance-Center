from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('search/', views.search_results, name='search_results'),
    path('certificate/<int:certificate_id>/', views.certificate_detail, name='certificate_detail'),
    path('download/<int:certificate_id>/<int:file_num>/', views.download_file, name='download_file'),
    path('permission/<int:certificate_id>/', views.permission_detail, name='permission_detail'),
    path('audit/<int:certificate_id>/<int:auditor_id>/', views.audit_detail, name='audit_detail'),
    
    # Генерация изображений и предпросмотров
    path('generate-audit-preview/<int:certificate_id>/<int:auditor_id>/', views.generate_audit_preview, name='generate_audit_preview'),
    path('generate-audit-image/<int:certificate_id>/<int:auditor_id>/', views.generate_audit_image, name='generate_audit_image'),
    
    # Административные маршруты
    path('admin/certificates/', views.admin_certificates, name='admin_certificates'),
    path('admin/certificates/add/', views.add_certificate, name='add_certificate'),
    path('admin/certificates/<int:certificate_id>/edit/', views.edit_certificate, name='edit_certificate'),
    path('admin/certificates/<int:certificate_id>/delete/', views.delete_certificate, name='delete_certificate'),
    path('admin/certificates/<int:certificate_id>/inspections/', views.manage_inspections, name='manage_inspections'),
    path('admin/certificates/<int:certificate_id>/delete-file/', views.delete_certificate_file, name='delete_certificate_file'),
    path('admin/statistics/', views.certificate_statistics, name='certificate_statistics'),
    
    # Системные маршруты
    path('trigger-notifications/', views.trigger_notifications, name='trigger_notifications'),
]