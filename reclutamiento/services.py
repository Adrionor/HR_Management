"""
Service layer para lógica de negocio de reportes de Reclutamiento y Selección.
Esquema 100% Capital Humano: métricas operativas de vacantes, asesoras,
semáforos visuales y 3 exportaciones directas en Excel (.xlsx con openpyxl).
"""
import io
import json
from datetime import datetime
from django.db.models import Count, Q, F, Sum
from django.core.cache import cache
from django.utils import timezone
from django.contrib.auth import get_user_model
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# Constantes de Estilo Openpyxl Corporativo (Fiori / Horizon Inter)
COLOR_SHELL = "1D2D3E"
COLOR_ACCENT = "0070F2"
COLOR_LIGHT_BG = "F5F6F8"
COLOR_BORDER = "D9DDE3"
COLOR_GREEN = "107E3E"
COLOR_RED = "BB0000"

FILL_HEADER = PatternFill(start_color=COLOR_SHELL, end_color=COLOR_SHELL, fill_type="solid")
FILL_SUBHEADER = PatternFill(start_color=COLOR_ACCENT, end_color=COLOR_ACCENT, fill_type="solid")
FILL_LIGHT = PatternFill(start_color=COLOR_LIGHT_BG, end_color=COLOR_LIGHT_BG, fill_type="solid")
FILL_SUCCESS = PatternFill(start_color="E7F6EC", end_color="E7F6EC", fill_type="solid")
FILL_WARNING = PatternFill(start_color="FFF4E5", end_color="FFF4E5", fill_type="solid")
FILL_DANGER = PatternFill(start_color="FFEEF0", end_color="FFEEF0", fill_type="solid")

FONT_HEADER = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
FONT_TITLE = Font(name="Calibri", size=14, bold=True, color=COLOR_SHELL)
FONT_SUBTITLE = Font(name="Calibri", size=10, italic=True, color="59697A")
FONT_SECTION = Font(name="Calibri", size=11, bold=True, color=COLOR_SHELL)
FONT_BOLD = Font(name="Calibri", size=10, bold=True, color="1D2D3E")
FONT_REGULAR = Font(name="Calibri", size=10, color="1D2D3E")
FONT_GREEN_BOLD = Font(name="Calibri", size=10, bold=True, color=COLOR_GREEN)
FONT_RED_BOLD = Font(name="Calibri", size=10, bold=True, color=COLOR_RED)

BORDER_THIN = Border(
    left=Side(style='thin', color=COLOR_BORDER),
    right=Side(style='thin', color=COLOR_BORDER),
    top=Side(style='thin', color=COLOR_BORDER),
    bottom=Side(style='thin', color=COLOR_BORDER)
)

ALIGN_LEFT = Alignment(horizontal="left", vertical="center")
ALIGN_CENTER = Alignment(horizontal="center", vertical="center")
ALIGN_RIGHT = Alignment(horizontal="right", vertical="center")


def _autofit_columns(ws, min_width=12, max_width=55):
    """Ajusta automáticamente el ancho de las columnas de una hoja de cálculo"""
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            val = str(cell.value or '')
            if '\n' in val:
                val = max(val.split('\n'), key=len)
            max_len = max(max_len, len(val))
        ws.column_dimensions[col_letter].width = min(max(max_len + 3, min_width), max_width)


class ReportesService:
    """Servicio para manejar la lógica de reportes de reclutamiento y exportación Excel"""
    
    CACHE_TIMEOUT = 60 * 15  # 15 minutos
    CACHE_KEY_PREFIX = 'reportes_'
    
    @staticmethod
    def get_cache_version():
        """Obtiene o inicializa el número de versión de caché de reportes"""
        v = cache.get('reportes_cache_version')
        if v is None:
            v = 1
            cache.set('reportes_cache_version', v, None)
        return v

    @staticmethod
    def get_cache_key(usuario_id, filtros):
        """Genera una clave de caché única basada en versión, usuario y filtros"""
        filtros_str = json.dumps(filtros, sort_keys=True)
        version = ReportesService.get_cache_version()
        return f"{ReportesService.CACHE_KEY_PREFIX}v{version}_{usuario_id}_{hash(filtros_str)}"
    
    @staticmethod
    def get_base_queryset(usuario):
        """
        Obtiene el queryset base de puestos según los permisos del usuario.
        - Directora / Gerencia de Capital Humano y Superusuarios: Visibilidad global de todas las vacantes.
        - Asesoras: Estrictamente restringido a sus vacantes asignadas individuales.
        """
        from .models import Puesto
        from .permissions import es_gerente_ch
        
        if not usuario or not usuario.is_authenticated:
            return Puesto.objects.none()
            
        if usuario.is_superuser or es_gerente_ch(usuario):
            return Puesto.objects.all()
            
        # Las asesoras únicamente tienen acceso a sus vacantes individuales asignadas
        return Puesto.objects.filter(asesora_encargada=usuario)
    
    @staticmethod
    def apply_filters(queryset, filtros, usuario=None):
        """
        Aplica filtros al queryset de puestos
        Args:
            queryset: QuerySet de Puesto
            filtros: dict con los filtros a aplicar
            usuario: Usuario solicitante (para aislar filtros de asesoras individuales)
        Returns:
            QuerySet filtrado
        """
        from .permissions import es_gerente_ch
        fecha_desde = filtros.get('fecha_desde', '').strip()
        fecha_hasta = filtros.get('fecha_hasta', '').strip()
        marca_filtro = filtros.get('marca', '').strip()
        agencia_filtro = filtros.get('agencia', '').strip()
        ciudad_filtro = filtros.get('ciudad', '').strip()
        asesora_filtro = filtros.get('asesora', '').strip()
        puesto_filtro = filtros.get('puesto', '').strip()
        
        if fecha_desde:
            queryset = queryset.filter(fecha_solicitud__date__gte=fecha_desde)
        if fecha_hasta:
            queryset = queryset.filter(fecha_solicitud__date__lte=fecha_hasta)
        if marca_filtro and marca_filtro.isdigit():
            queryset = queryset.filter(marca_id=int(marca_filtro))
        if agencia_filtro:
            queryset = queryset.filter(agencia__icontains=agencia_filtro)
        if ciudad_filtro:
            queryset = queryset.filter(ciudad=ciudad_filtro)

        # Regla de aislamiento RBAC: si el usuario no es Gerente CH ni superusuario,
        # forzar siempre que solo consulte sus vacantes asignadas individuales
        es_directora = (usuario and (usuario.is_superuser or es_gerente_ch(usuario)))
        if not es_directora and usuario and usuario.is_authenticated:
            queryset = queryset.filter(asesora_encargada=usuario)
        elif asesora_filtro and asesora_filtro.isdigit():
            queryset = queryset.filter(asesora_encargada_id=int(asesora_filtro))

        if puesto_filtro:
            if puesto_filtro.isdigit():
                queryset = queryset.filter(titulo_id=int(puesto_filtro))
            else:
                queryset = queryset.filter(titulo__nombre__icontains=puesto_filtro)
        
        return queryset
    
    @staticmethod
    def get_catalogos_optimizados(queryset, usuario=None):
        """
        Obtiene los catálogos para filtros de forma optimizada
        """
        from .models import Marca, CatalogoPuesto
        from .permissions import es_gerente_ch
        User = get_user_model()
        
        marcas_disponibles = Marca.objects.all().order_by('nombre')
        puestos_catalogo = CatalogoPuesto.objects.all().order_by('nombre')
        
        agencias_disponibles = sorted(list(set(
            queryset.exclude(agencia__isnull=True).exclude(agencia='').values_list('agencia', flat=True)
        )))
        
        from .models import Puesto
        ciudades_codigos = sorted(list(set(
            queryset.exclude(ciudad__isnull=True).exclude(ciudad='').values_list('ciudad', flat=True)
        )))
        ciudades_map = dict(Puesto.CIUDADES_CHOICES)
        ciudades_disponibles = [
            {'codigo': c, 'nombre': ciudades_map.get(c, c)} for c in ciudades_codigos
        ]
        
        # Asesoras de RH: si es asesora individual, solo se muestra a sí misma en el catálogo
        es_directora = (usuario and (usuario.is_superuser or es_gerente_ch(usuario)))
        if not es_directora and usuario and usuario.is_authenticated:
            asesoras_disponibles = User.objects.filter(id=usuario.id)
        else:
            asesoras_disponibles = User.objects.filter(
                Q(groups__name='Asesoras') | Q(puestos_asignados__isnull=False) | Q(is_staff=True)
            ).distinct().order_by('first_name', 'username')
        
        return {
            'marcas': marcas_disponibles,
            'puestos': puestos_catalogo,
            'agencias': agencias_disponibles,
            'ciudades': ciudades_disponibles,
            'asesoras': asesoras_disponibles
        }
    
    @staticmethod
    def compute_kpis(puestos):
        """
        Calcula los KPIs ejecutivos de RH de forma optimizada y matemáticamente consistente.
        """
        from .models import Puesto, Proceso
        
        if not puestos:
            return ReportesService.get_empty_kpis()
        
        vacantes_activas = [p for p in puestos if p.esta_abierto]
        total_activas = len(vacantes_activas)
        
        vencidas = [p for p in vacantes_activas if p.estatus_sla == 'VENCIDA' or p.dias_transcurridos > p.dias_meta]
        por_vencer = [p for p in vacantes_activas if p.estatus_sla == 'POR_VENCER']
        en_tiempo = [p for p in vacantes_activas if p.estatus_sla == 'EN_TIEMPO' and p.dias_transcurridos <= p.dias_meta]
        
        cubiertas = [p for p in puestos if not p.esta_abierto and p.estatus_autorizacion != Puesto.EstatusAutorizacion.RECHAZADO]
        canceladas = [p for p in puestos if p.estatus_autorizacion == Puesto.EstatusAutorizacion.RECHAZADO]
        total_cubiertas = len(cubiertas)
        total_canceladas = len(canceladas)
        
        total_plazas_solicitadas = sum(p.cantidad_vacantes for p in puestos)
        total_plazas_cubiertas = sum(p.plazas_cubiertas for p in puestos)
        total_plazas_canceladas = sum(p.plazas_pendientes for p in canceladas)
        
        # Cuadre matemático: Solicitadas - Cubiertas - Canceladas
        total_plazas_pendientes = max(0, total_plazas_solicitadas - total_plazas_cubiertas - total_plazas_canceladas)
        
        # Plazas pendientes por estatus de SLA en vacantes activas
        plazas_activas_pendientes = sum(p.plazas_pendientes for p in vacantes_activas)
        plazas_vencidas_pendientes = sum(p.plazas_pendientes for p in vencidas)
        plazas_por_vencer_pendientes = sum(p.plazas_pendientes for p in por_vencer)
        plazas_en_tiempo_pendientes = sum(p.plazas_pendientes for p in en_tiempo)
        
        # Auditoría de bono y reinicios
        vacantes_cumplio_bono = sum(1 for p in puestos if p.cumplio_meta_bono)
        vacantes_bono_indeterminado = sum(1 for p in puestos if p.cumplio_meta_bono is None)
        vacantes_con_reinicios = sum(1 for p in puestos if p.numero_reinicios > 0)
        total_reinicios = sum(p.numero_reinicios for p in puestos)
        
        cumplimiento_sla = round(
            ((len(en_tiempo) + len(por_vencer)) / total_activas * 100), 1
        ) if total_activas > 0 else 0.0
        
        tiempos = [p.dias_transcurridos_total for p in cubiertas if p.esta_completamente_cubierta]
        promedio_dias_cobertura = round(sum(tiempos) / len(tiempos), 1) if tiempos else 0
        
        # Pipeline de candidatos
        etapas_listas_ingreso = [
            Proceso.Estatus.MEDICO,
            Proceso.Estatus.DOCS,
            Proceso.Estatus.INGRESO_PROG,
            Proceso.Estatus.ALTA_ADMIN,
        ]
        etapas_en_proceso = [
            Proceso.Estatus.NUEVO,
            Proceso.Estatus.CONTACTO,
            Proceso.Estatus.PRUEBAS,
            Proceso.Estatus.ENT_CH,
            Proceso.Estatus.REF,
            Proceso.Estatus.ENT_JF,
            Proceso.Estatus.CONF_JF,
        ]
        
        todos_procesos = []
        for p in vacantes_activas:
            todos_procesos.extend(p.procesos.all())
            
        candidatos_listos_ingreso = sum(1 for pr in todos_procesos if pr.estatus_proceso in etapas_listas_ingreso)
        candidatos_en_proceso = sum(1 for pr in todos_procesos if pr.estatus_proceso in etapas_en_proceso)
        candidatos_estancados = sum(1 for pr in todos_procesos if pr.dias_en_etapa_actual >= 30 and pr.estatus_proceso not in [Proceso.Estatus.CONTRATADO, Proceso.Estatus.DESCARTADO_CH, Proceso.Estatus.NO_PRUEBAS, Proceso.Estatus.ABANDONO])

        return {
            'total_vacantes': len(puestos),
            'total_activas': total_activas,
            'vencidas_count': len(vencidas),
            'por_vencer_count': len(por_vencer),
            'en_tiempo_count': len(en_tiempo),
            'total_cubiertas': total_cubiertas,
            'total_canceladas': total_canceladas,
            'total_plazas_solicitadas': total_plazas_solicitadas,
            'total_plazas_cubiertas': total_plazas_cubiertas,
            'total_plazas_canceladas': total_plazas_canceladas,
            'total_plazas_pendientes': total_plazas_pendientes,
            'plazas_activas_pendientes': plazas_activas_pendientes,
            'plazas_vencidas_pendientes': plazas_vencidas_pendientes,
            'plazas_por_vencer_pendientes': plazas_por_vencer_pendientes,
            'plazas_en_tiempo_pendientes': plazas_en_tiempo_pendientes,
            'vacantes_cumplio_bono': vacantes_cumplio_bono,
            'vacantes_bono_indeterminado': vacantes_bono_indeterminado,
            'vacantes_con_reinicios': vacantes_con_reinicios,
            'total_reinicios': total_reinicios,
            'cumplimiento_sla': cumplimiento_sla,
            'promedio_dias_cobertura': promedio_dias_cobertura,
            'candidatos_listos_ingreso': candidatos_listos_ingreso,
            'candidatos_en_proceso': candidatos_en_proceso,
            'candidatos_estancados': candidatos_estancados,
        }
    
    @staticmethod
    def get_empty_kpis():
        """Retorna KPIs vacíos para cuando no hay datos"""
        return {
            'total_vacantes': 0,
            'total_activas': 0,
            'vencidas_count': 0,
            'por_vencer_count': 0,
            'en_tiempo_count': 0,
            'total_cubiertas': 0,
            'total_canceladas': 0,
            'total_plazas_solicitadas': 0,
            'total_plazas_cubiertas': 0,
            'total_plazas_canceladas': 0,
            'total_plazas_pendientes': 0,
            'plazas_activas_pendientes': 0,
            'plazas_vencidas_pendientes': 0,
            'plazas_por_vencer_pendientes': 0,
            'plazas_en_tiempo_pendientes': 0,
            'vacantes_cumplio_bono': 0,
            'vacantes_bono_indeterminado': 0,
            'vacantes_con_reinicios': 0,
            'total_reinicios': 0,
            'cumplimiento_sla': 0.0,
            'promedio_dias_cobertura': 0,
            'candidatos_listos_ingreso': 0,
            'candidatos_en_proceso': 0,
            'candidatos_estancados': 0,
        }

    @staticmethod
    def prepare_chart_data(puestos):
        """Prepara los datos para los gráficos de la suite analítica"""
        etapas_orden = [
            '1. En Búsqueda', '2. Pruebas / Filtros', '3. Entrevista CH',
            '4. Entrevista Jefe', '5. Trámites / Médico', '6. Cubierta / Cerrada'
        ]
        conteo_etapas = {e: 0 for e in etapas_orden}
        for p in puestos:
            if not p.esta_abierto:
                conteo_etapas['6. Cubierta / Cerrada'] += 1
            else:
                procs = list(p.procesos.all())
                if not procs:
                    conteo_etapas['1. En Búsqueda'] += 1
                elif any(pr.estatus_proceso in ['MEDICO', 'DOCS', 'INGRESO_PROG', 'ALTA_ADMIN'] for pr in procs):
                    conteo_etapas['5. Trámites / Médico'] += 1
                elif any(pr.estatus_proceso in ['ENT_JF', 'CONF_JF'] for pr in procs):
                    conteo_etapas['4. Entrevista Jefe'] += 1
                elif any(pr.estatus_proceso in ['ENT_CH', 'REF'] for pr in procs):
                    conteo_etapas['3. Entrevista CH'] += 1
                else:
                    conteo_etapas['2. Pruebas / Filtros'] += 1
        
        # Carga por Asesora
        asesoras_conteo = {}
        for p in puestos:
            nom = p.asesora_encargada.get_full_name() or p.asesora_encargada.username if p.asesora_encargada else "Sin Asignar"
            if nom not in asesoras_conteo:
                asesoras_conteo[nom] = {'activas': 0, 'cubiertas': 0}
            if p.esta_abierto:
                asesoras_conteo[nom]['activas'] += 1
            else:
                asesoras_conteo[nom]['cubiertas'] += 1

        top_asesoras = sorted(
            asesoras_conteo.items(), 
            key=lambda x: (x[1]['activas'] + x[1]['cubiertas']), 
            reverse=True
        )

        return {
            'embudo_labels': list(conteo_etapas.keys()),
            'embudo_data': list(conteo_etapas.values()),
            'asesoras_labels': [item[0] for item in top_asesoras],
            'asesoras_activas': [item[1]['activas'] for item in top_asesoras],
            'asesoras_cubiertas': [item[1]['cubiertas'] for item in top_asesoras],
        }

    @staticmethod
    def compute_agencias_scorecard(puestos):
        """Genera matriz consolidada por Marca, Agencia y Ciudad."""
        from .models import Proceso
        from .permissions import es_gerente_ch
        agencias_dict = {}
        for p in puestos:
            ag = (p.agencia or "Sin Agencia").strip()
            marca_nom = p.marca.nombre if p.marca else "Sin Marca"
            ciudad_nom = p.get_ciudad_display() if p.ciudad else "N/A"
            key = (marca_nom, ag, ciudad_nom)
            
            if key not in agencias_dict:
                agencias_dict[key] = {
                    'marca': marca_nom,
                    'agencia': ag,
                    'ciudad': ciudad_nom,
                    'total_vacantes': 0,
                    'activas': 0,
                    'en_tiempo': 0,
                    'vencidas': 0,
                    'cubiertas': 0,
                    'canceladas': 0,
                    'plazas_solicitadas': 0,
                    'plazas_cubiertas': 0,
                    'plazas_canceladas': 0,
                    'candidatos_listos': 0,
                    'candidatos_proceso': 0,
                }
            
            entry = agencias_dict[key]
            entry['total_vacantes'] += 1
            entry['plazas_solicitadas'] += p.cantidad_vacantes
            entry['plazas_cubiertas'] += p.plazas_cubiertas
            
            if p.esta_abierto:
                entry['activas'] += 1
                if p.estatus_sla == 'VENCIDA' or p.dias_transcurridos > p.dias_meta:
                    entry['vencidas'] += 1
                else:
                    entry['en_tiempo'] += 1
                for pr in p.procesos.all():
                    if pr.estatus_proceso in [Proceso.Estatus.MEDICO, Proceso.Estatus.DOCS, Proceso.Estatus.INGRESO_PROG, Proceso.Estatus.ALTA_ADMIN]:
                        entry['candidatos_listos'] += 1
                    elif pr.estatus_proceso in [Proceso.Estatus.NUEVO, Proceso.Estatus.CONTACTO, Proceso.Estatus.PRUEBAS, Proceso.Estatus.ENT_CH, Proceso.Estatus.REF, Proceso.Estatus.ENT_JF, Proceso.Estatus.CONF_JF]:
                        entry['candidatos_proceso'] += 1
            else:
                if p.estatus_autorizacion == 'RECHAZADO':
                    entry['canceladas'] += 1
                    entry['plazas_canceladas'] += p.plazas_pendientes
                elif p.estatus_autorizacion != p.EstatusAutorizacion.RECHAZADO:
                    entry['cubiertas'] += 1
                    
        scorecard = []
        for key, data in agencias_dict.items():
            plazas_pendientes = max(0, data['plazas_solicitadas'] - data['plazas_cubiertas'] - data['plazas_canceladas'])
            cumplimiento = round((data['en_tiempo'] / data['activas'] * 100), 1) if data['activas'] > 0 else 0.0
            scorecard.append({
                'marca': data['marca'],
                'agencia': data['agencia'],
                'ciudad': data['ciudad'],
                'total_vacantes': data['total_vacantes'],
                'activas': data['activas'],
                'en_tiempo': data['en_tiempo'],
                'vencidas': data['vencidas'],
                'cubiertas': data['cubiertas'],
                'canceladas': data['canceladas'],
                'plazas_solicitadas': data['plazas_solicitadas'],
                'plazas_cubiertas': data['plazas_cubiertas'],
                'plazas_canceladas': data['plazas_canceladas'],
                'plazas_pendientes': plazas_pendientes,
                'cumplimiento_sla': cumplimiento,
                'candidatos_listos': data['candidatos_listos'],
                'candidatos_proceso': data['candidatos_proceso'],
            })
            
        return sorted(scorecard, key=lambda x: (x['vencidas'], x['activas']), reverse=True)

    @staticmethod
    def compute_asesoras_scorecard(puestos):
        """
        Monitor de desempeño, productividad de cobertura y desglose de embudo por Asesora de RH.
        """
        from .models import Proceso
        from .permissions import es_gerente_ch
        asesoras_dict = {}
        
        for p in puestos:
            if p.asesora_encargada:
                a_id = p.asesora_encargada.id
                nombre = p.asesora_encargada.get_full_name() or p.asesora_encargada.username
                email = p.asesora_encargada.email or ""
            else:
                a_id = 0
                nombre = "Sin Asignar"
                email = ""
                
            if a_id not in asesoras_dict:
                asesoras_dict[a_id] = {
                    'asesora_id': a_id,
                    'nombre': nombre,
                    'email': email,
                    'total_asignadas': 0,
                    'activas': 0,
                    'cubiertas': 0,
                    'vencidas': 0,
                    'reiniciadas': 0,
                    'total_reinicios': 0,
                    'bono_cumplido': 0,
                    'bono_indeterminado': 0,
                    'plazas_solicitadas': 0,
                    'plazas_cubiertas': 0,
                    'plazas_pendientes': 0,
                    'integridad_aprobados': 0,
                    'integridad_reprobados': 0,
                    'pyxoom_aprobados': 0,
                    'pyxoom_reprobados': 0,
                    'descartados': 0,
                    'enviados_jefe': 0,
                    'confirmados_jefe': 0,
                    'abandonos': 0,
                    'contratados': 0,
                    'total_candidatos': 0,
                }
                
            entry = asesoras_dict[a_id]
            entry['total_asignadas'] += 1
            entry['plazas_solicitadas'] += p.cantidad_vacantes
            entry['plazas_cubiertas'] += p.plazas_cubiertas
            
            if p.numero_reinicios > 0:
                entry['reiniciadas'] += 1
            entry['total_reinicios'] += p.numero_reinicios
            
            if p.cumplio_meta_bono:
                entry['bono_cumplido'] += 1
            elif p.cumplio_meta_bono is None:
                entry['bono_indeterminado'] += 1
                
            if p.esta_abierto:
                entry['activas'] += 1
                entry['plazas_pendientes'] += p.plazas_pendientes
                if p.estatus_sla == 'VENCIDA' or p.dias_transcurridos > p.dias_meta:
                    entry['vencidas'] += 1
            elif p.estatus_autorizacion != p.EstatusAutorizacion.RECHAZADO:
                entry['cubiertas'] += 1
                
            for pr in p.procesos.all():
                entry['total_candidatos'] += 1
                if pr.resultado_integridad == Proceso.ResultadoIntegridad.APROBADO:
                    entry['integridad_aprobados'] += 1
                elif pr.resultado_integridad == Proceso.ResultadoIntegridad.NO_APROBADO:
                    entry['integridad_reprobados'] += 1
                    
                if pr.resultado_pyxoom in [Proceso.ResultadoPyxoom.OPTIMO, Proceso.ResultadoPyxoom.IDEAL]:
                    entry['pyxoom_aprobados'] += 1
                elif pr.resultado_pyxoom in [Proceso.ResultadoPyxoom.REPROBADO, Proceso.ResultadoPyxoom.BAJO]:
                    entry['pyxoom_reprobados'] += 1
                    
                if pr.estatus_proceso == Proceso.Estatus.DESCARTADO_CH:
                    entry['descartados'] += 1
                elif pr.estatus_proceso in [Proceso.Estatus.ENT_JF, Proceso.Estatus.CONF_JF, Proceso.Estatus.MEDICO, Proceso.Estatus.DOCS, Proceso.Estatus.INGRESO_PROG, Proceso.Estatus.ALTA_ADMIN, Proceso.Estatus.CONTRATADO]:
                    entry['enviados_jefe'] += 1
                if pr.estatus_proceso in [Proceso.Estatus.CONF_JF, Proceso.Estatus.MEDICO, Proceso.Estatus.DOCS, Proceso.Estatus.INGRESO_PROG, Proceso.Estatus.ALTA_ADMIN, Proceso.Estatus.CONTRATADO]:
                    entry['confirmados_jefe'] += 1
                if pr.estatus_proceso == Proceso.Estatus.ABANDONO:
                    entry['abandonos'] += 1
                if pr.estatus_proceso == Proceso.Estatus.CONTRATADO:
                    entry['contratados'] += 1

        scorecard = []
        for a_id, data in asesoras_dict.items():
            tot = data['total_candidatos']
            conversion = round((data['contratados'] / tot * 100), 1) if tot > 0 else 0.0
            
            venc = data['vencidas']
            act = data['activas']
            cub = data['cubiertas']

            if venc >= 2:
                semaforo = 'rojo'
                nivel_alerta = 'Crítico'
                diagnostico = f"Atención urgente: {venc} vacante(s) con retraso de SLA."
            elif venc == 1 or act >= 8:
                semaforo = 'amarillo'
                nivel_alerta = 'Atención'
                detalles = []
                if venc == 1:
                    detalles.append("1 vacante con retraso")
                if act >= 8:
                    detalles.append(f"sobrecarga ({act} activas)")
                diagnostico = f"Monitoreo sugerido: {', '.join(detalles)}."
            elif cub >= 3:
                semaforo = 'verde'
                nivel_alerta = 'Óptimo'
                diagnostico = f"Rendimiento destacado: {cub} vacante(s) cubiertas exitosamente."
            else:
                semaforo = 'verde'
                nivel_alerta = 'Óptimo'
                diagnostico = "Rendimiento óptimo: sin rezagos de SLA y flujo en tiempo."

            scorecard.append({
                'asesora_id': data['asesora_id'],
                'nombre': data['nombre'],
                'email': data['email'],
                'total_asignadas': data['total_asignadas'],
                'activas': data['activas'],
                'cubiertas': data['cubiertas'],
                'bono_cumplido': data['bono_cumplido'],
                'bono_indeterminado': data['bono_indeterminado'],
                'bono_pct': round((data['bono_cumplido'] / (data['total_asignadas'] - data['bono_indeterminado']) * 100), 1) if data['total_asignadas'] > data['bono_indeterminado'] else None,
                'vencidas': data['vencidas'],
                'reiniciadas': data['reiniciadas'],
                'total_reinicios': data['total_reinicios'],
                'plazas_solicitadas': data['plazas_solicitadas'],
                'plazas_cubiertas': data['plazas_cubiertas'],
                'plazas_pendientes': data['plazas_pendientes'],
                'integridad_aprobados': data['integridad_aprobados'],
                'integridad_reprobados': data['integridad_reprobados'],
                'pyxoom_aprobados': data['pyxoom_aprobados'],
                'pyxoom_reprobados': data['pyxoom_reprobados'],
                'descartados': data['descartados'],
                'enviados_jefe': data['enviados_jefe'],
                'confirmados_jefe': data['confirmados_jefe'],
                'abandonos': data['abandonos'],
                'contratados': data['contratados'],
                'total_candidatos': data['total_candidatos'],
                'tasa_conversion': conversion,
                'semaforo': semaforo,
                'nivel_alerta': nivel_alerta,
                'diagnostico': diagnostico,
            })
            
        return sorted(scorecard, key=lambda x: (x['cubiertas'], x['contratados'], -x['vencidas']), reverse=True)

    @staticmethod
    def compute_desglose_agencia_puesto(puestos):
        """Genera el desglose analítico de vacantes por agencia y puesto (Hoja 2 de Reporte 1)."""
        from .models import Proceso
        from .permissions import es_gerente_ch
        desglose_dict = {}
        for p in puestos:
            marca = p.marca.nombre if p.marca else "Sin Marca"
            agencia = p.agencia or "Sin Agencia"
            ciudad = p.get_ciudad_display() if p.ciudad else "N/A"
            puesto_nom = p.titulo.nombre if p.titulo else "Sin Título"
            key = (marca, agencia, ciudad, puesto_nom)
            
            if key not in desglose_dict:
                desglose_dict[key] = {
                    'marca': marca, 'agencia': agencia, 'ciudad': ciudad, 'puesto': puesto_nom,
                    'total_vacantes': 0, 'activas': 0, 'cubiertas': 0, 'canceladas': 0,
                    'solicitadas': 0, 'cubiertas_plazas': 0, 'plazas_canceladas': 0, 'vencidas': 0,
                    'listos_ingreso': 0, 'en_proceso': 0
                }
            entry = desglose_dict[key]
            entry['total_vacantes'] += 1
            entry['solicitadas'] += p.cantidad_vacantes
            entry['cubiertas_plazas'] += p.plazas_cubiertas
            
            if p.esta_abierto:
                entry['activas'] += 1
                if p.dias_transcurridos > p.dias_meta or p.estatus_sla == 'VENCIDA':
                    entry['vencidas'] += 1
                for pr in p.procesos.all():
                    if pr.estatus_proceso in [Proceso.Estatus.MEDICO, Proceso.Estatus.DOCS, Proceso.Estatus.INGRESO_PROG, Proceso.Estatus.ALTA_ADMIN]:
                        entry['listos_ingreso'] += 1
                    elif pr.estatus_proceso in [Proceso.Estatus.NUEVO, Proceso.Estatus.CONTACTO, Proceso.Estatus.PRUEBAS, Proceso.Estatus.ENT_CH, Proceso.Estatus.REF, Proceso.Estatus.ENT_JF, Proceso.Estatus.CONF_JF]:
                        entry['en_proceso'] += 1
            else:
                if p.estatus_autorizacion == 'RECHAZADO':
                    entry['canceladas'] += 1
                    entry['plazas_canceladas'] += p.plazas_pendientes
                else:
                    entry['cubiertas'] += 1
                    
        resultado = []
        for key, d in sorted(desglose_dict.items(), key=lambda x: (x[1]['agencia'], x[1]['puesto'])):
            pendientes = max(0, d['solicitadas'] - d['cubiertas_plazas'] - d['plazas_canceladas'])
            cobertura_pct = round((d['cubiertas_plazas'] / d['solicitadas'] * 100), 1) if d['solicitadas'] > 0 else 0.0
            resultado.append({
                'marca': d['marca'],
                'agencia': d['agencia'],
                'ciudad': d['ciudad'],
                'puesto': d['puesto'],
                'total_vacantes': d['total_vacantes'],
                'activas': d['activas'],
                'cubiertas': d['cubiertas'],
                'solicitadas': d['solicitadas'],
                'cubiertas_plazas': d['cubiertas_plazas'],
                'pendientes': pendientes,
                'vencidas': d['vencidas'],
                'listos_ingreso': d['listos_ingreso'],
                'en_proceso': d['en_proceso'],
                'cobertura_pct': cobertura_pct,
            })
        return resultado

    @staticmethod
    def compute_detalle_vacantes_bono(puestos):
        """Genera el detalle de auditoría de cada vacante para seguimiento de SLA (Hoja 2 de Reporte 2)."""
        from .models import Proceso
        from .permissions import es_gerente_ch
        resultado = []
        for p in puestos:
            criterio = ""
            if p.cumplio_meta_bono is True:
                criterio = "Cumple bono con SLA original"
            elif p.cumplio_meta_bono is None:
                criterio = "Bono indeterminado: falta historial verificable"
            elif p.dias_transcurridos <= p.dias_meta:
                criterio = "Sin bono acreditado; ciclo vigente en tiempo"
            else:
                criterio = f"Sin bono acreditado; ciclo vigente retrasado (+{p.dias_transcurridos - p.dias_meta}d)"
                
            cand_jefe = 0
            for pr in p.procesos.all():
                if pr.estatus_proceso in [
                    Proceso.Estatus.ENT_JF, Proceso.Estatus.CONF_JF, Proceso.Estatus.MEDICO,
                    Proceso.Estatus.DOCS, Proceso.Estatus.INGRESO_PROG, Proceso.Estatus.ALTA_ADMIN,
                    Proceso.Estatus.CONTRATADO
                ]:
                    cand_jefe += 1
                    
            resultado.append({
                'id': p.id,
                'puesto': p.titulo.nombre if p.titulo else "Sin Título",
                'marca': p.marca.nombre if p.marca else "Sin Marca",
                'agencia': p.agencia,
                'ciudad': p.get_ciudad_display(),
                'asesora': p.asesora_encargada.get_full_name() or p.asesora_encargada.username if p.asesora_encargada else "Sin Asignar",
                'fecha_solicitud': p.fecha_solicitud,
                'dias_transcurridos': p.dias_transcurridos,
                'dias_original': p.dias_transcurridos_total,
                'dias_meta': p.dias_meta,
                'estatus_sla': p.estatus_sla,
                'reinicios': p.numero_reinicios,
                'plazas_solicitadas': p.cantidad_vacantes,
                'plazas_cubiertas': p.plazas_cubiertas,
                'candidatos_jefe': cand_jefe,
                'cumple_bono': p.cumplio_meta_bono,
                'sla_historico_aproximado': p.fecha_registro_sla is None,
                'criterio': criterio,
                'esta_abierto': p.esta_abierto,
            })
        return sorted(resultado, key=lambda x: (x['estatus_sla'] == 'VENCIDA', -x['dias_transcurridos']), reverse=True)

    @staticmethod
    def compute_alertas_y_diagnosticos(lista_puestos, asesoras_scorecard, usuario=None):
        """Calcula el radar de semáforos accionables, vacantes atoradas y diagnósticos de consultoría."""
        from .models import Proceso
        from .permissions import es_gerente_ch
        
        terminales = [
            Proceso.Estatus.CONTRATADO,
            Proceso.Estatus.DESCARTADO_CH,
            Proceso.Estatus.NO_PRUEBAS,
            Proceso.Estatus.ABANDONO,
        ]
        
        vacantes_atoradas = []
        candidatos_estancados = []
        tiempos_por_etapa = {}
        
        for p in lista_puestos:
            if not p.esta_abierto:
                continue
                
            procesos = list(p.procesos.all())
            activos = [pr for pr in procesos if pr.estatus_proceso not in terminales]
            candidatos_en_jefe = [pr for pr in procesos if pr.estatus_proceso in [
                Proceso.Estatus.ENT_JF, Proceso.Estatus.CONF_JF, Proceso.Estatus.MEDICO,
                Proceso.Estatus.DOCS, Proceso.Estatus.INGRESO_PROG, Proceso.Estatus.ALTA_ADMIN,
                Proceso.Estatus.CONTRATADO
            ]]
            
            # 1. Vacantes Vencidas
            if p.dias_transcurridos > p.dias_meta or p.estatus_sla == 'VENCIDA':
                atraso = max(0, p.dias_transcurridos - p.dias_meta)
                vacantes_atoradas.append({
                    'puesto': p,
                    'tipo': 'VENCIDA',
                    'severidad': 'alta',
                    'badge_class': 'sap-badge-error',
                    'motivo': f"Vencida (+{atraso}d atraso)",
                    'dias_transcurridos': p.dias_transcurridos,
                    'dias_meta': p.dias_meta,
                    'candidatos_activos': len(activos),
                    'enviados_jefe': len(candidatos_en_jefe),
                    'asesora': p.asesora_encargada.get_full_name() or p.asesora_encargada.username if p.asesora_encargada else "Sin Asignar",
                })
            # 2. Sin candidatos en proceso pero con tiempo transcurrido considerable (mínimo 5 días o >= 30% del SLA consumido)
            elif len(activos) == 0 and (p.dias_transcurridos >= 5 or (p.dias_meta > 0 and (p.dias_transcurridos / p.dias_meta) >= 0.30)):
                vacantes_atoradas.append({
                    'puesto': p,
                    'tipo': 'SIN_CANDIDATOS',
                    'severidad': 'media',
                    'badge_class': 'sap-badge-warning',
                    'motivo': f"Pipeline Desierto ({p.dias_transcurridos}d sin candidatos)",
                    'dias_transcurridos': p.dias_transcurridos,
                    'dias_meta': p.dias_meta,
                    'candidatos_activos': 0,
                    'enviados_jefe': len(candidatos_en_jefe),
                    'asesora': p.asesora_encargada.get_full_name() or p.asesora_encargada.username if p.asesora_encargada else "Sin Asignar",
                })
            # 3. Riesgo de SLA (>= 75% del tiempo meta consumido y menos de 2 candidatos a jefe)
            elif p.dias_transcurridos >= (p.dias_meta * 0.75) and len(candidatos_en_jefe) < 2 and not p.esta_completamente_cubierta:
                pct_consumido = round((p.dias_transcurridos / p.dias_meta * 100)) if p.dias_meta > 0 else 0
                vacantes_atoradas.append({
                    'puesto': p,
                    'tipo': 'RIESGO_SLA',
                    'severidad': 'media',
                    'badge_class': 'sap-badge-warning',
                    'motivo': f"Riesgo de Vencimiento ({pct_consumido}% consumido)",
                    'dias_transcurridos': p.dias_transcurridos,
                    'dias_meta': p.dias_meta,
                    'candidatos_activos': len(activos),
                    'enviados_jefe': len(candidatos_en_jefe),
                    'asesora': p.asesora_encargada.get_full_name() or p.asesora_encargada.username if p.asesora_encargada else "Sin Asignar",
                })
                
            # Candidatos estancados (>= 30 días en etapa activa)
            for pr in activos:
                es_directora_usr = (usuario is None or usuario.is_superuser or es_gerente_ch(usuario))
                if not es_directora_usr:
                    if pr.asesora_asignada_id and pr.asesora_asignada_id != usuario.id:
                        continue
                dias_etapa = pr.dias_en_etapa_actual
                if dias_etapa >= 30:
                    candidatos_estancados.append({
                        'proceso_id': pr.id,
                        'candidato_nombre': pr.candidato.nombre_completo,
                        'puesto_nombre': p.titulo.nombre if p.titulo else "Sin título",
                        'puesto_id': p.id,
                        'agencia': p.agencia,
                        'ciudad': p.get_ciudad_display(),
                        'etapa': pr.get_estatus_proceso_display(),
                        'dias_en_etapa': dias_etapa,
                        'asesora': pr.asesora_asignada.get_full_name() or pr.asesora_asignada.username if pr.asesora_asignada else (p.asesora_encargada.get_full_name() if p.asesora_encargada else "Sin Asignar"),
                    })
                
                et_nombre = pr.get_estatus_proceso_display()
                if et_nombre not in tiempos_por_etapa:
                    tiempos_por_etapa[et_nombre] = []
                tiempos_por_etapa[et_nombre].append(dias_etapa)

        # Análisis de cuellos de botella
        cuellos_de_botella = []
        for etapa_nom, tiempos in tiempos_por_etapa.items():
            if tiempos:
                prom = round(sum(tiempos) / len(tiempos), 1)
                cuellos_de_botella.append({
                    'etapa': etapa_nom,
                    'promedio_dias': prom,
                    'total_candidatos': len(tiempos),
                })
        cuellos_de_botella.sort(key=lambda x: x['promedio_dias'], reverse=True)
        
        etapa_cuello_max = cuellos_de_botella[0]['etapa'] if cuellos_de_botella else "N/A"
        etapa_cuello_dias = cuellos_de_botella[0]['promedio_dias'] if cuellos_de_botella else 0

        # Insights Consultoría Senior
        asesoras_riesgo = [a for a in asesoras_scorecard if a.get('semaforo') == 'rojo']
        insights = []
        es_directora_diag = (usuario is None or usuario.is_superuser or es_gerente_ch(usuario))
        
        total_atoradas = len(vacantes_atoradas)
        vencidas_n = sum(1 for v in vacantes_atoradas if v['tipo'] == 'VENCIDA')
        sin_cand_n = sum(1 for v in vacantes_atoradas if v['tipo'] == 'SIN_CANDIDATOS')
        
        if total_atoradas > 0:
            insights.append({
                'titulo': 'Atención a Vacantes Críticas',
                'tipo': 'alerta' if vencidas_n > 0 else 'aviso',
                'badge': f"{total_atoradas} vacantes en observación",
                'texto': f"Se detectaron {vencidas_n} vacante(s) con SLA vencido y {sin_cand_n} con pipeline desierto (sin candidatos en proceso).",
                'accion': "Priorizar asignación y revisión de cartera en las vacantes con mayor atraso.",
            })
        elif any(p.esta_abierto for p in lista_puestos):
            insights.append({
                'titulo': 'Flujo de Vacantes Saludable',
                'tipo': 'exito',
                'badge': "100% en tiempo",
                'texto': "Todas las requisiciones activas se encuentran dentro de su ventana de días meta reglamentarios.",
                'accion': "Mantener el ritmo de preselección para asegurar la cobertura en tiempo SLA del periodo.",
            })

        if cuellos_de_botella and etapa_cuello_dias > 0:
            insights.append({
                'titulo': 'Cuello de Botella Operativo',
                'tipo': 'aviso',
                'badge': f"{etapa_cuello_max}: {etapa_cuello_dias} días prom.",
                'texto': f"La etapa '{etapa_cuello_max}' concentra la mayor retención de candidatos con un promedio de {etapa_cuello_dias} días.",
                'accion': "Agilizar retroalimentación con gerentes solicitantes o acelerar programación de citas.",
            })

        if asesoras_riesgo:
            if es_directora_diag:
                nom_riesgo = ", ".join(a['nombre'] for a in asesoras_riesgo[:3])
                insights.append({
                    'titulo': 'Asesoras con Sobrecarga o Atraso',
                    'tipo': 'alerta',
                    'badge': f"{len(asesoras_riesgo)} asesora(s) en semáforo rojo",
                    'texto': f"Las asesoras ({nom_riesgo}) registran vacantes vencidas o baja tasa de cobertura en el periodo.",
                    'accion': "Evaluar redistribución temporal de requisiciones o apoyo en prospección.",
                })
            else:
                insights.append({
                    'titulo': 'Alerta de Desempeño Individual',
                    'tipo': 'alerta',
                    'badge': "Semáforo Rojo",
                    'texto': "Registras vacante(s) vencidas o requerimientos con atraso de SLA en el periodo actual.",
                    'accion': "Priorizar la gestión de tus vacantes con mayor antigüedad y agilizar el avance de candidatos.",
                })
        elif asesoras_scorecard:
            if es_directora_diag:
                insights.append({
                    'titulo': 'Equipo de Asesoras Equilibrado',
                    'tipo': 'exito',
                    'badge': "Carga balanceada",
                    'texto': "Las asesoras encargadas mantienen sus vacantes activas dentro de los parámetros esperados de SLA.",
                    'accion': "Continuar seguimiento semanal habitual.",
                })
            else:
                insights.append({
                    'titulo': 'Rendimiento en Tiempo',
                    'tipo': 'exito',
                    'badge': "Flujo en tiempo",
                    'texto': "Tus vacantes asignadas se encuentran controladas y dentro de los parámetros de SLA esperados.",
                    'accion': "Continuar con el avance habitual de candidatos.",
                })
            
        procesos_evaluados = [
            pr for p in lista_puestos for pr in p.procesos.all()
            if pr.resultado_integridad or pr.resultado_pyxoom
        ]
        if procesos_evaluados:
            rechazados = sum(
                1 for pr in procesos_evaluados
                if pr.resultado_integridad == Proceso.ResultadoIntegridad.NO_APROBADO
                or pr.resultado_pyxoom in (Proceso.ResultadoPyxoom.REPROBADO, Proceso.ResultadoPyxoom.BAJO)
            )
            pct_descarte = round(rechazados / len(procesos_evaluados) * 100, 1)
            insights.append({
                'titulo': 'Filtros de Integridad y Psicometría',
                'tipo': 'info',
                'badge': f"{pct_descarte}% con resultado no aprobado",
                'texto': f"{rechazados} de {len(procesos_evaluados)} procesos con al menos una evaluación registran un resultado no aprobado.",
                'accion': "Calibrar fuentes de atracción para mejorar el índice de aprobación preliminar.",
            })
            
        return {
            'vacantes_atoradas': vacantes_atoradas,
            'candidatos_estancados': candidatos_estancados,
            'cuellos_de_botella': cuellos_de_botella,
            'insights': insights,
        }

    @staticmethod
    def get_movimientos_recientes(filtros, usuario=None, limit=25):
        """Obtiene la bitácora de movimientos recientes para visualizar en Reporte 3."""
        from .models import RegistroActividad
        from .permissions import es_gerente_ch
        qs = RegistroActividad.objects.all().select_related('usuario').order_by('-fecha_hora')
        es_directora = (usuario and (usuario.is_superuser or es_gerente_ch(usuario)))
        if not es_directora and usuario and usuario.is_authenticated:
            qs = qs.filter(usuario=usuario)
        fecha_desde = filtros.get('fecha_desde', '').strip()
        fecha_hasta = filtros.get('fecha_hasta', '').strip()
        if fecha_desde:
            qs = qs.filter(fecha_hora__date__gte=fecha_desde)
        if fecha_hasta:
            qs = qs.filter(fecha_hora__date__lte=fecha_hasta)
        return list(qs[:limit])

    @staticmethod
    def generate_reporte_data(usuario, filtros, use_cache=False):
        """Genera los datos consolidados y semáforos de reporte de RH"""
        cache_key = ReportesService.get_cache_key(usuario.id, filtros)
        
        if use_cache:
            cached_data = cache.get(cache_key)
            if cached_data:
                return cached_data
        
        queryset = ReportesService.get_base_queryset(usuario)
        queryset = ReportesService.apply_filters(queryset, filtros, usuario=usuario)
        queryset = queryset.select_related('titulo', 'marca', 'asesora_encargada').prefetch_related('procesos', 'procesos__candidato')
        
        lista_puestos = list(queryset)
        
        kpis = ReportesService.compute_kpis(lista_puestos)
        chart_data = ReportesService.prepare_chart_data(lista_puestos)
        catalogos = ReportesService.get_catalogos_optimizados(queryset, usuario=usuario)
        agencias_scorecard = ReportesService.compute_agencias_scorecard(lista_puestos)
        asesoras_scorecard = ReportesService.compute_asesoras_scorecard(lista_puestos)
        
        # 1. Semáforo: Vacantes Vencidas
        vacantes_vencidas = [
            p for p in lista_puestos
            if p.esta_abierto and (p.dias_transcurridos > p.dias_meta or p.estatus_sla == 'VENCIDA')
        ]
        vacantes_vencidas.sort(key=lambda x: (x.dias_transcurridos - x.dias_meta), reverse=True)
        
        # 2. Semáforo: Puestos con Más Vacantes (Top ranking)
        puestos_conteo = {}
        for p in lista_puestos:
            nom = p.titulo.nombre if p.titulo else "Sin título"
            if nom not in puestos_conteo:
                puestos_conteo[nom] = {
                    'nombre': nom,
                    'total_vacantes': 0,
                    'activas': 0,
                    'cubiertas': 0,
                    'plazas_solicitadas': 0,
                    'plazas_cubiertas': 0
                }
            puestos_conteo[nom]['total_vacantes'] += 1
            puestos_conteo[nom]['plazas_solicitadas'] += p.cantidad_vacantes
            puestos_conteo[nom]['plazas_cubiertas'] += p.plazas_cubiertas
            if p.esta_abierto:
                puestos_conteo[nom]['activas'] += 1
            else:
                puestos_conteo[nom]['cubiertas'] += 1

        puestos_mas_vacantes = sorted(
            puestos_conteo.values(),
            key=lambda x: (x['total_vacantes'], x['plazas_solicitadas']),
            reverse=True
        )[:8]

        # 3. Semáforo: Vacantes con Mayor Antigüedad (Abiertas)
        vacantes_mayor_antiguedad = sorted(
            [p for p in lista_puestos if p.esta_abierto],
            key=lambda x: x.dias_transcurridos,
            reverse=True
        )[:8]

        # 4. Métricas avanzadas para visualización in-app de Reportes 1, 2, 3 y Alertas
        desglose_agencia_puesto = ReportesService.compute_desglose_agencia_puesto(lista_puestos)
        detalle_vacantes_bono = ReportesService.compute_detalle_vacantes_bono(lista_puestos)
        alertas_diagnosticos = ReportesService.compute_alertas_y_diagnosticos(lista_puestos, asesoras_scorecard, usuario=usuario)
        movimientos_recientes = ReportesService.get_movimientos_recientes(filtros, usuario=usuario, limit=30)
        
        resultado = {
            'puestos': lista_puestos,
            'kpis': kpis,
            'chart_data': chart_data,
            'catalogos': catalogos,
            'agencias_scorecard': agencias_scorecard,
            'asesoras_scorecard': asesoras_scorecard,
            'vacantes_vencidas': vacantes_vencidas,
            'puestos_mas_vacantes': puestos_mas_vacantes,
            'vacantes_mayor_antiguedad': vacantes_mayor_antiguedad,
            'filtros_aplicados': filtros,
            # Nuevas estructuras para visualización interactiva in-app
            'desglose_agencia_puesto': desglose_agencia_puesto,
            'detalle_vacantes_bono': detalle_vacantes_bono,
            'vacantes_atoradas': alertas_diagnosticos['vacantes_atoradas'],
            'candidatos_estancados_detalle': sorted(alertas_diagnosticos['candidatos_estancados'], key=lambda x: x['dias_en_etapa'], reverse=True)[:15],
            'cuellos_de_botella': alertas_diagnosticos['cuellos_de_botella'],
            'insights_consultoria': alertas_diagnosticos['insights'],
            'movimientos_recientes': movimientos_recientes,
            'total_atoradas_count': len(alertas_diagnosticos['vacantes_atoradas']),
            'total_estancados_count': len(alertas_diagnosticos['candidatos_estancados']),
            'asesoras_riesgo_count': len([a for a in asesoras_scorecard if a.get('semaforo') == 'rojo']),
            'cuellos_labels': [c['etapa'] for c in alertas_diagnosticos['cuellos_de_botella']],
            'cuellos_data': [c['promedio_dias'] for c in alertas_diagnosticos['cuellos_de_botella']],
        }
        
        if use_cache:
            cache.set(cache_key, resultado, ReportesService.CACHE_TIMEOUT)
            
        return resultado

    @staticmethod
    def invalidate_user_cache(usuario_id=None):
        """Invalida la caché de reportes"""
        try:
            cache.incr('reportes_cache_version')
        except (ValueError, Exception):
            v = (cache.get('reportes_cache_version') or 1) + 1
            cache.set('reportes_cache_version', v, None)

    # =========================================================================
    # EXPORTACIÓN 1: Resumen Ejecutivo por Periodo (.xlsx)
    # =========================================================================
    @staticmethod
    def generar_excel_resumen_ejecutivo(filtros, usuario):
        """
        Genera el Reporte 1 — Resumen Ejecutivo por Periodo (.xlsx)
        Hoja 1: Balance de requisiciones, ingresos, pendientes cuadradas matemáticamente y pipeline.
        Hoja 2: Desglose consolidado por agencia y puesto.
        """
        from .models import Puesto, Proceso
        
        # Filtros de fecha
        fecha_desde_str = filtros.get('fecha_desde', '').strip()
        fecha_hasta_str = filtros.get('fecha_hasta', '').strip()
        
        qs_base = ReportesService.get_base_queryset(usuario)
        # Aplicar filtros dimensionales (asesora, ciudad, agencia, marca, puesto)
        filtros_dimensiones = {k: v for k, v in filtros.items() if k not in ('fecha_desde', 'fecha_hasta')}
        if filtros_dimensiones:
            qs_base = ReportesService.apply_filters(qs_base, filtros_dimensiones, usuario=usuario)
        
        # Puestos acumulados (hasta fecha_hasta si se especifica)
        qs_acum = qs_base
        if fecha_hasta_str:
            qs_acum = qs_acum.filter(fecha_solicitud__date__lte=fecha_hasta_str)
            
        # Puestos en el periodo
        qs_periodo = qs_base
        if fecha_desde_str:
            qs_periodo = qs_periodo.filter(fecha_solicitud__date__gte=fecha_desde_str)
        if fecha_hasta_str:
            qs_periodo = qs_periodo.filter(fecha_solicitud__date__lte=fecha_hasta_str)
            
        puestos_periodo = list(qs_periodo.select_related('titulo', 'marca', 'asesora_encargada').prefetch_related('procesos'))
        puestos_acum = list(qs_acum.select_related('titulo', 'marca', 'asesora_encargada').prefetch_related('procesos'))
        
        wb = openpyxl.Workbook()
        
        # ---------------------------------------------------------------------
        # HOJA 1: RESUMEN EJECUTIVO
        # ---------------------------------------------------------------------
        ws1 = wb.active
        ws1.title = "Resumen Ejecutivo"
        ws1.views.sheetView[0].showGridLines = True
        
        # Banner de Título
        ws1.append(["PREMIER AUTOMOTRIZ — GESTIÓN DE TALENTO HUMANO"])
        ws1.append(["REPORTE 1: RESUMEN EJECUTIVO DE VACANTES Y COBERTURA POR PERIODO"])
        rango_str = f"Cohorte por fecha de solicitud: {fecha_desde_str or 'Histórico'} al {fecha_hasta_str or timezone.localdate().strftime('%Y-%m-%d')} | Estados actuales, no fotografía histórica"
        ws1.append([rango_str])
        ws1.append([])
        
        ws1["A1"].font = FONT_TITLE
        ws1["A2"].font = FONT_SECTION
        ws1["A3"].font = FONT_SUBTITLE
        
        # Métricas de Vacantes Matemáticamente Cuadradas
        req_p = len(puestos_periodo)
        req_a = len(puestos_acum)
        
        plazas_sol_p = sum(p.cantidad_vacantes for p in puestos_periodo)
        plazas_sol_a = sum(p.cantidad_vacantes for p in puestos_acum)
        
        ingresos_p = sum(p.plazas_cubiertas for p in puestos_periodo)
        ingresos_a = sum(p.plazas_cubiertas for p in puestos_acum)
        
        canc_puestos_p = [p for p in puestos_periodo if p.estatus_autorizacion == 'RECHAZADO']
        canc_puestos_a = [p for p in puestos_acum if p.estatus_autorizacion == 'RECHAZADO']
        canc_plazas_p = sum(p.plazas_pendientes for p in canc_puestos_p)
        canc_plazas_a = sum(p.plazas_pendientes for p in canc_puestos_a)
        
        # Cuadre matemático: Pendientes = Solicitadas - Cubiertas - Canceladas
        pend_plazas_p = max(0, plazas_sol_p - ingresos_p - canc_plazas_p)
        pend_plazas_a = max(0, plazas_sol_a - ingresos_a - canc_plazas_a)
        
        vencidas_p = sum(1 for p in puestos_periodo if p.esta_abierto and (p.dias_transcurridos > p.dias_meta or p.estatus_sla == 'VENCIDA'))
        vencidas_a = sum(1 for p in puestos_acum if p.esta_abierto and (p.dias_transcurridos > p.dias_meta or p.estatus_sla == 'VENCIDA'))
        
        activas_p = sum(1 for p in puestos_periodo if p.esta_abierto)
        activas_a = sum(1 for p in puestos_acum if p.esta_abierto)
        
        cumpl_p = round(((activas_p - vencidas_p) / activas_p * 100), 1) if activas_p > 0 else 0.0
        cumpl_a = round(((activas_a - vencidas_a) / activas_a * 100), 1) if activas_a > 0 else 0.0
        
        ws1.append(["BALANCE GENERAL DE VACANTES Y PLAZAS", "EN EL PERIODO", "ACUMULADO HISTÓRICO", "REGLA DE CONTROL"])
        row_header_idx = ws1.max_row
        for col_i in range(1, 5):
            c = ws1.cell(row=row_header_idx, column=col_i)
            c.fill = FILL_HEADER
            c.font = FONT_HEADER
            c.alignment = ALIGN_CENTER if col_i in [2, 3] else ALIGN_LEFT
            c.border = BORDER_THIN
            
        data_balance = [
            ("1. Requisiciones Recibidas (Vacantes)", req_p, req_a, "Total de solicitudes capturadas por RH"),
            ("2. Plazas Solicitadas Totales", plazas_sol_p, plazas_sol_a, "Total de plazas autorizadas requeridas"),
            ("3. Plazas Cubiertas Actuales", ingresos_p, ingresos_a, "Cobertura actual de las requisiciones de la cohorte"),
            ("4. Plazas Pendientes Canceladas", canc_plazas_p, canc_plazas_a, "Plazas no cubiertas de requisiciones canceladas"),
            ("5. PLAZAS PENDIENTES", pend_plazas_p, pend_plazas_a, "Solicitadas - Cubiertas - Canceladas"),
            ("6. Vacantes Abiertas Vencidas (SLA)", vencidas_p, vencidas_a, "Vacantes activas con días transcurridos > meta"),
            ("7. Porcentaje Cumplimiento SLA", f"{cumpl_p}%" if activas_p else "Sin datos", f"{cumpl_a}%" if activas_a else "Sin datos", "% de vacantes abiertas en tiempo"),
        ]
        
        for titulo, vp, va, regla in data_balance:
            ws1.append([titulo, vp, va, regla])
            r = ws1.max_row
            is_highlight = "PLAZAS PENDIENTES" in titulo
            for c_idx in range(1, 5):
                cell = ws1.cell(row=r, column=c_idx)
                cell.border = BORDER_THIN
                if is_highlight:
                    cell.fill = FILL_LIGHT
                    cell.font = FONT_BOLD
                else:
                    cell.font = FONT_REGULAR
                if c_idx in [2, 3]:
                    cell.alignment = ALIGN_CENTER
                    if is_highlight:
                        cell.font = FONT_GREEN_BOLD
                else:
                    cell.alignment = ALIGN_LEFT
                    
        ws1.append([])
        ws1.append([])
        
        # Tabla 2: Pipeline de Candidatos en Gestión
        ws1.append(["PIPELINE DE TALENTO EN GESTIÓN DIRECTA RH", "CANDIDATOS ACTIVOS", "ETAPAS INVOLUCRADAS"])
        row_pipe_header = ws1.max_row
        for col_i in range(1, 4):
            c = ws1.cell(row=row_pipe_header, column=col_i)
            c.fill = FILL_SUBHEADER
            c.font = FONT_HEADER
            c.alignment = ALIGN_CENTER if col_i == 2 else ALIGN_LEFT
            c.border = BORDER_THIN
            
        procs_activos = []
        for p in puestos_acum:
            if p.esta_abierto:
                procs_activos.extend(p.procesos.all())
                
        listos_ingreso = sum(1 for pr in procs_activos if pr.estatus_proceso in ['MEDICO', 'DOCS', 'INGRESO_PROG', 'ALTA_ADMIN'])
        en_evaluacion = sum(1 for pr in procs_activos if pr.estatus_proceso in ['NUEVO', 'CONTACTO', 'PRUEBAS', 'ENT_CH', 'REF', 'ENT_JF', 'CONF_JF'])
        estancados_30 = sum(1 for pr in procs_activos if pr.dias_en_etapa_actual >= 30 and pr.estatus_proceso not in ['CONTRATADO', 'DESCARTADO_CH', 'NO_PRUEBAS', 'ABANDONO'])
        total_pipeline = listos_ingreso + en_evaluacion
        
        pipeline_rows = [
            ("Candidatos Listos para Ingreso", listos_ingreso, "Examen Médico, Documentación, Inducción UP, Alta Admin"),
            ("Candidatos en Proceso Activo", en_evaluacion, "Filtro inicial, Pruebas Integridad/Pyxoom, Entrevistas CH y Jefe"),
            ("TOTAL CANDIDATOS EN GESTIÓN", total_pipeline, "Suma de aspirantes en cartera operativa"),
            ("Alerta: Detenidos +30 Días", estancados_30, "Candidatos sin movimiento de etapa en más de un mes"),
        ]
        
        for nombre_p, cant, desc in pipeline_rows:
            ws1.append([nombre_p, cant, desc])
            r = ws1.max_row
            is_danger = "Detenidos +30" in nombre_p
            for c_idx in range(1, 4):
                cell = ws1.cell(row=r, column=c_idx)
                cell.border = BORDER_THIN
                if is_danger:
                    cell.fill = FILL_DANGER
                    cell.font = FONT_RED_BOLD
                elif "TOTAL" in nombre_p:
                    cell.fill = FILL_LIGHT
                    cell.font = FONT_BOLD
                else:
                    cell.font = FONT_REGULAR
                if c_idx == 2:
                    cell.alignment = ALIGN_CENTER
                else:
                    cell.alignment = ALIGN_LEFT
                    
        _autofit_columns(ws1)
        
        # ---------------------------------------------------------------------
        # HOJA 2: DESGLOSE POR AGENCIA Y PUESTO
        # ---------------------------------------------------------------------
        ws2 = wb.create_sheet(title="Desglose Agencia y Puesto")
        ws2.views.sheetView[0].showGridLines = True
        
        ws2.append(["DESGLOSE ANALÍTICO DE VACANTES POR AGENCIA Y PUESTO"])
        ws2.append([rango_str])
        ws2.append([])
        ws2["A1"].font = FONT_TITLE
        ws2["A2"].font = FONT_SUBTITLE
        
        headers_ws2 = [
            "Marca", "Agencia", "Ciudad", "Puesto Solicitado",
            "Req. Periodo", "Req. Acumuladas", "Plazas Solicitadas",
            "Plazas Cubiertas", "Plazas Canceladas", "Plazas Pendientes",
            "Vacantes Vencidas", "Listos Ingreso", "En Proceso", "% Cobertura"
        ]
        ws2.append(headers_ws2)
        r_h2 = ws2.max_row
        for c_i, h in enumerate(headers_ws2, 1):
            cell = ws2.cell(row=r_h2, column=c_i)
            cell.fill = FILL_HEADER
            cell.font = FONT_HEADER
            cell.alignment = ALIGN_CENTER if c_i >= 5 else ALIGN_LEFT
            cell.border = BORDER_THIN
            
        # Agrupar puestos por (marca, agencia, ciudad, titulo)
        desglose_dict = {}
        for p in puestos_acum:
            marca = p.marca.nombre if p.marca else "Sin Marca"
            agencia = p.agencia or "Sin Agencia"
            ciudad = p.get_ciudad_display() if p.ciudad else "N/A"
            puesto_nom = p.titulo.nombre if p.titulo else "Sin Título"
            key = (marca, agencia, ciudad, puesto_nom)
            
            if key not in desglose_dict:
                desglose_dict[key] = {
                    'marca': marca, 'agencia': agencia, 'ciudad': ciudad, 'puesto': puesto_nom,
                    'req_periodo': 0, 'req_acum': 0,
                    'solicitadas': 0, 'cubiertas': 0, 'canceladas': 0,
                    'vencidas': 0, 'listos_ingreso': 0, 'en_proceso': 0
                }
            entry = desglose_dict[key]
            entry['req_acum'] += 1
            entry['solicitadas'] += p.cantidad_vacantes
            entry['cubiertas'] += p.plazas_cubiertas
            
            if p in puestos_periodo:
                entry['req_periodo'] += 1
            if p.estatus_autorizacion == 'RECHAZADO':
                entry['canceladas'] += p.plazas_pendientes
            if p.esta_abierto:
                if p.dias_transcurridos > p.dias_meta or p.estatus_sla == 'VENCIDA':
                    entry['vencidas'] += 1
                for pr in p.procesos.all():
                    if pr.estatus_proceso in ['MEDICO', 'DOCS', 'INGRESO_PROG', 'ALTA_ADMIN']:
                        entry['listos_ingreso'] += 1
                    elif pr.estatus_proceso in ['NUEVO', 'CONTACTO', 'PRUEBAS', 'ENT_CH', 'REF', 'ENT_JF', 'CONF_JF']:
                        entry['en_proceso'] += 1

        for key, data in sorted(desglose_dict.items(), key=lambda x: (x[1]['agencia'], x[1]['puesto'])):
            pendientes = max(0, data['solicitadas'] - data['cubiertas'] - data['canceladas'])
            cob = round((data['cubiertas'] / data['solicitadas'] * 100), 1) if data['solicitadas'] > 0 else 0.0
            
            ws2.append([
                data['marca'], data['agencia'], data['ciudad'], data['puesto'],
                data['req_periodo'], data['req_acum'], data['solicitadas'],
                data['cubiertas'], data['canceladas'], pendientes,
                data['vencidas'], data['listos_ingreso'], data['en_proceso'], f"{cob}%"
            ])
            r = ws2.max_row
            for c_i in range(1, 15):
                cell = ws2.cell(row=r, column=c_i)
                cell.border = BORDER_THIN
                cell.font = FONT_REGULAR
                if c_i >= 5:
                    cell.alignment = ALIGN_CENTER
                else:
                    cell.alignment = ALIGN_LEFT
                    
        _autofit_columns(ws2)
        
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf

    # =========================================================================
    # EXPORTACIÓN 2: Auditoría y Productividad por Asesora (.xlsx)
    # =========================================================================
    @staticmethod
    def generar_excel_auditoria_bono(filtros, usuario):
        """
        Genera el Reporte 2 — Auditoría de Productividad y Desempeño por Asesora (.xlsx)
        Hoja 1: Indicadores individuales de desempeño, cobertura, SLA y desglose de embudo.
        Hoja 2: Detalle de cada vacante y cumplimiento de tiempos de SLA.
        """
        queryset = ReportesService.get_base_queryset(usuario)
        queryset = ReportesService.apply_filters(queryset, filtros, usuario=usuario)
        puestos = list(queryset.select_related('titulo', 'marca', 'asesora_encargada').prefetch_related('procesos'))
        
        scorecard_asesoras = ReportesService.compute_asesoras_scorecard(puestos)
        
        wb = openpyxl.Workbook()
        
        # ---------------------------------------------------------------------
        # HOJA 1: RESUMEN Y PRODUCTIVIDAD POR ASESORA
        # ---------------------------------------------------------------------
        ws1 = wb.active
        ws1.title = "Auditoría Asesoras"
        ws1.views.sheetView[0].showGridLines = True
        
        ws1.append(["PREMIER AUTOMOTRIZ — GESTIÓN DE TALENTO HUMANO"])
        ws1.append(["REPORTE 2: AUDITORÍA DE PRODUCTIVIDAD Y DESEMPEÑO POR ASESORA"])
        ws1.append([])
        ws1["A1"].font = FONT_TITLE
        ws1["A2"].font = FONT_SECTION
        
        headers_ws1 = [
            "Asesora de Capital Humano", "Correo Electrónico",
            "Vacantes Asignadas", "Vacantes Cubiertas",
            "Vacantes Vencidas", "Vacantes Reiniciadas", "Plazas Cubiertas",
            "Integridad Aprobados", "Integridad No Aprobados",
            "Pyxoom Aprobados", "Pyxoom No Aprobados",
            "Descartados CH", "Enviados a Jefe", "Confirmados Jefe",
            "Abandonos", "Contratados", "Total Candidatos",
            "% Conversión"
        ]
        ws1.append(headers_ws1)
        r_h1 = ws1.max_row
        for c_i, h in enumerate(headers_ws1, 1):
            cell = ws1.cell(row=r_h1, column=c_i)
            cell.fill = FILL_HEADER
            cell.font = FONT_HEADER
            cell.alignment = ALIGN_CENTER if c_i >= 3 else ALIGN_LEFT
            cell.border = BORDER_THIN
            
        for a in scorecard_asesoras:
            ws1.append([
                a['nombre'], a['email'],
                a['total_asignadas'], a['cubiertas'],
                a['vencidas'], a['reiniciadas'], a['plazas_cubiertas'],
                a['integridad_aprobados'], a['integridad_reprobados'],
                a['pyxoom_aprobados'], a['pyxoom_reprobados'],
                a['descartados'], a['enviados_jefe'], a['confirmados_jefe'],
                a['abandonos'], a['contratados'], a['total_candidatos'],
                f"{a['tasa_conversion']}%"
            ])
            r = ws1.max_row
            for c_i in range(1, 19):
                cell = ws1.cell(row=r, column=c_i)
                cell.border = BORDER_THIN
                cell.font = FONT_REGULAR
                if c_i >= 3:
                    cell.alignment = ALIGN_CENTER
                else:
                    cell.alignment = ALIGN_LEFT
                if c_i == 4:
                    cell.font = FONT_GREEN_BOLD
                if c_i == 5 and a['vencidas'] > 0:
                    cell.font = FONT_RED_BOLD
                    
        _autofit_columns(ws1)
        
        # ---------------------------------------------------------------------
        # HOJA 2: DETALLE DE VACANTES Y CUMPLIMIENTO SLA
        # ---------------------------------------------------------------------
        ws2 = wb.create_sheet(title="Detalle Vacantes y SLA")
        ws2.views.sheetView[0].showGridLines = True
        
        ws2.append(["DETALLE DE VACANTES Y CUMPLIMIENTO DE SLA"])
        ws2.append([f"Total de vacantes analizadas: {len(puestos)}"])
        ws2.append([])
        ws2["A1"].font = FONT_TITLE
        ws2["A2"].font = FONT_SUBTITLE
        
        headers_ws2 = [
            "ID Vacante", "Asesora Encargada", "Puesto", "Marca", "Agencia", "Ciudad",
            "Fecha Solicitud", "Días Ciclo Vigente", "Días Meta SLA", "Estatus SLA",
            "Ciclo SLA / Reinicios", "Plazas Solicitadas", "Plazas Cubiertas",
            "Cand. Enviados a Jefe", "Detalle de Seguimiento", "Días SLA Original",
            "Origen SLA Original", "Bono"
        ]
        ws2.append(headers_ws2)
        r_h2 = ws2.max_row
        for c_i, h in enumerate(headers_ws2, 1):
            cell = ws2.cell(row=r_h2, column=c_i)
            cell.fill = FILL_SUBHEADER
            cell.font = FONT_HEADER
            cell.alignment = ALIGN_CENTER if c_i in [1, 7, 8, 9, 10, 11, 12, 13, 14] else ALIGN_LEFT
            cell.border = BORDER_THIN
            
        detalles = {d['id']: d for d in ReportesService.compute_detalle_vacantes_bono(puestos)}
        for p in puestos:
            detalle = detalles[p.id]
            cand_jefe = sum(1 for pr in p.procesos.all() if pr.estatus_proceso in ['ENT_JF', 'CONF_JF', 'MEDICO', 'DOCS', 'INGRESO_PROG', 'ALTA_ADMIN', 'CONTRATADO'])
            ws2.append([
                p.id,
                p.asesora_encargada.get_full_name() or p.asesora_encargada.username if p.asesora_encargada else "Sin Asignar",
                p.titulo.nombre if p.titulo else "Sin Título",
                p.marca.nombre if p.marca else "Sin Marca",
                p.agencia,
                p.get_ciudad_display(),
                p.fecha_solicitud.strftime('%Y-%m-%d'),
                p.dias_transcurridos,
                p.dias_meta,
                p.estatus_sla,
                f"Ciclo #{p.numero_reinicios + 1}" if p.numero_reinicios > 0 else "Ciclo Inicial (0)",
                p.cantidad_vacantes,
                p.plazas_cubiertas,
                cand_jefe,
                detalle['criterio'],
                detalle['dias_original'],
                "Fecha de solicitud aproximada" if detalle['sla_historico_aproximado'] else "Registro",
                "Indeterminado" if detalle['cumple_bono'] is None else ("Cumple" if detalle['cumple_bono'] else "No acreditado"),
            ])
            r = ws2.max_row
            for c_i in range(1, len(headers_ws2) + 1):
                cell = ws2.cell(row=r, column=c_i)
                cell.border = BORDER_THIN
                cell.font = FONT_REGULAR
                if c_i in [1, 7, 8, 9, 10, 11, 12, 13, 14]:
                    cell.alignment = ALIGN_CENTER
                else:
                    cell.alignment = ALIGN_LEFT
                if c_i == 10:
                    if p.estatus_sla == 'EN_TIEMPO' or p.esta_completamente_cubierta:
                        cell.fill = FILL_SUCCESS
                        cell.font = FONT_GREEN_BOLD
                    elif p.estatus_sla == 'VENCIDA':
                        cell.fill = FILL_DANGER
                        cell.font = FONT_RED_BOLD
                        
        _autofit_columns(ws2)
        
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf

    # =========================================================================
    # EXPORTACIÓN 3: Sábana Histórica Filtrable (.xlsx)
    # =========================================================================
    @staticmethod
    def generar_excel_sabana_historica(filtros, usuario):
        """
        Genera el Reporte 3 — Sábana Histórica Filtrable (.xlsx)
        Todos los movimientos con usuario responsable, fecha/hora exacta, días en etapa y notas.
        """
        from .models import RegistroActividad, Proceso, Puesto
        from .permissions import es_gerente_ch
        
        qs_act = RegistroActividad.objects.all().select_related('usuario').order_by('-fecha_hora')
        es_directora = (usuario and (usuario.is_superuser or es_gerente_ch(usuario)))
        if not es_directora and usuario and usuario.is_authenticated:
            qs_act = qs_act.filter(usuario=usuario)
        
        fecha_desde_str = filtros.get('fecha_desde', '').strip()
        fecha_hasta_str = filtros.get('fecha_hasta', '').strip()
        if fecha_desde_str:
            qs_act = qs_act.filter(fecha_hora__date__gte=fecha_desde_str)
        if fecha_hasta_str:
            qs_act = qs_act.filter(fecha_hora__date__lte=fecha_hasta_str)
            
        filtros_dimensiones = {k: v for k, v in filtros.items() if k not in ('fecha_desde', 'fecha_hasta')}
        if any(filtros_dimensiones.values()):
            puestos_filtrados = ReportesService.apply_filters(
                ReportesService.get_base_queryset(usuario), filtros_dimensiones, usuario=usuario
            )
            procesos_filtrados = Proceso.objects.filter(puesto__in=puestos_filtrados).values('id')
            qs_act = qs_act.filter(
                Q(tipo_objeto='Puesto', id_objeto__in=puestos_filtrados.values('id'))
                | Q(tipo_objeto='Proceso', id_objeto__in=procesos_filtrados)
            )
        registros = list(qs_act[:3001])
        truncado = len(registros) > 3000
        registros = registros[:3000]
        
        # Identificar IDs de procesos y puestos
        proc_ids = [r.id_objeto for r in registros if r.tipo_objeto == 'Proceso' and r.id_objeto]
        puesto_ids = [r.id_objeto for r in registros if r.tipo_objeto == 'Puesto' and r.id_objeto]
        
        procesos_dict = {
            p.id: p for p in Proceso.objects.filter(id__in=proc_ids).select_related(
                'candidato', 'puesto', 'puesto__titulo', 'puesto__marca', 'asesora_asignada', 'puesto__asesora_encargada'
            )
        }
        puestos_dict = {
            p.id: p for p in Puesto.objects.filter(id__in=puesto_ids).select_related('titulo', 'marca', 'asesora_encargada')
        }
        
        # Filtros adicionales
        agencia_f = filtros.get('agencia', '').strip().lower()
        asesora_f = filtros.get('asesora', '').strip()
        puesto_f = filtros.get('puesto', '').strip().lower()
        
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Sábana Histórica Movimientos"
        ws.views.sheetView[0].showGridLines = True
        
        ws.append(["PREMIER AUTOMOTRIZ — GESTIÓN DE TALENTO HUMANO"])
        ws.append(["REPORTE 3: SÁBANA HISTÓRICA DE MOVIMIENTOS Y AUDITORÍA DE PROCESOS"])
        rango_str = f"Filtros: Periodo {fecha_desde_str or 'Histórico'} al {fecha_hasta_str or 'Hoy'} | Dimensiones y etapas actuales"
        if truncado:
            rango_str += " | Solo se muestran los 3000 movimientos más recientes"
        ws.append([rango_str])
        ws.append([])
        ws["A1"].font = FONT_TITLE
        ws["A2"].font = FONT_SECTION
        ws["A3"].font = FONT_SUBTITLE
        
        headers = [
            "ID Movimiento", "Fecha y Hora Exacta", "Usuario Responsable", "Acción Realizada",
            "Tipo Registro", "Candidato", "Puesto / Vacante", "Marca", "Agencia", "Ciudad",
            "Asesora Actual", "Etapa / Estatus Actual", "Días en Etapa Actual", "Detalles y Observaciones"
        ]
        ws.append(headers)
        r_h = ws.max_row
        for c_i, h in enumerate(headers, 1):
            cell = ws.cell(row=r_h, column=c_i)
            cell.fill = FILL_HEADER
            cell.font = FONT_HEADER
            cell.alignment = ALIGN_CENTER if c_i in [1, 2, 5, 10, 13] else ALIGN_LEFT
            cell.border = BORDER_THIN
            
        for r in registros:
            candidato_nom = "N/A"
            puesto_nom = "N/A"
            marca_nom = "N/A"
            agencia_nom = "N/A"
            ciudad_nom = "N/A"
            asesora_nom = "Sin Asignar"
            etapa_nom = "N/A"
            dias_etapa = 0
            
            puesto_ref = None
            asesora_ref_id = None
            
            if r.tipo_objeto == 'Proceso' and r.id_objeto in procesos_dict:
                pr = procesos_dict[r.id_objeto]
                candidato_nom = pr.candidato.nombre_completo if pr.candidato else "N/A"
                puesto_ref = pr.puesto
                etapa_nom = pr.get_estatus_proceso_display()
                dias_etapa = pr.dias_en_etapa_actual
                if pr.asesora_asignada:
                    asesora_nom = pr.asesora_asignada.get_full_name() or pr.asesora_asignada.username
                    asesora_ref_id = pr.asesora_asignada_id
                elif puesto_ref and puesto_ref.asesora_encargada:
                    asesora_nom = puesto_ref.asesora_encargada.get_full_name() or puesto_ref.asesora_encargada.username
                    asesora_ref_id = puesto_ref.asesora_encargada_id
            elif r.tipo_objeto == 'Puesto' and r.id_objeto in puestos_dict:
                puesto_ref = puestos_dict[r.id_objeto]
                candidato_nom = "N/A (Vacante General)"
                etapa_nom = puesto_ref.etapa_operativa
                dias_etapa = puesto_ref.dias_transcurridos
                if puesto_ref.asesora_encargada:
                    asesora_nom = puesto_ref.asesora_encargada.get_full_name() or puesto_ref.asesora_encargada.username
                    asesora_ref_id = puesto_ref.asesora_encargada_id
                    
            if puesto_ref:
                puesto_nom = puesto_ref.titulo.nombre if puesto_ref.titulo else "Sin Título"
                marca_nom = puesto_ref.marca.nombre if puesto_ref.marca else "Sin Marca"
                agencia_nom = puesto_ref.agencia or "Sin Agencia"
                ciudad_nom = puesto_ref.get_ciudad_display() if puesto_ref.ciudad else "N/A"
                
            user_nom = r.usuario.get_full_name() or r.usuario.username if r.usuario else "Sistema"
            
            ws.append([
                r.id,
                r.fecha_hora.strftime('%Y-%m-%d %H:%M:%S'),
                user_nom,
                r.accion,
                r.tipo_objeto or "General",
                candidato_nom,
                puesto_nom,
                marca_nom,
                agencia_nom,
                ciudad_nom,
                asesora_nom,
                etapa_nom,
                dias_etapa,
                r.detalles or ""
            ])
            curr_r = ws.max_row
            for c_i in range(1, 15):
                cell = ws.cell(row=curr_r, column=c_i)
                cell.border = BORDER_THIN
                cell.font = FONT_REGULAR
                if c_i in [1, 2, 5, 10, 13]:
                    cell.alignment = ALIGN_CENTER
                else:
                    cell.alignment = ALIGN_LEFT
                    
        _autofit_columns(ws)
        
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf
