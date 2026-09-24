release: python manage.py migrate && python manage.py crear_datos_demo --reset
web: gunicorn mi_proyecto.wsgi --log-file -
