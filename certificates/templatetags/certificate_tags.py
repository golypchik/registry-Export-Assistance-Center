from django import template
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

register = template.Library()

@register.filter
def add_years(value, years):
    """Добавляет указанное количество лет к дате"""
    try:
        date_obj = datetime.strptime(value, "%d.%m.%Y").date()
        new_date = date_obj + relativedelta(years=int(years))
        return new_date.strftime("%d.%m.%Y")
    except (ValueError, TypeError):
        return value