"""
Servicio centralizado para la integración de Telegram Bot con Premier Automotriz RH.
Especializado en Reportería Ejecutiva (BI), Alertas de SLAs, Vacantes Críticas y Contrataciones
para la Directora de Capital Humano, Gerentes de CH y Gerencias de Marca.
"""
import io
import logging
import uuid
import requests
from datetime import timedelta
from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Q

logger = logging.getLogger(__name__)


class TelegramService:
    """Motor de comunicación y reportería ejecutiva vía Telegram Bot API."""

    API_BASE = "https://api.telegram.org/bot{token}/{method}"

    @classmethod
    def get_token(cls):
        token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '') or ''
        return str(token).strip().strip('"').strip("'")

    @classmethod
    def get_bot_username(cls):
        bot = getattr(settings, 'TELEGRAM_BOT_USERNAME', 'Talento_premier_bot') or 'Talento_premier_bot'
        return str(bot).strip().strip('"').strip("'").lstrip('@')

    @classmethod
    def get_webhook_secret(cls):
        secret = getattr(settings, 'TELEGRAM_WEBHOOK_SECRET', '') or ''
        return str(secret).strip().strip('"').strip("'")

    @classmethod
    def is_configured(cls):
        """Verifica si el bot cuenta con un token configurado."""
        token = cls.get_token()
        return bool(token and len(token) > 10)

    @classmethod
    def _get_proxies(cls):
        proxy = getattr(settings, 'TELEGRAM_PROXY_URL', '') or ''
        if proxy:
            return {'http': proxy, 'https': proxy}
        return None

    @classmethod
    def api_call(cls, method, data=None, files=None, timeout=15):
        """Realiza una llamada HTTP a la API de Telegram."""
        token = cls.get_token()
        if not token:
            logger.warning("[TelegramService] Intento de llamada sin TELEGRAM_BOT_TOKEN.")
            return {'ok': False, 'description': 'Bot token no configurado.'}

        url = cls.API_BASE.format(token=token, method=method)
        try:
            response = requests.post(
                url,
                data=data or {},
                files=files or {},
                proxies=cls._get_proxies(),
                timeout=timeout
            )
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"[TelegramService] Error en llamada a Telegram ({method}): {e}")
            return {'ok': False, 'description': str(e)}

    # -------------------------------------------------------------------------
    # 1. ENVÍO DE MENSAJES Y ARCHIVOS EXCEL
    # -------------------------------------------------------------------------

    @classmethod
    def enviar_mensaje(cls, chat_id, texto_html, reply_markup=None):
        """Envía un mensaje formateado en HTML con soporte para botones inline."""
        if not chat_id:
            return {'ok': False, 'description': 'chat_id vacío.'}

        payload = {
            'chat_id': str(chat_id),
            'text': texto_html,
            'parse_mode': 'HTML',
            'disable_web_page_preview': True
        }
        if reply_markup:
            import json
            payload['reply_markup'] = json.dumps(reply_markup)

        resp = cls.api_call('sendMessage', data=payload)
        # Si fallara por etiquetas HTML no reconocidas, intentar como texto plano
        if not resp.get('ok') and 'can\'t parse entities' in resp.get('description', '').lower():
            payload.pop('parse_mode', None)
            resp = cls.api_call('sendMessage', data=payload)
        return resp

    @classmethod
    def editar_mensaje(cls, chat_id, message_id, texto_html, reply_markup=None):
        """Edita un mensaje existente en su sitio para evitar saturar el chat de Telegram."""
        if not chat_id or not message_id:
            return cls.enviar_mensaje(chat_id, texto_html, reply_markup=reply_markup)

        import json
        payload = {
            'chat_id': str(chat_id),
            'message_id': int(message_id),
            'text': texto_html,
            'parse_mode': 'HTML',
            'disable_web_page_preview': True
        }
        if reply_markup is not None:
            payload['reply_markup'] = json.dumps(reply_markup)

        resp = cls.api_call('editMessageText', data=payload)
        # Si Telegram rechaza la edición (ej. contenido idéntico o mensaje no encontrado), manejar limpiamente
        if not resp.get('ok'):
            desc = resp.get('description', '').lower()
            if 'message is not modified' in desc:
                return {'ok': True, 'description': 'No modificado.'}
            # Fallback seguro: enviar como mensaje nuevo
            return cls.enviar_mensaje(chat_id, texto_html, reply_markup=reply_markup)
        return resp

    @classmethod
    def enviar_documento_excel(cls, chat_id, buffer_bytes, nombre_archivo="Reporte_Ejecutivo_RH.xlsx", caption=None):
        """Envía un archivo Excel (.xlsx) generado en memoria al chat de Telegram."""
        if not chat_id or not buffer_bytes:
            return {'ok': False, 'description': 'Datos insuficientes para enviar documento.'}

        if isinstance(buffer_bytes, io.BytesIO):
            buffer_bytes.seek(0)
            file_data = buffer_bytes.read()
        else:
            file_data = buffer_bytes

        files = {
            'document': (
                nombre_archivo,
                file_data,
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
        }
        data = {
            'chat_id': str(chat_id),
            'caption': caption or '📊 <b>Reporte Ejecutivo Oficial • Premier Capital Humano</b>',
            'parse_mode': 'HTML'
        }
        return cls.api_call('sendDocument', data=data, files=files, timeout=30)

    @classmethod
    def responder_callback(cls, callback_query_id, texto=None, show_alert=False):
        """Responde a un callback_query de botón inline para quitar el estado de carga."""
        payload = {'callback_query_id': callback_query_id}
        if texto:
            payload['text'] = texto
            payload['show_alert'] = show_alert
        return cls.api_call('answerCallbackQuery', data=payload)

    # -------------------------------------------------------------------------
    # 2. VINCULACIÓN Y AUTORIZACIÓN SEGURA
    # -------------------------------------------------------------------------

    @classmethod
    def generar_token_vinculacion(cls, usuario):
        """
        Genera un token temporal seguro de 1 solo clic para vincular la cuenta.
        Retorna (token, url_deep_link).
        """
        perfil = usuario.perfilusuario
        token = str(uuid.uuid4()).replace('-', '')[:24]
        perfil.telegram_token_enlace = token
        perfil.save(update_fields=['telegram_token_enlace'])

        bot_user = cls.get_bot_username()
        deep_link = f"https://t.me/{bot_user}?start={token}"
        return token, deep_link

    @classmethod
    def vincular_usuario_por_token(cls, token, chat_id, telegram_username=''):
        """
        Valida el token recibido en /start <token>, verifica permisos directivos
        y guarda el chat_id en el PerfilUsuario.
        """
        from .models import PerfilUsuario, RegistroActividad
        from .permissions import puede_administrar_rh, es_gerente_ch

        token = (token or '').strip()
        if not token:
            return False, None, "Token de vinculación no proporcionado."

        perfil = PerfilUsuario.objects.select_related('usuario').filter(telegram_token_enlace=token).first()
        if not perfil:
            return False, None, "El enlace de vinculación es inválido o ya expiró. Por favor genera uno nuevo desde el portal web."

        usuario = perfil.usuario
        # Regla de seguridad: Solo directores, gerentes CH o superusuarios
        if not (usuario.is_superuser or puede_administrar_rh(usuario) or es_gerente_ch(usuario)):
            return False, usuario, "Acceso no autorizado: Este servicio de reportería ejecutiva es exclusivo para la Dirección y Gerencias de Capital Humano."

        # Desvincular cualquier cuenta que previamente tuviera este chat_id
        PerfilUsuario.objects.filter(telegram_chat_id=str(chat_id)).exclude(id=perfil.id).update(
            telegram_chat_id=None,
            telegram_username=None
        )

        perfil.telegram_chat_id = str(chat_id)
        perfil.telegram_username = (telegram_username or '').lstrip('@')
        perfil.telegram_token_enlace = None
        perfil.notificaciones_telegram = True
        perfil.save(update_fields=['telegram_chat_id', 'telegram_username', 'telegram_token_enlace', 'notificaciones_telegram'])

        RegistroActividad.objects.create(
            usuario=usuario,
            accion="Vinculación Telegram",
            tipo_objeto="User",
            id_objeto=usuario.id,
            detalles=f"Usuario {usuario.username} vinculó Telegram (Chat ID: {chat_id}, @{perfil.telegram_username})."
        )
        return True, usuario, "¡Vinculación completada exitosamente!"

    @classmethod
    def desvincular_usuario(cls, usuario):
        """Remueve la asociación de Telegram para un usuario."""
        from .models import RegistroActividad
        perfil = getattr(usuario, 'perfilusuario', None)
        if perfil and perfil.telegram_chat_id:
            chat_id = perfil.telegram_chat_id
            perfil.telegram_chat_id = None
            perfil.telegram_username = None
            perfil.telegram_token_enlace = None
            perfil.save(update_fields=['telegram_chat_id', 'telegram_username', 'telegram_token_enlace'])

            RegistroActividad.objects.create(
                usuario=usuario,
                accion="Desvinculación Telegram",
                tipo_objeto="User",
                id_objeto=usuario.id,
                detalles=f"Usuario {usuario.username} desvinculó su cuenta de Telegram ({chat_id})."
            )
            return True
        return False

    @classmethod
    def obtener_usuario_por_chat_id(cls, chat_id):
        """Retorna el objeto User vinculado a un chat_id, o None."""
        from .models import PerfilUsuario
        perfil = PerfilUsuario.objects.select_related('usuario').filter(telegram_chat_id=str(chat_id)).first()
        if perfil and perfil.usuario.is_active:
            return perfil.usuario
        return None

    # -------------------------------------------------------------------------
    # 3. GENERADORES DE REPORTES EJECUTIVOS (BUSINESS INTELLIGENCE)
    # -------------------------------------------------------------------------

    @classmethod
    def generar_resumen_ejecutivo_texto(cls, usuario=None):
        """
        Snapshot ejecutivo de métricas clave con mínima carga cognitiva.
        Utiliza ReportesService para máxima consistencia con el dashboard web.
        """
        from .services import ReportesService
        from .models import Proceso

        qs_puestos = ReportesService.get_base_queryset(usuario)
        lista_puestos = list(qs_puestos)
        kpis = ReportesService.compute_kpis(lista_puestos)

        ahora = timezone.now()
        mes_inicio = ahora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        contrataciones_mes = Proceso.objects.filter(
            estatus_proceso=Proceso.Estatus.CONTRATADO,
            fecha_inicio_etapa__gte=mes_inicio
        ).count()

        limite_7d = ahora - timedelta(days=7)
        terminales = [
            Proceso.Estatus.CONTRATADO,
            Proceso.Estatus.DESCARTADO_CH,
            Proceso.Estatus.NO_PRUEBAS,
            Proceso.Estatus.ABANDONO,
        ]
        estancados_count = Proceso.objects.filter(
            fecha_inicio_etapa__lte=limite_7d
        ).exclude(estatus_proceso__in=terminales).count()

        fecha_str = ahora.strftime("%d/%b • %H:%M hrs")
        total = kpis.get('total_abiertas', 0)
        en_tiempo = kpis.get('en_tiempo_total', 0)
        en_riesgo = kpis.get('en_riesgo_total', 0)
        vencidas = kpis.get('vencidas_total', 0)
        tiempo_prom = kpis.get('tiempo_promedio_cobertura', 0)
        sin_cand = kpis.get('puestos_sin_candidatos', 0)

        msg = (
            f"📊 <b>Resumen Ejecutivo • Capital Humano</b>\n"
            f"<i>Corte: {fecha_str}</i>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>ESTATUS GLOBAL DE VACANTES:</b> <b>{total}</b> plazas\n"
            f"🟢 {en_tiempo} en tiempo │ 🟡 {en_riesgo} en riesgo │ 🔴 {vencidas} vencidas\n\n"
            f"⚡ <b>Velocidad:</b> {tiempo_prom:.1f}d promedio (Meta: ≤20d)\n"
            f"🎉 <b>Ingresos del mes:</b> <b>{contrataciones_mes}</b> contratados\n"
            f"⚠️ <b>Atención:</b> {estancados_count} detenidos (+7d) • {sin_cand} sin candidatos\n\n"
            f"<i>💡 Usa los botones abajo para filtrar por Ciudad, Asesora o Agencia.</i>"
        )
        return msg

    @classmethod
    def generar_vacantes_agencias_texto(cls, usuario=None):
        """Desglose de plazas abiertas agrupadas por Ciudad y Agencia."""
        from .services import ReportesService
        from .models import Puesto

        qs = ReportesService.get_base_queryset(usuario).filter(
            esta_abierto=True,
            estatus_autorizacion='AUTORIZADO'
        ).select_related('marca')

        if not qs.exists():
            return "🏢 <b>VACANTES ABIERTAS POR AGENCIA</b>\n\nActualmente no hay vacantes abiertas en el grupo."

        dict_ciudades = dict(Puesto.CIUDADES_CHOICES)

        # Agrupar por ciudad -> agencias
        ciudades_map = {}
        for p in qs:
            cd_nombre = dict_ciudades.get(p.ciudad, p.ciudad) or 'Otras Plazas'
            agencia = p.agencia or 'Sin Agencia'
            if cd_nombre not in ciudades_map:
                ciudades_map[cd_nombre] = {'total': 0, 'agencias': {}}
            ciudades_map[cd_nombre]['total'] += p.cantidad_vacantes

            if agencia not in ciudades_map[cd_nombre]['agencias']:
                ciudades_map[cd_nombre]['agencias'][agencia] = {'total': 0, 'vencidas': 0}
            ciudades_map[cd_nombre]['agencias'][agencia]['total'] += p.cantidad_vacantes
            if p.dias_transcurridos > (p.dias_meta or 20):
                ciudades_map[cd_nombre]['agencias'][agencia]['vencidas'] += p.cantidad_vacantes

        msg = "🏢 <b>VACANTES ABIERTAS POR AGENCIA Y CIUDAD</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        for cd, data in sorted(ciudades_map.items(), key=lambda x: x[1]['total'], reverse=True):
            msg += f"📍 <b>{cd.upper()} ({data['total']} plazas):</b>\n"
            for ag, ag_info in sorted(data['agencias'].items(), key=lambda x: x[1]['total'], reverse=True)[:6]:
                alerta = f" (🔴 {ag_info['vencidas']} venc.)" if ag_info['vencidas'] > 0 else ""
                msg += f" • {ag}: <b>{ag_info['total']}</b>{alerta}\n"
            msg += "\n"

        msg += "<i>💡 Toca «🔍 Filtrar» para consultar una ciudad o agencia específica.</i>"
        return msg

    @classmethod
    def generar_alertas_sla_texto(cls, usuario=None):
        """Detalle prioritario de vacantes críticas vencidas o próximas a vencer (SLA)."""
        from .services import ReportesService
        qs = ReportesService.get_base_queryset(usuario).filter(
            esta_abierto=True,
            estatus_autorizacion='AUTORIZADO'
        ).select_related('titulo', 'marca', 'asesora_encargada')

        vencidas = []
        en_riesgo = []

        for p in qs:
            dias = p.dias_transcurridos
            meta = p.dias_meta or 20
            diff = meta - dias

            asesora_nom = (
                p.asesora_encargada.first_name or p.asesora_encargada.username
                if p.asesora_encargada else 'Sin asignar'
            )
            titulo_nom = p.titulo.nombre if p.titulo else 'Puesto'
            agencia_nom = p.agencia or 'General'

            info = {
                'titulo': titulo_nom,
                'agencia': agencia_nom,
                'dias': dias,
                'meta': meta,
                'asesora': asesora_nom,
                'exceso': abs(diff),
                'restantes': diff
            }

            if diff < 0:
                vencidas.append(info)
            elif diff <= 4:
                en_riesgo.append(info)

        vencidas.sort(key=lambda x: x['exceso'], reverse=True)
        en_riesgo.sort(key=lambda x: x['restantes'])

        msg = "⏱️ <b>MONITOREO DE TIEMPOS DE COBERTURA (SLA)</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"

        if vencidas:
            msg += f"🔴 <b>VACANTES VENCIDAS SLA ({len(vencidas)} plazas):</b>\n"
            for v in vencidas[:10]:
                msg += f"• <b>{v['titulo']}</b> ({v['agencia']}) │ <b>+{v['exceso']}d</b> ({v['dias']}/{v['meta']}d) • 👤 {v['asesora']}\n"
            if len(vencidas) > 10:
                msg += f"<i>...y {len(vencidas) - 10} más (usa Filtros para ver por Asesora).</i>\n"
            msg += "\n"
        else:
            msg += "🟢 <b>0 vacantes vencidas en el grupo.</b>\n\n"

        if en_riesgo:
            msg += f"🟡 <b>EN RIESGO CRÍTICO (≤4d restantes - {len(en_riesgo)} plazas):</b>\n"
            for r in en_riesgo[:8]:
                msg += f"• <b>{r['titulo']}</b> ({r['agencia']}) │ <b>{r['restantes']}d rest.</b> ({r['dias']}/{r['meta']}d) • 👤 {r['asesora']}\n"
            if len(en_riesgo) > 8:
                msg += f"<i>...y {len(en_riesgo) - 8} más.</i>\n"
        else:
            msg += "🟢 <b>0 vacantes en semáforo amarillo próximo.</b>\n"

        return msg

    @classmethod
    def generar_estancados_texto(cls, usuario=None):
        """Candidatos con más de 7 días sin avance en etapa, agrupados por Asesora."""
        from .models import Proceso
        ahora = timezone.now()
        limite_7d = ahora - timedelta(days=7)
        terminales = [
            Proceso.Estatus.CONTRATADO,
            Proceso.Estatus.DESCARTADO_CH,
            Proceso.Estatus.NO_PRUEBAS,
            Proceso.Estatus.ABANDONO,
        ]

        estancados = Proceso.objects.filter(
            fecha_inicio_etapa__lte=limite_7d
        ).exclude(
            estatus_proceso__in=terminales
        ).select_related(
            'candidato', 'puesto', 'puesto__titulo', 'asesora_asignada'
        ).order_by('fecha_inicio_etapa')

        total_estancados = estancados.count()
        if total_estancados == 0:
            return "⚠️ <b>PROCESOS ESTANCADOS</b>\n\n🟢 ¡Excelente! No hay candidatos con más de 7 días detenidos en la misma etapa."

        # Agrupar por asesora
        asesoras_map = {}
        for proc in estancados[:18]:
            dias = (ahora - proc.fecha_inicio_etapa).days
            asesora_nom = (
                proc.asesora_asignada.first_name or proc.asesora_asignada.username
                if proc.asesora_asignada else "Sin asignar"
            )
            cand_nom = proc.candidato.nombre_completo if proc.candidato else "Candidato"
            puesto_nom = proc.puesto.titulo.nombre if (proc.puesto and proc.puesto.titulo) else "Vacante"
            agencia_nom = proc.puesto.agencia if proc.puesto else "General"
            etapa_nom = proc.get_estatus_proceso_display()

            if asesora_nom not in asesoras_map:
                asesoras_map[asesora_nom] = []
            asesoras_map[asesora_nom].append({
                'cand': cand_nom,
                'puesto': puesto_nom,
                'agencia': agencia_nom,
                'dias': dias,
                'etapa': etapa_nom
            })

        msg = (
            f"⚠️ <b>PROCESOS ESTANCADOS (+7 DÍAS EN ETAPA)</b>\n"
            f"<b>{total_estancados} candidatos</b> requieren seguimiento urgente\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )
        for asesora, lista in asesoras_map.items():
            msg += f"👤 <b>{asesora} ({len(lista)}):</b>\n"
            for item in lista:
                msg += f" • <b>{item['cand']}</b> (<b>{item['dias']}d</b>) • {item['etapa']}\n   ↳ {item['puesto']} ({item['agencia']})\n"
            msg += "\n"

        return msg

    @classmethod
    def generar_contrataciones_mes_texto(cls, usuario=None):
        """Lista compacta de ingresos exitosos del mes en curso."""
        from .models import Proceso
        ahora = timezone.now()
        mes_inicio = ahora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        nombre_mes = ahora.strftime('%B').upper()

        contratados = Proceso.objects.filter(
            estatus_proceso=Proceso.Estatus.CONTRATADO,
            fecha_inicio_etapa__gte=mes_inicio
        ).select_related('candidato', 'puesto', 'puesto__titulo', 'asesora_asignada').order_by('-fecha_inicio_etapa')

        total = contratados.count()
        if total == 0:
            return f"🎉 <b>CONTRATACIONES DE {nombre_mes}</b>\n\nAún no se registran contrataciones en lo que va del mes."

        msg = (
            f"🎉 <b>CONTRATACIONES DE {nombre_mes}</b>\n"
            f"<b>{total} ingresos concretados</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )
        for c in contratados[:15]:
            cand = c.candidato.nombre_completo if c.candidato else "Colaborador"
            puesto = c.puesto.titulo.nombre if (c.puesto and c.puesto.titulo) else "Puesto"
            agencia = c.puesto.agencia if c.puesto else "Agencia"
            fecha_ingreso = c.fecha_inicio_etapa.strftime("%d/%b")
            msg += f"• <b>{cand}</b> ({fecha_ingreso}) │ {puesto} • {agencia}\n"

        return msg

    # -------------------------------------------------------------------------
    # 3.1 FICHAS EJECUTIVAS FILTRADAS POR DIMENSIÓN (CIUDAD / ASESORA / AGENCIA)
    # -------------------------------------------------------------------------

    @classmethod
    def generar_ficha_ciudad_texto(cls, ciudad_query, usuario=None):
        """Ficha ejecutiva condensada para una ciudad específica."""
        from .services import ReportesService
        from .models import Puesto

        dict_ciudades = dict(Puesto.CIUDADES_CHOICES)
        cd_code = None
        cd_nombre = None
        q_norm = str(ciudad_query).strip().lower()

        for code, name in Puesto.CIUDADES_CHOICES:
            if code.lower() == q_norm or name.lower() == q_norm or q_norm in name.lower():
                cd_code = code
                cd_nombre = name
                break

        if not cd_code:
            cd_code = ciudad_query.upper()
            cd_nombre = dict_ciudades.get(cd_code, cd_code)

        qs = ReportesService.get_base_queryset(usuario).filter(
            esta_abierto=True,
            estatus_autorizacion='AUTORIZADO',
            ciudad=cd_code
        ).select_related('titulo', 'marca', 'asesora_encargada')

        total = qs.count()
        if total == 0:
            return f"📍 <b>FICHA DE CIUDAD: {cd_nombre.upper()}</b>\n\n🟢 0 vacantes abiertas en esta plaza."

        en_tiempo = 0
        en_riesgo = 0
        vencidas = 0
        agencias = {}
        asesoras = set()
        alertas = []

        for p in qs:
            dias = p.dias_transcurridos
            meta = p.dias_meta or 20
            diff = meta - dias

            ag = p.agencia or "Sin Agencia"
            if ag not in agencias:
                agencias[ag] = {'total': 0, 'vencidas': 0}
            agencias[ag]['total'] += p.cantidad_vacantes

            if p.asesora_encargada:
                asesoras.add(p.asesora_encargada.first_name or p.asesora_encargada.username)

            if diff < 0:
                vencidas += p.cantidad_vacantes
                agencias[ag]['vencidas'] += p.cantidad_vacantes
                alertas.append({
                    'titulo': p.titulo.nombre if p.titulo else 'Puesto',
                    'ag': ag,
                    'dias': dias,
                    'meta': meta,
                    'exceso': abs(diff),
                    'asesora': p.asesora_encargada.first_name if p.asesora_encargada else 'Sin asignar'
                })
            elif diff <= 4:
                en_riesgo += p.cantidad_vacantes
            else:
                en_tiempo += p.cantidad_vacantes

        msg = (
            f"📍 <b>FICHA DE CIUDAD: {cd_nombre.upper()}</b>\n"
            f"<b>{total} vacantes abiertas</b> │ 🟢 {en_tiempo} │ 🟡 {en_riesgo} │ 🔴 {vencidas}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🏢 <b>Agencias en la plaza:</b>\n"
        )
        for ag, ag_info in sorted(agencias.items(), key=lambda x: x[1]['total'], reverse=True):
            alerta = f" (🔴 {ag_info['vencidas']} venc.)" if ag_info['vencidas'] > 0 else ""
            msg += f" • {ag}: <b>{ag_info['total']}</b> plazas{alerta}\n"

        if asesoras:
            msg += f"\n👤 <b>Asesoras a cargo:</b> {', '.join(sorted(asesoras))}\n"

        if alertas:
            msg += f"\n🔴 <b>Alertas Críticas (>20d SLA):</b>\n"
            for a in alertas[:5]:
                msg += f" • <b>{a['titulo']}</b> ({a['ag']}) │ <b>+{a['exceso']}d</b> • 👤 {a['asesora']}\n"

        return msg

    @classmethod
    def generar_scorecard_asesora_texto(cls, asesora_id_or_name, usuario=None):
        """Scorecard de productividad y SLAs para una asesora de atracción de talento."""
        from .services import ReportesService
        from .models import Proceso
        from django.contrib.auth.models import User

        asesora = None
        if str(asesora_id_or_name).isdigit():
            asesora = User.objects.filter(id=int(asesora_id_or_name)).first()
        else:
            q_norm = str(asesora_id_or_name).strip()
            asesora = User.objects.filter(
                Q(username__icontains=q_norm) |
                Q(first_name__icontains=q_norm) |
                Q(last_name__icontains=q_norm)
            ).first()

        if not asesora:
            return f"👤 <b>ASESORA DE TALENTO</b>\n\nNo se encontró asesora con el identificador «{asesora_id_or_name}»."

        nombre = asesora.get_full_name() or asesora.username

        qs = ReportesService.get_base_queryset(usuario).filter(
            esta_abierto=True,
            estatus_autorizacion='AUTORIZADO',
            asesora_encargada=asesora
        ).select_related('titulo', 'marca')

        total = qs.count()
        ahora = timezone.now()
        mes_inicio = ahora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        contrataciones = Proceso.objects.filter(
            asesora_asignada=asesora,
            estatus_proceso=Proceso.Estatus.CONTRATADO,
            fecha_inicio_etapa__gte=mes_inicio
        ).count()

        limite_7d = ahora - timedelta(days=7)
        terminales = [
            Proceso.Estatus.CONTRATADO,
            Proceso.Estatus.DESCARTADO_CH,
            Proceso.Estatus.NO_PRUEBAS,
            Proceso.Estatus.ABANDONO,
        ]
        estancados = Proceso.objects.filter(
            asesora_asignada=asesora,
            fecha_inicio_etapa__lte=limite_7d
        ).exclude(estatus_proceso__in=terminales).count()

        en_tiempo = 0
        en_riesgo = 0
        vencidas = 0
        dias_totales = 0
        criticas = []

        for p in qs:
            dias = p.dias_transcurridos
            dias_totales += dias
            meta = p.dias_meta or 20
            diff = meta - dias
            if diff < 0:
                vencidas += p.cantidad_vacantes
                criticas.append({
                    'titulo': p.titulo.nombre if p.titulo else 'Puesto',
                    'ag': p.agencia or 'General',
                    'exceso': abs(diff),
                    'dias': dias,
                    'meta': meta
                })
            elif diff <= 4:
                en_riesgo += p.cantidad_vacantes
            else:
                en_tiempo += p.cantidad_vacantes

        promedio = (dias_totales / total) if total > 0 else 0

        msg = (
            f"👤 <b>SCORECARD: {nombre.upper()}</b>\n"
            f"<b>{total} vacantes asignadas</b> │ 🟢 {en_tiempo} │ 🟡 {en_riesgo} │ 🔴 {vencidas}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"⚡ <b>SLA Promedio Actual:</b> {promedio:.1f} días\n"
            f"🎉 <b>Ingresos del mes:</b> {contrataciones} ingresos\n"
            f"⚠️ <b>Candidatos detenidos (+7d):</b> {estancados}\n"
        )

        if criticas:
            msg += f"\n🔴 <b>Vacantes Críticas Vencidas:</b>\n"
            for c in criticas[:6]:
                msg += f" • <b>{c['titulo']}</b> ({c['ag']}) │ <b>+{c['exceso']}d</b> ({c['dias']}/{c['meta']}d)\n"

        return msg

    @classmethod
    def generar_ficha_agencia_texto(cls, agencia_query, usuario=None):
        """Ficha condensada de vacantes abiertas en una agencia específica."""
        from .services import ReportesService
        from .models import Puesto

        q_norm = str(agencia_query).strip()
        qs = ReportesService.get_base_queryset(usuario).filter(
            esta_abierto=True,
            estatus_autorizacion='AUTORIZADO',
            agencia__icontains=q_norm
        ).select_related('titulo', 'marca', 'asesora_encargada')

        if not qs.exists():
            return f"🏢 <b>AGENCIA: {agencia_query.upper()}</b>\n\n🟢 0 vacantes abiertas en esta agencia."

        agencia_real = qs.first().agencia
        dict_ciudades = dict(Puesto.CIUDADES_CHOICES)
        ciudad_nombre = dict_ciudades.get(qs.first().ciudad, qs.first().ciudad)

        total = qs.count()
        en_tiempo = 0
        en_riesgo = 0
        vencidas = 0
        vacantes_list = []

        for p in qs:
            dias = p.dias_transcurridos
            meta = p.dias_meta or 20
            diff = meta - dias

            if diff < 0:
                vencidas += p.cantidad_vacantes
                tag = f"🔴 +{abs(diff)}d"
            elif diff <= 4:
                en_riesgo += p.cantidad_vacantes
                tag = f"🟡 {diff}d rest."
            else:
                en_tiempo += p.cantidad_vacantes
                tag = "🟢 OK"

            asesora = p.asesora_encargada.first_name if p.asesora_encargada else "Sin asignar"
            vacantes_list.append(f" • <b>{p.titulo.nombre if p.titulo else 'Puesto'}</b> │ {tag} • 👤 {asesora}")

        msg = (
            f"🏢 <b>FICHA AGENCIA: {agencia_real.upper()}</b>\n"
            f"<i>Plaza: {ciudad_nombre}</i>\n"
            f"<b>{total} vacantes activas</b> │ 🟢 {en_tiempo} │ 🟡 {en_riesgo} │ 🔴 {vencidas}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📋 <b>Plazas en Proceso:</b>\n"
        )
        for line in vacantes_list[:12]:
            msg += f"{line}\n"

        return msg

    @classmethod
    def generar_excel_buffer(cls, usuario=None):
        """Genera el reporte ejecutivo oficial en Excel .xlsx llamando a ReportesService."""
        from .services import ReportesService
        buffer = ReportesService.generar_excel_resumen_ejecutivo({}, usuario)
        fecha_tag = timezone.now().strftime("%Y%m%d_%H%M")
        nombre_archivo = f"Reporte_Ejecutivo_Premier_{fecha_tag}.xlsx"
        return buffer, nombre_archivo

    @classmethod
    def generar_excel_filtrado_buffer(cls, tipo, valor, usuario=None):
        """Genera el Excel oficial filtrado específicamente por ciudad, asesora o agencia."""
        from .services import ReportesService
        filtros = {}
        if tipo == 'ciudad':
            filtros['ciudad'] = str(valor)
        elif tipo == 'asesora':
            filtros['asesora'] = str(valor)
        elif tipo == 'agencia':
            filtros['agencia'] = str(valor)

        buffer = ReportesService.generar_excel_resumen_ejecutivo(filtros, usuario)
        fecha_tag = timezone.now().strftime("%Y%m%d_%H%M")
        nombre_archivo = f"Reporte_{tipo}_{valor}_{fecha_tag}.xlsx"
        return buffer, nombre_archivo

    # -------------------------------------------------------------------------
    # 4. TECLADOS INTERACTIVOS (INLINE KEYBOARDS)
    # -------------------------------------------------------------------------

    @classmethod
    def obtener_teclado_ejecutivo(cls):
        """Teclado inline interactivo principal con accesos directos y filtros."""
        return {
            'inline_keyboard': [
                [
                    {'text': '📊 Resumen General', 'callback_data': 'cmd_resumen'},
                    {'text': '⏱️ Alertas SLA', 'callback_data': 'cmd_sla'}
                ],
                [
                    {'text': '🏢 Por Agencia y Ciudad', 'callback_data': 'cmd_agencias'},
                    {'text': '🔍 Filtrar por...', 'callback_data': 'flt_menu'}
                ],
                [
                    {'text': '⚠️ Estancados', 'callback_data': 'cmd_estancados'},
                    {'text': '🎉 Contrataciones', 'callback_data': 'cmd_contrataciones'}
                ],
                [
                    {'text': '📥 Descargar Excel Global', 'callback_data': 'cmd_excel'}
                ]
            ]
        }

    @classmethod
    def obtener_teclado_menu_filtros(cls):
        """Menú selector de dimensión a filtrar."""
        return {
            'inline_keyboard': [
                [
                    {'text': '📍 Por Ciudad', 'callback_data': 'flt_tipo:ciudad'},
                    {'text': '👤 Por Asesora', 'callback_data': 'flt_tipo:asesora'}
                ],
                [
                    {'text': '🏢 Por Agencia', 'callback_data': 'flt_tipo:agencia'}
                ],
                [
                    {'text': '⬅️ Menú Principal', 'callback_data': 'menu_principal'}
                ]
            ]
        }

    @classmethod
    def obtener_teclado_ciudades(cls, usuario=None):
        """Genera botones dinámicos con las ciudades que tienen plazas abiertas."""
        from .services import ReportesService
        from .models import Puesto
        from django.db.models import Sum

        dict_ciudades = dict(Puesto.CIUDADES_CHOICES)
        ciudades_qs = ReportesService.get_base_queryset(usuario).filter(
            esta_abierto=True,
            estatus_autorizacion='AUTORIZADO'
        ).values('ciudad').annotate(total=Sum('cantidad_vacantes')).order_by('-total')

        buttons = []
        row = []
        for item in ciudades_qs:
            code = item['ciudad']
            total = item['total'] or 1
            nombre = dict_ciudades.get(code, code)
            row.append({'text': f"📍 {nombre} ({total})", 'callback_data': f"flt_cd:{code}"})
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)

        buttons.append([
            {'text': '⬅️ Volver a Filtros', 'callback_data': 'flt_menu'},
            {'text': '🏠 Menú', 'callback_data': 'menu_principal'}
        ])
        return {'inline_keyboard': buttons}

    @classmethod
    def obtener_teclado_asesoras(cls, usuario=None):
        """Genera botones dinámicos con las asesoras que tienen vacantes asignadas."""
        from .services import ReportesService
        from django.db.models import Sum

        asesoras_qs = ReportesService.get_base_queryset(usuario).filter(
            esta_abierto=True,
            estatus_autorizacion='AUTORIZADO',
            asesora_encargada__isnull=False
        ).values(
            'asesora_encargada__id',
            'asesora_encargada__first_name',
            'asesora_encargada__username'
        ).annotate(total=Sum('cantidad_vacantes')).order_by('-total')

        buttons = []
        row = []
        for item in asesoras_qs:
            u_id = item['asesora_encargada__id']
            nom = item['asesora_encargada__first_name'] or item['asesora_encargada__username']
            total = item['total'] or 1
            row.append({'text': f"👤 {nom} ({total})", 'callback_data': f"flt_as:{u_id}"})
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)

        buttons.append([
            {'text': '⬅️ Volver a Filtros', 'callback_data': 'flt_menu'},
            {'text': '🏠 Menú', 'callback_data': 'menu_principal'}
        ])
        return {'inline_keyboard': buttons}

    @classmethod
    def obtener_teclado_agencias(cls, usuario=None):
        """Genera botones dinámicos con las agencias con más plazas abiertas."""
        from .services import ReportesService
        from django.db.models import Sum

        agencias_qs = ReportesService.get_base_queryset(usuario).filter(
            esta_abierto=True,
            estatus_autorizacion='AUTORIZADO'
        ).values('agencia').annotate(total=Sum('cantidad_vacantes')).order_by('-total')[:10]

        buttons = []
        row = []
        for item in agencias_qs:
            ag = item['agencia']
            total = item['total'] or 1
            texto_btn = (ag[:18] + '..') if len(ag) > 20 else ag
            row.append({'text': f"🏢 {texto_btn} ({total})", 'callback_data': f"flt_ag:{ag[:24]}"})
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)

        buttons.append([
            {'text': '⬅️ Volver a Filtros', 'callback_data': 'flt_menu'},
            {'text': '🏠 Menú', 'callback_data': 'menu_principal'}
        ])
        return {'inline_keyboard': buttons}

    @classmethod
    def obtener_teclado_detalle_filtro(cls, tipo, valor):
        """Botones de acción al consultar el detalle de una dimensión."""
        return {
            'inline_keyboard': [
                [
                    {'text': f"📥 Descargar Excel de {tipo.capitalize()}", 'callback_data': f"cmd_excel_filtro:{tipo}:{valor}"}
                ],
                [
                    {'text': '🔄 Cambiar Filtro', 'callback_data': f"flt_tipo:{tipo}"},
                    {'text': '🏠 Menú Principal', 'callback_data': 'menu_principal'}
                ]
            ]
        }

    # -------------------------------------------------------------------------
    # 5. ALERTAS EN TIEMPO REAL (NOTIFICACIONES DE IMPACTO)
    # -------------------------------------------------------------------------

    @classmethod
    def notificar_plaza_cubierta(cls, proceso):
        """Notifica a todos los directivos y gerentes suscritos cuando se cubre una vacante."""
        from .models import PerfilUsuario
        if not cls.is_configured():
            return 0

        puesto = proceso.puesto
        if not puesto:
            return 0

        candidato_nombre = proceso.candidato.nombre_completo if proceso.candidato else "Colaborador"
        puesto_nombre = puesto.titulo.nombre if puesto.titulo else "Vacante"
        agencia = puesto.agencia or "Premier Automotriz"
        dias = puesto.dias_transcurridos
        meta = puesto.dias_meta or 20
        asesora = puesto.asesora_encargada.get_full_name() if puesto.asesora_encargada else "Capital Humano"

        texto = (
            f"🎉 <b>¡PLAZA CUBIERTA EXITOSAMENTE!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"• <b>Puesto:</b> {puesto_nombre}\n"
            f"• <b>Agencia:</b> {agencia}\n"
            f"• <b>Colaborador:</b> {candidato_nombre}\n"
            f"• <b>Tiempo de Cobertura:</b> {dias} días (Meta: {meta}d)\n"
            f"• <b>Asesora Encargada:</b> {asesora}\n\n"
            f"<i>La vacante ha sido cerrada automáticamente en el sistema.</i>"
        )

        destinatarios = PerfilUsuario.objects.filter(
            telegram_chat_id__isnull=False,
            notificaciones_telegram=True,
            recibir_alertas_criticas=True,
            usuario__is_active=True
        ).values_list('telegram_chat_id', flat=True)

        enviados = 0
        for chat_id in destinatarios:
            res = cls.enviar_mensaje(chat_id, texto)
            if res.get('ok'):
                enviados += 1
        return enviados

    @classmethod
    def notificar_requisicion_creada(cls, puesto):
        """Notifica a la Dirección cuando se abre una requisición de puesto."""
        from .models import PerfilUsuario
        if not cls.is_configured():
            return 0

        titulo = puesto.titulo.nombre if puesto.titulo else "Vacante"
        agencia = puesto.agencia or "Premier Automotriz"
        motivo = puesto.get_motivo_requisicion_display() if hasattr(puesto, 'get_motivo_requisicion_display') else "Requisición"
        solicitante = puesto.nombre_jefe_inmediato or "Gerencia Operativa"
        sueldo = f"${puesto.sueldo_base:,.2f}" if puesto.sueldo_base else "A convenir"

        texto = (
            f"📝 <b>NUEVA REQUISICIÓN DE PERSONAL REGISTRADA</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"• <b>Puesto:</b> {titulo}\n"
            f"• <b>Agencia:</b> {agencia}\n"
            f"• <b>Motivo:</b> {motivo}\n"
            f"• <b>Solicitante:</b> {solicitante}\n"
            f"• <b>Sueldo Propuesto:</b> {sueldo}\n"
            f"• <b>Días Meta SLA:</b> {puesto.dias_meta or 20} días\n"
        )

        destinatarios = PerfilUsuario.objects.filter(
            telegram_chat_id__isnull=False,
            notificaciones_telegram=True,
            recibir_alertas_criticas=True,
            usuario__is_active=True
        ).values_list('telegram_chat_id', flat=True)

        enviados = 0
        for chat_id in destinatarios:
            res = cls.enviar_mensaje(chat_id, texto)
            if res.get('ok'):
                enviados += 1
        return enviados

