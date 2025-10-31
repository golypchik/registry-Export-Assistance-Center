from django.core.management.base import BaseCommand
from certificates.models import Certificate


class Command(BaseCommand):
    help = 'Показать все поля модели Certificate'

    def handle(self, *args, **options):
        self.stdout.write("Поля модели Certificate:")
        self.stdout.write("=" * 80)
        
        for field in Certificate._meta.get_fields():
            field_name = field.name
            field_type = field.get_internal_type() if hasattr(field, 'get_internal_type') else type(field).__name__
            verbose = getattr(field, 'verbose_name', 'N/A')
            self.stdout.write(f"{field_name:30} | {field_type:20} | {verbose}")
        
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("Проверка конкретных полей:")
        self.stdout.write("=" * 80)
        
        fields_to_check = ['file1', 'file2', 'file3', 'auditor_certificate', 'file1_psd', 'file2_psd']
        for fname in fields_to_check:
            try:
                field = Certificate._meta.get_field(fname)
                status = "✓ ЕСТЬ"
                vname = getattr(field, 'verbose_name', 'N/A')
                self.stdout.write(f"{status} {fname:30} -> {vname}")
            except Exception as e:
                self.stdout.write(f"✗ НЕТ  {fname:30} ({str(e)})")


