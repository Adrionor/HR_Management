# 🚀 Instrucciones de Deploy - AWS Elastic Beanstalk

## ✅ **Deploy Package Listo**

Ejecuta `./create_deploy_package.sh` desde la raíz del proyecto para generar `deploy_package.zip` antes de subirlo a AWS Elastic Beanstalk.

### **📦 Archivos Incluidos:**

- ✅ **Procfile** - Configuración Gunicorn
- ✅ **requirements.txt** - Con gunicorn incluido
- ✅ **.ebextensions/django.config** - Configuración Django básica
- ✅ **manage.py** - Django management
- ✅ **mi_proyecto/** - Configuración del proyecto
- ✅ **reclutamiento/** - Aplicación principal
- ✅ **templates/** - Templates HTML
- ✅ **staticfiles/** - Archivos estáticos recolectados

---

## 🌐 **Pasos para Deploy via AWS UI**

### **Paso 1: Acceder a AWS Elastic Beanstalk**

1. Ir a [AWS Console](https://console.aws.amazon.com/)
2. Buscar "Elastic Beanstalk"
3. Seleccionar tu aplicación existente

### **Paso 2: Upload and Deploy**

1. En tu entorno de Elastic Beanstalk
2. Click en **"Upload and Deploy"**
3. Seleccionar archivo: `deploy_package.zip`
4. Versión: `capital-humano-v1.0`
5. Click en **"Deploy"**

### **Paso 3: Configurar Variables de Entorno en AWS UI**

En la consola de EB, ir a **Configuration > Software > Environment properties**:

```
# Django Settings
SECRET_KEY = tu-clave-super-segura-de-50-caracteres-minimo
DEBUG = False
DJANGO_SETTINGS_MODULE = mi_proyecto.settings

# Database (AWS RDS)
DB_NAME = recursos_humanos
DB_USER = postgres
DB_PASSWORD = GrupoPremier433
DB_HOST = recursos-humanos.ckgrykmwkt91.us-east-1.rds.amazonaws.com
DB_PORT = 5432

# Security
ALLOWED_HOSTS = .elasticbeanstalk.com,talentopremier.com,www.talentopremier.com
CSRF_TRUSTED_ORIGINS = https://talentopremier.com,https://www.talentopremier.com

# AWS S3 (opcional)
AWS_ACCESS_KEY_ID = your-aws-access-key-id
AWS_SECRET_ACCESS_KEY = your-aws-secret-access-key
AWS_STORAGE_BUCKET_NAME = capital-humano-premier
AWS_S3_REGION_NAME = us-east-2
```

---

## 🔧 **Configuración Automática**

El deploy ejecutará automáticamente:

1. ✅ **Instalación de dependencias** (`pip install -r requirements.txt`)
2. ✅ **Recolección de archivos estáticos** (`collectstatic`)
3. ✅ **Configuración de Nginx** (para servir logos y CSS)
4. ✅ **Ejecución de migraciones** (`migrate`)
5. ✅ **Inicio de Gunicorn** (servidor web)

**✅ LOGOS CORREGIDOS:** La configuración ahora incluye el mapeo correcto para servir archivos estáticos (`/static: staticfiles`) que resuelve el problema de visualización de logos.

---

## 📊 **Verificación del Deploy**

### **1. Estado del Entorno:**

- El entorno debe mostrar **"Healthy"** (verde)
- El deploy puede tomar 5-10 minutos

### **2. Probar la Aplicación:**

- **URL:** `https://tu-entorno.region.elasticbeanstalk.com`
- **Admin:** `https://tu-entorno.region.elasticbeanstalk.com/admin`

### **3. Ver Logs (si hay problemas):**

1. En la consola de EB
2. Ir a **"Logs"**
3. Seleccionar **"Request logs"**

---

## 🔄 **Para Futuras Actualizaciones**

1. Hacer cambios en el código
2. Ejecutar: `./create_deploy_package.sh`
3. Subir nuevo `deploy_package.zip` en AWS UI
4. ¡Listo!

---

## 🚨 **Solución de Problemas**

### **Error 400/500:**

- Verificar variables de entorno en AWS Console
- Revisar logs en EB Console

### **Error de BD:**

- Verificar credenciales RDS
- Verificar que el RDS esté en la misma región

### **Error de archivos estáticos:**

- El deploy automáticamente ejecuta `collectstatic`
- Los archivos se sirven desde `/static/`

---

## ✅ **Checklist Final**

- [ ] `deploy_package.zip` creado localmente
- [ ] Archivo subido a AWS Elastic Beanstalk
- [ ] Variables de entorno configuradas
- [ ] Estado del entorno: **"Healthy"**
- [ ] Aplicación accesible desde URL
- [ ] Admin panel funcionando
- [ ] Conexión a RDS confirmada

---

## 🎉 **¡Deploy Completo!**

Tu aplicación Django está lista y funcionando en AWS Elastic Beanstalk con:

- ✅ Servidor Gunicorn optimizado
- ✅ Base de datos AWS RDS
- ✅ Archivos estáticos servidos correctamente
- ✅ Configuración de seguridad para producción
