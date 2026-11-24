"""
Servicio centralizado para la integración de Telegram Bot con Premier Automotriz RH.
Especializado en Reportería Ejecutiva (BI), Alertas de SLAs, Vacantes Críticas y Contrataciones
para la Directora de Capital Humano, Gerentes de CH y Gerencias de Marca.
"""
import io
import html
import logging
import uuid
import requests
from datetime import timedelta
from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Q, Count

logger = logging.getLogger(__name__)


def _esc(valor):
    """
    Escapa caracteres especiales (&, <, >) para evitar errores en parse_mode='HTML' de Telegram.
    Aplica a nombres de agencias, puestos, ciudades, asesoras y candidatos.
    """
    return html.escape(str(valor or ''))


def _truncar_mensaje(texto, max_len=3900):
    """
    Trunca el texto de forma segura antes de enviar a Telegram para no exceder
    el límite estricto de 4,096 caracteres de la API de Telegram.
    """
    if not texto or len(texto) <= max_len:
        return texto
    return texto[:max_len] + "\n\n<i>[... Contenido recortado por límite de longitud ...]</i>"


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
        """Envía un mensaje formateado en HTML con soporte para botones inline y truncado seguro."""
        if not chat_id:
            return {'ok': False, 'description': 'chat_id vacío.'}

        texto_seguro = _truncar_mensaje(texto_html)
        payload = {
            'chat_id': str(chat_id),
            'text': texto_seguro,
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

        texto_seguro = _truncar_mensaje(texto_html)
        import json
        payload = {
            'chat_id': str(chat_id),
            'message_id': int(message_id),
            'text': texto_seguro,
            'parse_mode': 'HTML',
            'disable_web_page_preview': True
        }
        if reply_markup is not None:
            payload['reply_markup'] = json.dumps(reply_markup)

        resp = cls.api_call('editMessageText', data=payload)
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
        """Genera un token temporal seguro de 1 solo clic para vincular la cuenta."""
        perfil = usuario.perfilusuario
        token = str(uuid.uuid4()).replace('-', '')[:24]
        perfil.telegram_token_enlace = token
        perfil.save(update_fields=['telegram_token_enlace'])

        bot_user = cls.get_bot_username()
        deep_link = f"https://t.me/{bot_user}?start={token}"
        return token, deep_link

    @classmethod
    def vincular_usuario_por_token(cls, token, chat_id, telegram_username=''):
        """Valida el token recibido en /start <token> y guarda el chat_id en PerfilUsuario."""
        from .models import PerfilUsuario, RegistroActividad
        from .permissions import puede_administrar_rh, es_gerente_ch

        token = (token or '').strip()
        if not token:
            return False, None, "Token de vinculación no proporcionado."

        perfil = PerfilUsuario.objects.select_related('usuario').filter(telegram_token_enlace=token).first()
        if not perfil:
            return False, None, "El enlace de vinculación es inválido o ya expiró. Por favor genera uno nuevo desde el portal web."

        usuario = perfil.usuario
        if not (usuario.is_superuser or puede_administrar_rh(usuario) or es_gerente_ch(usuario)):
            return False, usuario, "Acceso no autorizado: Este servicio de reportería ejecutiva es exclusivo para la Dirección y Gerencias de Capital Humano."

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
    # 3. GENERADORES DE REPORTES EJECUTIVOS (ÚNICA FUENTE DE VERDAD)
    # -------------------------------------------------------------------------

    @classmethod
    def generar_resumen_ejecutivo_texto(cls, usuario=None):
        """
        Snapshot ejecutivo de métricas clave con mínima carga cognitiva.
        Centralizado al 100% en ReportesService para exacta coincidencia con Web y Excel.
        """
        from .services import ReportesService
        from .models import Proceso

        qs_puestos = ReportesService.get_base_queryset(usuario)
        lista_puestos = list(qs_puestos.select_related('titulo', 'marca', 'asesora_encargada').prefetch_related('procesos'))
        kpis = ReportesService.compute_kpis(lista_puestos)

        ahora = timezone.now()
        mes_inicio = ahora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        contrataciones_mes = Proceso.objects.filter(
            puesto__in=lista_puestos,
            estatus_proceso=Proceso.Estatus.CONTRATADO,
            fecha_inicio_etapa__gte=mes_inicio
        ).count()

        fecha_str = ahora.strftime("%d/%b • %H:%M hrs")
        total_req = kpis.get('total_activas', 0)
        total_pl = kpis.get('plazas_activas_pendientes', 0)
        en_tiempo_req = kpis.get('en_tiempo_count', 0)
        en_tiempo_pl = kpis.get('plazas_en_tiempo_pendientes', 0)
        por_vencer_req = kpis.get('por_vencer_count', 0)
        por_vencer_pl = kpis.get('plazas_por_vencer_pendientes', 0)
        vencidas_req = kpis.get('vencidas_count', 0)
        vencidas_pl = kpis.get('plazas_vencidas_pendientes', 0)

        sla_prom = kpis.get('promedio_dias_cobertura', 0)
        cumplimiento = kpis.get('cumplimiento_sla', 0.0)
        bono_cumplido = kpis.get('vacantes_cumplio_bono', 0)
        reinicios_vac = kpis.get('vacantes_con_reinicios', 0)
        reinicios_tot = kpis.get('total_reinicios', 0)
        estancados = kpis.get('candidatos_estancados', 0)

        msg = (
            f"📊 <b>Resumen Ejecutivo • Premier Capital Humano</b>\n"
            f"<i>Corte: {fecha_str}</i>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>ESTATUS GLOBAL DE VACANTES:</b>\n"
            f"📋 <b>{total_req}</b> requisiciones (<b>{total_pl}</b> plazas pendientes)\n"
            f"🟢 {en_tiempo_req} en tiempo ({en_tiempo_pl} pl) │ 🟡 {por_vencer_req} por vencer ({por_vencer_pl} pl) │ 🔴 {vencidas_req} vencidas ({vencidas_pl} pl)\n\n"
            f"⚡ <b>SLA Promedio:</b> {sla_prom:.1f} días │ <b>Cumplimiento:</b> {cumplimiento}%\n"
            f"🎉 <b>Ingresos del mes:</b> <b>{contrataciones_mes}</b> contrataciones\n"
            f"🎯 <b>Auditoría de Bono:</b> {bono_cumplido}/{len(lista_puestos)} vacantes cumplieron meta\n"
            f"🔄 <b>Reinicios:</b> {reinicios_vac} vacantes con reinicios ({reinicios_tot} totales)\n"
            f"⚠️ <b>Candidatos detenidos (≥30d):</b> {estancados}\n\n"
            f"<i>💡 Usa los botones inferiores para consultar por dimensión o descargar reportes en Excel.</i>"
        )
        return msg

    @classmethod
    def generar_focos_rojos_texto(cls, usuario=None):
        """
        Reporte unificado de focos rojos:
        - Vacantes vencidas SLA (dias > meta)
        - Vacantes por vencer (meta - dias <= 3d)
        - Candidatos estancados (>= 30 días sin cambio de etapa).
        Utiliza plazas_pendientes y escape seguro de HTML.
        """
        from .services import ReportesService
        from .models import Proceso

        qs = ReportesService.get_base_queryset(usuario).filter(
            esta_abierto=True,
            estatus_autorizacion='AUTORIZADO'
        ).select_related('titulo', 'marca', 'asesora_encargada')

        vencidas = []
        por_vencer = []

        for p in qs:
            dias = p.dias_transcurridos
            meta = p.dias_meta or 20
            diff = meta - dias
            asesora_nom = (
                p.asesora_encargada.first_name or p.asesora_encargada.username
                if p.asesora_encargada else 'Sin asignar'
            )
            item = {
                'titulo': p.titulo.nombre if p.titulo else 'Puesto',
                'agencia': p.agencia or 'General',
                'dias': dias,
                'meta': meta,
                'exceso': abs(diff),
                'restantes': diff,
                'plazas_pendientes': p.plazas_pendientes,
                'asesora': asesora_nom
            }
            if diff < 0:
                vencidas.append(item)
            elif diff <= 3:
                por_vencer.append(item)

        vencidas.sort(key=lambda x: x['exceso'], reverse=True)
        por_vencer.sort(key=lambda x: x['restantes'])

        total_pl_vencidas = sum(v['plazas_pendientes'] for v in vencidas)
        total_pl_por_vencer = sum(r['plazas_pendientes'] for r in por_vencer)

        # Candidatos estancados (umbral del sistema: >= 30 días sin cambio de etapa)
        ahora = timezone.now()
        limite_30d = ahora - timedelta(days=30)
        terminales = [
            Proceso.Estatus.CONTRATADO,
            Proceso.Estatus.DESCARTADO_CH,
            Proceso.Estatus.NO_PRUEBAS,
            Proceso.Estatus.ABANDONO,
        ]
        estancados = Proceso.objects.filter(
            puesto__in=qs,
            fecha_inicio_etapa__lte=limite_30d
        ).exclude(estatus_proceso__in=terminales).select_related(
            'candidato', 'puesto', 'puesto__titulo', 'asesora_asignada'
        ).order_by('fecha_inicio_etapa')

        total_estancados = estancados.count()

        msg = (
            f"🚨 <b>FOCOS ROJOS • CAPITAL HUMANO</b>\n"
            f"<i>{len(vencidas)} req. vencidas ({total_pl_vencidas} pl) │ {total_estancados} candidatos detenidos (≥30d)</i>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )

        if vencidas:
            msg += f"🔴 <b>VACANTES VENCIDAS SLA ({len(vencidas)} req / {total_pl_vencidas} pl):</b>\n"
            for v in vencidas[:8]:
                msg += (
                    f"• <b>{_esc(v['titulo'])}</b> ({_esc(v['agencia'])}) │ "
                    f"<b>+{v['exceso']}d</b> ({v['dias']}/{v['meta']}d) │ {v['plazas_pendientes']} pl • 👤 {_esc(v['asesora'])}\n"
                )
            if len(vencidas) > 8:
                msg += f"<i>...y {len(vencidas) - 8} requisiciones vencidas más.</i>\n"
            msg += "\n"
        else:
            msg += "🟢 <b>0 vacantes vencidas en el grupo.</b>\n\n"

        if por_vencer:
            msg += f"🟡 <b>POR VENCER (≤3 DÍAS RESTANTES - {len(por_vencer)} req / {total_pl_por_vencer} pl):</b>\n"
            for r in por_vencer[:6]:
                msg += (
                    f"• <b>{_esc(r['titulo'])}</b> ({_esc(r['agencia'])}) │ "
                    f"<b>{r['restantes']}d rest.</b> ({r['dias']}/{r['meta']}d) │ {r['plazas_pendientes']} pl • 👤 {_esc(r['asesora'])}\n"
                )
            if len(por_vencer) > 6:
                msg += f"<i>...y {len(por_vencer) - 6} más por vencer.</i>\n"
            msg += "\n"

        estancados_lista = list(estancados[:6])
        if estancados_lista:
            msg += f"⏳ <b>CANDIDATOS DETENIDOS EN ETAPA (≥30 DÍAS):</b>\n"
            for st in estancados_lista:
                dias = (ahora - st.fecha_inicio_etapa).days
                cand = st.candidato.nombre_completo if st.candidato else "Candidato"
                puesto = st.puesto.titulo.nombre if (st.puesto and st.puesto.titulo) else "Puesto"
                ag = st.puesto.agencia if st.puesto else "General"
                etapa = st.get_estatus_proceso_display()
                as_nom = (st.asesora_asignada.first_name or st.asesora_asignada.username) if st.asesora_asignada else "Sin asignar"
                msg += f"• <b>{_esc(cand)}</b> (<b>{dias}d en {etapa}</b>) │ {_esc(puesto)} ({_esc(ag)}) • 👤 {_esc(as_nom)}\n"
            if total_estancados > 6:
                msg += f"<i>...y {total_estancados - 6} candidatos más en seguimiento.</i>\n"
            msg += "\n"

        msg += "<i>👇 Filtra por Asesora o Ciudad para auditar las causas de rezago:</i>"
        return msg

    @classmethod
    def generar_scorecard_global_asesoras_texto(cls, usuario=None):
        """
        Scorecard integral de productividad del equipo de Atracción de Talento.
        Calcula contrataciones contando registros de Proceso (Count('id')),
        muestra plazas pendientes reales y métricas de auditoría de bono y reinicios.
        """
        from .services import ReportesService

        qs = ReportesService.get_base_queryset(usuario)
        lista_puestos = list(qs.select_related('titulo', 'marca', 'asesora_encargada').prefetch_related('procesos'))

        if not lista_puestos:
            return "👥 <b>SCORECARD DE ASESORAS • PREMIER CH</b>\n\n🟢 Actualmente no hay vacantes asignadas."

        scorecard = ReportesService.compute_asesoras_scorecard(lista_puestos)

        msg = (
            f"👥 <b>SCORECARD DE ASESORAS • PREMIER CH</b>\n"
            f"<i>Equipo de Atracción de Talento ({len(scorecard)} evaluadas)</i>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )

        for a in scorecard:
            nombre = a['nombre']
            activas = a['activas']
            plazas_pend = a['plazas_pendientes']
            vencidas = a['vencidas']
            en_tiempo = max(0, activas - vencidas)
            contratados = a['contratados']
            bono_cumplido = a['bono_cumplido']
            total_asig = a['total_asignadas']
            bono_pct = a['bono_pct']
            reiniciadas = a['reiniciadas']
            total_reinicios = a['total_reinicios']

            msg += (
                f"• <b>{_esc(nombre)}</b>\n"
                f"  <b>{activas} activas ({plazas_pend} pl pend.)</b> │ 🟢 {en_tiempo} │ 🔴 {vencidas}\n"
                f"  🎉 <b>{contratados}</b> contrataciones concretadas\n"
                f"  🎯 Meta Bono: <b>{bono_cumplido}/{total_asig}</b> ({bono_pct}%) │ 🔄 Reinicios: <b>{reiniciadas}</b> vac. ({total_reinicios} tot.)\n\n"
            )

        msg += "<i>👇 Selecciona una asesora para consultar su detalle individual y descargar su auditoría:</i>"
        return msg

    @classmethod
    def generar_scorecard_asesora_texto(cls, asesora_id_or_name, usuario=None):
        """Scorecard individual detallado de una asesora con cálculo exacto de plazas y bono."""
        from .services import ReportesService
        from .models import Proceso

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
            return f"👤 <b>ASESORA DE TALENTO</b>\n\nNo se encontró asesora con identificador «{_esc(asesora_id_or_name)}»."

        nombre = asesora.get_full_name() or asesora.username

        qs = ReportesService.get_base_queryset(usuario).filter(
            asesora_encargada=asesora
        ).select_related('titulo', 'marca').prefetch_related('procesos')

        puestos_todos = list(qs)
        puestos_activos = [p for p in puestos_todos if p.esta_abierto and p.estatus_autorizacion == 'AUTORIZADO']

        total_req_activas = len(puestos_activos)
        total_pl_activas = sum(p.plazas_pendientes for p in puestos_activos)

        # Contrataciones de la asesora (conteo de registros de Proceso)
        contrataciones_total = Proceso.objects.filter(
            asesora_asignada=asesora,
            estatus_proceso=Proceso.Estatus.CONTRATADO
        ).count()

        ahora = timezone.now()
        mes_inicio = ahora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        contrataciones_mes = Proceso.objects.filter(
            asesora_asignada=asesora,
            estatus_proceso=Proceso.Estatus.CONTRATADO,
            fecha_inicio_etapa__gte=mes_inicio
        ).count()

        # Candidatos detenidos (>= 30 días sin cambio de etapa)
        limite_30d = ahora - timedelta(days=30)
        terminales = [
            Proceso.Estatus.CONTRATADO,
            Proceso.Estatus.DESCARTADO_CH,
            Proceso.Estatus.NO_PRUEBAS,
            Proceso.Estatus.ABANDONO,
        ]
        estancados = Proceso.objects.filter(
            asesora_asignada=asesora,
            puesto__in=puestos_activos,
            fecha_inicio_etapa__lte=limite_30d
        ).exclude(estatus_proceso__in=terminales).count()

        en_tiempo = 0
        por_vencer = 0
        vencidas = 0
        pl_en_tiempo = 0
        pl_por_vencer = 0
        pl_vencidas = 0
        dias_totales = 0
        criticas = []

        for p in puestos_activos:
            dias = p.dias_transcurridos
            dias_totales += dias
            meta = p.dias_meta or 20
            diff = meta - dias
            pend = p.plazas_pendientes

            if diff < 0:
                vencidas += 1
                pl_vencidas += pend
                criticas.append({
                    'titulo': p.titulo.nombre if p.titulo else 'Puesto',
                    'ag': p.agencia or 'General',
                    'exceso': abs(diff),
                    'dias': dias,
                    'meta': meta,
                    'pend': pend
                })
            elif diff <= 3:
                por_vencer += 1
                pl_por_vencer += pend
            else:
                en_tiempo += 1
                pl_en_tiempo += pend

        promedio = (dias_totales / total_req_activas) if total_req_activas > 0 else 0
        bono_cumplido = sum(1 for p in puestos_todos if p.cumplio_meta_bono)
        total_puestos = len(puestos_todos)
        bono_pct = round((bono_cumplido / total_puestos * 100), 1) if total_puestos > 0 else 0.0
        reiniciadas = sum(1 for p in puestos_todos if p.numero_reinicios > 0)
        total_reinicios = sum(p.numero_reinicios for p in puestos_todos)

        msg = (
            f"👤 <b>SCORECARD: {_esc(nombre.upper())}</b>\n"
            f"<b>{total_req_activas} vacantes asignadas</b> ({total_pl_activas} plazas pendientes)\n"
            f"🟢 {en_tiempo} ({pl_en_tiempo} pl) │ 🟡 {por_vencer} ({pl_por_vencer} pl) │ 🔴 {vencidas} ({pl_vencidas} pl)\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"⚡ <b>SLA Promedio Activo:</b> {promedio:.1f} días\n"
            f"🎉 <b>Contrataciones:</b> {contrataciones_mes} este mes │ {contrataciones_total} históricas\n"
            f"🎯 <b>Meta de Bono:</b> {bono_cumplido}/{total_puestos} vacantes ({bono_pct}%)\n"
            f"🔄 <b>Reinicios:</b> {reiniciadas} vacantes ({total_reinicios} totales)\n"
            f"⚠️ <b>Candidatos detenidos (≥30d):</b> {estancados}\n"
        )

        if criticas:
            msg += f"\n🔴 <b>Vacantes Críticas Vencidas:</b>\n"
            for c in criticas[:6]:
                msg += f" • <b>{_esc(c['titulo'])}</b> ({_esc(c['ag'])}) │ <b>+{c['exceso']}d</b> ({c['dias']}/{c['meta']}d) │ {c['pend']} pl\n"

        return msg

    @classmethod
    def generar_ficha_ciudad_texto(cls, ciudad_query, usuario=None):
        """Ficha ejecutiva condensada para una ciudad/plaza específica."""
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

        total_req = qs.count()
        if total_req == 0:
            return f"📍 <b>FICHA DE CIUDAD: {_esc(cd_nombre.upper())}</b>\n\n🟢 0 vacantes abiertas en esta plaza."

        total_pl = sum(p.plazas_pendientes for p in qs)
        en_tiempo = 0
        por_vencer = 0
        vencidas = 0
        pl_en_tiempo = 0
        pl_por_vencer = 0
        pl_vencidas = 0
        agencias = {}
        asesoras = set()
        alertas = []

        for p in qs:
            dias = p.dias_transcurridos
            meta = p.dias_meta or 20
            diff = meta - dias
            pend = p.plazas_pendientes

            ag = p.agencia or "Sin Agencia"
            if ag not in agencias:
                agencias[ag] = {'req': 0, 'pl': 0, 'vencidas': 0}
            agencias[ag]['req'] += 1
            agencias[ag]['pl'] += pend

            if p.asesora_encargada:
                asesoras.add(p.asesora_encargada.first_name or p.asesora_encargada.username)

            if diff < 0:
                vencidas += 1
                pl_vencidas += pend
                agencias[ag]['vencidas'] += 1
                alertas.append({
                    'titulo': p.titulo.nombre if p.titulo else 'Puesto',
                    'ag': ag,
                    'dias': dias,
                    'meta': meta,
                    'exceso': abs(diff),
                    'pend': pend,
                    'asesora': p.asesora_encargada.first_name if p.asesora_encargada else 'Sin asignar'
                })
            elif diff <= 3:
                por_vencer += 1
                pl_por_vencer += pend
            else:
                en_tiempo += 1
                pl_en_tiempo += pend

        msg = (
            f"📍 <b>FICHA DE CIUDAD: {_esc(cd_nombre.upper())}</b>\n"
            f"<b>{total_req} requisiciones</b> ({total_pl} plazas pendientes)\n"
            f"🟢 {en_tiempo} ({pl_en_tiempo} pl) │ 🟡 {por_vencer} ({pl_por_vencer} pl) │ 🔴 {vencidas} ({pl_vencidas} pl)\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🏢 <b>Agencias en la plaza:</b>\n"
        )
        for ag, info in sorted(agencias.items(), key=lambda x: x[1]['pl'], reverse=True):
            alerta = f" (🔴 {info['vencidas']} venc.)" if info['vencidas'] > 0 else ""
            msg += f" • {_esc(ag)}: <b>{info['req']} req</b> ({info['pl']} pl){alerta}\n"

        if asesoras:
            msg += f"\n👤 <b>Asesoras a cargo:</b> {_esc(', '.join(sorted(asesoras)))}\n"

        if alertas:
            msg += f"\n🔴 <b>Alertas Críticas Vencidas:</b>\n"
            for a in alertas[:5]:
                msg += f" • <b>{_esc(a['titulo'])}</b> ({_esc(a['ag'])}) │ <b>+{a['exceso']}d</b> │ {a['pend']} pl • 👤 {_esc(a['asesora'])}\n"

        return msg

    @classmethod
    def generar_ficha_agencia_texto(cls, agencia_id_or_name, usuario=None):
        """Ficha condensada de vacantes abiertas en una agencia específica."""
        from .services import ReportesService
        from .models import Puesto, Agencia

        agencia_real = None
        if str(agencia_id_or_name).isdigit():
            ag_obj = Agencia.objects.filter(id=int(agencia_id_or_name)).first()
            if ag_obj:
                agencia_real = ag_obj.nombre
        if not agencia_real:
            agencia_real = str(agencia_id_or_name).strip()

        qs = ReportesService.get_base_queryset(usuario).filter(
            esta_abierto=True,
            estatus_autorizacion='AUTORIZADO',
            agencia__icontains=agencia_real
        ).select_related('titulo', 'marca', 'asesora_encargada')

        if not qs.exists():
            return f"🏢 <b>AGENCIA: {_esc(agencia_real.upper())}</b>\n\n🟢 0 vacantes abiertas en esta agencia."

        agencia_exacta = qs.first().agencia
        dict_ciudades = dict(Puesto.CIUDADES_CHOICES)
        ciudad_nombre = dict_ciudades.get(qs.first().ciudad, qs.first().ciudad)

        total_req = qs.count()
        total_pl = sum(p.plazas_pendientes for p in qs)

        en_tiempo = 0
        por_vencer = 0
        vencidas = 0
        pl_en_tiempo = 0
        pl_por_vencer = 0
        pl_vencidas = 0
        vacantes_list = []

        for p in qs:
            dias = p.dias_transcurridos
            meta = p.dias_meta or 20
            diff = meta - dias
            pend = p.plazas_pendientes

            if diff < 0:
                vencidas += 1
                pl_vencidas += pend
                tag = f"🔴 +{abs(diff)}d ({dias}/{meta}d)"
            elif diff <= 3:
                por_vencer += 1
                pl_por_vencer += pend
                tag = f"🟡 {diff}d rest."
            else:
                en_tiempo += 1
                pl_en_tiempo += pend
                tag = "🟢 En tiempo"

            asesora = (p.asesora_encargada.first_name or p.asesora_encargada.username) if p.asesora_encargada else "Sin asignar"
            titulo_nom = p.titulo.nombre if p.titulo else 'Puesto'
            vacantes_list.append(f" • <b>{_esc(titulo_nom)}</b> ({pend} pl) │ {tag} • 👤 {_esc(asesora)}")

        msg = (
            f"🏢 <b>FICHA AGENCIA: {_esc(agencia_exacta.upper())}</b>\n"
            f"<i>Plaza: {_esc(ciudad_nombre)}</i>\n"
            f"<b>{total_req} requisiciones</b> ({total_pl} plazas pendientes)\n"
            f"🟢 {en_tiempo} ({pl_en_tiempo} pl) │ 🟡 {por_vencer} ({pl_por_vencer} pl) │ 🔴 {vencidas} ({pl_vencidas} pl)\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📋 <b>Detalle de Plazas:</b>\n"
        )
        for line in vacantes_list[:12]:
            msg += f"{line}\n"

        return msg

    # -------------------------------------------------------------------------
    # 3.1 MÉTODOS COMPATIBLES / TEXTOS LEGACY PARA NLP Y COMANDOS DIRECTOS
    # -------------------------------------------------------------------------

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
        ciudades_map = {}
        for p in qs:
            cd_nombre = dict_ciudades.get(p.ciudad, p.ciudad) or 'Otras Plazas'
            agencia = p.agencia or 'Sin Agencia'
            if cd_nombre not in ciudades_map:
                ciudades_map[cd_nombre] = {'total_req': 0, 'total_pl': 0, 'agencias': {}}
            ciudades_map[cd_nombre]['total_req'] += 1
            ciudades_map[cd_nombre]['total_pl'] += p.plazas_pendientes

            if agencia not in ciudades_map[cd_nombre]['agencias']:
                ciudades_map[cd_nombre]['agencias'][agencia] = {'req': 0, 'pl': 0, 'vencidas': 0}
            ciudades_map[cd_nombre]['agencias'][agencia]['req'] += 1
            ciudades_map[cd_nombre]['agencias'][agencia]['pl'] += p.plazas_pendientes
            if p.dias_transcurridos > (p.dias_meta or 20):
                ciudades_map[cd_nombre]['agencias'][agencia]['vencidas'] += 1

        msg = "🏢 <b>VACANTES ABIERTAS POR AGENCIA Y CIUDAD</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        for cd, data in sorted(ciudades_map.items(), key=lambda x: x[1]['total_pl'], reverse=True):
            msg += f"📍 <b>{_esc(cd.upper())} ({data['total_req']} req / {data['total_pl']} pl):</b>\n"
            for ag, ag_info in sorted(data['agencias'].items(), key=lambda x: x[1]['pl'], reverse=True)[:6]:
                alerta = f" (🔴 {ag_info['vencidas']} venc.)" if ag_info['vencidas'] > 0 else ""
                msg += f" • {_esc(ag)}: <b>{ag_info['req']} req</b> ({ag_info['pl']} pl){alerta}\n"
            msg += "\n"

        msg += "<i>💡 Toca «🔎 Consultar por...» para filtrar por Agencia, Asesora o Ciudad.</i>"
        return msg

    @classmethod
    def generar_alertas_sla_texto(cls, usuario=None):
        """Detalle prioritario de vacantes críticas vencidas o próximas a vencer (SLA)."""
        txt = cls.generar_focos_rojos_texto(usuario)
        return txt.replace("🚨 <b>FOCOS ROJOS • CAPITAL HUMANO</b>", "⏱️ <b>MONITOREO DE TIEMPOS DE COBERTURA (SLA)</b>")

    @classmethod
    def generar_estancados_texto(cls, usuario=None):
        """Candidatos con más de 30 días sin avance en etapa, agrupados por Asesora."""
        from .models import Proceso
        ahora = timezone.now()
        limite_30d = ahora - timedelta(days=30)
        terminales = [
            Proceso.Estatus.CONTRATADO,
            Proceso.Estatus.DESCARTADO_CH,
            Proceso.Estatus.NO_PRUEBAS,
            Proceso.Estatus.ABANDONO,
        ]

        estancados = Proceso.objects.filter(
            fecha_inicio_etapa__lte=limite_30d
        ).exclude(
            estatus_proceso__in=terminales
        ).select_related(
            'candidato', 'puesto', 'puesto__titulo', 'asesora_asignada'
        ).order_by('fecha_inicio_etapa')

        total_estancados = estancados.count()
        if total_estancados == 0:
            return "⚠️ <b>PROCESOS ESTANCADOS</b>\n\n🟢 ¡Excelente! No hay candidatos con más de 30 días detenidos en la misma etapa."

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
            f"⚠️ <b>PROCESOS ESTANCADOS (≥30 DÍAS EN ETAPA)</b>\n"
            f"<b>{total_estancados} candidatos</b> requieren seguimiento urgente\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )
        for asesora, lista in asesoras_map.items():
            msg += f"👤 <b>{_esc(asesora)} ({len(lista)}):</b>\n"
            for item in lista:
                msg += f" • <b>{_esc(item['cand'])}</b> (<b>{item['dias']}d</b>) • {_esc(item['etapa'])}\n   ↳ {_esc(item['puesto'])} ({_esc(item['agencia'])})\n"
            msg += "\n"

        return msg

    @classmethod
    def generar_contrataciones_mes_texto(cls, usuario=None):
        """Lista compacta de contrataciones concretadas en el mes en curso."""
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
            f"<b>{total} contrataciones concretadas</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )
        for c in contratados[:15]:
            cand = c.candidato.nombre_completo if c.candidato else "Colaborador"
            puesto = c.puesto.titulo.nombre if (c.puesto and c.puesto.titulo) else "Puesto"
            agencia = c.puesto.agencia if c.puesto else "Agencia"
            fecha_ingreso = c.fecha_inicio_etapa.strftime("%d/%b")
            msg += f"• <b>{_esc(cand)}</b> ({fecha_ingreso}) │ {_esc(puesto)} • {_esc(agencia)}\n"

        return msg

    @classmethod
    def generar_panorama_ciudades_texto(cls, usuario=None):
        """Panorama ejecutivo consolidado por ciudades y plazas."""
        from .services import ReportesService
        from .models import Puesto

        qs = ReportesService.get_base_queryset(usuario).filter(
            esta_abierto=True,
            estatus_autorizacion='AUTORIZADO'
        )

        if not qs.exists():
            return "📍 <b>PANORAMA POR CIUDADES</b>\n\n🟢 0 vacantes abiertas en el grupo."

        dict_ciudades = dict(Puesto.CIUDADES_CHOICES)
        ciudades_map = {}
        total_req_global = 0
        total_pl_global = 0

        for p in qs:
            cd_nombre = dict_ciudades.get(p.ciudad, p.ciudad) or 'Otras Plazas'
            pend = p.plazas_pendientes
            if cd_nombre not in ciudades_map:
                ciudades_map[cd_nombre] = {'req': 0, 'pl': 0, 'vencidas': 0, 'agencias': set()}
            ciudades_map[cd_nombre]['req'] += 1
            ciudades_map[cd_nombre]['pl'] += pend
            total_req_global += 1
            total_pl_global += pend
            if p.agencia:
                ciudades_map[cd_nombre]['agencias'].add(p.agencia)
            if p.dias_transcurridos > (p.dias_meta or 20):
                ciudades_map[cd_nombre]['vencidas'] += 1

        msg = (
            f"📍 <b>PANORAMA POR CIUDADES Y PLAZAS</b>\n"
            f"<b>{total_req_global} requisiciones activas ({total_pl_global} plazas)</b> en {len(ciudades_map)} plazas\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )
        for cd, data in sorted(ciudades_map.items(), key=lambda x: x[1]['pl'], reverse=True):
            alerta = f" │ 🔴 <b>{data['vencidas']} vencidas</b>" if data['vencidas'] > 0 else " │ 🟢 en tiempo"
            num_ag = len(data['agencias'])
            msg += f"• <b>{_esc(cd)}:</b> <b>{data['req']} req</b> ({data['pl']} pl / {num_ag} agencias){alerta}\n"

        msg += "\n<i>👇 Consulta una plaza usando el botón «🔎 Consultar por...»:</i>"
        return msg

    # -------------------------------------------------------------------------
    # 4. EXPORTACIÓN EXCEL EN 2 PASOS Y POR DIMENSIÓN
    # -------------------------------------------------------------------------

    @classmethod
    def generar_excel_buffer(cls, usuario=None, tipo='resumen', periodo='todo'):
        """
        Genera el reporte Excel (.xlsx) aplicando el tipo y periodo exacto.
        Soporta los 3 reportes oficiales: resumen, bono, sabana.
        """
        from .services import ReportesService
        filtros = {}
        hoy = timezone.now().date()

        if periodo == 'semana':
            filtros['fecha_desde'] = (hoy - timedelta(days=7)).strftime('%Y-%m-%d')
            filtros['fecha_hasta'] = hoy.strftime('%Y-%m-%d')
        elif periodo == 'mes_actual':
            filtros['fecha_desde'] = hoy.replace(day=1).strftime('%Y-%m-%d')
            filtros['fecha_hasta'] = hoy.strftime('%Y-%m-%d')
        elif periodo == 'mes_pasado':
            primer_dia_mes_act = hoy.replace(day=1)
            ultimo_dia_mes_ant = primer_dia_mes_act - timedelta(days=1)
            primer_dia_mes_ant = ultimo_dia_mes_ant.replace(day=1)
            filtros['fecha_desde'] = primer_dia_mes_ant.strftime('%Y-%m-%d')
            filtros['fecha_hasta'] = ultimo_dia_mes_ant.strftime('%Y-%m-%d')

        fecha_tag = timezone.now().strftime("%Y%m%d_%H%M")
        if tipo == 'bono':
            buf = ReportesService.generar_excel_auditoria_bono(filtros, usuario)
            fname = f"Auditoria_Bono_Asesoras_{periodo}_{fecha_tag}.xlsx"
        elif tipo == 'sabana':
            buf = ReportesService.generar_excel_sabana_historica(filtros, usuario)
            fname = f"Sabana_Historica_{periodo}_{fecha_tag}.xlsx"
        else:
            buf = ReportesService.generar_excel_resumen_ejecutivo(filtros, usuario)
            fname = f"Reporte_Ejecutivo_{periodo}_{fecha_tag}.xlsx"

        return buf, fname

    @classmethod
    def generar_excel_filtrado_buffer(cls, tipo_dim, valor_id, usuario=None):
        """
        Genera el Excel de Resumen Ejecutivo filtrado estrictamente por
        Asesora (ID), Agencia (ID) o Ciudad (Código).
        """
        from .services import ReportesService
        from .models import Agencia

        filtros = {}
        label = str(valor_id)
        if tipo_dim in ('as', 'asesora'):
            filtros['asesora'] = str(valor_id)
        elif tipo_dim in ('cd', 'ciudad'):
            filtros['ciudad'] = str(valor_id).upper()
        elif tipo_dim in ('ag', 'agencia'):
            if str(valor_id).isdigit():
                ag_obj = Agencia.objects.filter(id=int(valor_id)).first()
                if ag_obj:
                    filtros['agencia'] = ag_obj.nombre
                    label = ag_obj.nombre
                else:
                    filtros['agencia'] = str(valor_id)
            else:
                filtros['agencia'] = str(valor_id)

        buffer = ReportesService.generar_excel_resumen_ejecutivo(filtros, usuario)
        fecha_tag = timezone.now().strftime("%Y%m%d_%H%M")
        clean_label = "".join(c for c in label if c.isalnum() or c in ('_', '-'))[:20]
        nombre_archivo = f"Reporte_{tipo_dim}_{clean_label}_{fecha_tag}.xlsx"
        return buffer, nombre_archivo

    # -------------------------------------------------------------------------
    # 5. TECLADOS INTERACTIVOS (CALLBACK DATA <= 64 BYTES GARANTIZADO)
    # -------------------------------------------------------------------------

    @classmethod
    def obtener_teclado_principal(cls):
        """
        Menú Principal directivo limpio: 4 botones en 2 filas.
        """
        return {
            'inline_keyboard': [
                [
                    {'text': '📊 Resumen Hoy', 'callback_data': 'nav:resumen'},
                    {'text': '🚨 Focos Rojos', 'callback_data': 'nav:focos'}
                ],
                [
                    {'text': '🔎 Consultar por...', 'callback_data': 'nav:filtros'},
                    {'text': '📥 Descargar Excels', 'callback_data': 'nav:excels'}
                ]
            ]
        }

    # Alias compatible
    obtener_teclado_ejecutivo = obtener_teclado_principal

    @classmethod
    def obtener_teclado_filtros(cls):
        """
        Selector de dimensión de filtrado en 2 pasos:
        Asesora, Agencia o Ciudad.
        """
        return {
            'inline_keyboard': [
                [
                    {'text': '👤 Por Asesora', 'callback_data': 'flist:as'},
                    {'text': '🏢 Por Agencia', 'callback_data': 'flist:ag'},
                    {'text': '📍 Por Ciudad', 'callback_data': 'flist:cd'}
                ],
                [
                    {'text': '🏠 Menú Principal', 'callback_data': 'nav:menu'}
                ]
            ]
        }

    # Alias compatible
    obtener_teclado_menu_filtros = obtener_teclado_filtros

    @classmethod
    def obtener_teclado_focos_rojos(cls):
        """Acciones rápidas desde la vista de Focos Rojos."""
        return {
            'inline_keyboard': [
                [
                    {'text': '👤 Por Asesora', 'callback_data': 'flist:as'},
                    {'text': '📍 Por Ciudad', 'callback_data': 'flist:cd'}
                ],
                [
                    {'text': '📥 Descargar Excels', 'callback_data': 'nav:excels'},
                    {'text': '🏠 Menú Principal', 'callback_data': 'nav:menu'}
                ]
            ]
        }

    @classmethod
    def obtener_teclado_lista_asesoras(cls, usuario=None):
        """
        Botones dinámicos de Asesoras pasando únicamente su ID numérico (f:as:<user_id>).
        Garantiza longitud <= 64 bytes UTF-8.
        """
        from .services import ReportesService

        qs = ReportesService.get_base_queryset(usuario).filter(
            esta_abierto=True,
            estatus_autorizacion='AUTORIZADO',
            asesora_encargada__isnull=False
        ).select_related('asesora_encargada')

        asesoras_map = {}
        for p in qs:
            u_id = p.asesora_encargada.id
            if u_id not in asesoras_map:
                nom = p.asesora_encargada.first_name or p.asesora_encargada.username
                asesoras_map[u_id] = {'nombre': nom, 'req': 0, 'pl': 0}
            asesoras_map[u_id]['req'] += 1
            asesoras_map[u_id]['pl'] += p.plazas_pendientes

        buttons = []
        row = []
        for u_id, data in sorted(asesoras_map.items(), key=lambda x: x[1]['pl'], reverse=True):
            nom_btn = (data['nombre'][:12] + '.') if len(data['nombre']) > 13 else data['nombre']
            cb_data = f"f:as:{u_id}"
            row.append({'text': f"👤 {nom_btn} ({data['req']}r/{data['pl']}p)", 'callback_data': cb_data})
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)

        buttons.append([
            {'text': '⬅️ Volver a Filtros', 'callback_data': 'nav:filtros'},
            {'text': '🏠 Menú Principal', 'callback_data': 'nav:menu'}
        ])
        return {'inline_keyboard': buttons}

    # Alias compatible
    obtener_teclado_asesoras = obtener_teclado_lista_asesoras

    @classmethod
    def obtener_teclado_lista_agencias(cls, usuario=None):
        """
        Botones dinámicos de Agencias pasando únicamente su ID numérico (f:ag:<agencia_id>).
        Garantiza longitud <= 64 bytes UTF-8.
        """
        from .services import ReportesService
        from .models import Agencia

        qs = ReportesService.get_base_queryset(usuario).filter(
            esta_abierto=True,
            estatus_autorizacion='AUTORIZADO'
        ).exclude(agencia__isnull=True).exclude(agencia='')

        agencias_map = {}
        for p in qs:
            ag = p.agencia
            if ag not in agencias_map:
                agencias_map[ag] = {'req': 0, 'pl': 0}
            agencias_map[ag]['req'] += 1
            agencias_map[ag]['pl'] += p.plazas_pendientes

        buttons = []
        row = []
        for ag_nombre, data in sorted(agencias_map.items(), key=lambda x: x[1]['pl'], reverse=True)[:14]:
            ag_obj = Agencia.objects.filter(nombre=ag_nombre).first()
            if not ag_obj:
                ag_obj, _ = Agencia.objects.get_or_create(nombre=ag_nombre)
            cb_data = f"f:ag:{ag_obj.id}"
            nom_btn = (ag_nombre[:12] + '..') if len(ag_nombre) > 14 else ag_nombre
            row.append({'text': f"🏢 {nom_btn} ({data['req']}r/{data['pl']}p)", 'callback_data': cb_data})
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)

        buttons.append([
            {'text': '⬅️ Volver a Filtros', 'callback_data': 'nav:filtros'},
            {'text': '🏠 Menú Principal', 'callback_data': 'nav:menu'}
        ])
        return {'inline_keyboard': buttons}

    # Alias compatible
    obtener_teclado_agencias = obtener_teclado_lista_agencias

    @classmethod
    def obtener_teclado_lista_ciudades(cls, usuario=None):
        """
        Botones dinámicos de Ciudades pasando únicamente el código de plaza (f:cd:<ciudad_code>).
        Garantiza longitud <= 64 bytes UTF-8.
        """
        from .services import ReportesService
        from .models import Puesto

        dict_ciudades = dict(Puesto.CIUDADES_CHOICES)
        qs = ReportesService.get_base_queryset(usuario).filter(
            esta_abierto=True,
            estatus_autorizacion='AUTORIZADO'
        ).exclude(ciudad__isnull=True).exclude(ciudad='')

        ciudades_map = {}
        for p in qs:
            cd = p.ciudad
            if cd not in ciudades_map:
                ciudades_map[cd] = {'req': 0, 'pl': 0}
            ciudades_map[cd]['req'] += 1
            ciudades_map[cd]['pl'] += p.plazas_pendientes

        buttons = []
        row = []
        for code, data in sorted(ciudades_map.items(), key=lambda x: x[1]['pl'], reverse=True):
            nombre = dict_ciudades.get(code, code)
            cb_data = f"f:cd:{code}"
            nom_btn = (nombre[:11] + '.') if len(nombre) > 12 else nombre
            row.append({'text': f"📍 {nom_btn} ({data['req']}r/{data['pl']}p)", 'callback_data': cb_data})
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)

        buttons.append([
            {'text': '⬅️ Volver a Filtros', 'callback_data': 'nav:filtros'},
            {'text': '🏠 Menú Principal', 'callback_data': 'nav:menu'}
        ])
        return {'inline_keyboard': buttons}

    # Alias compatible
    obtener_teclado_ciudades = obtener_teclado_lista_ciudades

    @classmethod
    def obtener_teclado_detalle(cls, tipo, id_o_codigo):
        """
        Botón de acción al entrar al detalle de Asesora, Agencia o Ciudad.
        Permite descargar el Excel filtrado por ese ID (xls:res:todo:<dim>:<id>).
        """
        tipo_code = 'as' if tipo in ('as', 'asesora') else ('ag' if tipo in ('ag', 'agencia') else 'cd')
        back_list = f"flist:{tipo_code}"
        xls_cb = f"xls:res:todo:{tipo_code}:{id_o_codigo}"

        return {
            'inline_keyboard': [
                [
                    {'text': '📥 Descargar Excel Filtrado', 'callback_data': xls_cb}
                ],
                [
                    {'text': '⬅️ Volver a Lista', 'callback_data': back_list},
                    {'text': '🏠 Menú Principal', 'callback_data': 'nav:menu'}
                ]
            ]
        }

    # Alias compatible
    obtener_teclado_detalle_filtro = obtener_teclado_detalle

    # -------------------------------------------------------------------------
    # 5.1 TECLADOS FLUJO 2: DESCARGA DE EXCELS EN 2 PASOS
    # -------------------------------------------------------------------------

    @classmethod
    def obtener_teclado_tipos_excel(cls):
        """Paso A de descarga: Selección del Tipo de Reporte Oficial."""
        return {
            'inline_keyboard': [
                [
                    {'text': '1️⃣ Resumen Ejecutivo', 'callback_data': 'xls_t:resumen'}
                ],
                [
                    {'text': '2️⃣ Auditoría y Bono Asesoras', 'callback_data': 'xls_t:bono'}
                ],
                [
                    {'text': '3️⃣ Sábana Histórica', 'callback_data': 'xls_t:sabana'}
                ],
                [
                    {'text': '🏠 Menú Principal', 'callback_data': 'nav:menu'}
                ]
            ]
        }

    @classmethod
    def obtener_teclado_periodos_excel(cls, tipo_reporte):
        """Paso B de descarga: Selección del Periodo temporal a exportar."""
        t = tipo_reporte or 'resumen'
        return {
            'inline_keyboard': [
                [
                    {'text': '📅 Esta semana', 'callback_data': f'xls:p:{t}:semana'},
                    {'text': '📅 Mes actual', 'callback_data': f'xls:p:{t}:mes_actual'}
                ],
                [
                    {'text': '📅 Mes pasado', 'callback_data': f'xls:p:{t}:mes_pasado'},
                    {'text': '📅 Todo el histórico', 'callback_data': f'xls:p:{t}:todo'}
                ],
                [
                    {'text': '⬅️ Cambiar de Reporte', 'callback_data': 'nav:excels'},
                    {'text': '🏠 Menú Principal', 'callback_data': 'nav:menu'}
                ]
            ]
        }

    # -------------------------------------------------------------------------
    # 6. ALERTAS EN TIEMPO REAL (NOTIFICACIONES DE IMPACTO)
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
            f"• <b>Puesto:</b> {_esc(puesto_nombre)}\n"
            f"• <b>Agencia:</b> {_esc(agencia)}\n"
            f"• <b>Colaborador:</b> {_esc(candidato_nombre)}\n"
            f"• <b>Tiempo de Cobertura:</b> {dias} días (Meta: {meta}d)\n"
            f"• <b>Asesora Encargada:</b> {_esc(asesora)}\n\n"
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
            f"• <b>Puesto:</b> {_esc(titulo)}\n"
            f"• <b>Agencia:</b> {_esc(agencia)}\n"
            f"• <b>Motivo:</b> {_esc(motivo)}\n"
            f"• <b>Solicitante:</b> {_esc(solicitante)}\n"
            f"• <b>Sueldo Propuesto:</b> {_esc(sueldo)}\n"
            f"• <b>Plazas Requeridas:</b> {puesto.cantidad_vacantes} (Pendientes: {puesto.plazas_pendientes})\n"
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
