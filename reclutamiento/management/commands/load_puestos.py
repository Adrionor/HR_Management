from django.core.management.base import BaseCommand
from reclutamiento.models import CatalogoPuesto

class Command(BaseCommand):
    help = 'Carga la lista inicial de puestos al catálogo desde una lista predefinida.'

    def handle(self, *args, **kwargs):
        self.stdout.write("Iniciando la carga de puestos de catálogo...")

        puestos_lista = [
            "Auxiliar de F&I", "Encargado(a) de F&I", "Asesor(a) de ventas de flotillas",
            "Encargado de Previas", "Previador", "Coordinador(a) de Leds", "Administradora de ventas",
            "Asesor(a) de ventas", "Asesor(a) leads", "asesor de sistemas", "Encargado de patio",
            "Encargado de Exhibicion y Demos", "Facturista", "Gerente de ventas", "Intercambios",
            "Subgerente de ventas", "Guardia de seguridad", "Comprador(a) de autos",
            "Encargado(a) de Inventarios", "Gerente de Seminuevos", "Asistente de dirección",
            "Auxiliar de Citas", "Coordinador(a) de Citas", "Administrador(a) de garantias",
            "Auxiliar de Garantias", "Jefe de lavado", "Lavador de autos", "Asesor de servicio",
            "Chofer", "Coodinador(a) de asesores de servicio", "Auxiliar administrativo",
            "Gerente de servicio", "Ayudante de Técnico", "Control de Calidad", "Jefe de taller",
            "Técnico en Diagnóstico", "Técnico en Mantenimiento", "Técnico en Reparación",
            "Técnico Master", "Gerente de HYP", "Hojalatero", "Jefe de taller HyP", "Pintor",
            "Preparador", "Pulidor", "Tecnico de HyP", "Asesor de HYP", "Auxiliar administrativo HYP",
            "Coordinador de HYP", "Valuador", "Almacenista", "Encargado de compras", "Jefe de almacén",
            "Auditor Interno", "Jefe de Mayoreo de Colisión", "Jefe de Mayoreo Partes",
            "Vendedor Ecommerce", "Vendedor de Mayoreo Colision", "Vendedor de Mayoreo Foráneo",
            "Vendedor de Mayoreo Partes", "Asesor de ventas accesorios", "Jefe de ventas Mostrador",
            "Vendedor de Mostrador", "Gerente de refacciones", "Subgerente de refacciones",
            "Despachador de Body shop", "Despachador de Ventanilla", "Capacitador", "Conmutador",
            "Gerente Comercial", "Gerente General", "Subgerente de Sistemas", "Auditor(a) de marca",
            "Encargado(a) de Caja general", "Asesor(a) de capital humano", "Auxiliar Crédito y Cobranza",
            "Cobrador", "Encargado(a) de Crédito y cobranza", "Auxiliar contable", "Contador(a) general",
            "Gerente Administrativo(a)", "Office boy", "Subcontador (a)", "Asesor(a) de Mejora Continua",
            "Encargado(a) de Mejora continua", "Encargado(a) de Mercadotecnia", "Practicante",
            "Encargado de Sistemas", "Atención a clientes", "Coordinador de Seguridad",
            "Supervisor de seguridad", "Anfitriona/Hostess", "Asesor(a) ventas ETA",
            "Asesor(a) de marca Sr", "Asesor(a) de marca Jr", "Asesor(a) de marca training",
            "Asesor(a) training", "Responding", "Coordinador (a) de Hospitalidad y Responding",
            "Coordinador (a) de Publicidad", "Coordinador(a) ETA", "Coordinador(a) Digital",
            "Especialista en contenido", "Diseñador(a) Sr.", "Diseñador(a) training",
            "Ejecutivo(a) de Responding", "Ejecutiva de Imagen", "Especialista en Paid Media",
            "Especialista en Paid Media Training", "Gerente Corporativo de Mercadotecnia",
            "Gerente de ATL y Digital", "Gerente de BTL", "Gerente de Hospitalidad",
            "Productor(a) Audiovisual", "User Experience Jr", "Coord. Desarrollo y Bienestar",
            "Coord. Vinculación con la Comunidad", "Coord. Comunicación interna", "Ejecutivo(a) BTL",
            "Coord. De Clima y Mentoring", "Coord Gastos Médicos Mayores", "Médico general",
            "Técnico de motos", "Técnico de autos", "Subgerente de Capital Humano", "Vendedor de ventanilla",
            "Encargado de mantenimiento", "Asesor(a) de Normatividad"
        ]

        for nombre_puesto in puestos_lista:
            # get_or_create evita duplicados. Si el puesto ya existe, no hace nada.
            obj, created = CatalogoPuesto.objects.get_or_create(nombre=nombre_puesto.strip())
            if created:
                self.stdout.write(self.style.SUCCESS(f'Se creó el puesto: "{obj.nombre}"'))

        self.stdout.write(self.style.SUCCESS("¡Carga de puestos finalizada!"))