from django.db import models
from django.utils import timezone
from django.conf import settings
from django.contrib.auth.models import User
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.exceptions import ObjectDoesNotExist
from django.core.cache import cache

class Marca(models.Model):
    nombre = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.nombre

class PerfilUsuario(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE)
    marcas = models.ManyToManyField(Marca, blank=True)

    def __str__(self):
        return self.usuario.username

class CatalogoPuesto(models.Model):
    nombre = models.CharField(max_length=200, unique=True, verbose_name="Nombre del Puesto")

    class Meta:
        ordering = ['nombre']
        verbose_name = "Puesto de Catálogo"
        verbose_name_plural = "Catálogo de Puestos"

    def __str__(self):
        return self.nombre

@receiver(post_save, sender=User)
def ensure_user_profile(sender, instance, **kwargs):
    """
    Asegura que cada User tenga un PerfilUsuario asociado sin duplicación ni doble save().
    """
    PerfilUsuario.objects.get_or_create(usuario=instance)


class Puesto(models.Model):
    CIUDADES_CHOICES = [
        ('CUL', 'Culiacán'), ('MZT', 'Mazatlán'), ('LMM', 'Los Mochis'),
        ('GVE', 'Guasave'), ('CJM', 'Cajeme'), ('HMO', 'Hermosillo'),
        ('MXL', 'Mexicali'), ('TIJ', 'Tijuana'), ('LPZ', 'La Paz'),
        ('LCB', 'Los Cabos'), ('CDMX', 'CDMX'), ('MTY', 'Monterrey'),
    ]


    class EstatusAutorizacion(models.TextChoices):
        PENDIENTE = 'PENDIENTE', 'Pendiente de Aprobación de Gerente de Marca'
        # CAMBIO: Ahora es pendiente de Director
        PENDIENTE_DIR = 'PENDIENTE_DIR', 'Pendiente de Aprobación de Dirección'
        AUTORIZADO = 'AUTORIZADO', 'Autorizado'
        RECHAZADO = 'RECHAZADO', 'Rechazado'
    marca = models.ForeignKey(Marca, on_delete=models.PROTECT, verbose_name="Marca", null=True)

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

    aprobado_por_gerente_marca = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                                   related_name='puestos_aprobados_gm',
                                                   verbose_name="Aprobado por Gerente de Marca")
    fecha_aprobacion_gerente_marca = models.DateTimeField(null=True, blank=True,
                                                          verbose_name="Fecha Aprobación Gerente de Marca")

    aprobado_por_director = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                              related_name='puestos_aprobados_dir',
                                              verbose_name="Aprobado por Director")
    fecha_aprobacion_director = models.DateTimeField(null=True, blank=True, verbose_name="Fecha Aprobación Director")
    # --- Campos del Puesto ---
    titulo = models.ForeignKey(CatalogoPuesto, on_delete=models.PROTECT, verbose_name="Nombre del Puesto Vacante", null=True)
    agencia = models.CharField(max_length=100, verbose_name="Agencia", db_index=True)
    area = models.CharField(max_length=4, choices=Area.choices, verbose_name="Área")
    ciudad = models.CharField(max_length=100, verbose_name="Ciudad de la Vacante", choices=CIUDADES_CHOICES)
    cantidad_vacantes = models.PositiveIntegerField(default=1, verbose_name="Cantidad de Vacantes Solicitadas")
    experiencia_minima = models.PositiveIntegerField(null=True, blank=True, verbose_name="Experiencia Mínima (años)",
                                                     help_text="Años de experiencia requeridos para el puesto.")
    carrera_sugerida = models.CharField(max_length=200, blank=True, verbose_name="Carrera o Especialidad Sugerida")
    reemplaza_a = models.CharField(max_length=200, blank=True,
                                   verbose_name="Nombre de la persona a quien reemplaza (si aplica)")
    # --- Detalles del Jefe ---
    nombre_jefe_inmediato = models.CharField(max_length=200, verbose_name="Nombre del Jefe Inmediato")
    puesto_jefe_inmediato = models.CharField(max_length=200, verbose_name="Puesto del Jefe Inmediato")

    # --- Justificación y Descripción ---
    motivo_requisicion = models.CharField(max_length=4, choices=Motivo.choices, verbose_name="Motivo de la Requisición")
    objetivo_puesto = models.TextField(verbose_name="Objetivo/Propósito del Puesto")
    funciones_puesto = models.TextField(verbose_name="Actividades o Funciones Principales (5)", help_text="Listar las 5 funciones más importantes.")
    indicador_puesto = models.TextField(verbose_name="Indicador más relevante con el que se mide el puesto")

    # --- Requisitos y Condiciones ---
    herramientas_puesto = models.CharField(max_length=255, verbose_name="Herramientas específicas de uso (Office, programas, etc.)", help_text="Puede colocar 'No aplica'.")
    conocimientos_tecnicos = models.CharField(max_length=255, verbose_name="Conocimientos técnicos específicos", help_text="Puede colocar 'No aplica'.")
    horario = models.CharField(max_length=100, verbose_name="Horario a cubrir")
    sueldo_base = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Sueldo Base Mensual (Bruto)")
    esquema_comisiones = models.TextField(blank=True, verbose_name="Esquema de comisiones y/o bonos (si aplica)")
    # --- AÑADE ESTE NUEVO CAMPO ---
    archivo_justificacion = models.FileField(
        upload_to='justificaciones/',
        null=True,
        blank=True,
        verbose_name="Archivo de Justificación (Opcional)",
        help_text="Anexa un correo o documento que respalde la solicitud (PDF, Word, etc.)"
    )
    es_confidencial = models.BooleanField(default=False, verbose_name="¿Es una vacante confidencial?")
    motivo_rechazo = models.TextField(null=True, blank=True, verbose_name="Motivo de Rechazo")

    # --- Flujo de Aprobación y Asignación (campos que ya teníamos) ---
    estatus_autorizacion = models.CharField(max_length=20, choices=EstatusAutorizacion.choices, default=EstatusAutorizacion.PENDIENTE, db_index=True)
    solicitado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='puestos_solicitados')
    fecha_solicitud = models.DateTimeField(default=timezone.now)
    autorizado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='puestos_autorizados')
    fecha_autorizacion = models.DateTimeField(null=True, blank=True)
    segundo_autorizado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                               related_name='puestos_segunda_autorizacion',
                                               verbose_name="Segunda Aprobación Por")
    fecha_segunda_autorizacion = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de Segunda Aprobación")
    esta_abierto = models.BooleanField(default=False, db_index=True)
    asesora_encargada = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='puestos_asignados')

    METAS_POR_PUESTO_DEFAULT = {
        'Asesor(a) de ventas': 20, 'Asesor(a) de ventas de flotillas': 20, 'Asesor de servicio': 20,
        'Vendedor Ecommerce': 12, 'Vendedor de Mayoreo Colisión': 12, 'Vendedor de Mayoreo Foráneo': 12,
        'Vendedor de Mayoreo Partes': 12, 'Asesor de ventas accesorios': 12, 'Vendedor de Mostrador': 12,
        'Previador': 12, 'Asesor(a) leads': 12, 'Intercambios': 12, 'Guardia de seguridad': 12,
        'Lavador de autos': 12, 'Chofer': 12, 'Chofer/Almacenisa': 12, 'Ayudante de Técnico': 12,
        'Hojalatero': 12, 'Pintor': 12, 'Preparador': 12, 'Pulidor': 12, 'Asesor de HYP': 12,
        'Despachador de Body shop': 12, 'Despachador de Ventanilla': 12, 'Encargado de patio': 12,
        'Encargado de Exhibición y Demos': 12, 'Encargado de Previas': 12, 'Jefe de lavado': 12,
        'Responding': 12, 'Especialista de marketing Digital': 12, 'Auxiliar contable': 20,
        'Auxiliar de F&I': 12, 'Administradora de ventas': 12, 'Facturista': 12,
        'Comprador(a) de autos': 12, 'Asistente de dirección': 12, 'Auxiliar de Citas': 12,
        'Administrador(a) de garantías': 12, 'Auxiliar de Garantías': 12, 'Auxiliar administrativo': 12,
        'Auxiliar administrativo HYP': 12, 'Almacenista': 12, 'Conmutador': 12,
        'Encargado(a) de Caja general': 12, 'Asesor(a) de capital humano': 12,
        'Auxiliar Crédito y Cobranza': 12, 'Cobrador': 12, 'Encargado(a) de Crédito y cobranza': 12,
        'Contador(a) general': 12, 'Office boy': 12, 'Subcontador(a)': 12, 'Practicante': 10,
        'Asesor de sistemas': 20, 'Control de Calidad': 20, 'Técnico en Diagnóstico': 20,
        'Técnico en Mantenimiento': 20, 'Técnico en Reparación': 20, 'Técnico Master': 20,
        'Técnico de HyP': 20, 'Valuador': 20, 'Auditor Interno': 20, 'Capacitador': 20,
        'Auditor(a) de marca': 20, 'Asesor(a) de Mejora Continua': 20, 'Especialista en contenido': 20,
        'Diseñador(a) Sr.': 20, 'Diseñador(a) training': 20, 'Ejecutivo(a) de Responding': 20,
        'Ejecutiva de Imagen': 20, 'Especialista en Paid Media': 20,
        'Especialista en Paid Media Training': 20, 'Productor(a) Audiovisual': 20,
        'User Experience Jr': 20, 'Ejecutivo(a) BTL': 20, 'Médico general': 20,
        'Técnico de motos': 20, 'Técnico de autos': 20, 'Asesor(a) de Normatividad': 20,
        'Encargado de mantenimiento': 20, 'Coord Gastos Médicos Mayores': 20,
        'Subgerente de Capital Humano': 20, 'Coord. Desarrollo y Bienestar': 20,
        'Coord. Vinculación con la Comunidad': 20, 'Coord. Comunicación interna': 20,
        'Coord. De Clima y Mentoring': 20, 'Gerente de ATL y Digital': 20, 'Gerente de BTL': 20,
        'Gerente de Hospitalidad': 20, 'Subgerente de ventas': 20,
        'Encargado(a) de Mejora continua': 20, 'Encargado(a) de Mercadotecnia': 20,
        'Encargado de Sistemas': 20, 'Coordinador de Seguridad': 20, 'Supervisor de seguridad': 20,
        'Coordinador(a) de Hospitalidad y Responding': 20, 'Coordinador(a) de Publicidad': 20,
        'Coordinador(a) ETA': 20, 'Coordinador(a) Digital': 20, 'Jefe de taller HyP': 20,
        'Jefe de taller': 20, 'Coordinador de HYP': 20, 'Encargado de compras': 20,
        'Jefe de almacén': 20, 'Jefe de Mayoreo de Colisión': 20, 'Jefe de Mayoreo Partes': 20,
        'Jefe de ventas Mostrador': 20, 'Subgerente de refacciones': 20, 'Subgerente de Sistemas': 20,
        'Coordinador(a) de Leds': 20, 'Encargado(a) de Inventarios': 20,
        'Coordinador(a) de Citas': 20, 'Coordinador(a) de asesores de servicio': 20,
        'Encargado(a) de F&I': 20, 'Gerente General / Comercial / Director': 30,
        'Gerente de servicio / ventas /  refacciones / administrativo / seminuevos / HYP': 25,
        'Gerente Corporativo': 25
    }

    @property
    def plazas_cubiertas(self):
        if hasattr(self, '_prefetched_objects_cache') and 'procesos' in self._prefetched_objects_cache:
            return sum(1 for pr in self.procesos.all() if pr.estatus_proceso == Proceso.Estatus.CONTRATADO_CERRADO)
        return self.procesos.filter(estatus_proceso=Proceso.Estatus.CONTRATADO_CERRADO).count()

    @property
    def plazas_pendientes(self):
        return max(0, self.cantidad_vacantes - self.plazas_cubiertas)

    @property
    def esta_completamente_cubierta(self):
        return self.plazas_cubiertas >= self.cantidad_vacantes

    @property
    def dias_meta(self):
        puesto_nom = self.titulo.nombre.strip() if self.titulo and self.titulo.nombre else ""
        return self.METAS_POR_PUESTO_DEFAULT.get(puesto_nom, 20)

    @property
    def fecha_inicio_sla(self):
        """El reloj de SLA inicia formalmente cuando la vacante es autorizada (o fecha_solicitud si sigue en proceso de aprobación)."""
        return self.fecha_aprobacion_director or self.fecha_aprobacion_gerente_marca or self.fecha_solicitud

    @property
    def dias_transcurridos(self):
        fecha_inicio = self.fecha_inicio_sla
        if not self.esta_abierto:
            if self.estatus_autorizacion == self.EstatusAutorizacion.RECHAZADO:
                fecha_fin = self.fecha_aprobacion_director or self.fecha_aprobacion_gerente_marca or self.fecha_solicitud
            else:
                if hasattr(self, '_prefetched_objects_cache') and 'procesos' in self._prefetched_objects_cache:
                    contratados = [pr for pr in self.procesos.all() if pr.estatus_proceso == Proceso.Estatus.CONTRATADO_CERRADO]
                    contratados.sort(key=lambda pr: pr.fecha_inicio_etapa or timezone.now(), reverse=True)
                    ultimo_contratado = contratados[0] if contratados else None
                else:
                    ultimo_contratado = self.procesos.filter(
                        estatus_proceso=Proceso.Estatus.CONTRATADO_CERRADO
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
    def etapa_operativa(self):
        if self.estatus_autorizacion in [self.EstatusAutorizacion.PENDIENTE, self.EstatusAutorizacion.PENDIENTE_DIR]:
            return '1. En Aprobación'
        if self.estatus_autorizacion == self.EstatusAutorizacion.RECHAZADO:
            return 'Rechazada / Cancelada'
        if not self.esta_abierto:
            return '8. Cubierta / Cerrada'
        if not self.asesora_encargada:
            return '2. Por Asignar Asesora'
        try:
            _ = self.perfil_detallado
        except ObjectDoesNotExist:
            return '3. Por Definir Perfil'

        if hasattr(self, '_prefetched_objects_cache') and 'procesos' in self._prefetched_objects_cache:
            procesos_activos = [
                pr for pr in self.procesos.all()
                if pr.estatus_proceso not in (Proceso.Estatus.NO_APROBADO_PSICO, Proceso.Estatus.EN_BOLSA)
            ]
            if not procesos_activos:
                return '4. En Búsqueda'
            estatus_set = {pr.estatus_proceso for pr in procesos_activos}
        else:
            procesos_activos = self.procesos.exclude(
                estatus_proceso__in=[Proceso.Estatus.NO_APROBADO_PSICO, Proceso.Estatus.EN_BOLSA]
            )
            if not procesos_activos.exists():
                return '4. En Búsqueda'
            estatus_set = set(procesos_activos.values_list('estatus_proceso', flat=True))

        tramites = [
            Proceso.Estatus.EXAMENES_MEDICOS, Proceso.Estatus.SOLICITUD_DOCS,
            Proceso.Estatus.FIRMA_CONTRATO, Proceso.Estatus.ALTA_SISTEMAS, Proceso.Estatus.FECHA_INGRESO
        ]
        if any(e in estatus_set for e in tramites):
            return '7. En Trámites de Ingreso'
        if Proceso.Estatus.ENTREVISTA_JEFE in estatus_set:
            return '6. En Entrevista con Jefe Inmediato'
        filtros = [
            Proceso.Estatus.NUEVO, Proceso.Estatus.INTEGRIDAD,
            Proceso.Estatus.PSICOMETRICOS, Proceso.Estatus.REFERENCIAS,
            Proceso.Estatus.ENTREVISTA_ASESORA
        ]
        if any(e in estatus_set for e in filtros):
            return '5. En Filtros y Evaluaciones'

        return '4. En Búsqueda'

    @property
    def candidato_mas_avanzado(self):
        if hasattr(self, '_prefetched_objects_cache') and 'procesos' in self._prefetched_objects_cache:
            activos = [
                pr for pr in self.procesos.all()
                if pr.estatus_proceso not in (Proceso.Estatus.NO_APROBADO_PSICO, Proceso.Estatus.EN_BOLSA)
            ]
        else:
            activos = list(self.procesos.exclude(
                estatus_proceso__in=[Proceso.Estatus.NO_APROBADO_PSICO, Proceso.Estatus.EN_BOLSA]
            ))
        if not activos:
            return None
        etapa_pesos = {
            Proceso.Estatus.NUEVO: 1,
            Proceso.Estatus.INTEGRIDAD: 2,
            Proceso.Estatus.PSICOMETRICOS: 3,
            Proceso.Estatus.REFERENCIAS: 4,
            Proceso.Estatus.ENTREVISTA_ASESORA: 5,
            Proceso.Estatus.ENTREVISTA_JEFE: 6,
            Proceso.Estatus.EXAMENES_MEDICOS: 7,
            Proceso.Estatus.SOLICITUD_DOCS: 8,
            Proceso.Estatus.FIRMA_CONTRATO: 9,
            Proceso.Estatus.ALTA_SISTEMAS: 10,
            Proceso.Estatus.FECHA_INGRESO: 11,
            Proceso.Estatus.CONTRATADO_CERRADO: 12,
        }
        activos.sort(key=lambda p: (etapa_pesos.get(p.estatus_proceso, 0), p.fecha_inicio_etapa or timezone.now()), reverse=True)
        return activos[0].candidato

    @property
    def ultima_observacion(self):
        proc = self.procesos.order_by('-fecha_inicio_etapa').first()
        return proc.retroalimentacion if proc and proc.retroalimentacion else "Sin observaciones"

    def __str__(self):
        return f"{self.titulo} ({self.get_ciudad_display()})"


class Publicacion(models.Model):
    PLATAFORMAS = [
        ('FB', 'Facebook'), ('IG', 'Instagram'), ('LI', 'LinkedIn'),
        ('OCC', 'OCC Mundial'), ('CT', 'Computrabajo'), ('OTRA', 'Otra'),
    ]
    puesto = models.ForeignKey(Puesto, on_delete=models.CASCADE, related_name="publicaciones")
    plataforma = models.CharField(max_length=4, choices=PLATAFORMAS, verbose_name="Plataforma")
    enlace = models.URLField(max_length=500, verbose_name="Enlace al Post")
    monto_inversion = models.DecimalField(max_digits=8, decimal_places=2, default=0, verbose_name="Monto de Inversión (MXN)")

    fecha_publicacion = models.DateField(default=timezone.now)
    publicado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name = "Publicación de Vacante"
        verbose_name_plural = "Publicaciones de Vacantes"
        ordering = ['-fecha_publicacion']

    def __str__(self): return f"Publicación para {self.puesto.titulo} en {self.get_plataforma_display()}"


# reclutamiento/models.py

class Candidato(models.Model):
    # --- LISTA DE OPCIONES PARA LOS CAMPOS ---
    NIVELES_EDUCATIVOS = [
        ('SEC', 'Secundaria'),
        ('TEC', 'Técnico / Preparatoria'),
        ('LIC', 'Licenciatura'),
        ('MAE', 'Maestría'),
        ('DOC', 'Doctorado'),
        ('OTR', 'Otro'),
    ]

    # --- NUEVA LISTA DE OPCIONES PARA EL MOTIVO DE BÚSQUEDA ---
    class MotivoBusqueda(models.TextChoices):
        DESAFIO = 'DESAFIO', 'Desafío personal'
        CRECIMIENTO = 'CREC', 'Crecimiento profesional'
        SALARIO = 'SALARIO', 'Mejor salario'
        CULTURA = 'CULTURA', 'Cultura empresarial saludable'

    # --- CAMPOS DEL MODELO ---
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

    # CAMBIO: Ahora es un CharField con opciones y es opcional
    motivo_busqueda = models.CharField(
        max_length=10,
        choices=MotivoBusqueda.choices,
        blank=True,
        verbose_name="Razón por la que buscas nuevas oportunidades"
    )

    # NUEVO CAMPO: Checkbox para saber si es colaborador
    es_colaborador_actual = models.BooleanField(default=False, verbose_name="Ya soy colaborador de Premier")

    habilidades = models.TextField(blank=True, null=True, verbose_name="Habilidades Principales",
                                   help_text="Ej: Liderazgo, Excel Avanzado, Ventas, SAP, etc. (separadas por comas)")
    expectativa_salarial = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                               verbose_name="Expectativa Salarial Mensual (Bruta)")
    cv = models.FileField(upload_to='cvs/', blank=True, null=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)

    # --- PROPIEDAD RESTAURADA Y ESENCIAL ---
    @property
    def nombre_completo(self):
        return f"{self.nombres} {self.apellidos}"

    # La propiedad proceso_activo no cambia
    @property
    def proceso_activo(self):
        estados_finalizados = [
            Proceso.Estatus.NO_APROBADO_PSICO,
            Proceso.Estatus.EN_BOLSA,
            Proceso.Estatus.FECHA_INGRESO,
            Proceso.Estatus.CONTRATADO_CERRADO,
        ]
        return self.procesos.exclude(estatus_proceso__in=estados_finalizados).first()

    def __str__(self):
        return self.nombre_completo


class Proceso(models.Model):
    class Estatus(models.TextChoices):
        NUEVO = 'NUEVO', 'Nuevo'
        INTEGRIDAD = 'INTEG', 'Examen de Integridad'
        PSICOMETRICOS = 'PSICO', 'Examen de Psicometría'
        REFERENCIAS = 'REF', 'Validación de Referencias'
        # Punto de traspaso
        ENTREVISTA_ASESORA = 'ENT_AS', 'Entrevista con Asesora'
        ENTREVISTA_JEFE = 'ENT_JF', 'Entrevista con Jefe Inmediato'
        EXAMENES_MEDICOS = 'MEDIC', 'Exámenes Médicos'
        SOLICITUD_DOCS = 'DOCS', 'Solicitud de Documentos'
        FIRMA_CONTRATO = 'FIRMA', 'Firma de Contrato'
        ALTA_SISTEMAS = 'ALTA', 'Alta en Sistemas (Contabilidad, GMM, etc.)'
        FECHA_INGRESO = 'INGRESO', 'Fecha de Ingreso Confirmada'
        # Estatus finales que devuelven al candidato a la bolsa
        NO_APROBADO_PSICO = 'NO_PSICO', 'No Aprobado (Psicometría/Integridad)'
        EN_BOLSA = 'EN_BOLSA', 'En Bolsa de Trabajo (No Continuó)'
        CONTRATADO_CERRADO = 'CONTRATADO', 'Contratado (Cierra Vacante)'

    candidato = models.ForeignKey('Candidato', on_delete=models.CASCADE, related_name='procesos', verbose_name="Candidato")
    puesto = models.ForeignKey('Puesto', on_delete=models.SET_NULL, null=True, blank=True, related_name='procesos', verbose_name="Puesto Aplicado")
    asesora_asignada = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Asesora Asignada")
    estatus_proceso = models.CharField(max_length=20, choices=Estatus.choices, default=Estatus.NUEVO, verbose_name="Estatus del Proceso")
    fecha_inicio_etapa = models.DateTimeField(default=timezone.now, verbose_name="Inicio de Etapa")
    retroalimentacion = models.TextField(blank=True)

    # --- ESTA ES LA FUNCIÓN CORRECTA PARA OBTENER EL HISTORIAL ---
    @property
    def registros_de_actividad(self):
        return RegistroActividad.objects.filter(tipo_objeto='Proceso', id_objeto=self.id).order_by('fecha_hora')

    def __str__(self):
        puesto_titulo = self.puesto.titulo if self.puesto else "N/A"
        return f"{self.candidato.nombre_completo} para {puesto_titulo}"


@receiver([post_save, post_delete], sender=Puesto)
def invalidar_cache_puesto(sender, instance, **kwargs):
    cache.clear()


@receiver([post_save, post_delete], sender=Proceso)
def invalidar_cache_proceso(sender, instance, **kwargs):
    cache.clear()


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
        return f"{self.fecha_hora.strftime('%Y-%m-%d %H:%M')} - {self.usuario.username if self.usuario else 'Sistema'} - {self.accion}"


class PerfilDePuesto(models.Model):
    class Sexo(models.TextChoices):
        HOMBRE = 'H', 'Hombre'
        MUJER = 'M', 'Mujer'
        INDISTINTO = 'I', 'Indistinto'

    class MotivoSexo(models.TextChoices):
        DESEMPENO = 'DES', 'Afecta el desempeño'
        COSTUMBRE = 'COS', 'Costumbre'
        OTRO = 'OTR', 'Otro motivo'

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

    # Conexión uno a uno con la requisición de Puesto.
    puesto = models.OneToOneField(Puesto, on_delete=models.CASCADE, related_name="perfil_detallado")

    # --- CAMPOS ACTUALIZADOS ---

    # Campos que ahora son OBLIGATORIOS (hemos quitado blank=True)
    rango_edad = models.CharField(max_length=50, verbose_name="1. Rango de edad ideal")
    preferencia_sexo = models.CharField(max_length=1, choices=Sexo.choices, default=Sexo.INDISTINTO,
                                        verbose_name="2. ¿Preferencia de sexo?")
    area_experiencia_enfoque = models.CharField(max_length=4, choices=AreaExperiencia.choices,
                                                verbose_name="4. ¿En qué área de experiencia nos enfocamos más?")
    importancia_apariencia = models.CharField(max_length=4, choices=ImportanciaApariencia.choices,
                                              verbose_name="5. ¿Qué importancia tiene la apariencia personal?")
    feedback_anterior = models.TextField(
        verbose_name="6. ¿Qué te gustaría que se repitiera y qué no del ocupante anterior?")
    requiere_licencia = models.CharField(max_length=2, choices=Licencia.choices,
                                         verbose_name="7. ¿Requiere licencia y saber conducir estándar?")

    # Campos que siguen siendo opcionales o condicionales
    motivo_preferencia_sexo = models.CharField(max_length=3, choices=MotivoSexo.choices, blank=True, null=True,
                                               verbose_name="3. Motivo de la preferencia")
    justificacion_apariencia = models.TextField(blank=True, verbose_name="5a. Si importa mucho, ¿por qué?")
    comentarios_adicionales = models.TextField(blank=True, verbose_name="Comentarios adicionales")

    # ... (Campos de auditoría no cambian) ...

    # Auditoría (sin cambios)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Perfil para {self.puesto.titulo.nombre}"


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

    def __str__(self):
        return self.titulo