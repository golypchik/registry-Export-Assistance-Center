@echo off
cd C:\cert_checker
python manage.py update_certificate_statuses >> C:\cert_checker\logs\status_updates.log 2>&1