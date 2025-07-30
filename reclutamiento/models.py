from django.db import models
from django.utils import timezone
from django.conf import settings
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
# Ya no hay 'from .models import Puesto'
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
    Asegura que cada User tenga un PerfilUsuario asociado.
    Si el usuario es nuevo, crea el perfil.
    Si el usuario ya existe pero no tiene perfil, se lo crea.
    Si ya existe el perfil, no hace nada.
    """
    PerfilUsuario.objects.get_or_create(usuario=instance)

    # Para usuarios existentes, nos aseguramos de que el perfil se guarde.
    # El related_name por defecto es el nombre del modelo en minúsculas.
    # hasattr comprueba si el atributo existe antes de intentar acceder a él.
    if hasattr(instance, 'perfilusuario'):
        instance.perfilusuario.save()
    else:
        # Si no tiene perfil (porque es un usuario antiguo), se lo creamos.
        PerfilUsuario.objects.create(usuario=instance)


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
    agencia = models.CharField(max_length=100, verbose_name="Agencia")
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

    # --- Flujo de Aprobación y Asignación (campos que ya teníamos) ---
    estatus_autorizacion = models.CharField(max_length=20, choices=EstatusAutorizacion.choices, default=EstatusAutorizacion.PENDIENTE)
    solicitado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='puestos_solicitados')
    fecha_solicitud = models.DateTimeField(default=timezone.now)
    autorizado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='puestos_autorizados')
    fecha_autorizacion = models.DateTimeField(null=True, blank=True)
    segundo_autorizado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                               related_name='puestos_segunda_autorizacion',
                                               verbose_name="Segunda Aprobación Por")
    fecha_segunda_autorizacion = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de Segunda Aprobación")
    esta_abierto = models.BooleanField(default=False)
    asesora_encargada = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='puestos_asignados')

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
        estados_finalizados = ['NO_APROBADO_PSICO', 'EN_BOLSA', 'FECHA_INGRESO']
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


# --- SEÑALES AL FINAL ---
@receiver(post_save, sender=User)
def ensure_user_profile(sender, instance, **kwargs):
    """
    Asegura que cada User tenga un PerfilUsuario asociado.
    Si el usuario es nuevo, crea el perfil.
    Si el usuario ya existe pero no tiene perfil, se lo crea.
    Si ya existe el perfil, no hace nada.
    """
    PerfilUsuario.objects.get_or_create(usuario=instance)


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