# reclutamiento/forms.py
from django import forms
from .models import Puesto, Candidato, Publicacion, PerfilDePuesto
from django.core.exceptions import ValidationError
import filetype # Importamos la librería para la validación de archivos


class SolicitudPuestoForm(forms.ModelForm):
    class Meta:
        model = Puesto
        # --- LISTA COMPLETA Y FINAL DE CAMPOS PARA LA REQUISICIÓN ---
        fields = [
            'marca', 'agencia', 'titulo', 'ciudad', 'area', 'cantidad_vacantes',
            'nombre_jefe_inmediato', 'puesto_jefe_inmediato',
            'motivo_requisicion',
            'reemplaza_a',  # <-- AÑADIDO AQUÍ, ESTE ERA EL CAMPO FALTANTE
            'objetivo_puesto', 'funciones_puesto',
            'indicador_puesto',
            'experiencia_minima',
            'carrera_sugerida',
            'herramientas_puesto', 'conocimientos_tecnicos',
            'horario', 'sueldo_base', 'esquema_comisiones',
            'archivo_justificacion',
            'es_confidencial'
        ]
        # Los widgets no necesitan cambios
        widgets = {
            'funciones_puesto': forms.Textarea(attrs={'rows': 5}),
            'esquema_comisiones': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Describe los bonos, comisiones, etc. Si no aplica, déjalo en blanco.'}),
            'objetivo_puesto': forms.Textarea(attrs={'rows': 3}),
            'indicador_puesto': forms.Textarea(attrs={'rows': 3}),
            'reemplaza_a': forms.TextInput(attrs={'placeholder': 'Nombre del colaborador anterior'}),
        }


# reclutamiento/forms.py

class PerfilDePuestoForm(forms.ModelForm):
    class Meta:
        model = PerfilDePuesto
        # --- LISTA DE CAMPOS ACTUALIZADA CON LOS NUEVOS CAMPOS ---
        fields = [
            'rango_edad',
            'preferencia_sexo',
            'motivo_preferencia_sexo',
            'area_experiencia_enfoque',
            'importancia_apariencia',
            'justificacion_apariencia',
            'feedback_anterior',
            'requiere_licencia',
            'comentarios_adicionales',
        ]
        widgets = {
            # Hacemos que las opciones se vean como botones de radio en lugar de un menú
            'preferencia_sexo': forms.RadioSelect,
            'motivo_preferencia_sexo': forms.RadioSelect,
            'importancia_apariencia': forms.RadioSelect,
            'requiere_licencia': forms.RadioSelect,
            # Hacemos los campos de texto más grandes para facilidad de uso
            'justificacion_apariencia': forms.Textarea(attrs={'rows': 3}),
            'feedback_anterior': forms.Textarea(attrs={'rows': 4}),
            'comentarios_adicionales': forms.Textarea(attrs={'rows': 4}),
        }

    # --- NUEVA FUNCIÓN DE VALIDACIÓN PERSONALIZADA ---
    def clean(self):
        cleaned_data = super().clean()

        # Regla 1: Si se elige preferencia de sexo, el motivo es obligatorio
        preferencia_sexo = cleaned_data.get("preferencia_sexo")
        motivo_preferencia = cleaned_data.get("motivo_preferencia_sexo")

        if preferencia_sexo in ['H', 'M'] and not motivo_preferencia:
            self.add_error('motivo_preferencia_sexo',
                           "Este campo es obligatorio si se especifica una preferencia de sexo.")

        # Regla 2: Si la apariencia es muy importante, la justificación es obligatoria
        importancia_apariencia = cleaned_data.get("importancia_apariencia")
        justificacion_apariencia = cleaned_data.get("justificacion_apariencia")

        if importancia_apariencia == 'ALTA' and not justificacion_apariencia:
            self.add_error('justificacion_apariencia',
                           "Debe justificar por qué la apariencia es muy importante para este puesto.")

        return cleaned_data

class RegistroCandidatoForm(forms.ModelForm):
    # Sobreescribimos el campo para tener control total
    puesto_de_interes = forms.ChoiceField(
        required=False,
        label="¿Te interesa un puesto en particular?"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Obtenemos los puestos activos de la base de datos
        puestos_activos = Puesto.objects.filter(esta_abierto=True, estatus_autorizacion='AUTORIZADO')

        # Creamos una lista de opciones para el menú desplegable
        opciones_puestos = [
            (puesto.id, f"{puesto.titulo.nombre} ({puesto.get_ciudad_display()})")
            for puesto in puestos_activos
        ]

        # Añadimos nuestras opciones personalizadas al principio
        opciones_personalizadas = [
            ('', 'Me gustaría que me consideren para futuras oportunidades'),
            ('PRACTICAS', 'Prácticas Profesionales')
        ]

        # Combinamos las listas y las asignamos al campo
        self.fields['puesto_de_interes'].choices = opciones_personalizadas + opciones_puestos

    class Meta:
        model = Candidato
        # Excluimos 'puesto_de_interes' de aquí porque ya lo definimos arriba
        fields = [
            'nombres', 'apellidos', 'email', 'telefono',
            'nivel_educativo', 'años_de_experiencia',
            'ultimo_puesto', 'ultima_empresa',
            'es_colaborador_actual', 'motivo_busqueda',
            'habilidades', 'expectativa_salarial',
            'rfc', 'fecha_nacimiento', 'cv'
        ]
        labels = {
            'nombres': 'Nombre(s)', # Nuevo label
            'apellidos': 'Apellidos', # Nuevo label
            'email': 'Correo Electrónico',
            'telefono': 'Teléfono de Contacto',
            'puesto_de_interes': '¿Te interesa un puesto en particular?',
            'cv': 'Sube tu CV (PDF o DOCX, máx. 5MB)',
            'nivel_educativo': 'Máximo Nivel Educativo Alcanzado',
            'años_de_experiencia': 'Años de Experiencia Profesional',
            'ultimo_puesto': 'Último Puesto Desempeñado',
            'ultima_empresa': 'Última Empresa donde Laboró',
            'motivo_busqueda': 'Razón por la que buscas nuevas oportunidades',
            'rfc': 'RFC (con homoclave)',
            'fecha_nacimiento': 'Fecha de Nacimiento',
            'es_colaborador_actual': '¿Ya eres colaborador de Premier Automotriz?'
        }
        widgets = {
            'nombres': forms.TextInput(attrs={'placeholder': 'Ej: Ana Sofía'}),
            'apellidos': forms.TextInput(attrs={'placeholder': 'Ej: García López'}),
            'motivo_busqueda': forms.Textarea(attrs={'rows': 3}),
            'fecha_nacimiento': forms.DateInput(attrs={'type': 'date'}),
            'motivo_busqueda': forms.Select(),
        }

    # --- VALIDACIÓN DE ARCHIVO COMPLETA USANDO PYTHON-MAGIC ---
    def clean_cv(self):
        cv = self.cleaned_data.get('cv', False)
        if not cv:
            return None

        # Validación de Tamaño (sigue igual)
        if cv.size > 5 * 1024 * 1024:
            raise ValidationError("El archivo es demasiado grande. El máximo permitido es 5 MB.")

        # Validación de Tipo de Archivo con 'filetype'
        try:
            kind = filetype.guess(cv)
            cv.seek(0) # Rebobinamos el archivo
        except Exception:
            raise ValidationError("No se pudo leer el archivo. Intenta con otro.")

        if kind is None:
            raise ValidationError('Tipo de archivo no reconocido. Sube un PDF o DOCX válido.')

        allowed_mime_types = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']

        if kind.mime not in allowed_mime_types:
            raise ValidationError(f"Tipo de archivo no válido ({kind.mime}). Solo se permiten PDF y DOCX.")

        return cv

class SolicitudPuestoForm(forms.ModelForm):
    class Meta:
        model = Puesto
        fields = [
            'marca', 'agencia', 'titulo', 'ciudad', 'area', 'cantidad_vacantes',
            'nombre_jefe_inmediato', 'puesto_jefe_inmediato',
            'motivo_requisicion',
            'reemplaza_a',  # <-- AÑADIDO
            'objetivo_puesto', 'funciones_puesto',
            'indicador_puesto',
            'experiencia_minima', 'carrera_sugerida',  # <-- AÑADIDOS
            'herramientas_puesto', 'conocimientos_tecnicos',
            'horario', 'sueldo_base', 'esquema_comisiones',
            'archivo_justificacion', 'es_confidencial'
        ]


class PublicacionForm(forms.ModelForm):
    # Hacemos el campo opcional en el formulario para que no sea obligatorio llenarlo
    monto_inversion = forms.DecimalField(
        max_digits=8,
        decimal_places=2,
        required=False, # <-- Permite que el campo se envíe vacío
        label="Monto Invertido (MXN)",
        widget=forms.NumberInput(attrs={'placeholder': '0.00'})
    )

    class Meta:
        model = Publicacion
        # Cambiamos tuvo_inversion por monto_inversion
        fields = ['plataforma', 'enlace', 'monto_inversion']
        labels = {
            'plataforma': 'Plataforma',
            'enlace': 'Enlace a la Publicación',
        }