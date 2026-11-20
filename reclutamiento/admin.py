# reclutamiento/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html
from .models import (
    Marca,
    PerfilUsuario,
    CatalogoPuesto,
    Puesto,
    Candidato,
    Proceso,
    RegistroActividad,
    Publicacion,
    Aviso,
    PerfilDePuesto,
)

# --------------------------------------------------------------------------
# --- PERSONALIZACIÓN DEL MODELO USER ---
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


# --------------------------------------------------------------------------
# --- CATÁLOGO DE PUESTOS Y MARCAS ---
# --------------------------------------------------------------------------

@admin.register(CatalogoPuesto)
class CatalogoPuestoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'dias_meta')
    search_fields = ('nombre',)
    list_filter = ('dias_meta',)
    ordering = ('nombre',)


@admin.register(Marca)
class MarcaAdmin(admin.ModelAdmin):
    list_display = ('nombre',)
    search_fields = ('nombre',)


# --------------------------------------------------------------------------
# --- PUESTO (VACANTES OPERADAS EXCLUSIVAMENTE POR RH) ---
# --------------------------------------------------------------------------

@admin.register(Puesto)
class PuestoAdmin(admin.ModelAdmin):
    list_display = (
        'titulo',
        'marca',
        'agencia',
        'jefe_inmediato_nombre',
        'asesora_encargada',
        'dias_meta',
        'dias_transcurridos_badge',
        'estatus_sla_badge',
        'esta_abierto',
    )
    list_filter = (
        'esta_abierto',
        'marca',
        'area',
        'ciudad',
        'asesora_encargada',
        'motivo_requisicion',
    )
    search_fields = ('titulo__nombre', 'agencia', 'ciudad')
    readonly_fields = (
        'plazas_cubiertas',
        'plazas_pendientes',
        'dias_transcurridos',
        'fecha_limite_sla',
        'estatus_sla',
        'etapa_operativa',
    )
    fieldsets = (
        ('1. Identificación de la Vacante', {
            'fields': (
                'titulo',
                'marca',
                'agencia',
                'area',
                'ciudad',
                'cantidad_vacantes',
                'motivo_requisicion',
                'reemplaza_a',
                'es_confidencial',
            )
        }),
        ('2. Datos del Jefe Inmediato (Requisición Física)', {
            'fields': (
                'jefe_inmediato_nombre',
                'jefe_inmediato_puesto',
                'archivo_justificacion',
            )
        }),
        ('3. Parámetros de Puesto y Compensación', {
            'fields': (
                'sueldo_base',
                'esquema_comisiones',
                'horario',
                'experiencia_minima',
                'carrera_sugerida',
                'objetivo_puesto',
                'funciones_puesto',
                'indicador_puesto',
                'herramientas_puesto',
                'conocimientos_tecnicos',
            )
        }),
        ('4. Control Operativo de RH y SLAs', {
            'fields': (
                'asesora_encargada',
                'dias_meta',
                'fecha_inicio_sla_custom',
                'numero_reinicios',
                'esta_abierto',
                'estatus_autorizacion',
                'comentarios',
            )
        }),
        ('5. Métricas y Cumplimiento (Automático)', {
            'fields': (
                'plazas_cubiertas',
                'plazas_pendientes',
                'dias_transcurridos',
                'fecha_limite_sla',
                'estatus_sla',
                'etapa_operativa',
            )
        }),
    )

    @admin.display(description="Días Transc.")
    def dias_transcurridos_badge(self, obj):
        return f"{obj.dias_transcurridos} d"

    @admin.display(description="SLA")
    def estatus_sla_badge(self, obj):
        st = obj.estatus_sla
        colores = {
            'EN_TIEMPO': '#28a745',
            'POR_VENCER': '#fd7e14',
            'VENCIDA': '#dc3545',
            'CUBIERTA': '#007bff',
            'CANCELADA': '#6c757d',
        }
        color = colores.get(st, '#333')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;">{}</span>',
            color, st
        )


# --------------------------------------------------------------------------
# --- CANDIDATO ---
# --------------------------------------------------------------------------

@admin.register(Candidato)
class CandidatoAdmin(admin.ModelAdmin):
    list_display = (
        'nombre_completo',
        'email',
        'telefono',
        'ciudad_residencia',
        'no_contratable_badge',
        'puesto_de_interes',
        'fecha_registro',
    )
    list_filter = (
        'es_no_contratable',
        'ciudad_residencia',
        'nivel_educativo',
        'es_colaborador_actual',
    )
    search_fields = (
        'nombres',
        'apellidos',
        'email',
        'rfc',
        'habilidades',
    )
    fieldsets = (
        ('Datos Personales', {
            'fields': (
                'nombres',
                'apellidos',
                'email',
                'telefono',
                'rfc',
                'fecha_nacimiento',
                'ciudad_residencia',
            )
        }),
        ('Perfil Profesional', {
            'fields': (
                'puesto_de_interes',
                'interes_custom',
                'nivel_educativo',
                'años_de_experiencia',
                'ultimo_puesto',
                'ultima_empresa',
                'motivo_busqueda',
                'es_colaborador_actual',
                'habilidades',
                'expectativa_salarial',
                'cv',
            )
        }),
        ('Control de Contratabilidad (RH)', {
            'fields': (
                'es_no_contratable',
                'motivo_no_contratable',
            )
        }),
    )

    @admin.display(description="No Contratable", boolean=True)
    def no_contratable_badge(self, obj):
        return obj.es_no_contratable


# --------------------------------------------------------------------------
# --- PROCESO (PIPELINE OPERATIVO DE SELECCIÓN) ---
# --------------------------------------------------------------------------

@admin.register(Proceso)
class ProcesoAdmin(admin.ModelAdmin):
    list_display = (
        'candidato',
        'puesto',
        'asesora_asignada',
        'estatus_proceso',
        'fecha_inicio_etapa',
        'dias_en_etapa_badge',
        'estancado_badge',
        'resultado_integridad',
        'resultado_pyxoom',
    )
    list_filter = (
        'estatus_proceso',
        'resultado_integridad',
        'resultado_pyxoom',
        'asesora_asignada',
        'puesto__marca',
    )
    search_fields = (
        'candidato__nombres',
        'candidato__apellidos',
        'puesto__titulo__nombre',
    )
    readonly_fields = ('dias_en_etapa_actual', 'esta_estancado')

    @admin.display(description="Días en Etapa")
    def dias_en_etapa_badge(self, obj):
        return f"{obj.dias_en_etapa_actual} d"

    @admin.display(description="¿Estancado (>=30d)?", boolean=True)
    def estancado_badge(self, obj):
        return obj.esta_estancado


# --------------------------------------------------------------------------
# --- AUDITORÍA, PUBLICACIONES Y AVISOS ---
# --------------------------------------------------------------------------

@admin.register(RegistroActividad)
class RegistroActividadAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'accion', 'fecha_hora', 'tipo_objeto', 'id_objeto')
    list_filter = ('usuario', 'tipo_objeto')
    search_fields = ('accion', 'detalles')
    readonly_fields = ('usuario', 'accion', 'fecha_hora', 'tipo_objeto', 'id_objeto', 'detalles')


@admin.register(Publicacion)
class PublicacionAdmin(admin.ModelAdmin):
    list_display = ('puesto', 'plataforma', 'monto_inversion', 'fecha_publicacion', 'publicado_por')
    list_filter = ('plataforma', 'fecha_publicacion')


@admin.register(Aviso)
class AvisoAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'creado_por', 'fecha_creacion', 'esta_activo')
    list_filter = ('esta_activo', 'fecha_creacion')
    search_fields = ('titulo', 'contenido')


# Compatibilidad con suite de pruebas
class PerfilDePuestoAdmin(admin.ModelAdmin):
    list_display = ('puesto', 'creado_por', 'fecha_actualizacion')
    search_fields = ('puesto__titulo__nombre', 'comentarios_adicionales')
