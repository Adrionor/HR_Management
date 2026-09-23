from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.contrib.admin.sites import site
from django.urls import reverse
from reclutamiento.models import (
    Marca, CatalogoPuesto, Puesto, Candidato, Proceso, PerfilDePuesto, PerfilUsuario
)
from reclutamiento.forms import SolicitudPuestoForm


class HRManagementTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='password123')
        self.marca = Marca.objects.create(nombre='Toyota')
        self.cat_puesto = CatalogoPuesto.objects.create(nombre='Asesor de Ventas')

    def test_ensure_user_profile_signal(self):
        """Verifica que la señal ensure_user_profile cree el PerfilUsuario sin duplicación ni error."""
        self.assertTrue(hasattr(self.user, 'perfilusuario'))
        self.assertIsInstance(self.user.perfilusuario, PerfilUsuario)

    def test_homepage_publica_view_renders(self):
        """Verifica que la página pública rediseñada cargue con status 200."""
        # Crear un puesto autorizado y abierto
        puesto = Puesto.objects.create(
            titulo=self.cat_puesto,
            marca=self.marca,
            agencia='Toyota Premier',
            ciudad='CUL',
            area='VTAS',
            estatus_autorizacion='AUTORIZADO',
            esta_abierto=True,
            es_confidencial=False,
            nombre_jefe_inmediato='Juan Pérez',
            puesto_jefe_inmediato='Gerente',
            motivo_requisicion='ROT',
            objetivo_puesto='Venta de unidades',
            funciones_puesto='Prospección, atención, cierre',
            indicador_puesto='Unidades vendidas',
            sueldo_base=15000.00
        )
        response = self.client.get(reverse('homepage_publica'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Toyota Premier')
        self.assertContains(response, 'Asesor de Ventas')
        self.assertContains(response, 'Google Sans Flex')

    def test_admin_search_fields_validity(self):
        """Verifica que los search_fields de los ModelAdmin no contengan campos o propiedades inválidas."""
        from reclutamiento.admin import PuestoAdmin, CandidatoAdmin, ProcesoAdmin, PerfilDePuestoAdmin

        puesto_admin = PuestoAdmin(Puesto, site)
        self.assertEqual(puesto_admin.search_fields, ('titulo__nombre', 'agencia', 'ciudad'))

        candidato_admin = CandidatoAdmin(Candidato, site)
        self.assertEqual(candidato_admin.search_fields, ('nombres', 'apellidos', 'email', 'rfc', 'habilidades'))

        proceso_admin = ProcesoAdmin(Proceso, site)
        self.assertEqual(proceso_admin.search_fields, ('candidato__nombres', 'candidato__apellidos', 'puesto__titulo__nombre'))

        perfil_admin = PerfilDePuestoAdmin(PerfilDePuesto, site)
        self.assertEqual(perfil_admin.search_fields, ('puesto__titulo__nombre', 'comentarios_adicionales'))

    def test_solicitud_puesto_form_integrity(self):
        """Verifica que SolicitudPuestoForm mantenga todos los campos requeridos y widgets personalizados."""
        form = SolicitudPuestoForm()
        self.assertIn('reemplaza_a', form.fields)
        self.assertIn('funciones_puesto', form.fields)
        self.assertIn('sueldo_base', form.fields)
        # Verificar que el widget de funciones_puesto tenga los rows definidos
        self.assertEqual(form.fields['funciones_puesto'].widget.attrs.get('rows'), 5)

    def test_puesto_sla_y_etapas_operativas(self):
        """Verifica el cálculo de días meta, estatus de SLA y etapa operativa en Puesto."""
        puesto = Puesto.objects.create(
            titulo=self.cat_puesto,
            marca=self.marca,
            agencia='Toyota Premier',
            ciudad='CUL',
            area='VTAS',
            estatus_autorizacion=Puesto.EstatusAutorizacion.PENDIENTE,
            cantidad_vacantes=3,
            nombre_jefe_inmediato='Juan Pérez',
            puesto_jefe_inmediato='Gerente',
            motivo_requisicion='ROT',
            objetivo_puesto='Venta de autos',
            funciones_puesto='Atención y prospección',
            indicador_puesto='Ventas mes',
            sueldo_base=12000.00
        )
        # 1. En Aprobación
        self.assertEqual(puesto.etapa_operativa, '1. En Aprobación')
        self.assertEqual(puesto.dias_meta, 20)  # Según catálogo
        self.assertEqual(puesto.plazas_cubiertas, 0)
        self.assertEqual(puesto.plazas_pendientes, 3)
        self.assertFalse(puesto.esta_completamente_cubierta)

        # 2. Autorizado sin asesora
        puesto.estatus_autorizacion = Puesto.EstatusAutorizacion.AUTORIZADO
        puesto.esta_abierto = True
        puesto.save()
        self.assertEqual(puesto.etapa_operativa, '2. Por Asignar Asesora')

        # 3. Asignado a asesora sin perfil detallado
        puesto.asesora_encargada = self.user
        puesto.save()
        self.assertEqual(puesto.etapa_operativa, '3. Por Definir Perfil')

        # 4. Con perfil detallado pero sin procesos -> En Búsqueda
        PerfilDePuesto.objects.create(
            puesto=puesto,
            rango_edad='25-35',
            preferencia_sexo='I',
            area_experiencia_enfoque='VTAS',
            importancia_apariencia='BAJA',
            feedback_anterior='N/A',
            requiere_licencia='SI'
        )
        self.assertEqual(puesto.etapa_operativa, '4. En Búsqueda')

        # 5. Agregar candidato en proceso y contratar 1 plaza (vacante debe seguir abierta)
        cand = Candidato.objects.create(
            nombres='Carlos',
            apellidos='López',
            email='carlos@example.com'
        )
        proc = Proceso.objects.create(
            candidato=cand,
            puesto=puesto,
            asesora_asignada=self.user,
            estatus_proceso=Proceso.Estatus.CONTRATADO_CERRADO
        )
        self.assertEqual(puesto.plazas_cubiertas, 1)
        self.assertEqual(puesto.plazas_pendientes, 2)
        self.assertFalse(puesto.esta_completamente_cubierta)

    def test_reportes_view_permissions_and_csv_export(self):
        """Verifica que reportes_view sea accesible por staff y soporte exportación a CSV."""
        self.user.is_staff = True
        self.user.save()
        self.client.login(username='testuser', password='password123')

        response = self.client.get(reverse('vista_reportes'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Dashboard Ejecutivo')

        # Probar exportación a CSV
        response_csv = self.client.get(reverse('vista_reportes') + '?export=csv')
        self.assertEqual(response_csv.status_code, 200)
        self.assertEqual(response_csv['Content-Type'], 'text/csv; charset=utf-8-sig')
        self.assertIn('ID Vacante', response_csv.content.decode('utf-8-sig'))

    def test_evaluacion_entrevista_jefe_operativo(self):
        """Verifica que el gerente operativo pueda evaluar a un candidato en ENT_JF desde su portal."""
        from django.contrib.auth.models import Group
        grupo_go, _ = Group.objects.get_or_create(name='Gerentes Operativos')
        self.user.groups.add(grupo_go)

        puesto = Puesto.objects.create(
            titulo=self.cat_puesto,
            marca=self.marca,
            agencia='Toyota Premier',
            ciudad='CUL',
            area='VTAS',
            solicitado_por=self.user,
            estatus_autorizacion=Puesto.EstatusAutorizacion.AUTORIZADO,
            esta_abierto=True,
            nombre_jefe_inmediato='Juan Pérez',
            puesto_jefe_inmediato='Gerente',
            motivo_requisicion='ROT',
            sueldo_base=12000.00
        )
        cand = Candidato.objects.create(nombres='Laura', apellidos='Sánchez', email='laura@example.com')
        proc = Proceso.objects.create(
            candidato=cand,
            puesto=puesto,
            estatus_proceso=Proceso.Estatus.ENTREVISTA_JEFE
        )

        self.client.login(username='testuser', password='password123')

        # Evaluar candidato aprobándolo
        response = self.client.post(reverse('portal_gerente'), {
            'action': 'evaluar_candidato',
            'proceso_id': proc.id,
            'decision': 'APROBAR',
            'retroalimentacion_jefe': 'Excelente actitud y experiencia en prospección.'
        })
        self.assertEqual(response.status_code, 302)
        proc.refresh_from_db()
        self.assertEqual(proc.estatus_proceso, Proceso.Estatus.EXAMENES_MEDICOS)
        self.assertIn('Excelente actitud', proc.retroalimentacion)

    def test_rechazo_solicitud_con_motivo(self):
        """Verifica que el rechazo de una requisición guarde el motivo_rechazo."""
        self.user.is_staff = True
        self.user.save()
        self.client.login(username='testuser', password='password123')

        puesto = Puesto.objects.create(
            titulo=self.cat_puesto,
            marca=self.marca,
            agencia='Toyota Premier',
            ciudad='CUL',
            area='VTAS',
            solicitado_por=self.user,
            estatus_autorizacion=Puesto.EstatusAutorizacion.PENDIENTE_DIR,
            nombre_jefe_inmediato='Juan Pérez',
            puesto_jefe_inmediato='Gerente',
            motivo_requisicion='INC',
            sueldo_base=15000.00
        )
        response = self.client.post(reverse('rechazar_solicitud', args=[puesto.id]), {
            'motivo_rechazo': 'Plantilla congelada por Dirección General.'
        })
        self.assertEqual(response.status_code, 302)
        puesto.refresh_from_db()
        self.assertEqual(puesto.estatus_autorizacion, Puesto.EstatusAutorizacion.RECHAZADO)
        self.assertFalse(puesto.esta_abierto)
        self.assertEqual(puesto.motivo_rechazo, 'Plantilla congelada por Dirección General.')


