#!/bin/bash
set -e

echo "📦 Creando deploy_package.zip para AWS Elastic Beanstalk..."

# Limpiar archivo ZIP previo
rm -f deploy_package.zip

# Recolectar archivos estáticos
echo "🔧 Recolectando archivos estáticos..."
python manage.py collectstatic --noinput

# Crear ZIP con archivos esenciales
echo "📦 Empaquetando archivos..."
zip -r deploy_package.zip . \
  -x "venv/*" \
     "__pycache__/*" \
     ".env" ".env.*" "*/.env" "*/.env.*" \
     "*.zip" \
     "*.pyc" \
     ".git/*" \
     "media/*" \
     "*.log" \
     "cvs/*" \
     "create_deploy_package.sh"

echo "✅ deploy_package.zip creado exitosamente"
echo "📊 Tamaño: $(du -h deploy_package.zip | cut -f1)"
echo ""
echo "🚀 Listo para subir en AWS Elastic Beanstalk UI:"
echo "   1. Ve a AWS EB Console"
echo "   2. Selecciona 'Upload and Deploy'"
echo "   3. Sube el archivo deploy_package.zip"
echo "   4. Configura variables de entorno en la UI"
