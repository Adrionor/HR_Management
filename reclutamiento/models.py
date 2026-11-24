from django.db import models
from django.utils import timezone
from django.conf import settings
from django.contrib.auth.models import User
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.exceptions import ObjectDoesNotExist
from django.core.cache import cache
from .storage import CVStorage, RequisicionStorage

class Marca(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    activo = models.BooleanField(default=True, verbose_name="¿Activa?")

    class Meta:
        ordering = ['nombre']
        verbose_name = "Marca"
        verbose_name_plural = "Marcas"

    def __str__(self):
        return self.nombre

class Ciudad(models.Model):
    nombre = models.CharField(max_length=100, unique=True, verbose_name="Nombre de la Ciudad")
    activo = models.BooleanField(default=True, verbose_name="¿Activa?")

    class Meta:
        ordering = ['nombre']
        verbose_name = "Ciudad"
        verbose_name_plural = "Ciudades"

    def __str__(self):
        return self.nombre

class Agencia(models.Model):
    nombre = models.CharField(max_length=150, unique=True, verbose_name="Nombre de la Agencia")
    marca = models.ForeignKey(Marca, on_delete=models.SET_NULL, null=True, blank=True, related_name='agencias', verbose_name="Marca")
    ciudad = models.ForeignKey(Ciudad, on_delete=models.SET_NULL, null=True, blank=True, related_name='agencias', verbose_name="Ciudad")
    activo = models.BooleanField(default=True, verbose_name="¿Activa?")

    class Meta:
        ordering = ['nombre']
        verbose_name = "Agencia"
        verbose_name_plural = "Agencias"

    def __str__(self):
        return self.nombre

class PerfilUsuario(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE)
    marcas = models.ManyToManyField(Marca, blank=True)

    # Integración Telegram para Dirección y Gerencias
    telegram_chat_id = models.CharField(
        max_length=64, blank=True, null=True, unique=True,
        verbose_name="Telegram Chat ID",
        help_text="Identificador único del chat de Telegram para recibir reportes"
    )
    telegram_username = models.CharField(
        max_length=64, blank=True, null=True,
        verbose_name="Usuario de Telegram",
        help_text="Alias @usuario en Telegram"
    )
    telegram_token_enlace = models.CharField(
        max_length=64, blank=True, null=True, unique=True,
        verbose_name="Token de Vinculación",
        help_text="Token temporal seguro para conectar Telegram en 1 clic"
    )
    telegram_token_creado = models.DateTimeField(null=True, blank=True)
    notificaciones_telegram = models.BooleanField(
        default=True,
        verbose_name="Notificaciones Telegram Activas"
    )
    recibir_pulse_matutino = models.BooleanField(
        default=True,
        verbose_name="Recibir Pulse Matutino Diario"
    )
    recibir_alertas_criticas = models.BooleanField(
        default=True,
        verbose_name="Recibir Alertas Inmediatas (Contrataciones y SLAs)"
    )

    def __str__(self):
        return self.usuario.username

class CatalogoPuesto(models.Model):
    nombre = models.CharField(max_length=200, unique=True, verbose_name="Nombre del Puesto")
    activo = models.BooleanField(default=True, verbose_name="¿Activo?")
    dias_meta_default = models.PositiveIntegerField(
        default=20,
        verbose_name="Días Meta Sugeridos",
        help_text="Tiempo meta sugerido en días para sugerir automáticamente al elegir el puesto"
    )
    dias_meta = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Días Meta para Contratación",
        help_text="Número de días objetivo para completar el proceso de contratación de este puesto"
    )

    class Meta:
        ordering = ['nombre']
        verbose_name = "Puesto de Catálogo"
        verbose_name_plural = "Catálogo de Puestos"

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        if not self.dias_meta:
            self.dias_meta = self.dias_meta_default
        elif not self.dias_meta_default and self.dias_meta:
            self.dias_meta_default = self.dias_meta
        super().save(*args, **kwargs)

@receiver(post_save, sender=User)
def ensure_user_profile(sender, instance, **kwargs):
    """
    Asegura que cada User tenga un PerfilUsuario asociado sin duplicación ni doble save().
    """
    if kwargs.get('raw', False):
        return
    PerfilUsuario.objects.get_or_create(usuario=instance)


class Puesto(models.Model):
    CIUDADES_CHOICES = [
        ('CUL', 'Culiacán'), ('MZT', 'Mazatlán'), ('LMM', 'Los Mochis'),
        ('GVE', 'Guasave'), ('CJM', 'Cajeme'), ('HMO', 'Hermosillo'),
        ('MXL', 'Mexicali'), ('TIJ', 'Tijuana'), ('LPZ', 'La Paz'),
        ('LCB', 'Los Cabos'), ('CDMX', 'CDMX'), ('MTY', 'Monterrey'),
    ]

    class EstatusAutorizacion(models.TextChoices):
        AUTORIZADO = 'AUTORIZADO', 'Autorizado'
        PENDIENTE = 'PENDIENTE', 'Pendiente de Aprobación'
        PENDIENTE_DIR = 'PENDIENTE_DIR', 'Pendiente de Dirección'
        RECHAZADO = 'RECHAZADO', 'Rechazado'

    marca = models.ForeignKey(Marca, on_delete=models.PROTECT, verbose_name="Marca", null=True, blank=True)

    class Area(models.TextChoices):
        VENTAS = 'VTAS', 'Ventas'
        SERVICIO = 'SERV', 'Servicio'
        REFACCIONES = 'REF', 'Refacciones'
        ADMIN = 'ADM', 'Administración'
        OTRA = 'OTRA', 'Otra'

    class Motivo(models.TextChoices):
        ROTACION = 'ROT', 'Rotación de Personal'
        INCREMENTO = 'INC', 'Incremento de Plantilla'
        INCAPACIDAD = 'INCA', 'Cubrir Incapacidad'

    # Campos de aprobación (mantenidos para auditoría/historial pero ahora opcionales sin flujos externos)
    aprobado_por_gerente_marca = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='puestos_aprobados_gm',
        verbose_name="Aprobado por Gerente de Marca"
    )
    fecha_aprobacion_gerente_marca = models.DateTimeField(
        null=True, blank=True,
        verbose_name="Fecha Aprobación Gerente de Marca"
    )
    aprobado_por_director = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='puestos_aprobados_dir',
        verbose_name="Aprobado por Director"
    )
    fecha_aprobacion_director = models.DateTimeField(
        null=True, blank=True,
        verbose_name="Fecha Aprobación Director"
    )

    # --- Campos del Puesto ---
    titulo = models.ForeignKey(CatalogoPuesto, on_delete=models.PROTECT, verbose_name="Nombre del Puesto Vacante", null=True)
    agencia = models.CharField(max_length=100, verbose_name="Agencia", db_index=True)
    area = models.CharField(max_length=4, choices=Area.choices, verbose_name="Área", default=Area.OTRA, blank=True)
    ciudad = models.CharField(max_length=100, verbose_name="Ciudad de la Vacante", choices=CIUDADES_CHOICES)
    cantidad_vacantes = models.PositiveIntegerField(default=1, verbose_name="Cantidad de Vacantes Solicitadas")
    experiencia_minima = models.PositiveIntegerField(null=True, blank=True, verbose_name="Experiencia Mínima (años)",
                                                     help_text="Años de experiencia requeridos para el puesto.")
    carrera_sugerida = models.CharField(max_length=200, blank=True, verbose_name="Carrera o Especialidad Sugerida")
    reemplaza_a = models.CharField(max_length=200, blank=True,
                                   verbose_name="Nombre de la persona a quien reemplaza (si aplica)")

    # --- Detalles del Jefe Inmediato (Texto informativo de requisición física) ---
    jefe_inmediato_nombre = models.CharField(
        max_length=200,
        blank=True,
        default="",
        verbose_name="Nombre del Jefe Inmediato",
        help_text="Texto informativo de la requisición física (sin relación ForeignKey)"
    )
    jefe_inmediato_puesto = models.CharField(
        max_length=200,
        blank=True,
        default="",
        verbose_name="Puesto del Jefe Inmediato",
        help_text="Texto informativo de la requisición física (sin relación ForeignKey)"
    )
    # Campos de compatibilidad histórica
    nombre_jefe_inmediato = models.CharField(max_length=200, blank=True, default="", verbose_name="Nombre del Jefe Inmediato (Ref)")
    puesto_jefe_inmediato = models.CharField(max_length=200, blank=True, default="", verbose_name="Puesto del Jefe Inmediato (Ref)")

    # --- Justificación y Descripción ---
    motivo_requisicion = models.CharField(max_length=4, choices=Motivo.choices, verbose_name="Motivo de la Requisición", default=Motivo.ROTACION)
    objetivo_puesto = models.TextField(blank=True, default="", verbose_name="Objetivo/Propósito del Puesto")
    funciones_puesto = models.TextField(blank=True, default="", verbose_name="Actividades o Funciones Principales", help_text="Listar las funciones principales.")
    indicador_puesto = models.TextField(blank=True, default="", verbose_name="Indicador relevante con el que se mide el puesto")

    # --- Requisitos y Condiciones ---
    herramientas_puesto = models.CharField(max_length=255, blank=True, default="", verbose_name="Herramientas específicas de uso (Office, programas, etc.)")
    conocimientos_tecnicos = models.CharField(max_length=255, blank=True, default="", verbose_name="Conocimientos técnicos específicos")
    horario = models.CharField(max_length=100, blank=True, default="", verbose_name="Horario a cubrir")
    sueldo_base = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Sueldo Base Mensual (Bruto)")
    esquema_comisiones = models.TextField(blank=True, default="", verbose_name="Esquema de comisiones y/o bonos (si aplica)")

    archivo_justificacion = models.FileField(
        upload_to="requisiciones/",
        null=True,
        blank=True,
        storage=RequisicionStorage(),
        verbose_name="Archivo de Justificación (Opcional)",
        help_text="Suba un archivo PDF o imagen que justifique la solicitud de este puesto",
    )
    es_confidencial = models.BooleanField(default=False, verbose_name="¿Es una vacante confidencial?")
    motivo_rechazo = models.TextField(null=True, blank=True, verbose_name="Motivo de Rechazo")

    # --- Flujo Operativo de RH (Nace autorizada y activa directamente) ---
    estatus_autorizacion = models.CharField(
        max_length=20,
        choices=EstatusAutorizacion.choices,
        default=EstatusAutorizacion.AUTORIZADO,
        db_index=True,
        verbose_name="Estatus de Autorización"
    )
    esta_abierto = models.BooleanField(default=True, db_index=True, verbose_name="¿Vacante Activa/Abierta?")
    solicitado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='puestos_solicitados')
    fecha_solicitud = models.DateTimeField(default=timezone.now)
    fecha_registro_sla = models.DateTimeField(null=True, blank=True, editable=False)
    autorizado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='puestos_autorizados')
    fecha_autorizacion = models.DateTimeField(null=True, blank=True)
    segundo_autorizado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='puestos_segunda_autorizacion')
    fecha_segunda_autorizacion = models.DateTimeField(null=True, blank=True)
    asesora_encargada = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='puestos_asignados', verbose_name="Asesora de RH Responsable")

    # --- SLA y Control Operativo RH ---
    dias_meta = models.PositiveIntegerField(
        default=20,
        verbose_name="Días Meta (SLA)",
        help_text="Días objetivo para cubrir la vacante (editable)"
    )
    fecha_inicio_sla_custom = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha Inicio SLA Personalizada / Reinicio",
        help_text="Permite reiniciar el conteo del SLA cuando la vacante vence"
    )
    numero_reinicios = models.PositiveIntegerField(
        default=0,
        verbose_name="Número de Reinicios de SLA"
    )
    comentarios = models.TextField(
        blank=True,
        default="",
        verbose_name="Comentarios / Observaciones de RH"
    )

    def save(self, *args, **kwargs):
        if self._state.adding and self.fecha_registro_sla is None:
            self.fecha_registro_sla = timezone.now()
        # Sincronización bidireccional de nombres de jefe inmediato
        if not self.jefe_inmediato_nombre and self.nombre_jefe_inmediato:
            self.jefe_inmediato_nombre = self.nombre_jefe_inmediato
        elif not self.nombre_jefe_inmediato and self.jefe_inmediato_nombre:
            self.nombre_jefe_inmediato = self.jefe_inmediato_nombre

        if not self.jefe_inmediato_puesto and self.puesto_jefe_inmediato:
            self.jefe_inmediato_puesto = self.puesto_jefe_inmediato
        elif not self.puesto_jefe_inmediato and self.jefe_inmediato_puesto:
            self.puesto_jefe_inmediato = self.jefe_inmediato_puesto

        # Asignación automática a quien captura si no se ha asignado asesora
        if not self.asesora_encargada and self.solicitado_por:
            self.asesora_encargada = self.solicitado_por

        super().save(*args, **kwargs)

    def reiniciar_sla(self, nueva_fecha=None, comentario=""):
        """
        Reinicia el reloj de SLA de la vacante e incrementa el contador de reinicios.
        Regla de negocio: Límite estricto de máximo 2 reinicios por vacante.
        """
        if self.numero_reinicios >= 2:
            from django.core.exceptions import ValidationError
            raise ValidationError("Límite máximo alcanzado: Solo se permiten hasta 2 reinicios de SLA por vacante.")

        self.fecha_inicio_sla_custom = nueva_fecha or timezone.now()
        self.numero_reinicios += 1
        if comentario:
            ts = timezone.now().strftime("%d/%m/%Y %H:%M")
            nuevo = f"[{ts}] Reinicio SLA #{self.numero_reinicios}: {comentario}"
            self.comentarios = f"{self.comentarios}\n{nuevo}".strip()
        self.save()

    @property
    def plazas_cubiertas(self):
        if hasattr(self, '_prefetched_objects_cache') and 'procesos' in self._prefetched_objects_cache:
            return sum(1 for pr in self.procesos.all() if pr.estatus_proceso == Proceso.Estatus.CONTRATADO)
        return self.procesos.filter(estatus_proceso=Proceso.Estatus.CONTRATADO).count()

    @property
    def plazas_pendientes(self):
        return max(0, self.cantidad_vacantes - self.plazas_cubiertas)

    @property
    def esta_completamente_cubierta(self):
        return self.plazas_cubiertas >= self.cantidad_vacantes

    @property
    def fecha_inicio_sla(self):
        """El reloj de SLA inicia con fecha_inicio_sla_custom (si hubo reinicio), o fecha_solicitud."""
        return self.fecha_inicio_sla_custom or self.fecha_inicio_sla_original

    @property
    def dias_transcurridos(self):
        fecha_inicio = self.fecha_inicio_sla
        if not self.esta_abierto:
            if self.estatus_autorizacion == self.EstatusAutorizacion.RECHAZADO:
                fecha_fin = self.fecha_inicio_sla
            else:
                if hasattr(self, '_prefetched_objects_cache') and 'procesos' in self._prefetched_objects_cache:
                    contratados = [pr for pr in self.procesos.all() if pr.estatus_proceso == Proceso.Estatus.CONTRATADO]
                    contratados.sort(key=lambda pr: pr.fecha_inicio_etapa or timezone.now(), reverse=True)
                    ultimo_contratado = contratados[0] if contratados else None
                else:
                    ultimo_contratado = self.procesos.filter(
                        estatus_proceso=Proceso.Estatus.CONTRATADO
                    ).order_by('-fecha_inicio_etapa').first()
                fecha_fin = ultimo_contratado.fecha_inicio_etapa if ultimo_contratado else timezone.now()
            return max(0, (fecha_fin - fecha_inicio).days)
        return max(0, (timezone.now() - fecha_inicio).days)

    @property
    def fecha_limite_sla(self):
        return self.fecha_inicio_sla + timezone.timedelta(days=self.dias_meta)

    @property
    def estatus_sla(self):
        if not self.esta_abierto:
            if self.estatus_autorizacion == self.EstatusAutorizacion.RECHAZADO:
                return 'CANCELADA'
            return 'CUBIERTA'
        dias = self.dias_transcurridos
        meta = self.dias_meta
        if dias > meta:
            return 'VENCIDA'
        elif meta - dias <= 3:
            return 'POR_VENCER'
        return 'EN_TIEMPO'

    @property
    def cumplio_meta_bono(self):
        """Cumplimiento con el SLA original; None indica historial insuficiente."""
        inicio = self.fecha_inicio_sla_original
        limite = self.fecha_limite_sla_original
        procesos = list(self.procesos.all())
        contratados = [p for p in procesos if p.estatus_proceso == Proceso.Estatus.CONTRATADO]
        if len(contratados) >= self.cantidad_vacantes:
            fecha_cobertura = max(p.fecha_inicio_etapa for p in contratados)
            if inicio <= fecha_cobertura <= limite:
                return True

        candidatos = {
            p.candidato_id for p in procesos
            if p.fecha_envio_jefe_apto and inicio <= p.fecha_envio_jefe_apto <= limite
        }
        if len(candidatos) >= 3:
            return True
        if self.fecha_registro_sla is None:
            return None
        return False

    @property
    def fecha_inicio_sla_original(self):
        """Conserva la fecha de solicitud original sin alterar para auditoría."""
        return self.fecha_registro_sla or self.fecha_solicitud

    @property
    def fecha_limite_sla_original(self):
        """Conserva la fecha límite original del SLA para auditoría."""
        return self.fecha_inicio_sla_original + timezone.timedelta(days=self.dias_meta)

    @property
    def dias_transcurridos_total(self):
        """Días del SLA original, hasta la cobertura completa o hasta ahora."""
        fin = timezone.now()
        if self.esta_completamente_cubierta:
            contratados = [p for p in self.procesos.all() if p.estatus_proceso == Proceso.Estatus.CONTRATADO]
            fin = max(p.fecha_inicio_etapa for p in contratados)
        return max(0, (fin - self.fecha_inicio_sla_original).days)

    @property
    def etapa_operativa(self):
        if self.estatus_autorizacion in [self.EstatusAutorizacion.PENDIENTE, self.EstatusAutorizacion.PENDIENTE_DIR]:
            return '1. En Aprobación'

        if not self.esta_abierto:
            if self.estatus_autorizacion == self.EstatusAutorizacion.RECHAZADO:
                return 'Rechazada / Cancelada'
            return '7. Cubierta / Cerrada'

        if not self.asesora_encargada:
            return '2. Por Asignar Asesora'

        terminales = (
            Proceso.Estatus.DESCARTADO_CH,
            Proceso.Estatus.NO_PRUEBAS,
            Proceso.Estatus.ABANDONO,
            Proceso.Estatus.CONTRATADO,
        )

        if hasattr(self, '_prefetched_objects_cache') and 'procesos' in self._prefetched_objects_cache:
            procesos_activos = [pr for pr in self.procesos.all() if pr.estatus_proceso not in terminales]
            if not procesos_activos:
                return '3. En Búsqueda'
            estatus_set = {pr.estatus_proceso for pr in procesos_activos}
        else:
            procesos_activos = self.procesos.exclude(estatus_proceso__in=terminales)
            if not procesos_activos.exists():
                return '3. En Búsqueda'
            estatus_set = set(procesos_activos.values_list('estatus_proceso', flat=True))

        tramites = [
            Proceso.Estatus.MEDICO,
            Proceso.Estatus.DOCS,
            Proceso.Estatus.INGRESO_PROG,
            Proceso.Estatus.ALTA_ADMIN,
        ]
        if any(e in estatus_set for e in tramites):
            return '6. En Trámites de Ingreso'

        if Proceso.Estatus.ENT_JF in estatus_set or Proceso.Estatus.CONF_JF in estatus_set:
            return '5. En Entrevista / Decisión con Jefe'

        filtros = [
            Proceso.Estatus.NUEVO,
            Proceso.Estatus.CONTACTO,
            Proceso.Estatus.PRUEBAS,
            Proceso.Estatus.ENT_CH,
            Proceso.Estatus.REF,
        ]
        if any(e in estatus_set for e in filtros):
            return '4. En Filtros y Evaluaciones RH'

        return '3. En Búsqueda'

    @property
    def candidato_mas_avanzado(self):
        terminales = (
            Proceso.Estatus.DESCARTADO_CH,
            Proceso.Estatus.NO_PRUEBAS,
            Proceso.Estatus.ABANDONO,
            Proceso.Estatus.CONTRATADO,
        )
        if hasattr(self, '_prefetched_objects_cache') and 'procesos' in self._prefetched_objects_cache:
            activos = [pr for pr in self.procesos.all() if pr.estatus_proceso not in terminales]
        else:
            activos = list(self.procesos.exclude(estatus_proceso__in=terminales))

        if not activos:
            return None

        etapa_pesos = {
            Proceso.Estatus.NUEVO: 1,
            Proceso.Estatus.CONTACTO: 2,
            Proceso.Estatus.PRUEBAS: 3,
            Proceso.Estatus.ENT_CH: 4,
            Proceso.Estatus.REF: 5,
            Proceso.Estatus.ENT_JF: 6,
            Proceso.Estatus.CONF_JF: 7,
            Proceso.Estatus.MEDICO: 8,
            Proceso.Estatus.DOCS: 9,
            Proceso.Estatus.INGRESO_PROG: 10,
            Proceso.Estatus.ALTA_ADMIN: 11,
            Proceso.Estatus.CONTRATADO: 12,
        }
        activos.sort(key=lambda p: (etapa_pesos.get(p.estatus_proceso, 0), p.fecha_inicio_etapa or timezone.now()), reverse=True)
        return activos[0].candidato

    @property
    def ultima_observacion(self):
        if hasattr(self, '_prefetched_objects_cache') and 'procesos' in self._prefetched_objects_cache:
            con_retro = [pr for pr in self.procesos.all() if pr.retroalimentacion]
            con_retro.sort(key=lambda pr: pr.fecha_inicio_etapa or timezone.now(), reverse=True)
            return con_retro[0].retroalimentacion if con_retro else "Sin observaciones registradas."
        p = self.procesos.exclude(retroalimentacion='').order_by('-fecha_inicio_etapa').first()
        return p.retroalimentacion if p else "Sin observaciones registradas."

    def __str__(self):
        return f"{self.titulo.nombre if self.titulo else 'Vacante'} - {self.agencia} ({self.get_ciudad_display()})"


class Publicacion(models.Model):
    PLATAFORMAS_CHOICES = [
        ('FB', 'Facebook Ads / Grupos'),
        ('IG', 'Instagram'),
        ('LI', 'LinkedIn Jobs'),
        ('OCC', 'OCC Mundial'),
        ('CT', 'Computrabajo'),
        ('OTRA', 'Otra Plataforma / Manta'),
    ]

    puesto = models.ForeignKey(Puesto, on_delete=models.CASCADE, related_name='publicaciones', verbose_name="Vacante Publicada")
    plataforma = models.CharField(max_length=10, choices=PLATAFORMAS_CHOICES, verbose_name="Plataforma de Publicación")
    enlace = models.URLField(blank=True, null=True, verbose_name="Enlace a la Publicación", help_text="URL donde los candidatos pueden ver el post")
    monto_inversion = models.DecimalField(max_digits=8, decimal_places=2, default=0.00, verbose_name="Monto Invertido (MXN)")
    fecha_publicacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Publicación")
    publicado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, verbose_name="Publicado Por")

    def __str__(self):
        return f"{self.puesto.titulo.nombre if self.puesto.titulo else 'Vacante'} en {self.get_plataforma_display()}"


class Candidato(models.Model):
    NIVELES_EDUCATIVOS = [
        ('SEC', 'Secundaria'),
        ('TEC', 'Técnico / Preparatoria'),
        ('LIC', 'Licenciatura'),
        ('MAE', 'Maestría'),
        ('DOC', 'Doctorado'),
        ('OTR', 'Otro'),
    ]

    class MotivoBusqueda(models.TextChoices):
        DESAFIO = 'DESAFIO', 'Desafío personal'
        CRECIMIENTO = 'CREC', 'Crecimiento profesional'
        SALARIO = 'SALARIO', 'Mejor salario'
        CULTURA = 'CULTURA', 'Cultura empresarial saludable'

    nombres = models.CharField(max_length=100, verbose_name="Nombre(s)")
    apellidos = models.CharField(max_length=100, verbose_name="Apellidos")
    email = models.EmailField(unique=True)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    rfc = models.CharField(max_length=13, unique=True, null=True, blank=True, verbose_name="RFC")
    fecha_nacimiento = models.DateField(null=True, blank=True, verbose_name="Fecha de Nacimiento")

    puesto_de_interes = models.ForeignKey(Puesto, on_delete=models.SET_NULL, null=True, blank=True,
                                          verbose_name="Puesto de Interés")
    interes_custom = models.CharField(max_length=100, blank=True, null=True, verbose_name="Interés Personalizado")

    nivel_educativo = models.CharField(max_length=3, choices=NIVELES_EDUCATIVOS, null=True, blank=True,
                                        verbose_name="Máximo Nivel Educativo")
    años_de_experiencia = models.PositiveIntegerField(null=True, blank=True,
                                                      verbose_name="Años de Experiencia Profesional")

    ultimo_puesto = models.CharField(max_length=200, blank=True, verbose_name="Último Puesto Desempeñado")
    ultima_empresa = models.CharField(max_length=200, blank=True, verbose_name="Última Empresa donde Laboró")

    motivo_busqueda = models.CharField(
        max_length=10,
        choices=MotivoBusqueda.choices,
        blank=True,
        verbose_name="Razón por la que buscas nuevas oportunidades"
    )

    es_colaborador_actual = models.BooleanField(default=False, verbose_name="Ya soy colaborador de Premier")

    habilidades = models.TextField(blank=True, null=True, verbose_name="Habilidades Principales",
                                   help_text="Ej: Liderazgo, Excel Avanzado, Ventas, SAP, etc. (separadas por comas)")
    expectativa_salarial = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                               verbose_name="Expectativa Salarial Mensual (Bruta)")

    CIUDADES_RESIDENCIA_CHOICES = [
        ("CUL", "Culiacán"),
        ("MZT", "Mazatlán"),
        ("LMM", "Los Mochis"),
        ("GVE", "Guasave"),
        ("CJM", "Cajeme"),
        ("HMO", "Hermosillo"),
        ("MXL", "Mexicali"),
        ("TIJ", "Tijuana"),
        ("LPZ", "La Paz"),
        ("LCB", "Los Cabos"),
        ("CDMX", "CDMX"),
        ("MTY", "Monterrey"),
        ("OTRA", "Otra ciudad"),
    ]
    ciudad_residencia = models.CharField(
        max_length=4,
        choices=CIUDADES_RESIDENCIA_CHOICES,
        default="CUL",
        verbose_name="Ciudad de Residencia",
        help_text="Ciudad donde reside actualmente el candidato",
    )
    cv = models.FileField(
        upload_to="cvs/",
        blank=True,
        null=True,
        storage=CVStorage(),
        verbose_name="Curriculum Vitae",
        help_text="Suba el CV en formato PDF o Word",
    )
    fecha_registro = models.DateTimeField(auto_now_add=True)

    # --- Campos para control de candidatos no contratables (RH) ---
    es_no_contratable = models.BooleanField(
        default=False,
        verbose_name="¿Es No Contratable?",
        help_text="Marcar si el candidato está boletinado o vetado para contratación en el grupo"
    )
    motivo_no_contratable = models.TextField(
        blank=True,
        default="",
        verbose_name="Motivo de No Contratable",
        help_text="Razón detallada por la cual no es contratable"
    )

    @property
    def nombre_completo(self):
        return f"{self.nombres} {self.apellidos}"

    @property
    def proceso_activo(self):
        estados_finalizados = [
            Proceso.Estatus.DESCARTADO_CH,
            Proceso.Estatus.NO_PRUEBAS,
            Proceso.Estatus.ABANDONO,
            Proceso.Estatus.CONTRATADO,
        ]
        return self.procesos.exclude(estatus_proceso__in=estados_finalizados).first()

    def __str__(self):
        return self.nombre_completo


class Proceso(models.Model):
    class Estatus(models.TextChoices):
        NUEVO = 'NUEVO', 'Nuevo'
        CONTACTO = 'CONTACTO', 'Contactado por CH'
        PRUEBAS = 'PRUEBAS', 'Pruebas Integridad/Pyxoom'
        ENT_CH = 'ENT_CH', 'Entrevista CH'
        REF = 'REF', 'Referencias'
        ENT_JF = 'ENT_JF', 'Enviado a Entrevista con Jefe'
        CONF_JF = 'CONF_JF', 'Confirmado por Jefe'
        MEDICO = 'MEDICO', 'Examen Médico'
        DOCS = 'DOCS', 'Revisión Documentos'
        INGRESO_PROG = 'INGRESO_PROG', 'Fecha Ingreso / Cursos UP'
        ALTA_ADMIN = 'ALTA_ADMIN', 'Enviado a Alta'
        CONTRATADO = 'CONTRATADO', 'Ingresó - Cierra Plaza'
        # Terminales
        DESCARTADO_CH = 'DESCARTADO_CH', 'Descartado por Perfil'
        NO_PRUEBAS = 'NO_PRUEBAS', 'No Aprobó Integridad/Pyxoom'
        ABANDONO = 'ABANDONO', 'Abandonó Proceso'

    # Aliases de compatibilidad hacia atrás
    Estatus.CONTRATADO_CERRADO = Estatus.CONTRATADO
    Estatus.NO_APROBADO_PSICO = Estatus.NO_PRUEBAS
    Estatus.EN_BOLSA = Estatus.DESCARTADO_CH
    Estatus.ENTREVISTA_JEFE = Estatus.ENT_JF
    Estatus.ENTREVISTA_ASESORA = Estatus.ENT_CH
    Estatus.INTEGRIDAD = Estatus.PRUEBAS
    Estatus.PSICOMETRICOS = Estatus.PRUEBAS
    Estatus.REFERENCIAS = Estatus.REF
    Estatus.EXAMENES_MEDICOS = Estatus.MEDICO
    Estatus.SOLICITUD_DOCS = Estatus.DOCS
    Estatus.FECHA_INGRESO = Estatus.INGRESO_PROG
    Estatus.ALTA_SISTEMAS = Estatus.ALTA_ADMIN
    Estatus.FIRMA_CONTRATO = Estatus.ALTA_ADMIN

    class ResultadoIntegridad(models.TextChoices):
        APROBADO = 'APROBADO', 'Aprobado'
        NO_APROBADO = 'NO_APROBADO', 'No Aprobado'

    class ResultadoPyxoom(models.TextChoices):
        REPROBADO = 'REPROBADO', 'Reprobado'
        BAJO = 'BAJO', 'Bajo'
        OPTIMO = 'OPTIMO', 'Óptimo'
        IDEAL = 'IDEAL', 'Ideal'

    @classmethod
    def estatus_siguientes(cls, actual):
        secuencia = [
            cls.Estatus.NUEVO, cls.Estatus.CONTACTO, cls.Estatus.PRUEBAS,
            cls.Estatus.ENT_CH, cls.Estatus.REF, cls.Estatus.ENT_JF,
            cls.Estatus.CONF_JF, cls.Estatus.MEDICO, cls.Estatus.DOCS,
            cls.Estatus.INGRESO_PROG, cls.Estatus.ALTA_ADMIN, cls.Estatus.CONTRATADO,
        ]
        if actual not in secuencia or actual == cls.Estatus.CONTRATADO:
            return {actual}
        return {
            actual, secuencia[secuencia.index(actual) + 1],
            cls.Estatus.DESCARTADO_CH, cls.Estatus.NO_PRUEBAS, cls.Estatus.ABANDONO,
        }

    candidato = models.ForeignKey('Candidato', on_delete=models.CASCADE, related_name='procesos', verbose_name="Candidato")
    puesto = models.ForeignKey('Puesto', on_delete=models.SET_NULL, null=True, blank=True, related_name='procesos', verbose_name="Puesto Aplicado")
    asesora_asignada = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Asesora Asignada")
    estatus_proceso = models.CharField(max_length=20, choices=Estatus.choices, default=Estatus.NUEVO, verbose_name="Estatus del Proceso")
    fecha_inicio_etapa = models.DateTimeField(default=timezone.now, verbose_name="Inicio de Etapa")
    retroalimentacion = models.TextField(blank=True, default="", verbose_name="Retroalimentación / Notas")

    # Nuevos campos de evaluación RH
    resultado_integridad = models.CharField(
        max_length=20,
        choices=ResultadoIntegridad.choices,
        blank=True,
        null=True,
        verbose_name="Resultado Examen de Integridad"
    )
    resultado_pyxoom = models.CharField(
        max_length=20,
        choices=ResultadoPyxoom.choices,
        blank=True,
        null=True,
        verbose_name="Resultado Psicométrico Pyxoom"
    )
    fecha_envio_jefe_apto = models.DateTimeField(null=True, blank=True, editable=False)
    motivo_descarte = models.TextField(
        blank=True,
        default="",
        verbose_name="Motivo de Descarte / No Contratación"
    )

    @property
    def dias_en_etapa_actual(self):
        if not self.fecha_inicio_etapa:
            return 0
        return max(0, (timezone.now() - self.fecha_inicio_etapa).days)

    @property
    def esta_estancado(self):
        terminales = [
            self.Estatus.CONTRATADO,
            self.Estatus.DESCARTADO_CH,
            self.Estatus.NO_PRUEBAS,
            self.Estatus.ABANDONO,
        ]
        if self.estatus_proceso in terminales:
            return False
        return self.dias_en_etapa_actual >= 30

    @property
    def registros_de_actividad(self):
        return RegistroActividad.objects.filter(tipo_objeto='Proceso', id_objeto=self.id).order_by('fecha_hora')

    def __str__(self):
        puesto_titulo = self.puesto.titulo.nombre if self.puesto and self.puesto.titulo else "N/A"
        return f"{self.candidato.nombre_completo} -> {puesto_titulo} ({self.get_estatus_proceso_display()})"


class RegistroActividad(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    fecha_hora = models.DateTimeField(auto_now_add=True)
    accion = models.CharField(max_length=255, verbose_name="Acción Realizada")
    tipo_objeto = models.CharField(max_length=50, blank=True, null=True)
    id_objeto = models.PositiveIntegerField(blank=True, null=True)
    detalles = models.TextField(blank=True, null=True, verbose_name="Detalles Adicionales (Notas)")

    class Meta:
        verbose_name = "Registro de Actividad"
        verbose_name_plural = "Registros de Actividad"
        ordering = ['-fecha_hora']

    def __str__(self):
        return f"[{self.fecha_hora.strftime('%Y-%m-%d %H:%M')}] {self.usuario.username if self.usuario else 'Sistema'}: {self.accion}"


class PerfilDePuesto(models.Model):
    class Sexo(models.TextChoices):
        HOMBRE = 'H', 'Hombre'
        MUJER = 'M', 'Mujer'
        INDISTINTO = 'I', 'Indistinto'

    class MotivoSexo(models.TextChoices):
        EQUIDAD = 'EQ', 'Por equidad de género en el área'
        FUERZA = 'FZ', 'Por requerimiento de fuerza física'
        OTRO = 'OT', 'Otro motivo justificado'

    class AreaExperiencia(models.TextChoices):
        VENTAS = 'VTAS', 'Ventas/Comercial'
        SERVICIO = 'SERV', 'Servicio al cliente'
        ADMIN = 'ADM', 'Administrativo'
        OPERATIVO = 'OPE', 'Operativo (Taller)'

    class ImportanciaApariencia(models.TextChoices):
        ALTA = 'ALTA', 'Importa mucho'
        BAJA = 'BAJA', 'No importa'

    class Licencia(models.TextChoices):
        SI = 'SI', 'Sí'
        NO = 'NO', 'No'

    puesto = models.OneToOneField(Puesto, on_delete=models.CASCADE, related_name="perfil_detallado")
    rango_edad = models.CharField(max_length=50, blank=True, default="", verbose_name="1. Rango de edad ideal")
    preferencia_sexo = models.CharField(max_length=1, choices=Sexo.choices, default=Sexo.INDISTINTO, verbose_name="2. ¿Preferencia de sexo?")
    area_experiencia_enfoque = models.CharField(max_length=4, choices=AreaExperiencia.choices, blank=True, default=AreaExperiencia.VENTAS, verbose_name="4. ¿En qué área de experiencia nos enfocamos más?")
    importancia_apariencia = models.CharField(max_length=4, choices=ImportanciaApariencia.choices, blank=True, default=ImportanciaApariencia.BAJA, verbose_name="5. ¿Qué importancia tiene la apariencia personal?")
    feedback_anterior = models.TextField(blank=True, default="", verbose_name="6. ¿Qué te gustaría que se repitiera y qué no del ocupante anterior?")
    requiere_licencia = models.CharField(max_length=2, choices=Licencia.choices, blank=True, default=Licencia.NO, verbose_name="7. ¿Requiere licencia y saber conducir estándar?")
    motivo_preferencia_sexo = models.CharField(max_length=3, choices=MotivoSexo.choices, blank=True, null=True, verbose_name="3. Motivo de la preferencia")
    justificacion_apariencia = models.TextField(blank=True, default="", verbose_name="5a. Si importa mucho, ¿por qué?")
    comentarios_adicionales = models.TextField(blank=True, default="", verbose_name="Comentarios adicionales")
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    modificado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='perfiles_modificados', verbose_name="Última modificación por")
    fecha_ultima_modificacion = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de última modificación")

    def __str__(self):
        return f"Perfil para {self.puesto.titulo.nombre if self.puesto.titulo else 'Puesto'}"


class Aviso(models.Model):
    titulo = models.CharField(max_length=200, verbose_name="Título del Aviso")
    contenido = models.TextField(verbose_name="Contenido del Aviso")
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, verbose_name="Autor")
    esta_activo = models.BooleanField(default=True, verbose_name="¿Aviso Activo?")

    class Meta:
        verbose_name = "Aviso General"
        verbose_name_plural = "Avisos Generales"
        ordering = ['-fecha_creacion']

    @property
    def activo(self):
        return self.esta_activo

    @activo.setter
    def activo(self, value):
        self.esta_activo = bool(value)

    def __str__(self):
        return self.titulo
