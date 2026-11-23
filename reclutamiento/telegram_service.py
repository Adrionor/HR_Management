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
        Snapshot completo de métricas operativas y estado de SLAs para Dirección.
        Utiliza ReportesService para máxima consistencia con el dashboard web.
        """
        from .services import ReportesService
        from .models import Puesto, Proceso

        # Si el usuario es directivo, ve la visión global corporativa
        qs_puestos = ReportesService.get_base_queryset(usuario)
        lista_puestos = list(qs_puestos)
        kpis = ReportesService.compute_kpis(lista_puestos)

        # Conteo de contrataciones en el mes actual
        ahora = timezone.now()
        mes_inicio = ahora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        contrataciones_mes = Proceso.objects.filter(
            estatus_proceso=Proceso.Estatus.CONTRATADO,
            fecha_inicio_etapa__gte=mes_inicio
        ).count()

        # Candidatos detenidos (+7 días sin avance)
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

        fecha_str = ahora.strftime("%d/%b/%Y • %H:%M hrs")

        msg = (
            f"🏢 <b>PREMIER AUTOMOTRIZ • CAPITAL HUMANO</b>\n"
            f"<i>Resumen Ejecutivo • {fecha_str}</i>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"<b>📊 ESTATUS GLOBAL DE VACANTES:</b>\n"
            f"• Total Abiertas: <b>{kpis.get('total_abiertas', 0)}</b> plazas\n"
            f"• 🟢 En Tiempo: <b>{kpis.get('en_tiempo_total', 0)}</b>\n"
            f"• 🟡 En Riesgo (SLA próximo): <b>{kpis.get('en_riesgo_total', 0)}</b>\n"
            f"• 🔴 Vencidas SLA: <b>{kpis.get('vencidas_total', 0)}</b>\n\n"
            f"<b>⏱️ VELOCIDAD DE COBERTURA:</b>\n"
            f"• Promedio Real: <b>{kpis.get('tiempo_promedio_cobertura', 0):.1f} días</b> (Meta: 20d)\n"
            f"• 🎉 Contrataciones este mes: <b>{contrataciones_mes}</b> ingresos\n\n"
            f"<b>⚠️ ALERTAS OPERATIVAS:</b>\n"
            f"• Candidatos estancados (+7d): <b>{estancados_count}</b> en proceso\n"
            f"• Vacantes sin candidatos: <b>{kpis.get('puestos_sin_candidatos', 0)}</b> plazas\n"
        )
        return msg

    @classmethod
    def generar_vacantes_agencias_texto(cls, usuario=None):
        """Desglose de plazas abiertas organizadas por agencia y ciudad."""
        from .services import ReportesService
        qs = ReportesService.get_base_queryset(usuario).filter(esta_abierto=True)
        agencias_scorecard = ReportesService.compute_agencias_scorecard(list(qs))

        if not agencias_scorecard:
            return "🏢 <b>VACANTES POR AGENCIA</b>\n\nActualmente no hay vacantes abiertas en el grupo."

        msg = "🏢 <b>VACANTES ABIERTAS POR AGENCIA</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        for item in sorted(agencias_scorecard, key=lambda x: x.get('total_abiertas', 0), reverse=True)[:15]:
            nombre = item.get('agencia', 'Sin Agencia')
            abiertas = item.get('total_abiertas', 0)
            vencidas = item.get('vencidas_sla', 0)
            marca = item.get('marca', '')

            marca_tag = f"[{marca}] " if marca else ""
            alerta_txt = f" (🔴 {vencidas} vencidas)" if vencidas > 0 else " (🟢 OK)"
            msg += f"• <b>{marca_tag}{nombre}:</b> <b>{abiertas}</b> plazas{alerta_txt}\n"

        return msg

    @classmethod
    def generar_alertas_sla_texto(cls, usuario=None):
        """Detalle prioritario de vacantes vencidas o a punto de vencer."""
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

            info = {
                'titulo': p.titulo.nombre if p.titulo else 'Puesto',
                'agencia': p.agencia or 'General',
                'dias': dias,
                'meta': meta,
                'asesora': p.asesora_encargada.get_full_name() if p.asesora_encargada else (p.asesora_encargada.username if p.asesora_encargada else 'Sin asignar')
            }

            if diff < 0:
                info['exceso'] = abs(diff)
                vencidas.append(info)
            elif diff <= 4:
                info['restantes'] = diff
                en_riesgo.append(info)

        msg = "⏱️ <b>MONITOREO DE TIEMPOS DE COBERTURA (SLA)</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"

        if vencidas:
            msg += "<b>🔴 VACANTES VENCIDAS SLA:</b>\n"
            for v in vencidas[:10]:
                msg += (
                    f"• <b>{v['titulo']}</b> ({v['agencia']})\n"
                    f"   ↳ {v['dias']}d transcurridos (+{v['exceso']}d de meta {v['meta']}d) | 👤 {v['asesora']}\n"
                )
            msg += "\n"
        else:
            msg += "🟢 <b>No hay vacantes vencidas en el grupo.</b>\n\n"

        if en_riesgo:
            msg += "<b>🟡 EN RIESGO DE VENCIMIENTO (≤ 4 días):</b>\n"
            for r in en_riesgo[:10]:
                msg += (
                    f"• <b>{r['titulo']}</b> ({r['agencia']})\n"
                    f"   ↳ {r['dias']}d de {r['meta']}d ({r['restantes']}d restantes) | 👤 {r['asesora']}\n"
                )
        else:
            msg += "🟢 <b>No hay vacantes en semáforo amarillo próximo.</b>\n"

        return msg

    @classmethod
    def generar_estancados_texto(cls, usuario=None):
        """Reporte de cuellos de botella: candidatos con >7 días en la misma etapa."""
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
        ).order_by('fecha_inicio_etapa')[:12]

        if not estancados:
            return "⚠️ <b>PROCESOS ESTANCADOS</b>\n\n🟢 Excelente: No hay candidatos con más de 7 días detenidos en la misma etapa."

        msg = "⚠️ <b>CANDIDATOS ESTANCADOS (> 7 DÍAS EN ETAPA)</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        for proc in estancados:
            dias = (ahora - proc.fecha_inicio_etapa).days
            nombre_cand = proc.candidato.nombre_completo if proc.candidato else "Candidato"
            puesto_nombre = proc.puesto.titulo.nombre if (proc.puesto and proc.puesto.titulo) else "Vacante"
            agencia = proc.puesto.agencia if proc.puesto else "General"
            etapa = proc.get_estatus_proceso_display()
            asesora = proc.asesora_asignada.first_name if proc.asesora_asignada else "Sin asignar"

            msg += (
                f"• <b>{nombre_cand}</b> → {puesto_nombre} ({agencia})\n"
                f"   ↳ Etapa: <i>{etapa}</i> (<b>{dias} días detenidos</b>) | 👤 {asesora}\n"
            )

        return msg

    @classmethod
    def generar_contrataciones_mes_texto(cls, usuario=None):
        """Lista de ingresos exitosos concretados en el mes en curso."""
        from .models import Proceso
        ahora = timezone.now()
        mes_inicio = ahora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        contratados = Proceso.objects.filter(
            estatus_proceso=Proceso.Estatus.CONTRATADO,
            fecha_inicio_etapa__gte=mes_inicio
        ).select_related('candidato', 'puesto', 'puesto__titulo', 'asesora_asignada').order_by('-fecha_inicio_etapa')[:15]

        if not contratados:
            return f"🎉 <b>CONTRATACIONES DE {ahora.strftime('%B').upper()}</b>\n\nAún no se registran contrataciones en lo que va del mes."

        msg = f"🎉 <b>CONTRATACIONES CONCRETADAS EN {ahora.strftime('%B').upper()} ({len(contratados)} total)</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        for c in contratados:
            cand = c.candidato.nombre_completo if c.candidato else "Colaborador"
            puesto = c.puesto.titulo.nombre if (c.puesto and c.puesto.titulo) else "Puesto"
            agencia = c.puesto.agencia if c.puesto else "Agencia"
            fecha_ingreso = c.fecha_inicio_etapa.strftime("%d/%m")
            msg += f"• <b>{cand}</b> ({fecha_ingreso})\n   ↳ <i>{puesto}</i> • {agencia}\n"

        return msg

    @classmethod
    def generar_excel_buffer(cls, usuario=None):
        """Genera el reporte ejecutivo oficial en Excel .xlsx llamando a ReportesService."""
        from .services import ReportesService
        buffer = ReportesService.generar_excel_resumen_ejecutivo({}, usuario)
        fecha_tag = timezone.now().strftime("%Y%m%d_%H%M")
        nombre_archivo = f"Reporte_Ejecutivo_Premier_{fecha_tag}.xlsx"
        return buffer, nombre_archivo

    # -------------------------------------------------------------------------
    # 4. TECLADOS INTERACTIVOS (INLINE KEYBOARDS)
    # -------------------------------------------------------------------------

    @classmethod
    def obtener_teclado_ejecutivo(cls):
        """Teclado inline interactivo con accesos directos de BI."""
        return {
            'inline_keyboard': [
                [
                    {'text': '📊 Resumen General', 'callback_data': 'cmd_resumen'},
                    {'text': '🏢 Por Agencia', 'callback_data': 'cmd_agencias'}
                ],
                [
                    {'text': '⏱️ Alertas SLA', 'callback_data': 'cmd_sla'},
                    {'text': '⚠️ Estancados', 'callback_data': 'cmd_estancados'}
                ],
                [
                    {'text': '🎉 Contrataciones', 'callback_data': 'cmd_contrataciones'},
                    {'text': '📥 Descargar Excel', 'callback_data': 'cmd_excel'}
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

