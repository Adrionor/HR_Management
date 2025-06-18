# reclutamiento/forms.py
from django import forms
from .models import Puesto, Candidato
from django.core.exceptions import ValidationError
import magic  # Importamos la librería para la validación de archivos


class SolicitudPuestoForm(forms.ModelForm):
    class Meta:
        model = Puesto
        # Lista de campos correcta, sin 'descripcion'
        fields = [
            'agencia', 'titulo', 'area', 'cantidad_vacantes',
            'nombre_jefe_inmediato', 'puesto_jefe_inmediato',
            'motivo_requisicion', 'objetivo_puesto', 'funciones_puesto',
            'indicador_puesto', 'herramientas_puesto', 'conocimientos_tecnicos',
            'horario', 'sueldo_base', 'esquema_comisiones'
        ]
        widgets = {
            'funciones_puesto': forms.Textarea(attrs={'rows': 5}),
            'esquema_comisiones': forms.Textarea(attrs={'rows': 3,
                                                        'placeholder': 'Describe los bonos, comisiones, etc. Si no aplica, déjalo en blanco.'}),
        }


class RegistroCandidatoForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        queryset_puestos = Puesto.objects.filter(esta_abierto=True, estatus_autorizacion='AUTORIZADO')
        self.fields['puesto_de_interes'].queryset = queryset_puestos
        self.fields['puesto_de_interes'].empty_label = "No tengo un puesto específico en mente"

    class Meta:
        model = Candidato
        fields = [
            'nombre_completo', 'email', 'telefono',
            'puesto_de_interes', 'nivel_educativo', 'años_de_experiencia',
            'habilidades', 'expectativa_salarial', 'cv'
        ]
        labels = {
            'nombre_completo': 'Nombre Completo',
            'email': 'Correo Electrónico',
            'telefono': 'Teléfono de Contacto',
            'puesto_de_interes': '¿Te interesa un puesto en particular?',
            'cv': 'Sube tu CV (PDF o DOCX, máx. 5MB)',
            'nivel_educativo': 'Máximo Nivel Educativo Alcanzado',
            'años_de_experiencia': 'Años de Experiencia Profesional',
            'habilidades': 'Habilidades Principales',
            'expectativa_salarial': 'Expectativa Salarial Mensual (Opcional)',
        }
        widgets = {
            'nombre_completo': forms.TextInput(attrs={'placeholder': 'Ej: Ana Sofía García'}),
            'email': forms.EmailInput(attrs={'placeholder': 'Ej: ana.garcia@email.com'}),
            'telefono': forms.TextInput(attrs={'placeholder': 'Ej: 6671234567'}),
            'años_de_experiencia': forms.NumberInput(attrs={'placeholder': 'Ej: 5'}),
            'habilidades': forms.Textarea(
                attrs={'rows': 3, 'placeholder': 'Ej: Liderazgo, Excel Avanzado, Ventas, SAP (separadas por comas)'}),
            'expectativa_salarial': forms.NumberInput(attrs={'placeholder': 'Ej: 25000.00'}),
        }

    # --- VALIDACIÓN DE ARCHIVO COMPLETA USANDO PYTHON-MAGIC ---
    def clean_cv(self):
        cv = self.cleaned_data.get('cv', False)

        # Si el campo CV es opcional y no se sube archivo, no hay nada que validar.
        if not cv:
            return None

        # 1. Validación de Tamaño (máximo 5 MB)
        if cv.size > 5 * 1024 * 1024:
            raise ValidationError("El archivo es demasiado grande. El máximo permitido es 5 MB.")

        # 2. Validación de Tipo de Archivo con 'magic'
        try:
            # Leemos los primeros 2048 bytes para que magic los analice
            mime_type = magic.from_buffer(cv.read(2048), mime=True)
            # ¡MUY IMPORTANTE! Rebobinamos el archivo para que Django pueda guardarlo.
            cv.seek(0)
        except Exception as e:
            raise ValidationError(f"No se pudo leer el archivo. Por favor, intenta con otro. ({e})")

        # Lista de tipos MIME permitidos
        allowed_mime_types = [
            'application/pdf',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document'  # DOCX
        ]

        if mime_type not in allowed_mime_types:
            raise ValidationError(f"Tipo de archivo no válido ({mime_type}). Solo se permiten PDF y DOCX.")

        return cv

class SolicitudPuestoForm(forms.ModelForm):
    class Meta:
        model = Puesto
        fields = [
            'agencia', 'titulo', 'area', 'cantidad_vacantes',
            'nombre_jefe_inmediato', 'puesto_jefe_inmediato',
            'motivo_requisicion', 'objetivo_puesto', 'funciones_puesto',
            'indicador_puesto', 'herramientas_puesto', 'conocimientos_tecnicos',
            'horario', 'sueldo_base', 'esquema_comisiones',
            'archivo_justificacion'  # <-- AÑADIR AQUÍ
        ]