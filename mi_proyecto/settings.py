"""
Django settings for mi_proyecto project.

Generated by 'django-admin startproject' using Django 5.2.2.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/5.2/ref/settings/
"""
import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-qe!iin2wvekik3sbuc&bvxq&b#sau&$#n9@5zz&b=)di=zpa84'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []


# Application definition

INSTALLED_APPS = [
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'reclutamiento.apps.ReclutamientoConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'mi_proyecto.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        # --- LA LÍNEA CLAVE A MODIFICAR ---
        'DIRS': [BASE_DIR / 'templates'],
        # ---------------------------------
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'mi_proyecto.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/



# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LOGIN_REDIRECT_URL = 'dashboard' # Redirige al dashboard por su nombre
LOGIN_URL = 'login'              # La página de login
LOGOUT_REDIRECT_URL = 'login'    # A dónde ir después de cerrar sesión
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
ALLOWED_HOSTS = ['aguzmaninz.pythonanywhere.com','127.0.0.1']

# mi_proyecto/settings.py

# --- CONFIGURACIÓN DE DJANGO JAZZMIN ---
JAZZMIN_SETTINGS = {
    # Título que aparece en la pestaña del navegador y en la página de login
    "site_title": "Portal de Administración",
    "custom_css": "reclutamiento/css/admin_custom.css",
    # Título en la parte superior de la barra de navegación
    "site_header": "Bolsa de Trabajo",

    # Texto o logo para la barra de navegación (puedes usar HTML)
    "site_brand": "Premier Automotriz",

    # Logo para la página de login
    # "login_logo": "/ruta/a/tu/logo.png", # Opcional

    # Copyright en el pie de página
    "copyright": "Bolsa de Trabajo Premier",

    # Menú superior con enlaces útiles
    "topmenu_links": [
        {"name": "Inicio (Dashboard)", "url": "/dashboard", "permissions": ["auth.view_user"]},
        {"name": "Ver Sitio Público", "url": "/", "new_window": True},
        {"model": "auth.User"}, # Enlace al modelo de Usuarios
    ],

    # Ajustes de la interfaz de usuario
    "ui_tweaks": {
        "theme": "flatly",
        "dark_mode_theme": "darkly",
        "navbar_small_text": False,
        "footer_small_text": False,
        "body_small_text": False,
        "brand_small_text": False,
        "brand_colour": "navbar-dark",
        "accent": "accent-primary",
        "navbar": "navbar-dark",
        "no_navbar_border": False,
        "sidebar": "sidebar-dark-primary",
        "sidebar_nav_small_text": False,
        "sidebar_disable_expand": False,
        "sidebar_nav_child_indent": False,
        "sidebar_nav_compact_style": False,
        "sidebar_nav_legacy_style": False,
        "sidebar_nav_flat_style": False
    }
}

STATIC_URL = '/static/'
# --- AÑADE O REEMPLAZA ESTE BLOQUE ---
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'reclutamiento/static'),
]
STATIC_ROOT = BASE_DIR / "staticfiles"