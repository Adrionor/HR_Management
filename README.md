# HR Management - Premier Automotriz

Sistema de gestión de recursos humanos y reclutamiento para Premier Automotriz.

## 🚀 Mejoras Recientes en Módulo de Reportes

Se han implementado mejoras significativas en el módulo de reportes (`/reportes/`):

### ✨ Nuevas Características

1. **Service Layer Architecture**
   - Separación de lógica de negocio en `reclutamiento/services.py`
   - Código más mantenible y testeable
   - Reutilización de componentes lógicos

2. **Optimización de Performance**
   - La caché de reportes es opcional; la vista recalcula por defecto para evitar cifras obsoletas
   - Queries optimizados con `select_related` y `prefetch_related`
   - Cálculos de KPIs optimizados

3. **Paginación Implementada**
   - 25 registros por página
   - Navegación mejorada con indicador de rango
   - Preservación de filtros al cambiar de página
   - Compatibilidad con DataTables

4. **Mejoras UX/UI**
   - Indicador de carga durante filtrado
   - Información de rango de registros visibles
   - Paginación mejorada visualmente
   - Compatibilidad mantenida con DataTables

### 🏗️ Arquitectura

```
reclutamiento/
├── services.py          # Service layer para lógica de reportes
├── views.py             # Views simplificados usando services
├── models.py            # Modelos de datos
└── test_services.py     # Script de prueba del service layer
```

### 🔧 Configuración de Caché

El sistema ahora incluye configuración de caché en `mi_proyecto/settings.py`:

```python
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
        'OPTIONS': {
            'MAX_ENTRIES': 1000
        }
    }
}
```

La vista de reportes no usa caché por defecto. Si se habilita expresamente, debe utilizarse una caché compartida y una estrategia de invalidación.

### 📊 Métricas Disponibles

El dashboard ejecutivo ahora calcula automáticamente:
- Total de vacantes y vacantes activas
- Cumplimiento de SLA (en tiempo, por vencer, vencidas)
- Plazas cubiertas vs solicitadas
- Tiempo promedio de cobertura
- Distribución por etapas operativas
- Carga de trabajo por asesora
- Estado de SLA por agencia

### 🧪 Pruebas

Para probar el service layer:

```bash
python reclutamiento/test_services.py
```

### 📈 Performance Mejoras

- **Memoria**: Paginación reduce carga en datasets grandes
- **Escalabilidad**: Arquitectura preparada para crecimiento

### SLA, bono y Telegram

- Las vacantes nuevas inician el SLA al registrarse; la fecha de requisición física se conserva por separado. La meta proviene del catálogo; gerencia puede indicar una excepción con motivo.
- Solo gerencia distinta de la responsable puede reiniciar una vacante abierta y vencida, con motivo y hasta dos veces. El bono usa el SLA original, no el ciclo reiniciado.
- El bono requiere cobertura completa dentro del SLA original o tres candidatos distintos enviados al jefe dentro de ese plazo, con Integridad aprobada y Pyxoom Óptimo o Ideal al momento del envío.
- Las vacantes anteriores a esta versión usan la fecha de solicitud como aproximación del inicio original. Cuando no existe evidencia suficiente para la terna, el bono queda indeterminado y requiere revisión manual; no debe utilizarse como resultado definitivo de nómina.
- El Excel ejecutivo agrupa por fecha de solicitud y muestra estados actuales; no es una fotografía histórica ni un reporte de ingresos por fecha de contratación.
- Para activar Telegram, configure `TELEGRAM_WEBHOOK_SECRET` con un valor secreto compatible con Telegram y vuelva a registrar el webhook con `python manage.py telegram_setup_webhook`. Sin secreto, el endpoint rechaza las solicitudes. Cada gerente debe generar su propio enlace, que dura 15 minutos y solo funciona en chat privado; los enlaces anteriores deben regenerarse.
- Ejecute las migraciones antes de desplegar estas funciones. Las vacantes existentes no reciben una fecha de registro inventada.

## 🛠️ Instalación y Configuración

### Requisitos
- Python 3.8+
- Django 5.2.2
- Dependencias en `requirements.txt`

### Configuración Inicial

1. Copiar archivo de entorno:
```bash
cp .env.example .env
```

2. Configurar variables en `.env`:
```
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost
```

3. Ejecutar migraciones:
```bash
python manage.py migrate
```

4. Crear superusuario:
```bash
python manage.py createsuperuser
```

5. Iniciar servidor:
```bash
python manage.py runserver
```

## 📚 Estructura del Proyecto

```
HR_Management/
├── mi_proyecto/          # Configuración de Django
├── reclutamiento/        # App principal de reclutamiento
│   ├── models.py         # Modelos de datos
│   ├── views.py          # Vistas y controladores
│   ├── services.py       # Lógica de negocio (nuevo)
│   ├── forms.py          # Formularios
│   ├── admin.py          # Configuración de admin
│   └── templates/        # Plantillas HTML
├── templates/            # Plantillas globales
├── Reporting/            # Scripts de reporting externos
└── manage.py             # CLI de Django
```

## 🔐 Seguridad

- Sistema de autenticación de Django
- Control de acceso basado en roles
- Validación de archivos subidos
- Protección CSRF habilitada

## 📝 Notas de Desarrollo

### Service Layer Pattern
El nuevo service layer sigue el patrón de separación de responsabilidades:
- **Views**: Manejan HTTP request/response
- **Services**: Contienen lógica de negocio
- **Models**: Definen estructura de datos

### Caché Strategy
- Caché por usuario + combinación de filtros
- TTL de 15 minutos para balance entre frescura y performance
- Invalidación manual disponible para actualizaciones críticas

## 🤝 Contribución

Para contribuir al proyecto:
1. Seguir la estructura de service layer para nueva lógica
2. Mantener compatibilidad con caché en nuevas vistas
3. Documentar cambios en este README
4. Probar con `test_services.py` antes de commits

## 📞 Soporte

Para problemas o preguntas contactar al equipo de desarrollo.