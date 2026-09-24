release: python manage.py migrate && python manage.py init_admin
web: gunicorn mi_proyecto.wsgi --log-file -
