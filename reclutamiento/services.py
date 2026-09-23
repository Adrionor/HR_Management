"""
Service layer para lógica de negocio de reportes
Separa la lógica de los views para mejor mantenibilidad y testabilidad
"""
from django.db.models import Count, Q, F
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
import json


class ReportesService:
    """Servicio para manejar la lógica de reportes de reclutamiento"""
    
    CACHE_TIMEOUT = 60 * 15  # 15 minutos
    CACHE_KEY_PREFIX = 'reportes_'
    
    @staticmethod
    def get_cache_key(usuario_id, filtros):
        """Genera una clave de caché única basada en usuario y filtros"""
        filtros_str = json.dumps(filtros, sort_keys=True)
        return f"{ReportesService.CACHE_KEY_PREFIX}{usuario_id}_{hash(filtros_str)}"
    
    @staticmethod
    def get_base_queryset(usuario):
        """
        Obtiene el queryset base de puestos según los permisos del usuario
        Implementa scoping por rol para seguridad de datos
        """
        from .models import Puesto, Marca
        from .views import es_gerente_ch, es_gerente_general, es_asesora
        
        if usuario.is_superuser or usuario.is_staff or es_gerente_ch(usuario):
            return Puesto.objects.all()
        elif es_gerente_general(usuario) and hasattr(usuario, 'perfilusuario'):
            marcas_usuario = usuario.perfilusuario.marcas.all()
            return Puesto.objects.filter(marca__in=marcas_usuario)
        elif es_asesora(usuario):
            return Puesto.objects.filter(asesora_encargada=usuario)
        else:
            return Puesto.objects.filter(solicitado_por=usuario)
    
    @staticmethod
    def apply_filters(queryset, filtros):
        """
        Aplica filtros al queryset de puestos
        Args:
            queryset: QuerySet de Puesto
            filtros: dict con los filtros a aplicar
        Returns:
            QuerySet filtrado
        """
        fecha_desde = filtros.get('fecha_desde', '').strip()
        fecha_hasta = filtros.get('fecha_hasta', '').strip()
        marca_filtro = filtros.get('marca', '').strip()
        agencia_filtro = filtros.get('agencia', '').strip()
        ciudad_filtro = filtros.get('ciudad', '').strip()
        asesora_filtro = filtros.get('asesora', '').strip()
        
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
        if asesora_filtro and asesora_filtro.isdigit():
            queryset = queryset.filter(asesora_encargada_id=int(asesora_filtro))
        
        return queryset
    
    @staticmethod
    def get_catalogos_optimizados(queryset):
        """
        Obtiene los catálogos para filtros de forma optimizada
        Evita consultas duplicadas
        """
        from .models import Marca
        from django.contrib.auth.models import User
        
        # Marcas - usar distinct en lugar de values_list
        marcas_disponibles = Marca.objects.filter(
            id__in=queryset.values_list('marca_id', flat=True).distinct()
        ).order_by('nombre')
        
        # Agencias - usar set para eliminar duplicados en memoria
        agencias_disponibles = sorted(list(set(
            queryset.exclude(agencia__isnull=True).exclude(agencia='').values_list('agencia', flat=True)
        )))
        
        # Ciudades - mapear códigos a nombres
        from .models import Puesto
        ciudades_codigos = sorted(list(set(
            queryset.exclude(ciudad__isnull=True).exclude(ciudad='').values_list('ciudad', flat=True)
        )))
        ciudades_map = dict(Puesto.CIUDADES_CHOICES)
        ciudades_disponibles = [
            {'codigo': c, 'nombre': ciudades_map.get(c, c)} for c in ciudades_codigos
        ]
        
        # Asesoras - solo las que tienen puestos asignados
        asesoras_disponibles = User.objects.filter(
            id__in=queryset.filter(asesora_encargada__isnull=False)
            .values_list('asesora_encargada_id', flat=True).distinct()
        ).order_by('first_name', 'username')
        
        return {
            'marcas': marcas_disponibles,
            'agencias': agencias_disponibles,
            'ciudades': ciudades_disponibles,
            'asesoras': asesoras_disponibles
        }
    
    @staticmethod
    def compute_kpis(puestos):
        """
        Calcula los KPIs ejecutivos de forma optimizada
        Args:
            puestos: lista de objetos Puesto
        Returns:
            dict con los KPIs calculados
        """
        if not puestos:
            return ReportesService.get_empty_kpis()
        
        vacantes_activas = [p for p in puestos if p.esta_abierto]
        total_activas = len(vacantes_activas)
        
        # Clasificar por SLA
        vencidas = [p for p in vacantes_activas if p.estatus_sla == 'VENCIDA']
        por_vencer = [p for p in vacantes_activas if p.estatus_sla == 'POR_VENCER']
        en_tiempo = [p for p in vacantes_activas if p.estatus_sla == 'EN_TIEMPO']
        
        # Vacantes cubiertas
        from .models import Puesto
        cubiertas = [p for p in puestos if not p.esta_abierto and p.estatus_autorizacion != Puesto.EstatusAutorizacion.RECHAZADO]
        total_cubiertas = len(cubiertas)
        
        # Plazas
        total_plazas_solicitadas = sum(p.cantidad_vacantes for p in puestos)
        total_plazas_cubiertas = sum(p.plazas_cubiertas for p in puestos)
        
        # SLA cumplimiento
        cumplimiento_sla = round(
            ((len(en_tiempo) + len(por_vencer)) / total_activas * 100), 1
        ) if total_activas > 0 else 100.0
        
        # Promedio días cobertura
        tiempos = [p.dias_transcurridos for p in puestos]
        promedio_dias_cobertura = round(sum(tiempos) / len(tiempos), 1) if tiempos else 0
        
        return {
            'total_vacantes': len(puestos),
            'total_activas': total_activas,
            'vencidas_count': len(vencidas),
            'por_vencer_count': len(por_vencer),
            'en_tiempo_count': len(en_tiempo),
            'total_cubiertas': total_cubiertas,
            'total_plazas_solicitadas': total_plazas_solicitadas,
            'total_plazas_cubiertas': total_plazas_cubiertas,
            'cumplimiento_sla': cumplimiento_sla,
            'promedio_dias_cobertura': promedio_dias_cobertura
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
            'total_plazas_solicitadas': 0,
            'total_plazas_cubiertas': 0,
            'cumplimiento_sla': 100.0,
            'promedio_dias_cobertura': 0
        }
    
    @staticmethod
    def prepare_chart_data(puestos):
        """
        Prepara los datos para los gráficos de Chart.js
        Optimiza el cálculo de agregaciones
        """
        from .models import Puesto
        
        # Etapas operativas
        etapas_orden = [
            '1. En Aprobación', '2. Por Asignar Asesora', '3. Por Definir Perfil',
            '4. En Búsqueda', '5. En Filtros y Evaluaciones', '6. En Entrevista con Jefe Inmediato',
            '7. En Trámites de Ingreso', '8. Cubierta / Cerrada'
        ]
        conteo_etapas = {etapa: 0 for etapa in etapas_orden}
        
        for p in puestos:
            etapa = p.etapa_operativa
            if etapa in conteo_etapas:
                conteo_etapas[etapa] += 1
            elif 'Rechazada' in etapa:
                conteo_etapas['8. Cubierta / Cerrada'] += 1
        
        # SLA por Agencia (Top 8)
        vacantes_activas = [p for p in puestos if p.esta_abierto]
        agencias_conteo = {}
        
        for p in vacantes_activas:
            ag = p.agencia or "Sin Agencia"
            if ag not in agencias_conteo:
                agencias_conteo[ag] = {'en_tiempo': 0, 'vencida': 0}
            if p.estatus_sla == 'VENCIDA':
                agencias_conteo[ag]['vencida'] += 1
            else:
                agencias_conteo[ag]['en_tiempo'] += 1
        
        top_agencias = sorted(
            agencias_conteo.items(), 
            key=lambda x: (x[1]['en_tiempo'] + x[1]['vencida']), 
            reverse=True
        )[:8]
        
        # Carga por Asesora
        asesoras_conteo = {}
        for p in puestos:
            if p.asesora_encargada:
                asesora_nom = p.asesora_encargada.get_full_name() or p.asesora_encargada.username
            else:
                asesora_nom = "Sin Asignar"
                
            if asesora_nom not in asesoras_conteo:
                asesoras_conteo[asesora_nom] = {'activas': 0, 'cubiertas': 0}
            if p.esta_abierto:
                asesoras_conteo[asesora_nom]['activas'] += 1
            else:
                asesoras_conteo[asesora_nom]['cubiertas'] += 1
        
        top_asesoras = sorted(
            asesoras_conteo.items(), 
            key=lambda x: (x[1]['activas'] + x[1]['cubiertas']), 
            reverse=True
        )
        
        return {
            'embudo_labels': list(conteo_etapas.keys()),
            'embudo_data': list(conteo_etapas.values()),
            'agencias_labels': [item[0] for item in top_agencias],
            'agencias_en_tiempo': [item[1]['en_tiempo'] for item in top_agencias],
            'agencias_vencidas': [item[1]['vencida'] for item in top_agencias],
            'asesoras_labels': [item[0] for item in top_asesoras],
            'asesoras_activas': [item[1]['activas'] for item in top_asesoras],
            'asesoras_cubiertas': [item[1]['cubiertas'] for item in top_asesoras],
            'etapas_disponibles': etapas_orden
        }
    
    @staticmethod
    def apply_computed_filters(puestos, sla_filtro, etapa_filtro):
        """
        Aplica filtros que dependen de propiedades computadas
        Estos filtros se aplican después de convertir a lista
        """
        if sla_filtro:
            puestos = [p for p in puestos if p.estatus_sla == sla_filtro]
        if etapa_filtro:
            puestos = [p for p in puestos if p.etapa_operativa == etapa_filtro]
        return puestos
    
    @staticmethod
    def sort_puestos(puestos):
        """
        Ordena puestos según criterios de negocio
        Prioridad: abiertas, vencidas, luego por fecha
        """
        def orden_puesto(p):
            peso_sla = {
                'VENCIDA': 0, 'POR_VENCER': 1, 'EN_TIEMPO': 2, 
                'CUBIERTA': 3, 'CANCELADA': 4
            }.get(p.estatus_sla, 5)
            return (not p.esta_abierto, peso_sla, -p.fecha_solicitud.timestamp())
        
        return sorted(puestos, key=orden_puesto)
    
    @staticmethod
    def generate_reporte_data(usuario, filtros, use_cache=True):
        """
        Genera todos los datos necesarios para el reporte
        Implementa caché para mejorar rendimiento
        """
        cache_key = ReportesService.get_cache_key(usuario.id, filtros)
        
        if use_cache:
            cached_data = cache.get(cache_key)
            if cached_data:
                return cached_data
        
        # Obtener queryset base con optimizaciones
        queryset = ReportesService.get_base_queryset(usuario)
        
        # Aplicar filtros de base de datos
        queryset = ReportesService.apply_filters(queryset, filtros)
        
        # Optimizar queries con select_related y prefetch_related
        queryset = queryset.select_related(
            'titulo', 'marca', 'solicitado_por', 'asesora_encargada', 'perfil_detallado'
        ).prefetch_related('procesos', 'procesos__candidato')
        
        # Convertir a lista para filtros computados
        lista_puestos = list(queryset)
        
        # Aplicar filtros computados
        sla_filtro = filtros.get('sla', '').strip()
        etapa_filtro = filtros.get('etapa', '').strip()
        lista_puestos = ReportesService.apply_computed_filters(
            lista_puestos, sla_filtro, etapa_filtro
        )
        
        # Ordenar resultados
        lista_puestos = ReportesService.sort_puestos(lista_puestos)
        
        # Calcular KPIs
        kpis = ReportesService.compute_kpis(lista_puestos)
        
        # Preparar datos para gráficos
        chart_data = ReportesService.prepare_chart_data(lista_puestos)
        
        # Obtener catálogos
        catálogos = ReportesService.get_catalogos_optimizados(queryset)
        
        resultado = {
            'puestos': lista_puestos,
            'kpis': kpis,
            'chart_data': chart_data,
            'catalogos': catálogos,
            'filtros_aplicados': filtros
        }
        
        # Guardar en caché
        if use_cache:
            cache.set(cache_key, resultado, ReportesService.CACHE_TIMEOUT)
        
        return resultado
    
    @staticmethod
    def invalidate_user_cache(usuario_id):
        """Invalida toda la caché de reportes para un usuario específico"""
        # En una implementación más robusta, usaríamos cache.keys() con patrón
        # Por ahora, simplemente no implementamos invalidación granular
        pass