from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.contrib.admin.sites import site
from django.urls import reverse
from django.utils import timezone
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
        """Verifica que reportes_view sea accesible por staff y soporte exportaciones multicriterio a CSV."""
        self.user.is_staff = True
        self.user.save()
        self.client.login(username='testuser', password='password123')

        response = self.client.get(reverse('vista_reportes'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Dashboard Ejecutivo')
        self.assertIn('agencias_scorecard', response.context)
        self.assertIn('asesoras_scorecard', response.context)
        self.assertIn('solicitantes_scorecard', response.context)

        # 1. Probar exportación a CSV Maestro
        response_csv = self.client.get(reverse('vista_reportes') + '?export=csv')
        self.assertEqual(response_csv.status_code, 200)
        self.assertEqual(response_csv['Content-Type'], 'text/csv; charset=utf-8-sig')
        self.assertIn('ID Vacante', response_csv.content.decode('utf-8-sig'))

        # 2. Probar exportación a CSV Agencias
        response_agencias = self.client.get(reverse('vista_reportes') + '?export=csv_agencias')
        self.assertEqual(response_agencias.status_code, 200)
        self.assertIn('Agencia', response_agencias.content.decode('utf-8-sig'))

        # 3. Probar exportación a CSV Asesoras
        response_asesoras = self.client.get(reverse('vista_reportes') + '?export=csv_asesoras')
        self.assertEqual(response_asesoras.status_code, 200)
        self.assertIn('Asesora', response_asesoras.content.decode('utf-8-sig'))

        # 4. Probar exportación a CSV Solicitantes
        response_solicitantes = self.client.get(reverse('vista_reportes') + '?export=csv_solicitantes')
        self.assertEqual(response_solicitantes.status_code, 200)
        self.assertIn('Jefe Solicitante', response_solicitantes.content.decode('utf-8-sig'))

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

    def test_require_post_en_aprobacion_y_rechazo(self):
        """BUG-02 y BUG-03: Verifica que GET a aprobar o rechazar devuelva 405 Method Not Allowed."""
        self.user.is_superuser = True
        self.user.save()
        self.client.login(username='testuser', password='password123')

        puesto = Puesto.objects.create(
            titulo=self.cat_puesto,
            marca=self.marca,
            agencia='Toyota Premier',
            ciudad='CUL',
            area='VTAS',
            solicitado_por=self.user,
            estatus_autorizacion=Puesto.EstatusAutorizacion.PENDIENTE,
            nombre_jefe_inmediato='Juan Pérez',
            puesto_jefe_inmediato='Gerente',
            motivo_requisicion='ROT',
            sueldo_base=15000.00
        )

        # GET debe ser rechazado con 405 Method Not Allowed
        response_get_aprobar = self.client.get(reverse('aprobar_solicitud', args=[puesto.id]))
        self.assertEqual(response_get_aprobar.status_code, 405)

        response_get_rechazar = self.client.get(reverse('rechazar_solicitud', args=[puesto.id]))
        self.assertEqual(response_get_rechazar.status_code, 405)

    def test_contratado_cerrado_excluido_de_mis_procesos(self):
        """LN-02: Verifica que candidatos en CONTRATADO_CERRADO no aparezcan en mis_procesos."""
        from django.contrib.auth.models import Group
        grupo_asesoras, _ = Group.objects.get_or_create(name='Asesoras')
        self.user.groups.add(grupo_asesoras)

        puesto = Puesto.objects.create(
            titulo=self.cat_puesto,
            marca=self.marca,
            agencia='Toyota Premier',
            ciudad='CUL',
            area='VTAS',
            estatus_autorizacion=Puesto.EstatusAutorizacion.AUTORIZADO,
            esta_abierto=True,
            nombre_jefe_inmediato='Juan Pérez',
            puesto_jefe_inmediato='Gerente',
            motivo_requisicion='ROT',
            sueldo_base=12000.00
        )
        cand1 = Candidato.objects.create(nombres='Ana', apellidos='Soto', email='ana@example.com')
        cand2 = Candidato.objects.create(nombres='Beto', apellidos='Ríos', email='beto@example.com')

        # Proceso 1: Contratado
        proc1 = Proceso.objects.create(
            candidato=cand1, puesto=puesto, asesora_asignada=self.user,
            estatus_proceso=Proceso.Estatus.CONTRATADO_CERRADO
        )
        # Proceso 2: En Entrevista
        proc2 = Proceso.objects.create(
            candidato=cand2, puesto=puesto, asesora_asignada=self.user,
            estatus_proceso=Proceso.Estatus.ENTREVISTA_ASESORA
        )

        self.client.login(username='testuser', password='password123')
        response = self.client.get(reverse('mis_procesos'))
        self.assertEqual(response.status_code, 200)

        procesos_en_contexto = list(response.context['procesos'])
        self.assertIn(proc2, procesos_en_contexto)
        self.assertNotIn(proc1, procesos_en_contexto)

    def test_candidato_mas_avanzado_ponderado(self):
        """LN-03: Verifica que candidato_mas_avanzado ordene por peso de etapa y no solo por fecha."""
        puesto = Puesto.objects.create(
            titulo=self.cat_puesto,
            marca=self.marca,
            agencia='Toyota Premier',
            ciudad='CUL',
            area='VTAS',
            estatus_autorizacion=Puesto.EstatusAutorizacion.AUTORIZADO,
            esta_abierto=True,
            nombre_jefe_inmediato='Juan Pérez',
            puesto_jefe_inmediato='Gerente',
            motivo_requisicion='ROT',
            sueldo_base=12000.00
        )
        cand_nuevo = Candidato.objects.create(nombres='Reciente', apellidos='Nuevo', email='reciente@example.com')
        cand_avanzado = Candidato.objects.create(nombres='Avanzado', apellidos='Jefe', email='avanzado@example.com')

        # El candidato avanzado entró antes a entrevista jefe
        Proceso.objects.create(
            candidato=cand_avanzado, puesto=puesto,
            estatus_proceso=Proceso.Estatus.ENTREVISTA_JEFE,
            fecha_inicio_etapa=timezone.now() - timezone.timedelta(days=3)
        )
        # El candidato nuevo entró hoy a integridad (más reciente en fecha)
        Proceso.objects.create(
            candidato=cand_nuevo, puesto=puesto,
            estatus_proceso=Proceso.Estatus.INTEGRIDAD,
            fecha_inicio_etapa=timezone.now()
        )

        # A pesar de que cand_nuevo tiene fecha_inicio_etapa más reciente, cand_avanzado está más avanzado
        self.assertEqual(puesto.candidato_mas_avanzado, cand_avanzado)

    def test_asignar_candidato_evita_duplicados_y_asigna_nuevo(self):
        """LN-04 y LN-06: Verifica estatus inicial NUEVO y prevención de duplicidad de procesos activos."""
        from django.contrib.auth.models import Group
        grupo_asesoras, _ = Group.objects.get_or_create(name='Asesoras')
        self.user.groups.add(grupo_asesoras)

        puesto = Puesto.objects.create(
            titulo=self.cat_puesto,
            marca=self.marca,
            agencia='Toyota Premier',
            ciudad='CUL',
            area='VTAS',
            estatus_autorizacion=Puesto.EstatusAutorizacion.AUTORIZADO,
            esta_abierto=True,
            nombre_jefe_inmediato='Juan Pérez',
            puesto_jefe_inmediato='Gerente',
            motivo_requisicion='ROT',
            sueldo_base=12000.00
        )
        cand = Candidato.objects.create(nombres='Daniel', apellidos='Castro', email='daniel@example.com')

        self.client.login(username='testuser', password='password123')

        # Primera asignación
        resp1 = self.client.post(reverse('asignar_candidato', args=[puesto.id]), {'candidato_id': cand.id})
        self.assertEqual(resp1.status_code, 302)

        proc = Proceso.objects.get(candidato=cand, puesto=puesto)
        self.assertEqual(proc.estatus_proceso, Proceso.Estatus.NUEVO)

        # Segunda asignación para el mismo puesto debe ser prevenida
        resp2 = self.client.post(reverse('asignar_candidato', args=[puesto.id]), {'candidato_id': cand.id})
        self.assertEqual(resp2.status_code, 302)
        # Solo debe existir un proceso
        self.assertEqual(Proceso.objects.filter(candidato=cand, puesto=puesto).count(), 1)

    def test_service_layer_reportes_completo(self):
        """QA-05: Prueba formal de ReportesService en TestCase de Django."""
        from reclutamiento.services import ReportesService

        self.user.is_staff = True
        self.user.save()

        puesto = Puesto.objects.create(
            titulo=self.cat_puesto,
            marca=self.marca,
            agencia='Toyota Premier',
            ciudad='CUL',
            area='VTAS',
            estatus_autorizacion=Puesto.EstatusAutorizacion.AUTORIZADO,
            esta_abierto=True,
            solicitado_por=self.user,
            nombre_jefe_inmediato='Juan Pérez',
            puesto_jefe_inmediato='Gerente',
            motivo_requisicion='ROT',
            sueldo_base=12000.00
        )

        filtros = {
            'fecha_desde': '', 'fecha_hasta': '', 'marca': '', 'agencia': '',
            'ciudad': '', 'asesora': '', 'sla': '', 'etapa': ''
        }

        datos = ReportesService.generate_reporte_data(self.user, filtros, use_cache=False)
        self.assertIn('kpis', datos)
        self.assertIn('agencias_scorecard', datos)
        self.assertIn('asesoras_scorecard', datos)
        self.assertIn('solicitantes_scorecard', datos)
        self.assertEqual(datos['kpis']['total_vacantes'], 1)
        self.assertEqual(datos['kpis']['total_activas'], 1)



