import pandas as pd
from django.core.management.base import BaseCommand
from certificates.models import ISOStandard

class Command(BaseCommand):
    help = 'Импорт стандартов ИСО из Excel-файла'

    def add_arguments(self, parser):
        parser.add_argument('excel_file', type=str, help='Путь к Excel-файлу со стандартами ИСО')

    def handle(self, *args, **options):
        excel_file = options['excel_file']
        
        try:
            # Чтение Excel-файла
            df = pd.read_excel(excel_file, header=0)
            
            # Проверка наличия необходимых столбцов
            required_columns = ['Стандарт ИСО', 'Расшифровка стандарта', 'Нумерация в сертификате', 'Наименование стандарта в сертификате']
            for column in required_columns:
                if column not in df.columns:
                    self.stdout.write(self.style.ERROR(f'В файле отсутствует столбец "{column}"'))
                    return
            
            # Счетчики для статистики
            created_count = 0
            updated_count = 0
            error_count = 0
            
            # Обработка строк до первой пустой ячейки в столбце "Стандарт ИСО"
            for index, row in df.iterrows():
                if pd.isna(row['Стандарт ИСО']):
                    break
                
                try:
                    # Проверка наличия стандарта в базе данных
                    standard, created = ISOStandard.objects.update_or_create(
                        standard_name=row['Стандарт ИСО'],
                        defaults={
                            'description': row['Расшифровка стандарта'],
                            'certificate_number_prefix': row['Нумерация в сертификате'],
                            'certificate_standard_name': row['Наименование стандарта в сертификате']
                        }
                    )
                    
                    if created:
                        created_count += 1
                    else:
                        updated_count += 1
                        
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Ошибка при обработке строки {index + 2}: {str(e)}'))
                    error_count += 1
            
            # Вывод статистики
            self.stdout.write(self.style.SUCCESS(f'Импорт завершен. Создано: {created_count}, обновлено: {updated_count}, ошибок: {error_count}'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Ошибка при чтении файла: {str(e)}'))