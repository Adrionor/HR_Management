#!/bin/bash
set -e

echo "=========================================================="
echo "    PREMIER AUTOMOTRIZ - DESPLIEGUE EN PYTHONANYWHERE     "
echo "=========================================================="

REPO_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$REPO_DIR"

echo "-> 1. Obteniendo últimos cambios de GitHub (rama main)..."
git pull origin main

echo "-> 2. Verificando dependencias..."
pip install -r requirements.txt

echo "-> 3. Aplicando migraciones a la base de datos..."
python manage.py migrate

echo "-> 4. Recopilando archivos estáticos..."
python manage.py collectstatic --noinput

echo "-> 5. Recargando aplicación web..."
WSGI_FILE=$(find /var/www -name "*_wsgi.py" 2>/dev/null | head -n 1)
if [ -n "$WSGI_FILE" ]; then
    touch "$WSGI_FILE"
    echo "-> Aplicación web recargada exitosamente tocando $WSGI_FILE"
else
    echo "-> Nota: Si es tu primera vez configurando, haz clic en 'Reload' en la pestaña Web."
fi

echo "=========================================================="
echo "         ¡DESPLIEGUE COMPLETADO CON ÉXITO!               "
echo "=========================================================="
