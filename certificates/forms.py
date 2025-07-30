from django.db.models import Max
from django import forms
from django.forms import inlineformset_factory
from .models import Certificate, Auditor, ISOStandard

class CertificateAdminForm(forms.ModelForm):
    class Meta:
        model = Certificate
        fields = '__all__'

class CertificateForm(forms.ModelForm):
    iso_standard = forms.ModelChoiceField(
        queryset=ISOStandard.objects.all(),
        label='Стандарт ИСО',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    iso_standard_name = forms.CharField(
        label='Наименование стандарта в сертификате',
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'readonly': 'readonly'})
    )
    
    # Поля для удаления файлов
    file1_cleared = forms.BooleanField(required=False, label="Удалить файл сертификата")
    file1_psd_cleared = forms.BooleanField(required=False, label="Удалить PSD файл сертификата")
    file2_cleared = forms.BooleanField(required=False, label="Удалить файл приложения")
    file2_psd_cleared = forms.BooleanField(required=False, label="Удалить PSD файл приложения")
    file3_cleared = forms.BooleanField(required=False, label="Удалить дополнительный файл")
    
    class Meta:
        model = Certificate
        fields = ['name', 'inn', 'address', 'certificate_number_part', 'iso_standard',
                  'iso_standard_name', 'quality_management_system', 'start_date', 'expiry_date',
                  'status', 'first_inspection_date', 'first_inspection_status',
                  'second_inspection_date', 'second_inspection_status',
                  'file1', 'file1_psd', 'file2', 'file2_psd', 'file3', 'client_email', 'notifications_enabled',
                  'validity_period', 'certification_area', 'qr_code']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'expiry_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'first_inspection_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'second_inspection_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'certificate_number_part': forms.TextInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'certificate_number_part': 'Номер сертификата (часть)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.iso_standard:
            self.fields['iso_standard_name'].initial = self.instance.iso_standard.certificate_standard_name
        
        if not self.instance.pk:
            self.fields['certificate_number_part'].initial = self.get_next_number()

    def clean_certificate_number_part(self):
        part = self.cleaned_data['certificate_number_part']
        if not part.isdigit() or len(part) != 5:
            raise forms.ValidationError("Номер сертификата должен состоять из 5 цифр")
        
        # Проверка на уникальность
        if Certificate.objects.filter(certificate_number_part=part).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Этот номер сертификата уже занят")
        
        return part

    def get_next_number(self):
        max_number = Certificate.objects.aggregate(Max('certificate_number_part'))['certificate_number_part__max']
        if max_number:
            return f"{int(max_number) + 1:05d}"
        else:
            return "01001"

    def clean(self):
        cleaned_data = super().clean()
        
        # Проверка конфликтов между загрузкой новых файлов и их удалением
        file_fields = [
            ('file1', 'file1_cleared'),
            ('file1_psd', 'file1_psd_cleared'),
            ('file2', 'file2_cleared'),
            ('file2_psd', 'file2_psd_cleared'),
            ('file3', 'file3_cleared')
        ]
        
        for file_field, clear_field in file_fields:
            if cleaned_data.get(clear_field) and cleaned_data.get(file_field):
                self.add_error(file_field, 'Нельзя одновременно загрузить новый файл и удалить существующий')
        
        return cleaned_data

class AuditorForm(forms.ModelForm):
    clear_audit_file = forms.BooleanField(required=False, label='Очистить файл аудита')
    clear_audit_file_psd = forms.BooleanField(required=False, label='Очистить PSD файл аудита')

    class Meta:
        model = Auditor
        fields = ('full_name', 'audit_file', 'audit_file_psd')

    audit_file_preview = forms.CharField(widget=forms.HiddenInput(), required=False)

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('clear_audit_file') and cleaned_data.get('audit_file'):
            self.add_error('audit_file', 'Нельзя одновременно загрузить новый файл и очистить существующий')
        if cleaned_data.get('clear_audit_file_psd') and cleaned_data.get('audit_file_psd'):
            self.add_error('audit_file_psd', 'Нельзя одновременно загрузить новый PSD файл и очистить существующий')
        return cleaned_data

AuditorFormSet = inlineformset_factory(
    Certificate, 
    Auditor, 
    form=AuditorForm,
    extra=1, 
    can_delete=True
)