# reclutamiento/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

# Importamos todos nuestros modelos
from .models import (
    Marca,
    PerfilUsuario,
    Puesto,
    Candidato,
    Proceso,
    RegistroActividad, PerfilDePuesto, Aviso,CatalogoPuesto
)

# --------------------------------------------------------------------------
# --- CONFIGURACIÓN PARA MOSTRAR EL PERFIL DENTRO DE LA PÁGINA DE USUARIO ---
# --------------------------------------------------------------------------

# Primero, definimos cómo se verá el "inline" del perfil
class PerfilUsuarioInline(admin.StackedInline):
    model = PerfilUsuario
    can_delete = False
    verbose_name_plural = 'Perfiles de Usuario y Marcas'
    # 'filter_horizontal' crea un widget más amigable para seleccionar muchas marcas
    filter_horizontal = ('marcas',)

# Luego, definimos un nuevo admin de Usuario que incluya nuestro perfil inline
class UserAdmin(BaseUserAdmin):
    inlines = (PerfilUsuarioInline,)

# Finalmente, damos de baja el User admin por defecto y registramos el nuestro
admin.site.unregister(User)
admin.site.register(User, UserAdmin)
admin.site.register(CatalogoPuesto)

# --------------------------------------------------------------------------
# --- REGISTRO DEL RESTO DE LOS MODELOS (PARA VERLOS EN EL ADMIN) ---
# --------------------------------------------------------------------------

@admin.register(Marca)
class MarcaAdmin(admin.ModelAdmin):
    list_display = ('nombre',)
    search_fields = ('nombre',)

@admin.register(Puesto)
class PuestoAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'marca', 'estatus_autorizacion', 'asesora_encargada', 'esta_abierto')
    list_filter = ('estatus_autorizacion', 'marca', 'area', 'esta_abierto')
    search_fields = ('titulo', 'descripcion')

@admin.register(Candidato)
class CandidatoAdmin(admin.ModelAdmin):
    list_display = ('nombres', 'apellidos', 'email', 'telefono', 'puesto_de_interes')
    search_fields = ('nombre_completo', 'email', 'habilidades')

@admin.register(Proceso)
class ProcesoAdmin(admin.ModelAdmin):
    list_display = ('candidato', 'puesto', 'asesora_asignada', 'estatus_proceso')
    list_filter = ('estatus_proceso', 'asesora_asignada', 'puesto__marca')
    search_fields = ('candidato__nombre_completo', 'puesto__titulo')

@admin.register(RegistroActividad)
class RegistroActividadAdmin(admin.ModelAdmin):
    list_display = ('fecha_hora', 'usuario', 'accion', 'tipo_objeto', 'id_objeto')
    list_filter = ('usuario', 'tipo_objeto', 'fecha_hora')
    search_fields = ('accion', 'usuario__username')


@admin.register(PerfilDePuesto)
class PerfilDePuestoAdmin(admin.ModelAdmin):
    list_display = ('puesto', 'creado_por', 'fecha_actualizacion')
    list_filter = ('puesto__marca', 'creado_por')
    search_fields = ('puesto__titulo', 'habilidades_clave')
# Nota: El modelo PerfilUsuario no necesita registrarse por separado
# porque ya lo estamos mostrando "inline" dentro del Usuario.

@admin.register(Aviso)
class AvisoAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'creado_por', 'fecha_creacion', 'esta_activo')
    list_filter = ('esta_activo', 'creado_por')
    search_fields = ('titulo', 'contenido')

    def save_model(self, request, obj, form, change):
        # Asigna el usuario actual automáticamente si el campo está vacío
        if not obj.creado_por:
            obj.creado_por = request.user
        super().save_model(request, obj, form, change)