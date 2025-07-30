# mi_proyecto/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    # ANTES: path('reclutamiento/', include('reclutamiento.urls')),
    # AHORA:
    path('', include('reclutamiento.urls')), # La app principal ahora responde en la raíz
    path('accounts/', include('django.contrib.auth.urls')),

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
