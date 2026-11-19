# reclutamiento/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import (
    Marca,
    PerfilUsuario,
    CatalogoPuesto,
    Puesto,
    Candidato,
    Proceso,
    RegistroActividad,
    Publicacion,
    PerfilDePuesto,
    Aviso,
)

# --------------------------------------------------------------------------
# --- PERSONALIZACIÓN DEL MODELO USER PARA INCLUIR PERFILUSUARIO ---
# --------------------------------------------------------------------------

class PerfilUsuarioInline(admin.StackedInline):
    model = PerfilUsuario
    can_delete = False
    verbose_name_plural = 'Perfil de Usuario (Marcas Asignadas)'
    fk_name = 'usuario'

class UserAdmin(BaseUserAdmin):
    inlines = (PerfilUsuarioInline,)

admin.site.unregister(User)
admin.site.register(User, UserAdmin)

@admin.register(CatalogoPuesto)
class CatalogoPuestoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'dias_meta')
    search_fields = ('nombre',)
    list_filter = ('dias_meta',)
    ordering = ('nombre',)

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
    search_fields = ('titulo__nombre', 'agencia', 'ciudad')

@admin.register(Candidato)
class CandidatoAdmin(admin.ModelAdmin):
    list_display = ('nombres', 'apellidos', 'email', 'telefono', 'ciudad_residencia', 'puesto_de_interes')
    search_fields = ('nombres', 'apellidos', 'email', 'rfc', 'habilidades')

@admin.register(Proceso)
class ProcesoAdmin(admin.ModelAdmin):
    list_display = ('candidato', 'puesto', 'asesora_asignada', 'estatus_proceso')
    list_filter = ('estatus_proceso', 'asesora_asignada', 'puesto__marca')
    search_fields = ('candidato__nombres', 'candidato__apellidos', 'puesto__titulo__nombre')

@admin.register(RegistroActividad)
class RegistroActividadAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'accion', 'fecha_hora', 'tipo_objeto', 'id_objeto')
    list_filter = ('usuario', 'tipo_objeto')
    search_fields = ('accion', 'detalles')
    readonly_fields = ('usuario', 'accion', 'fecha_hora', 'tipo_objeto', 'id_objeto', 'detalles')

@admin.register(PerfilDePuesto)
class PerfilDePuestoAdmin(admin.ModelAdmin):
    list_display = ('puesto', 'creado_por', 'fecha_actualizacion')
    list_filter = ('puesto__marca', 'creado_por')
    search_fields = ('puesto__titulo__nombre', 'comentarios_adicionales')

@admin.register(Publicacion)
class PublicacionAdmin(admin.ModelAdmin):
    list_display = ('puesto', 'plataforma', 'monto_inversion', 'fecha_publicacion')

@admin.register(Aviso)
class AvisoAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'creado_por', 'fecha_creacion', 'esta_activo')
    list_filter = ('esta_activo', 'fecha_creacion')
    search_fields = ('titulo', 'contenido')
