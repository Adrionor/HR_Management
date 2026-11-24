from django.test import TestCase, Client, override_settings
from django.core.management import call_command
from unittest.mock import patch, MagicMock
from io import BytesIO, StringIO
import json
import openpyxl
from django.contrib.auth.models import User, Group
from django.contrib.admin.sites import site
from django.urls import reverse
from django.utils import timezone
from reclutamiento.models import (
    Marca, CatalogoPuesto, Puesto, Candidato, Proceso, PerfilDePuesto, PerfilUsuario,
    Ciudad, Agencia, Aviso, RegistroActividad
)
from reclutamiento.forms import SolicitudPuestoForm, RegistroCandidatoForm


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
        """Verifica que SolicitudPuestoForm contenga únicamente los campos definidos para la captura directa de RH."""
        form = SolicitudPuestoForm()
        campos_esperados = [
            'fecha_solicitud', 'agencia', 'ciudad', 'titulo', 'cantidad_vacantes',
            'jefe_inmediato_nombre', 'jefe_inmediato_puesto', 'motivo_requisicion',
            'sueldo_base', 'esquema_comisiones', 'dias_meta', 'comentarios',
            'archivo_justificacion'
        ]
        for campo in campos_esperados:
            self.assertIn(campo, form.fields)

        # Campos eliminados no deben existir en el formulario
        self.assertNotIn('reemplaza_a', form.fields)
        self.assertNotIn('funciones_puesto', form.fields)
        self.assertNotIn('objetivo_puesto', form.fields)

    def test_puesto_sla_y_etapas_operativas(self):
        """Verifica el cálculo de días meta, estatus de SLA y etapa operativa en Puesto."""
        puesto = Puesto.objects.create(
            titulo=self.cat_puesto,
            marca=self.marca,
            agencia='Toyota Premier',
            ciudad='CUL',
            area='VTAS',
            estatus_autorizacion=Puesto.EstatusAutorizacion.AUTORIZADO,
            esta_abierto=True,
            cantidad_vacantes=3,
            nombre_jefe_inmediato='Juan Pérez',
            puesto_jefe_inmediato='Gerente',
            motivo_requisicion='ROT',
            objetivo_puesto='Venta de autos',
            funciones_puesto='Atención y prospección',
            indicador_puesto='Ventas mes',
            sueldo_base=12000.00
        )
        self.assertEqual(puesto.dias_meta, 20)  # Según catálogo
        self.assertEqual(puesto.plazas_cubiertas, 0)
        self.assertEqual(puesto.plazas_pendientes, 3)
        self.assertFalse(puesto.esta_completamente_cubierta)

        # 1. Autorizado sin asesora -> Por Asignar Asesora
        self.assertEqual(puesto.etapa_operativa, '2. Por Asignar Asesora')

        # 2. Asignado a asesora sin procesos activos -> En Búsqueda
        puesto.asesora_encargada = self.user
        puesto.save()
        self.assertEqual(puesto.etapa_operativa, '3. En Búsqueda')

        # 4. Agregar candidato en proceso y contratar 1 plaza (vacante debe seguir abierta)
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

    def test_calculo_cumplio_meta_bono(self):
        """Verifica la regla de bono: cumplio_meta_bono es True si cubre plazas o si envía >=3 candidatos a jefe en tiempo."""
        # Caso 1: Vacante con plazas completamente cubiertas
        puesto_cubierto = Puesto.objects.create(
            titulo=self.cat_puesto,
            marca=self.marca,
            agencia='Toyota Premier',
            ciudad='CUL',
            cantidad_vacantes=1,
            esta_abierto=False,
            dias_meta=20
        )
        cand1 = Candidato.objects.create(nombres='Pedro', apellidos='Pérez', email='pedro@example.com')
        Proceso.objects.create(
            candidato=cand1,
            puesto=puesto_cubierto,
            asesora_asignada=self.user,
            estatus_proceso=Proceso.Estatus.CONTRATADO
        )
        self.assertTrue(puesto_cubierto.esta_completamente_cubierta)
        self.assertTrue(puesto_cubierto.cumplio_meta_bono)

        # Caso 2: Vacante abierta no cubierta, pero con 3 candidatos enviados a jefe dentro del plazo
        puesto_abierto = Puesto.objects.create(
            titulo=self.cat_puesto,
            marca=self.marca,
            agencia='Toyota Premier',
            ciudad='CUL',
            cantidad_vacantes=2,
            esta_abierto=True,
            dias_meta=20
        )
        for i in range(3):
            c = Candidato.objects.create(nombres=f'Candidato{i}', apellidos='Test', email=f'c{i}@example.com')
            Proceso.objects.create(
                candidato=c,
                puesto=puesto_abierto,
                asesora_asignada=self.user,
                estatus_proceso=Proceso.Estatus.ENT_JF
            )
        self.assertFalse(puesto_abierto.esta_completamente_cubierta)
        self.assertTrue(puesto_abierto.cumplio_meta_bono)

        # Caso 3: Vacante abierta con solo 2 candidatos enviados a jefe -> No cumple bono aún
        puesto_incompleto = Puesto.objects.create(
            titulo=self.cat_puesto,
            marca=self.marca,
            agencia='Toyota Premier',
            ciudad='CUL',
            cantidad_vacantes=2,
            esta_abierto=True,
            dias_meta=20
        )
        for i in range(2):
            c = Candidato.objects.create(nombres=f'CandIncomp{i}', apellidos='Test', email=f'ci{i}@example.com')
            Proceso.objects.create(
                candidato=c,
                puesto=puesto_incompleto,
                asesora_asignada=self.user,
                estatus_proceso=Proceso.Estatus.ENT_JF
            )
        self.assertFalse(puesto_incompleto.cumplio_meta_bono)

    def test_generacion_sin_errores_tres_archivos_xlsx(self):
        """Verifica que los 3 reportes en Excel (.xlsx con openpyxl) se generen limpiamente sin errores."""
        import openpyxl
        import io

        from django.contrib.auth.models import Group
        grupo_ch, _ = Group.objects.get_or_create(name='Gerentes de Capital Humano')
        self.user.groups.add(grupo_ch)
        self.client.login(username='testuser', password='password123')

        # Crear datos de prueba
        puesto = Puesto.objects.create(
            titulo=self.cat_puesto,
            marca=self.marca,
            agencia='Toyota Premier Culiacán',
            ciudad='CUL',
            cantidad_vacantes=2,
            esta_abierto=True,
            asesora_encargada=self.user,
            dias_meta=20
        )
        cand = Candidato.objects.create(nombres='Laura', apellidos='Vega', email='laura@example.com')
        Proceso.objects.create(
            candidato=cand,
            puesto=puesto,
            asesora_asignada=self.user,
            estatus_proceso=Proceso.Estatus.ENT_JF
        )

        xlsx_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

        # 1. Reporte 1: Resumen Ejecutivo por Periodo
        resp1 = self.client.get(reverse('vista_reportes') + '?export=resumen_ejecutivo')
        self.assertEqual(resp1.status_code, 200)
        self.assertEqual(resp1['Content-Type'], xlsx_type)
        wb1 = openpyxl.load_workbook(io.BytesIO(resp1.content))
        self.assertIn("Resumen Ejecutivo", wb1.sheetnames)
        self.assertIn("Desglose Agencia y Puesto", wb1.sheetnames)

        # 2. Reporte 2: Auditoría y Productividad por Asesora
        resp2 = self.client.get(reverse('vista_reportes') + '?export=auditoria_bono')
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2['Content-Type'], xlsx_type)
        wb2 = openpyxl.load_workbook(io.BytesIO(resp2.content))
        self.assertIn("Auditoría Asesoras", wb2.sheetnames)
        self.assertIn("Detalle Vacantes y SLA", wb2.sheetnames)

        # 3. Reporte 3: Sábana Histórica Filtrable
        resp3 = self.client.get(reverse('vista_reportes') + '?export=sabana_historica')
        self.assertEqual(resp3.status_code, 200)
        self.assertEqual(resp3['Content-Type'], xlsx_type)
        wb3 = openpyxl.load_workbook(io.BytesIO(resp3.content))
        self.assertIn("Sábana Histórica Movimientos", wb3.sheetnames)

    def test_captura_directa_vacante_por_asesora(self):
        """Verifica que la captura directa por una asesora guarde la vacante activa y autoasignada."""
        from django.contrib.auth.models import Group
        grupo_asesoras, _ = Group.objects.get_or_create(name='Asesoras')
        self.user.groups.add(grupo_asesoras)
        self.client.login(username='testuser', password='password123')

        response = self.client.post(reverse('crear_vacante'), {
            'titulo': self.cat_puesto.id,
            'agencia': 'Toyota Premier Culiacán',
            'ciudad': 'CUL',
            'cantidad_vacantes': 2,
            'jefe_inmediato_nombre': 'Ing. Roberto Gómez',
            'jefe_inmediato_puesto': 'Gerente de Ventas',
            'motivo_requisicion': 'ROT',
            'sueldo_base': 18000.00,
            'esquema_comisiones': 'Comisiones por vehículo vendido',
            'dias_meta': 25,
            'comentarios': 'Requisición física entregada con firma de autorización.'
        })
        self.assertEqual(response.status_code, 302)
        puesto = Puesto.objects.filter(agencia='Toyota Premier Culiacán').first()
        self.assertIsNotNone(puesto)
        self.assertEqual(puesto.estatus_autorizacion, Puesto.EstatusAutorizacion.AUTORIZADO)
        self.assertTrue(puesto.esta_abierto)
        self.assertEqual(puesto.asesora_encargada, self.user)
        self.assertEqual(puesto.solicitado_por, self.user)
        self.assertEqual(puesto.dias_meta, 25)
        self.assertEqual(puesto.jefe_inmediato_nombre, 'Ing. Roberto Gómez')

    def test_captura_vacante_por_gerente_con_asignacion_a_otra_asesora(self):
        """Verifica que un perfil de Gerente/Director pueda asignar la requisición a otra persona al crearla."""
        from django.contrib.auth.models import Group
        grupo_ch, _ = Group.objects.get_or_create(name='Gerentes de Capital Humano')
        grupo_asesoras, _ = Group.objects.get_or_create(name='Asesoras')
        self.user.groups.add(grupo_ch)
        self.client.login(username='testuser', password='password123')

        asesora_operativa = User.objects.create_user(
            username='asesora.operativa',
            password='password123',
            first_name='Laura',
            last_name='Torres'
        )
        asesora_operativa.groups.add(grupo_asesoras)

        response = self.client.post(reverse('crear_vacante'), {
            'titulo': self.cat_puesto.id,
            'agencia': 'Toyota Premier Culiacán',
            'ciudad': 'CUL',
            'cantidad_vacantes': 1,
            'jefe_inmediato_nombre': 'Lic. Patricia Aréchiga',
            'jefe_inmediato_puesto': 'Directora CH',
            'motivo_requisicion': 'INC',
            'sueldo_base': 22000.00,
            'dias_meta': 20,
            'comentarios': 'Asignación directa a asesora de ventas.',
            'asesora_encargada': asesora_operativa.id
        })
        self.assertEqual(response.status_code, 302)
        puesto = Puesto.objects.filter(agencia='Toyota Premier Culiacán', sueldo_base=22000.00).first()
        self.assertIsNotNone(puesto)
        self.assertEqual(puesto.solicitado_por, self.user)
        self.assertEqual(puesto.asesora_encargada, asesora_operativa)
        self.assertTrue(puesto.esta_abierto)

    def test_reasignar_vacante_por_gerente_exitoso(self):
        """Verifica que Gerencia CH pueda reasignar posteriormente una vacante y que se transfieran sus procesos activos."""
        from django.contrib.auth.models import Group
        from reclutamiento.models import RegistroActividad
        grupo_ch, _ = Group.objects.get_or_create(name='Gerentes de Capital Humano')
        grupo_asesoras, _ = Group.objects.get_or_create(name='Asesoras')
        self.user.groups.add(grupo_ch)
        self.client.login(username='testuser', password='password123')

        asesora_1 = User.objects.create_user(username='asesora.uno', password='password123', first_name='Ana')
        asesora_1.groups.add(grupo_asesoras)
        asesora_2 = User.objects.create_user(username='asesora.dos', password='password123', first_name='Beatriz')
        asesora_2.groups.add(grupo_asesoras)

        puesto = Puesto.objects.create(
            titulo=self.cat_puesto,
            marca=self.marca,
            agencia='Toyota Culiacán',
            ciudad='CUL',
            solicitado_por=self.user,
            asesora_encargada=asesora_1,
            sueldo_base=18000.00,
            esta_abierto=True
        )

        candidato = Candidato.objects.create(
            nombres='Carlos',
            apellidos='López',
            email='carlos.lopez@example.com',
            telefono='6671234567'
        )
        proceso = Proceso.objects.create(
            candidato=candidato,
            puesto=puesto,
            asesora_asignada=asesora_1,
            estatus_proceso=Proceso.Estatus.NUEVO
        )

        resp = self.client.post(reverse('reasignar_vacante', args=[puesto.id]), {
            'asesora_id': asesora_2.id,
            'motivo': 'Rebalanceo de carga laboral'
        })
        self.assertEqual(resp.status_code, 302)

        puesto.refresh_from_db()
        self.assertEqual(puesto.asesora_encargada, asesora_2)

        proceso.refresh_from_db()
        self.assertEqual(proceso.asesora_asignada, asesora_2)

        actividad = RegistroActividad.objects.filter(tipo_objeto='Puesto', id_objeto=puesto.id).latest('id')
        self.assertIn('Reasignó la vacante', actividad.accion)
        self.assertIn('Rebalanceo de carga laboral', actividad.detalles)

    def test_reasignar_vacante_denegado_para_asesora(self):
        """Verifica que una asesora sin privilegios de gerencia tenga prohibido reasignar vacantes."""
        from django.contrib.auth.models import Group
        grupo_asesoras, _ = Group.objects.get_or_create(name='Asesoras')
        self.user.groups.add(grupo_asesoras)
        self.client.login(username='testuser', password='password123')

        asesora_2 = User.objects.create_user(username='asesora.dos.denegada', password='password123')
        asesora_2.groups.add(grupo_asesoras)

        puesto = Puesto.objects.create(
            titulo=self.cat_puesto,
            marca=self.marca,
            agencia='Toyota Mazatlán',
            ciudad='MZT',
            solicitado_por=self.user,
            asesora_encargada=self.user,
            sueldo_base=16000.00,
            esta_abierto=True
        )

        resp = self.client.post(reverse('reasignar_vacante', args=[puesto.id]), {
            'asesora_id': asesora_2.id
        })
        self.assertEqual(resp.status_code, 403)

    def test_modulos_externos_desactivados(self):
        """Verifica que los módulos y rutas ajenos a RH estén desactivados y redirijan al dashboard o mis vacantes."""
        from django.contrib.auth.models import Group
        grupo_ch, _ = Group.objects.get_or_create(name='Gerentes de Capital Humano')
        self.user.groups.add(grupo_ch)
        self.client.login(username='testuser', password='password123')

        puesto = Puesto.objects.create(
            titulo=self.cat_puesto,
            marca=self.marca,
            agencia='Toyota Premier',
            ciudad='CUL',
            area='VTAS',
            solicitado_por=self.user,
            sueldo_base=15000.00
        )
        resp_rechazar = self.client.post(reverse('rechazar_solicitud', args=[puesto.id]), {'motivo_rechazo': 'test'})
        self.assertEqual(resp_rechazar.status_code, 302)
        self.assertIn('/dashboard/', resp_rechazar.url)

        resp_aprobar = self.client.post(reverse('aprobar_solicitud', args=[puesto.id]))
        self.assertEqual(resp_aprobar.status_code, 302)
        self.assertIn('/dashboard/', resp_aprobar.url)

        resp_pendientes = self.client.get(reverse('lista_solicitudes'))
        self.assertEqual(resp_pendientes.status_code, 302)
        self.assertIn('/dashboard/', resp_pendientes.url)

        resp_perfil = self.client.get(reverse('gestion_perfil_puesto', args=[puesto.id]))
        self.assertEqual(resp_perfil.status_code, 302)
        self.assertIn('/mis-vacantes/', resp_perfil.url)

        resp_portal = self.client.get(reverse('portal_gerente'))
        self.assertEqual(resp_portal.status_code, 302)
        self.assertIn('/vacantes/crear/', resp_portal.url)

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
        self.assertIn('vacantes_vencidas', datos)
        self.assertIn('puestos_mas_vacantes', datos)
        self.assertIn('vacantes_mayor_antiguedad', datos)
        self.assertEqual(datos['kpis']['total_vacantes'], 1)
        self.assertEqual(datos['kpis']['total_activas'], 1)

    def test_audit_fecha_ingreso_is_intermediate_active(self):
        """Hallazgo #1: FECHA_INGRESO se considera etapa activa, no terminal."""
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
            sueldo_base=10000
        )
        cand = Candidato.objects.create(nombres='Pedro', apellidos='Infante', email='pedro@example.com')
        proc = Proceso.objects.create(
            candidato=cand,
            puesto=puesto,
            asesora_asignada=self.user,
            estatus_proceso=Proceso.Estatus.FECHA_INGRESO
        )

        # 1. proceso_activo debe devolverlo
        self.assertEqual(cand.proceso_activo, proc)

        # 2. mis_procesos_view debe incluirlo
        self.client.login(username='testuser', password='password123')
        resp = self.client.get(reverse('mis_procesos'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn(proc, resp.context['procesos'])

    def test_audit_candidato_contratado_reaparece_en_bolsa(self):
        """Hallazgo #2: Un candidato con historial CONTRATADO_CERRADO puede reaparecer en la bolsa si no tiene proceso activo."""
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
            sueldo_base=10000
        )
        cand = Candidato.objects.create(nombres='María', apellidos='Felix', email='maria@example.com')
        # Proceso finalizado en el pasado
        Proceso.objects.create(
            candidato=cand,
            puesto=puesto,
            asesora_asignada=self.user,
            estatus_proceso=Proceso.Estatus.CONTRATADO_CERRADO
        )

        self.client.login(username='testuser', password='password123')
        resp = self.client.get(reverse('bolsa_trabajo_consulta'))
        self.assertEqual(resp.status_code, 200)
        candidatos_ids = [c.id for c in resp.context['candidatos']]
        self.assertIn(cand.id, candidatos_ids)

    def test_audit_validacion_estatus_detalle_proceso(self):
        """Hallazgo #3: detalle_proceso_view rechaza cadenas de estatus inválidas."""
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
            sueldo_base=10000
        )
        cand = Candidato.objects.create(nombres='Jorge', apellidos='Negrete', email='jorge@example.com')
        proc = Proceso.objects.create(
            candidato=cand,
            puesto=puesto,
            asesora_asignada=self.user,
            estatus_proceso=Proceso.Estatus.NUEVO
        )

        self.client.login(username='testuser', password='password123')
        resp = self.client.post(reverse('detalle_proceso', args=[proc.id]), {
            'action': 'actualizar_estatus',
            'estatus_proceso': 'ESTATUS_TOTALMENTE_INVALIDO',
            'retroalimentacion': 'Nota de prueba'
        })
        self.assertEqual(resp.status_code, 302)
        proc.refresh_from_db()
        self.assertEqual(proc.estatus_proceso, Proceso.Estatus.NUEVO)

    def test_audit_supervisar_procesos_sin_asesora_no_truena(self):
        """Verifica que el módulo de supervisión y reasignación externa esté desactivado y redirija al dashboard."""
        self.client.login(username='testuser', password='password123')
        resp = self.client.post(reverse('vista_supervisar_procesos'), {
            'proceso_id': 1,
            'nueva_asesora_id': 2
        })
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/dashboard/', resp.url)

    def test_audit_reportes_versioned_cache_invalidation(self):
        """Hallazgo #8: La invalidación por versión funciona sin cache.clear()."""
        from reclutamiento.services import ReportesService
        v1 = ReportesService.get_cache_version()
        ReportesService.invalidate_user_cache()
        v2 = ReportesService.get_cache_version()
        self.assertGreater(v2, v1)

    def test_detalle_proceso_avance_directo_y_evaluaciones(self):
        """Verifica que la asesora gestione directamente ENT_JF, CONF_JF y capture resultados de pruebas."""
        from django.contrib.auth.models import Group
        from reclutamiento.models import RegistroActividad
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
            sueldo_base=12000
        )
        cand = Candidato.objects.create(nombres='Pedro', apellidos='Infante', email='pedro@example.com')
        proc = Proceso.objects.create(
            candidato=cand,
            puesto=puesto,
            asesora_asignada=self.user,
            estatus_proceso=Proceso.Estatus.PRUEBAS
        )

        self.client.login(username='testuser', password='password123')

        # 1. Capturar resultados de pruebas y avanzar a ENT_JF
        resp = self.client.post(reverse('detalle_proceso', args=[proc.id]), {
            'action': 'actualizar_estatus',
            'estatus_proceso': Proceso.Estatus.ENT_JF,
            'resultado_integridad': 'APROBADO',
            'resultado_pyxoom': 'OPTIMO',
            'retroalimentacion': 'Candidato enviado con jefe de ventas.'
        })
        self.assertEqual(resp.status_code, 302)
        proc.refresh_from_db()
        self.assertEqual(proc.estatus_proceso, Proceso.Estatus.ENT_JF)
        self.assertEqual(proc.resultado_integridad, 'APROBADO')
        self.assertEqual(proc.resultado_pyxoom, 'OPTIMO')

        # Verificar rastro en RegistroActividad
        reg = RegistroActividad.objects.filter(tipo_objeto='Proceso', id_objeto=proc.id).first()
        self.assertIsNotNone(reg)
        self.assertEqual(reg.usuario, self.user)
        self.assertIn('Enviado a Entrevista con Jefe', reg.accion)

        # 2. Confirmación directa por la asesora sin esperar intervención externa (CONF_JF)
        resp2 = self.client.post(reverse('detalle_proceso', args=[proc.id]), {
            'action': 'actualizar_estatus',
            'estatus_proceso': Proceso.Estatus.CONF_JF,
            'retroalimentacion': 'Jefe confirmó visto bueno por correo.'
        })
        self.assertEqual(resp2.status_code, 302)
        proc.refresh_from_db()
        self.assertEqual(proc.estatus_proceso, Proceso.Estatus.CONF_JF)

    def test_detalle_proceso_motivo_descarte_obligatorio(self):
        """Verifica que al descartar o marcar abandono sea obligatorio ingresar motivo_descarte."""
        from django.contrib.auth.models import Group
        grupo_asesoras, _ = Group.objects.get_or_create(name='Asesoras')
        self.user.groups.add(grupo_asesoras)

        puesto = Puesto.objects.create(
            titulo=self.cat_puesto,
            marca=self.marca,
            agencia='Toyota Premier',
            ciudad='CUL',
            area='VTAS',
            esta_abierto=True,
            sueldo_base=10000
        )
        cand = Candidato.objects.create(nombres='Luis', apellidos='Aguilar', email='luis@example.com')
        proc = Proceso.objects.create(
            candidato=cand,
            puesto=puesto,
            asesora_asignada=self.user,
            estatus_proceso=Proceso.Estatus.ENT_CH
        )

        self.client.login(username='testuser', password='password123')

        # Intento de descarte sin motivo
        resp_fallo = self.client.post(reverse('detalle_proceso', args=[proc.id]), {
            'action': 'actualizar_estatus',
            'estatus_proceso': Proceso.Estatus.DESCARTADO_CH,
            'motivo_descarte': '   '
        })
        self.assertEqual(resp_fallo.status_code, 302)
        proc.refresh_from_db()
        self.assertEqual(proc.estatus_proceso, Proceso.Estatus.ENT_CH)  # No debe cambiar

        # Descarte con motivo válido
        resp_exito = self.client.post(reverse('detalle_proceso', args=[proc.id]), {
            'action': 'actualizar_estatus',
            'estatus_proceso': Proceso.Estatus.DESCARTADO_CH,
            'motivo_descarte': 'Expectativa salarial fuera del tabulador corporativo'
        })
        self.assertEqual(resp_exito.status_code, 302)
        proc.refresh_from_db()
        self.assertEqual(proc.estatus_proceso, Proceso.Estatus.DESCARTADO_CH)
        self.assertEqual(proc.motivo_descarte, 'Expectativa salarial fuera del tabulador corporativo')

    def test_detalle_proceso_marcar_no_contratable(self):
        """Verifica que la asesora pueda boletinar permanentemente a un candidato con motivo obligatorio."""
        from django.contrib.auth.models import Group
        from reclutamiento.models import RegistroActividad
        grupo_asesoras, _ = Group.objects.get_or_create(name='Asesoras')
        self.user.groups.add(grupo_asesoras)

        puesto = Puesto.objects.create(
            titulo=self.cat_puesto,
            marca=self.marca,
            agencia='Toyota Premier',
            ciudad='CUL',
            area='VTAS',
            esta_abierto=True,
            sueldo_base=10000
        )
        cand = Candidato.objects.create(nombres='Víctor', apellidos='Manuel', email='victor@example.com')
        proc = Proceso.objects.create(
            candidato=cand,
            puesto=puesto,
            asesora_asignada=self.user,
            estatus_proceso=Proceso.Estatus.CONTACTO
        )

        self.client.login(username='testuser', password='password123')

        # Intento sin motivo
        resp_sin_motivo = self.client.post(reverse('detalle_proceso', args=[proc.id]), {
            'action': 'marcar_no_contratable',
            'motivo_no_contratable': ''
        })
        self.assertEqual(resp_sin_motivo.status_code, 302)
        cand.refresh_from_db()
        self.assertFalse(cand.es_no_contratable)

        # Con motivo válido
        resp_con_motivo = self.client.post(reverse('detalle_proceso', args=[proc.id]), {
            'action': 'marcar_no_contratable',
            'motivo_no_contratable': 'Presentó documentos falsificados en entrevista.'
        })
        self.assertEqual(resp_con_motivo.status_code, 302)
        cand.refresh_from_db()
        self.assertTrue(cand.es_no_contratable)
        self.assertEqual(cand.motivo_no_contratable, 'Presentó documentos falsificados en entrevista.')

        # El proceso activo debe haberse cancelado/descartado
        proc.refresh_from_db()
        self.assertEqual(proc.estatus_proceso, Proceso.Estatus.DESCARTADO_CH)

        # Debe existir registro de actividad para el candidato
        reg_cand = RegistroActividad.objects.filter(tipo_objeto='Candidato', id_objeto=cand.id).first()
        self.assertIsNotNone(reg_cand)
        self.assertIn('NO CONTRATABLE', reg_cand.accion)

    def test_reiniciar_vacante_view(self):
        """Verifica que reiniciar_vacante_view incremente numero_reinicios y actualice fecha_inicio_sla_custom al ser autorizado por Gerente CH."""
        from django.contrib.auth.models import Group
        from reclutamiento.models import RegistroActividad
        grupo_ch, _ = Group.objects.get_or_create(name='Gerentes de Capital Humano')
        self.user.groups.add(grupo_ch)

        otra_asesora = User.objects.create_user(username='otra.asesora', password='password123')

        fecha_antigua = timezone.now() - timezone.timedelta(days=25)
        puesto = Puesto.objects.create(
            titulo=self.cat_puesto,
            marca=self.marca,
            agencia='Toyota Premier',
            ciudad='CUL',
            area='VTAS',
            asesora_encargada=otra_asesora,
            fecha_solicitud=fecha_antigua,
            dias_meta=20,
            esta_abierto=True,
            sueldo_base=15000
        )
        self.assertEqual(puesto.numero_reinicios, 0)
        self.assertGreater(puesto.dias_transcurridos, 20)

        self.client.login(username='testuser', password='password123')
        resp = self.client.post(reverse('reiniciar_vacante', args=[puesto.id]), {
            'comentario': 'Se extiende búsqueda por falta de candidatos en la plaza.'
        })
        self.assertEqual(resp.status_code, 302)
        puesto.refresh_from_db()

        self.assertEqual(puesto.numero_reinicios, 1)
        self.assertIsNotNone(puesto.fecha_inicio_sla_custom)
        self.assertEqual(puesto.dias_transcurridos, 0)
        self.assertIn('Reinicio SLA #1', puesto.comentarios)

        # Registro en auditoría
        reg = RegistroActividad.objects.filter(tipo_objeto='Puesto', id_objeto=puesto.id).first()
        self.assertIsNotNone(reg)
        self.assertIn('Autorizó reinicio de SLA', reg.accion)

    def test_bolsa_trabajo_filtros_y_expirados(self):
        """Verifica filtros por puesto y ciudad, y exclusión por defecto de candidatos inactivos >365 días."""
        from django.contrib.auth.models import Group
        grupo_asesoras, _ = Group.objects.get_or_create(name='Asesoras')
        self.user.groups.add(grupo_asesoras)

        # Candidato reciente en Mazatlán
        c_mzt = Candidato.objects.create(
            nombres='Ana', apellidos='Soto', email='ana@example.com',
            ciudad_residencia='MZT', interes_custom='Asesor de Ventas'
        )
        # Candidato reciente en Culiacán
        c_cul = Candidato.objects.create(
            nombres='Carlos', apellidos='Ríos', email='carlos@example.com',
            ciudad_residencia='CUL', interes_custom='Técnico Mecánico'
        )
        # Candidato inactivo hace más de 400 días
        c_viejo = Candidato.objects.create(
            nombres='Viejo', apellidos='Inactivo', email='viejo@example.com',
            ciudad_residencia='CUL', interes_custom='Asesor de Ventas'
        )
        # Forzar fecha_registro antigua
        fecha_antigua = timezone.now() - timezone.timedelta(days=400)
        Candidato.objects.filter(id=c_viejo.id).update(fecha_registro=fecha_antigua)

        self.client.login(username='testuser', password='password123')

        # 1. Sin filtros: c_viejo NO debe aparecer por defecto
        resp = self.client.get(reverse('bolsa_trabajo_consulta'))
        ids = [c.id for c in resp.context['candidatos']]
        self.assertIn(c_mzt.id, ids)
        self.assertIn(c_cul.id, ids)
        self.assertNotIn(c_viejo.id, ids)

        # 2. Con mostrar_expirados=1: c_viejo DEBE aparecer con alerta INACTIVO
        resp_exp = self.client.get(reverse('bolsa_trabajo_consulta') + '?mostrar_expirados=1')
        ids_exp = [c.id for c in resp_exp.context['candidatos']]
        self.assertIn(c_viejo.id, ids_exp)

        # 3. Filtrar por ciudad MZT
        resp_ciudad = self.client.get(reverse('bolsa_trabajo_consulta') + '?q_ciudad=MZT')
        ids_ciudad = [c.id for c in resp_ciudad.context['candidatos']]
        self.assertIn(c_mzt.id, ids_ciudad)
        self.assertNotIn(c_cul.id, ids_ciudad)

        # 4. Filtrar por puesto 'Mecánico'
        resp_puesto = self.client.get(reverse('bolsa_trabajo_consulta') + '?q_puesto=Mecánico')
        ids_puesto = [c.id for c in resp_puesto.context['candidatos']]
        self.assertIn(c_cul.id, ids_puesto)
        self.assertNotIn(c_mzt.id, ids_puesto)

    def test_asignar_candidato_bloquea_no_contratable(self):
        """Verifica que asignar_candidato_view bloquee rotundamente la postulación de candidatos no contratables."""
        from django.contrib.auth.models import Group
        grupo_asesoras, _ = Group.objects.get_or_create(name='Asesoras')
        self.user.groups.add(grupo_asesoras)

        puesto = Puesto.objects.create(
            titulo=self.cat_puesto,
            marca=self.marca,
            agencia='Toyota Premier',
            ciudad='CUL',
            area='VTAS',
            esta_abierto=True,
            sueldo_base=10000
        )
        cand_vetado = Candidato.objects.create(
            nombres='Beto',
            apellidos='Vetado',
            email='beto@example.com',
            es_no_contratable=True,
            motivo_no_contratable='Falta grave en empresa anterior'
        )

        self.client.login(username='testuser', password='password123')

        # Intentar asignarlo vía POST
        resp = self.client.post(reverse('asignar_candidato', args=[puesto.id]), {
            'candidato_id': cand_vetado.id
        })
        self.assertEqual(resp.status_code, 302)

        # No debe haberse creado ningún proceso
        self.assertFalse(Proceso.objects.filter(candidato=cand_vetado, puesto=puesto).exists())

    def test_creacion_directa_vacante_por_asesora(self):
        """Alias para validación unitaria de creación directa de vacante por asesora."""
        self.test_captura_directa_vacante_por_asesora()

    def test_reinicio_vacante_vencida(self):
        """Alias para validación unitaria de reinicio de vacante vencida."""
        self.test_reiniciar_vacante_view()

    def test_bloqueo_por_es_no_contratable(self):
        """Alias para validación unitaria de bloqueo por es_no_contratable."""
        self.test_asignar_candidato_bloquea_no_contratable()

    def test_asesora_no_puede_reiniciar_propio_o_ajeno_sla(self):
        """P1: Una asesora no puede reiniciar su propio SLA ni el de otra asesora (403)."""
        from django.contrib.auth.models import Group
        grupo_asesoras, _ = Group.objects.get_or_create(name='Asesoras')
        self.user.groups.add(grupo_asesoras)

        puesto = Puesto.objects.create(
            titulo=self.cat_puesto,
            marca=self.marca,
            agencia='Toyota Premier',
            ciudad='CUL',
            area='VTAS',
            asesora_encargada=self.user,
            fecha_solicitud=timezone.now() - timezone.timedelta(days=30),
            dias_meta=20,
            esta_abierto=True,
            sueldo_base=15000
        )
        self.client.login(username='testuser', password='password123')
        resp = self.client.post(reverse('reiniciar_vacante', args=[puesto.id]), {
            'comentario': 'Intento no autorizado de reinicio'
        })
        self.assertEqual(resp.status_code, 403)
        puesto.refresh_from_db()
        self.assertEqual(puesto.numero_reinicios, 0)

    def test_gerente_ch_no_puede_reiniciar_propia_vacante_responsable(self):
        """P1: La persona que aprueba la excepción debe ser distinta a la responsable."""
        from django.contrib.auth.models import Group
        grupo_ch, _ = Group.objects.get_or_create(name='Gerentes de Capital Humano')
        self.user.groups.add(grupo_ch)

        # Si el gerente es asignado como responsable de la vacante, no puede autoreiniciarla
        puesto = Puesto.objects.create(
            titulo=self.cat_puesto,
            marca=self.marca,
            agencia='Toyota Premier',
            ciudad='CUL',
            area='VTAS',
            asesora_encargada=self.user,
            esta_abierto=True,
            sueldo_base=15000
        )
        self.client.login(username='testuser', password='password123')
        resp = self.client.post(reverse('reiniciar_vacante', args=[puesto.id]), {
            'comentario': 'Intento de auto-excepción'
        })
        self.assertEqual(resp.status_code, 403)

    def test_asesora_no_puede_modificar_proceso_ajeno(self):
        """P1: Una asesora no puede modificar procesos de otra asesora."""
        from django.contrib.auth.models import Group
        grupo_asesoras, _ = Group.objects.get_or_create(name='Asesoras')
        self.user.groups.add(grupo_asesoras)

        otra_asesora = User.objects.create_user(username='asesora.otra', password='password123')
        otra_asesora.groups.add(grupo_asesoras)

        puesto = Puesto.objects.create(
            titulo=self.cat_puesto,
            marca=self.marca,
            agencia='Toyota Premier',
            ciudad='CUL',
            area='VTAS',
            asesora_encargada=otra_asesora,
            esta_abierto=True,
            sueldo_base=15000
        )
        candidato = Candidato.objects.create(nombres='Candidato', apellidos='Prueba', email='c@test.com')
        proceso = Proceso.objects.create(
            candidato=candidato,
            puesto=puesto,
            asesora_asignada=otra_asesora,
            estatus_proceso=Proceso.Estatus.NUEVO
        )

        self.client.login(username='testuser', password='password123')
        # GET bloqueado con 403 para asesora ajena (Aislamiento individual RBAC)
        resp_get = self.client.get(reverse('detalle_proceso', args=[proceso.id]))
        self.assertEqual(resp_get.status_code, 403)

        # POST bloqueado con 403
        resp_post = self.client.post(reverse('detalle_proceso', args=[proceso.id]), {
            'action': 'actualizar_estatus',
            'estatus_proceso': Proceso.Estatus.CONTACTO,
            'retroalimentacion': 'Intento no autorizado'
        })
        self.assertEqual(resp_post.status_code, 403)
        proceso.refresh_from_db()
        self.assertEqual(proceso.estatus_proceso, Proceso.Estatus.NUEVO)

    def test_guardar_notas_no_reinicia_fecha_inicio_etapa(self):
        """P2: Guardar notas sin cambiar etapa conserva fecha_inicio_etapa."""
        from django.contrib.auth.models import Group
        grupo_asesoras, _ = Group.objects.get_or_create(name='Asesoras')
        self.user.groups.add(grupo_asesoras)

        fecha_original = timezone.now() - timezone.timedelta(days=12)
        puesto = Puesto.objects.create(
            titulo=self.cat_puesto,
            marca=self.marca,
            agencia='Toyota Premier',
            ciudad='CUL',
            area='VTAS',
            asesora_encargada=self.user,
            esta_abierto=True,
            sueldo_base=15000
        )
        candidato = Candidato.objects.create(nombres='Luis', apellidos='Notas', email='luis@test.com')
        proceso = Proceso.objects.create(
            candidato=candidato,
            puesto=puesto,
            asesora_asignada=self.user,
            estatus_proceso=Proceso.Estatus.CONTACTO,
            fecha_inicio_etapa=fecha_original
        )

        self.client.login(username='testuser', password='password123')
        resp = self.client.post(reverse('detalle_proceso', args=[proceso.id]), {
            'action': 'actualizar_estatus',
            'estatus_proceso': Proceso.Estatus.CONTACTO,
            'retroalimentacion': 'Se añadió nota de seguimiento sin cambiar etapa'
        })
        self.assertEqual(resp.status_code, 302)
        proceso.refresh_from_db()
        self.assertEqual(proceso.retroalimentacion, 'Se añadió nota de seguimiento sin cambiar etapa')
        # La fecha de inicio de etapa no debe haber cambiado
        self.assertEqual(proceso.fecha_inicio_etapa.date(), fecha_original.date())

    def test_sobrecontratacion_bloqueada_select_for_update(self):
        """P2: Evita sobrecontratar una vacante que ya cubrió sus plazas."""
        from django.contrib.auth.models import Group
        grupo_asesoras, _ = Group.objects.get_or_create(name='Asesoras')
        self.user.groups.add(grupo_asesoras)

        puesto = Puesto.objects.create(
            titulo=self.cat_puesto,
            marca=self.marca,
            agencia='Toyota Premier',
            ciudad='CUL',
            area='VTAS',
            asesora_encargada=self.user,
            cantidad_vacantes=1,
            esta_abierto=True,
            sueldo_base=15000
        )
        cand1 = Candidato.objects.create(nombres='Ana', apellidos='Hired', email='ana@test.com')
        cand2 = Candidato.objects.create(nombres='Beto', apellidos='Overhire', email='beto2@test.com')

        proc1 = Proceso.objects.create(
            candidato=cand1, puesto=puesto, asesora_asignada=self.user, estatus_proceso=Proceso.Estatus.DOCS
        )
        proc2 = Proceso.objects.create(
            candidato=cand2, puesto=puesto, asesora_asignada=self.user, estatus_proceso=Proceso.Estatus.DOCS
        )

        self.client.login(username='testuser', password='password123')

        # Contratar al primero -> Éxito y llena la plaza (1/1)
        resp1 = self.client.post(reverse('detalle_proceso', args=[proc1.id]), {
            'action': 'actualizar_estatus',
            'estatus_proceso': Proceso.Estatus.CONTRATADO
        })
        self.assertEqual(resp1.status_code, 302)
        puesto.refresh_from_db()
        self.assertFalse(puesto.esta_abierto)
        self.assertEqual(puesto.plazas_cubiertas, 1)

        # Intentar contratar al segundo en la misma vacante llena -> Bloqueado
        resp2 = self.client.post(reverse('detalle_proceso', args=[proc2.id]), {
            'action': 'actualizar_estatus',
            'estatus_proceso': Proceso.Estatus.CONTRATADO
        })
        self.assertEqual(resp2.status_code, 302)
        proc2.refresh_from_db()
        self.assertNotEqual(proc2.estatus_proceso, Proceso.Estatus.CONTRATADO)
        puesto.refresh_from_db()
        self.assertEqual(puesto.plazas_cubiertas, 1)

    def test_reversion_contratacion_reabre_vacante(self):
        """P2: Revertir una contratación reabre la vacante automáticamente si estaba cerrada."""
        from django.contrib.auth.models import Group
        grupo_asesoras, _ = Group.objects.get_or_create(name='Asesoras')
        self.user.groups.add(grupo_asesoras)

        puesto = Puesto.objects.create(
            titulo=self.cat_puesto,
            marca=self.marca,
            agencia='Toyota Premier',
            ciudad='CUL',
            area='VTAS',
            asesora_encargada=self.user,
            cantidad_vacantes=1,
            esta_abierto=False,
            sueldo_base=15000
        )
        cand = Candidato.objects.create(nombres='Carlos', apellidos='Cancelado', email='carlos@test.com')
        proc = Proceso.objects.create(
            candidato=cand, puesto=puesto, asesora_asignada=self.user, estatus_proceso=Proceso.Estatus.CONTRATADO
        )
        self.assertEqual(puesto.plazas_cubiertas, 1)

        self.client.login(username='testuser', password='password123')
        # Revertir a PRUEBAS
        resp = self.client.post(reverse('detalle_proceso', args=[proc.id]), {
            'action': 'actualizar_estatus',
            'estatus_proceso': Proceso.Estatus.PRUEBAS
        })
        self.assertEqual(resp.status_code, 302)
        puesto.refresh_from_db()
        self.assertTrue(puesto.esta_abierto)
        self.assertEqual(puesto.plazas_cubiertas, 0)

    def test_no_asignar_candidato_a_vacante_cerrada(self):
        """P2: No permitir asignar candidatos a una vacante cerrada."""
        from django.contrib.auth.models import Group
        grupo_asesoras, _ = Group.objects.get_or_create(name='Asesoras')
        self.user.groups.add(grupo_asesoras)

        puesto = Puesto.objects.create(
            titulo=self.cat_puesto,
            marca=self.marca,
            agencia='Toyota Premier',
            ciudad='CUL',
            area='VTAS',
            asesora_encargada=self.user,
            esta_abierto=False,
            sueldo_base=15000
        )
        cand = Candidato.objects.create(nombres='Dora', apellidos='Libre', email='dora@test.com')

        self.client.login(username='testuser', password='password123')
        resp = self.client.get(reverse('asignar_candidato', args=[puesto.id]))
        self.assertEqual(resp.status_code, 302)

    def test_vacantes_confidenciales_ocultas_en_registro_publico(self):
        """P1/P4: Las vacantes confidenciales no aparecen en opciones públicas ni en homepage."""
        puesto_conf = Puesto.objects.create(
            titulo=self.cat_puesto,
            marca=self.marca,
            agencia='Dirección General Secreta',
            ciudad='CUL',
            area='ADMIN',
            estatus_autorizacion='AUTORIZADO',
            esta_abierto=True,
            es_confidencial=True,
            sueldo_base=50000
        )
        form = RegistroCandidatoForm()
        choices_keys = [c[0] for c in form.fields['puesto_de_interes'].choices]
        self.assertNotIn(puesto_conf.id, choices_keys)

        resp = self.client.get(reverse('homepage_publica'))
        self.assertNotContains(resp, 'Dirección General Secreta')

    def test_preseleccion_puesto_por_parametro_url(self):
        """P4: Preselección del puesto en formulario de registro vía query param ?puesto=ID."""
        puesto_pub = Puesto.objects.create(
            titulo=self.cat_puesto,
            marca=self.marca,
            agencia='Toyota Premier',
            ciudad='CUL',
            area='VTAS',
            estatus_autorizacion='AUTORIZADO',
            esta_abierto=True,
            es_confidencial=False,
            sueldo_base=15000
        )
        resp = self.client.get(reverse('registro_candidato') + f'?puesto={puesto_pub.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(str(resp.context['form'].initial.get('puesto_de_interes')), str(puesto_pub.id))

    def test_descarga_cv_restringida_a_personal_rh(self):
        """P1: Descarga de CV prohibida a usuarios externos o sin rol de RH."""
        cand = Candidato.objects.create(nombres='Eva', apellidos='Test', email='eva@test.com')
        self.client.login(username='testuser', password='password123')
        resp = self.client.get(reverse('descargar_cv', args=[cand.id]))
        # testuser no pertenece a Asesoras ni Gerencia de CH
        self.assertEqual(resp.status_code, 302)
        self.assertIn('acceso-denegado', resp.url)

    def test_bono_cobertura_fuera_de_tiempo_no_cumple(self):
        """P3: Vacante completamente cubierta pero fuera de tiempo NO cumple bono."""
        fecha_antigua = timezone.now() - timezone.timedelta(days=25)
        puesto_tardio = Puesto.objects.create(
            titulo=self.cat_puesto,
            marca=self.marca,
            agencia='Toyota Premier',
            ciudad='CUL',
            cantidad_vacantes=1,
            esta_abierto=False,
            fecha_solicitud=fecha_antigua,
            dias_meta=20
        )
        cand = Candidato.objects.create(nombres='Tarde', apellidos='Contratado', email='tarde@example.com')
        Proceso.objects.create(
            candidato=cand,
            puesto=puesto_tardio,
            asesora_asignada=self.user,
            estatus_proceso=Proceso.Estatus.CONTRATADO,
            fecha_inicio_etapa=timezone.now()
        )
        self.assertTrue(puesto_tardio.esta_completamente_cubierta)
        self.assertGreater(puesto_tardio.dias_transcurridos, puesto_tardio.dias_meta)
        self.assertFalse(puesto_tardio.cumplio_meta_bono)

    def test_bono_candidatos_reprobados_no_califican(self):
        """P3: Candidatos con pruebas reprobadas o boletinados no cuentan para la terna del bono."""
        puesto = Puesto.objects.create(
            titulo=self.cat_puesto,
            marca=self.marca,
            agencia='Toyota Premier',
            ciudad='CUL',
            cantidad_vacantes=2,
            esta_abierto=True,
            dias_meta=20
        )
        c1 = Candidato.objects.create(nombres='Aprobado1', apellidos='Test', email='ap1@test.com')
        c2 = Candidato.objects.create(nombres='Aprobado2', apellidos='Test', email='ap2@test.com')
        c_reprobado_psico = Candidato.objects.create(nombres='Reprobado', apellidos='Psico', email='rep@test.com')
        c_boletinado = Candidato.objects.create(nombres='Boletinado', apellidos='Veto', email='veto@test.com', es_no_contratable=True)

        # 2 candidatos válidos
        Proceso.objects.create(candidato=c1, puesto=puesto, asesora_asignada=self.user, estatus_proceso=Proceso.Estatus.ENT_JF)
        Proceso.objects.create(candidato=c2, puesto=puesto, asesora_asignada=self.user, estatus_proceso=Proceso.Estatus.ENT_JF)
        # 1 reprobó Pyxoom
        Proceso.objects.create(
            candidato=c_reprobado_psico, puesto=puesto, asesora_asignada=self.user,
            estatus_proceso=Proceso.Estatus.ENT_JF, resultado_pyxoom=Proceso.ResultadoPyxoom.REPROBADO
        )
        # 1 es boletinado No Contratable
        Proceso.objects.create(candidato=c_boletinado, puesto=puesto, asesora_asignada=self.user, estatus_proceso=Proceso.Estatus.ENT_JF)

        # Solo 2 candidatos calificados válidos -> No cumple bono de terna
        self.assertFalse(puesto.cumplio_meta_bono)

    def test_limite_maximo_dos_reinicios_sla(self):
        """P2: Límite estricto de máximo 2 reinicios permitidos por vacante."""
        from django.contrib.auth.models import Group
        from django.core.exceptions import ValidationError
        grupo_ch, _ = Group.objects.get_or_create(name='Gerentes de Capital Humano')
        self.user.groups.add(grupo_ch)

        otra_asesora = User.objects.create_user(username='asesora.responsable', password='password123')
        puesto = Puesto.objects.create(
            titulo=self.cat_puesto,
            marca=self.marca,
            agencia='Toyota Premier',
            ciudad='CUL',
            asesora_encargada=otra_asesora,
            esta_abierto=True,
            dias_meta=20
        )
        self.client.login(username='testuser', password='password123')

        # 1er reinicio -> Exitoso
        resp1 = self.client.post(reverse('reiniciar_vacante', args=[puesto.id]), {'comentario': 'Excepción 1'})
        self.assertEqual(resp1.status_code, 302)
        puesto.refresh_from_db()
        self.assertEqual(puesto.numero_reinicios, 1)

        # 2do reinicio -> Exitoso
        resp2 = self.client.post(reverse('reiniciar_vacante', args=[puesto.id]), {'comentario': 'Excepción 2'})
        self.assertEqual(resp2.status_code, 302)
        puesto.refresh_from_db()
        self.assertEqual(puesto.numero_reinicios, 2)

        # 3er intento en vista -> Bloqueado y permanece en 2
        resp3 = self.client.post(reverse('reiniciar_vacante', args=[puesto.id]), {'comentario': 'Excepción 3'})
        self.assertEqual(resp3.status_code, 302)
        puesto.refresh_from_db()
        self.assertEqual(puesto.numero_reinicios, 2)

        # 3er intento a nivel de modelo -> Lanza ValidationError
        with self.assertRaises(ValidationError):
            puesto.reiniciar_sla(comentario='Intento directo en modelo')

    def test_reversion_no_contratable_restringida_a_gerente_ch(self):
        """P1: La reversión de NO CONTRATABLE está reservada a la Gerencia de CH con motivo obligatorio."""
        from django.contrib.auth.models import Group
        from reclutamiento.models import RegistroActividad
        grupo_asesoras, _ = Group.objects.get_or_create(name='Asesoras')
        grupo_ch, _ = Group.objects.get_or_create(name='Gerentes de Capital Humano')

        asesora = User.objects.create_user(username='asesora.test', password='password123')
        asesora.groups.add(grupo_asesoras)

        gerente = User.objects.create_user(username='gerente.ch.test', password='password123')
        gerente.groups.add(grupo_ch)

        cand = Candidato.objects.create(
            nombres='Mario', apellidos='Veto', email='mario@test.com',
            es_no_contratable=True, motivo_no_contratable='Falta grave'
        )

        # Asesora intenta revertir -> 403 Forbidden
        self.client.login(username='asesora.test', password='password123')
        resp_asesora = self.client.post(reverse('candidato_detalle', args=[cand.id]), {
            'action': 'revertir_no_contratable',
            'motivo_reversion': 'Intento de asesora'
        })
        self.assertEqual(resp_asesora.status_code, 403)
        cand.refresh_from_db()
        self.assertTrue(cand.es_no_contratable)

        # Gerente de CH revierte con motivo -> Exitoso
        self.client.login(username='gerente.ch.test', password='password123')
        resp_gerente = self.client.post(reverse('candidato_detalle', args=[cand.id]), {
            'action': 'revertir_no_contratable',
            'motivo_reversion': 'Aclaración de RH favorable'
        })
        self.assertEqual(resp_gerente.status_code, 302)
        cand.refresh_from_db()
        self.assertFalse(cand.es_no_contratable)
        self.assertEqual(cand.motivo_no_contratable, '')

        # Se registra auditoría
        reg = RegistroActividad.objects.filter(tipo_objeto='Candidato', id_objeto=cand.id).first()
        self.assertIsNotNone(reg)
        self.assertIn('Revirtió', reg.accion)


class AislamientoInformacionAsesorasRBACTestCase(TestCase):
    """
    Pruebas rigurosas de aislamiento por rol (RBAC):
    Las asesoras únicamente pueden gestionar, visualizar y descargar reportes que contengan
    su información individual. Gerentes de CH y Directores tienen visibilidad global.
    """

    def setUp(self):
        from django.contrib.auth.models import Group
        self.grupo_asesoras, _ = Group.objects.get_or_create(name='Asesoras')
        self.grupo_gerentes, _ = Group.objects.get_or_create(name='Gerentes de Capital Humano')

        # Asesora 1
        self.asesora_1 = User.objects.create_user(
            username='asesora.ana', email='ana@test.com', password='password123',
            first_name='Ana', last_name='López'
        )
        self.asesora_1.groups.add(self.grupo_asesoras)

        # Asesora 2
        self.asesora_2 = User.objects.create_user(
            username='asesora.sofia', email='sofia@test.com', password='password123',
            first_name='Sofía', last_name='Navarro'
        )
        self.asesora_2.groups.add(self.grupo_asesoras)

        # Gerente CH
        self.gerente_ch = User.objects.create_user(
            username='gerente.ch', email='gerente@test.com', password='password123',
            first_name='Laura', last_name='Directora'
        )
        self.gerente_ch.groups.add(self.grupo_gerentes)

        # Catálogo y Marca
        self.marca = Marca.objects.create(nombre='Chevrolet')
        self.cat_puesto_1 = CatalogoPuesto.objects.create(nombre='Asesor de Ventas', dias_meta=20)
        self.cat_puesto_2 = CatalogoPuesto.objects.create(nombre='Mecánico Master', dias_meta=15)

        # Vacante Asesora 1
        self.puesto_1 = Puesto.objects.create(
            titulo=self.cat_puesto_1,
            marca=self.marca,
            agencia='Chevrolet Premier',
            ciudad='CUL',
            asesora_encargada=self.asesora_1,
            solicitado_por=self.asesora_1,
            cantidad_vacantes=1,
            esta_abierto=True,
            dias_meta=20
        )

        # Vacante Asesora 2
        self.puesto_2 = Puesto.objects.create(
            titulo=self.cat_puesto_2,
            marca=self.marca,
            agencia='Chevrolet Hermosillo Kino',
            ciudad='HMO',
            asesora_encargada=self.asesora_2,
            solicitado_por=self.asesora_2,
            cantidad_vacantes=1,
            esta_abierto=True,
            dias_meta=15
        )

        # Candidato y Proceso de Asesora 2
        self.candidato_2 = Candidato.objects.create(
            nombres='Carlos', apellidos='Ruiz', email='carlos@test.com'
        )
        self.proceso_2 = Proceso.objects.create(
            candidato=self.candidato_2,
            puesto=self.puesto_2,
            asesora_asignada=self.asesora_2,
            estatus_proceso=Proceso.Estatus.NUEVO
        )

    def test_asesora_solo_ve_sus_vacantes_en_reportes(self):
        """Una asesora solo debe ver sus propias vacantes y métricas individuales en reportes."""
        self.client.login(username='asesora.ana', password='password123')
        resp = self.client.get(reverse('vista_reportes'))
        self.assertEqual(resp.status_code, 200)

        # El contexto solo debe traer la vacante de Ana (puesto_1), jamás la de Sofía (puesto_2)
        puestos_en_reporte = resp.context['puestos'].object_list
        self.assertIn(self.puesto_1, puestos_en_reporte)
        self.assertNotIn(self.puesto_2, puestos_en_reporte)

        # En el scorecard de asesoras solo debe aparecer Ana
        scorecard = resp.context['asesoras_scorecard']
        self.assertEqual(len(scorecard), 1)
        self.assertEqual(scorecard[0]['asesora_id'], self.asesora_1.id)

        # Catálogos de asesoras solo la incluyen a ella
        asesoras_catalogo = list(resp.context['asesoras_disponibles'])
        self.assertEqual(len(asesoras_catalogo), 1)
        self.assertEqual(asesoras_catalogo[0].id, self.asesora_1.id)

    def test_gerente_ch_ve_todas_las_vacantes_en_reportes(self):
        """La Dirección / Gerencia de CH tiene visibilidad global de todas las vacantes y asesoras."""
        self.client.login(username='gerente.ch', password='password123')
        resp = self.client.get(reverse('vista_reportes'))
        self.assertEqual(resp.status_code, 200)

        puestos_en_reporte = resp.context['puestos'].object_list
        self.assertIn(self.puesto_1, puestos_en_reporte)
        self.assertIn(self.puesto_2, puestos_en_reporte)

        # Scorecard incluye a ambas asesoras
        scorecard = resp.context['asesoras_scorecard']
        self.assertGreaterEqual(len(scorecard), 2)
        asesoras_ids = [a['asesora_id'] for a in scorecard]
        self.assertIn(self.asesora_1.id, asesoras_ids)
        self.assertIn(self.asesora_2.id, asesoras_ids)

    def test_asesora_no_puede_consultar_detalle_proceso_de_otra_asesora(self):
        """Asesora 1 no puede acceder al detalle del proceso de Asesora 2 (403 Forbidden)."""
        self.client.login(username='asesora.ana', password='password123')
        resp = self.client.get(reverse('detalle_proceso', args=[self.proceso_2.id]))
        self.assertEqual(resp.status_code, 403)

    def test_gerente_ch_si_puede_consultar_detalle_proceso(self):
        """Gerente CH puede acceder al detalle del proceso de cualquier asesora."""
        self.client.login(username='gerente.ch', password='password123')
        resp = self.client.get(reverse('detalle_proceso', args=[self.proceso_2.id]))
        self.assertEqual(resp.status_code, 200)

    def test_asesora_no_puede_consultar_vacante_de_otra_asesora(self):
        """Asesora 1 no puede inspeccionar la vacante asignada a Asesora 2 (403 Forbidden)."""
        self.client.login(username='asesora.ana', password='password123')
        resp = self.client.get(reverse('puesto_detalle', args=[self.puesto_2.id]))
        self.assertEqual(resp.status_code, 403)

    def test_gerente_ch_si_puede_consultar_cualquier_vacante(self):
        """Gerente CH puede inspeccionar el expediente de cualquier vacante."""
        self.client.login(username='gerente.ch', password='password123')
        resp = self.client.get(reverse('puesto_detalle', args=[self.puesto_2.id]))
        self.assertEqual(resp.status_code, 200)


class PanelAdministracionTests(TestCase):
    """Pruebas unitarias para el Centro de Administración y Catálogos."""

    def setUp(self):
        self.client = Client()
        self.grupo_gerentes, _ = Group.objects.get_or_create(name='Gerentes de Capital Humano')
        self.grupo_asesoras, _ = Group.objects.get_or_create(name='Asesoras')

        self.superuser = User.objects.create_superuser(
            username='admin_boss',
            email='admin@premier.com',
            password='Password123!'
        )
        self.gerente = User.objects.create_user(
            username='gerente_rh',
            email='gerente@premier.com',
            password='Password123!',
            first_name='Patricia',
            last_name='Aréchiga'
        )
        self.gerente.groups.add(self.grupo_gerentes)

        self.asesora = User.objects.create_user(
            username='asesora_rh',
            email='asesora@premier.com',
            password='Password123!',
            first_name='Laura',
            last_name='Gómez'
        )
        self.asesora.groups.add(self.grupo_asesoras)

        self.ciudad, _ = Ciudad.objects.get_or_create(nombre='Mazatlán', defaults={'activo': True})
        self.marca, _ = Marca.objects.get_or_create(nombre='Audi', defaults={'activo': True})
        self.agencia, _ = Agencia.objects.get_or_create(
            nombre='Audi Center Mazatlán Test',
            defaults={'marca': self.marca, 'ciudad': self.ciudad, 'activo': True}
        )
        self.puesto_cat, _ = CatalogoPuesto.objects.get_or_create(
            nombre='Especialista Audi Test',
            defaults={'dias_meta_default': 25, 'activo': True}
        )

    def test_permiso_puede_administrar_rh(self):
        """Verifica la función centralizada de permisos puede_administrar_rh."""
        from reclutamiento.permissions import puede_administrar_rh

        user_sin_grupo = User.objects.create_user(username='sin_grupo', password='Password123!')
        self.assertFalse(puede_administrar_rh(None))
        self.assertFalse(puede_administrar_rh(user_sin_grupo))
        self.assertFalse(puede_administrar_rh(self.asesora))
        self.assertTrue(puede_administrar_rh(self.gerente))
        self.assertTrue(puede_administrar_rh(self.superuser))

    def test_control_acceso_vista_panel_administracion(self):
        """Verifica que solo personal con puede_administrar_rh acceda a /configuracion/."""
        url = reverse('panel_administracion')

        # No autenticado -> redirect login
        resp_anon = self.client.get(url)
        self.assertEqual(resp_anon.status_code, 302)

        # Asesora -> redirección (no autorizada)
        self.client.login(username='asesora_rh', password='Password123!')
        resp_asesora = self.client.get(url)
        self.assertEqual(resp_asesora.status_code, 302)
        self.client.logout()

        # Gerente de Capital Humano -> 200 OK
        self.client.login(username='gerente_rh', password='Password123!')
        resp_gerente = self.client.get(url)
        self.assertEqual(resp_gerente.status_code, 200)
        self.assertTemplateUsed(resp_gerente, 'reclutamiento/panel_administracion.html')
        self.assertContains(resp_gerente, 'Centro de Administración y Catálogos')
        self.client.logout()

        # Superuser -> 200 OK
        self.client.login(username='admin_boss', password='Password123!')
        resp_super = self.client.get(url)
        self.assertEqual(resp_super.status_code, 200)

    def test_dar_de_alta_nueva_integrante_rh(self):
        """Gerente puede crear una nueva asesora desde el panel y se registra en bitácora."""
        from reclutamiento.models import RegistroActividad

        self.client.login(username='gerente_rh', password='Password123!')
        url = reverse('panel_administracion')

        post_data = {
            'accion': 'crear_usuario',
            'first_name': 'Sofía',
            'last_name': 'Reyes',
            'username': 'sofia.reyes',
            'email': 'sofia@premier.com',
            'rol': 'asesora',
            'password': 'SeguraPassword123!'
        }
        resp = self.client.post(url, post_data, follow=True)
        self.assertEqual(resp.status_code, 200)

        nueva_user = User.objects.filter(username='sofia.reyes').first()
        self.assertIsNotNone(nueva_user)
        self.assertEqual(nueva_user.first_name, 'Sofía')
        self.assertTrue(nueva_user.groups.filter(name='Asesoras').exists())

        # Bitácora
        log = RegistroActividad.objects.filter(usuario=self.gerente, accion="Alta de Usuario RH").first()
        self.assertIsNotNone(log)
        self.assertIn('sofia.reyes', log.detalles)

    def test_seguridad_no_desactivar_a_si_misma_o_superuser(self):
        """Una Gerente RH no puede desactivar su propio usuario ni el de un Superusuario."""
        self.client.login(username='gerente_rh', password='Password123!')
        url = reverse('panel_administracion')

        # Intento de desactivarse a sí misma
        self.client.post(url, {'accion': 'toggle_usuario_activo', 'user_id': self.gerente.id})
        self.gerente.refresh_from_db()
        self.assertTrue(self.gerente.is_active)

        # Intento de desactivar a superuser
        self.client.post(url, {'accion': 'toggle_usuario_activo', 'user_id': self.superuser.id})
        self.superuser.refresh_from_db()
        self.assertTrue(self.superuser.is_active)

        # Desactivar a asesora -> permitido
        self.client.post(url, {'accion': 'toggle_usuario_activo', 'user_id': self.asesora.id})
        self.asesora.refresh_from_db()
        self.assertFalse(self.asesora.is_active)

    def test_gestion_catalogos_agencia_marca_puesto_ciudad_aviso(self):
        """Prueba las acciones de creación y alternado de estado en los catálogos."""
        from reclutamiento.models import Ciudad, Marca, Agencia, CatalogoPuesto, Aviso

        self.client.login(username='gerente_rh', password='Password123!')
        url = reverse('panel_administracion')

        # 1. Crear ciudad
        self.client.post(url, {'accion': 'crear_ciudad', 'nombre': 'Navojoa'})
        navojoa = Ciudad.objects.filter(nombre='Navojoa').first()
        self.assertIsNotNone(navojoa)
        self.assertTrue(navojoa.activo)

        # Toggle ciudad
        self.client.post(url, {'accion': 'toggle_ciudad_activo', 'item_id': navojoa.id})
        navojoa.refresh_from_db()
        self.assertFalse(navojoa.activo)

        # 2. Crear marca
        self.client.post(url, {'accion': 'crear_marca', 'nombre': 'Porsche'})
        porsche = Marca.objects.filter(nombre='Porsche').first()
        self.assertIsNotNone(porsche)
        self.assertTrue(porsche.activo)

        # 3. Crear puesto con meta sugerida
        self.client.post(url, {'accion': 'crear_puesto', 'nombre': 'Técnico Master', 'dias_meta_default': '18'})
        puesto = CatalogoPuesto.objects.filter(nombre='Técnico Master').first()
        self.assertIsNotNone(puesto)
        self.assertEqual(puesto.dias_meta_default, 18)
        self.assertEqual(puesto.dias_meta, 18)

        # 4. Crear agencia asociada
        self.client.post(url, {
            'accion': 'crear_agencia',
            'nombre': 'Porsche Culiacán',
            'marca': porsche.id,
            'ciudad': self.ciudad.id
        })
        agencia = Agencia.objects.filter(nombre='Porsche Culiacán').first()
        self.assertIsNotNone(agencia)
        self.assertEqual(agencia.marca, porsche)
        self.assertEqual(agencia.ciudad, self.ciudad)

        # 5. Crear aviso interno
        self.client.post(url, {
            'accion': 'crear_aviso',
            'titulo': 'Nuevo Protocolo de Reclutamiento',
            'mensaje': 'Por favor consultar las guías actualizadas.'
        })
        aviso = Aviso.objects.filter(titulo='Nuevo Protocolo de Reclutamiento').first()
        self.assertIsNotNone(aviso)
        self.assertTrue(aviso.esta_activo)

        # Toggle aviso
        self.client.post(url, {'accion': 'toggle_aviso_activo', 'item_id': aviso.id})
        aviso.refresh_from_db()
        self.assertFalse(aviso.esta_activo)


class TelegramBotExecutiveTests(TestCase):
    """Pruebas unitarias para la integración del bot ejecutivo de Telegram (Reportería y BI)."""

    def setUp(self):
        self.client = Client()
        # Grupos de seguridad
        self.grupo_gerentes, _ = Group.objects.get_or_create(name='Gerentes de Capital Humano')
        self.grupo_asesoras, _ = Group.objects.get_or_create(name='Asesoras')

        # Usuarios
        self.directora, _ = User.objects.get_or_create(
            username='patricia_arechiga',
            defaults={
                'first_name': 'Patricia',
                'last_name': 'Aréchiga',
                'email': 'patricia@premier.com'
            }
        )
        self.directora.set_password('password123')
        self.directora.save()
        self.directora.groups.add(self.grupo_gerentes)

        self.asesora, _ = User.objects.get_or_create(
            username='asesora_test',
            defaults={
                'first_name': 'Laura',
                'last_name': 'Gómez',
                'email': 'laura@premier.com'
            }
        )
        self.asesora.set_password('password123')
        self.asesora.save()
        self.asesora.groups.add(self.grupo_asesoras)

        self.superuser, _ = User.objects.get_or_create(
            username='admin_ch',
            defaults={
                'email': 'admin@premier.com',
                'is_superuser': True,
                'is_staff': True
            }
        )
        self.superuser.set_password('password123')
        self.superuser.save()

        # Datos base de reclutamiento
        self.marca, _ = Marca.objects.get_or_create(nombre='Toyota Premier', defaults={'activo': True})
        self.ciudad, _ = Ciudad.objects.get_or_create(nombre='Culiacán', defaults={'activo': True})
        self.agencia, _ = Agencia.objects.get_or_create(
            nombre='Toyota Culiacán',
            defaults={'marca': self.marca, 'ciudad': self.ciudad, 'activo': True}
        )
        self.puesto_cat, _ = CatalogoPuesto.objects.get_or_create(
            nombre='Gerente de Ventas',
            defaults={'dias_meta_default': 25, 'activo': True}
        )

        self.vacante = Puesto.objects.create(
            titulo=self.puesto_cat,
            marca=self.marca,
            agencia=self.agencia.nombre,
            ciudad='CUL',
            area='VTAS',
            estatus_autorizacion=Puesto.EstatusAutorizacion.AUTORIZADO,
            esta_abierto=True,
            cantidad_vacantes=1,
            nombre_jefe_inmediato='Director Comercial',
            puesto_jefe_inmediato='Director',
            motivo_requisicion='CRE',
            objetivo_puesto='Liderar ventas',
            funciones_puesto='Gestión de equipo comercial',
            indicador_puesto='Cumplimiento de cuota',
            sueldo_base=35000.00
        )

        self.candidato = Candidato.objects.create(
            nombres='Carlos',
            apellidos='Mendoza Ríos',
            email='carlos.mendoza@email.com',
            telefono='6671234567'
        )

        self.proceso = Proceso.objects.create(
            puesto=self.vacante,
            candidato=self.candidato,
            asesora_asignada=self.asesora,
            estatus_proceso=Proceso.Estatus.ENT_CH
        )

    def test_generar_token_y_vincular_directora(self):
        """Verifica generación de token seguro y vinculación de una cuenta con rol Gerente/Directora."""
        from reclutamiento.telegram_service import TelegramService
        token, deep_link = TelegramService.generar_token_vinculacion(self.directora)
        self.assertTrue(bool(token))
        self.assertEqual(len(token), 24)
        self.assertIn("t.me", deep_link)
        self.directora.perfilusuario.refresh_from_db()
        self.assertEqual(self.directora.perfilusuario.telegram_token_enlace, token)

        # Vinculación exitosa
        ok, user, msg = TelegramService.vincular_usuario_por_token(token, 987654321, "patricia_tg")
        self.assertTrue(ok)
        self.assertEqual(user, self.directora)
        self.assertIn("exitosamente", msg)

        self.directora.perfilusuario.refresh_from_db()
        self.assertEqual(self.directora.perfilusuario.telegram_chat_id, '987654321')
        self.assertEqual(self.directora.perfilusuario.telegram_username, 'patricia_tg')
        self.assertIsNone(self.directora.perfilusuario.telegram_token_enlace)

        # Intentar vincular de nuevo con el mismo token debe fallar
        ok2, user2, msg2 = TelegramService.vincular_usuario_por_token(token, 111111, "otro")
        self.assertFalse(ok2)
        self.assertIsNone(user2)

    def test_asesora_rechazada_al_vincular_bot_ejecutivo(self):
        """Verifica que un usuario con rol de Asesora no pueda vincularse al bot reservado para Dirección."""
        from reclutamiento.telegram_service import TelegramService
        token, _ = TelegramService.generar_token_vinculacion(self.asesora)
        ok, user, msg = TelegramService.vincular_usuario_por_token(token, 555555, "asesora_tg")
        self.assertFalse(ok)
        self.assertIn("Acceso no autorizado", msg)
        self.asesora.perfilusuario.refresh_from_db()
        self.assertIsNone(self.asesora.perfilusuario.telegram_chat_id)

    def test_generacion_textos_reporteria_y_excel(self):
        """Verifica la generación correcta de reportes de texto y buffer de Excel."""
        from reclutamiento.telegram_service import TelegramService

        # 1. Resumen ejecutivo
        resumen = TelegramService.generar_resumen_ejecutivo_texto(self.directora)
        self.assertIn("Resumen Ejecutivo", resumen)
        self.assertIn("ESTATUS GLOBAL DE VACANTES", resumen)

        # 2. Desglose de agencias
        agencias_txt = TelegramService.generar_vacantes_agencias_texto(self.directora)
        self.assertIn("VACANTES ABIERTAS POR AGENCIA", agencias_txt)
        self.assertIn("Toyota Culiacán", agencias_txt)

        # 3. Monitoreo de SLA
        sla_txt = TelegramService.generar_alertas_sla_texto(self.directora)
        self.assertIn("MONITOREO DE TIEMPOS DE COBERTURA (SLA)", sla_txt)

        # 4. Candidatos estancados
        estancados_txt = TelegramService.generar_estancados_texto(self.directora)
        self.assertIn("PROCESOS ESTANCADOS", estancados_txt)

        # 5. Contrataciones
        contrataciones_txt = TelegramService.generar_contrataciones_mes_texto(self.directora)
        self.assertIn("CONTRATACIONES DE", contrataciones_txt)

        # 6. Generación de Excel binario
        buf, filename = TelegramService.generar_excel_buffer(self.directora)
        self.assertTrue(filename.endswith('.xlsx'))
        self.assertGreater(buf.getbuffer().nbytes, 1000)

        # Validar que es un Excel legible por openpyxl
        wb = openpyxl.load_workbook(buf)
        self.assertIn("Resumen Ejecutivo", wb.sheetnames)

    @override_settings(TELEGRAM_WEBHOOK_SECRET='clave_secreta_test')
    def test_webhook_seguridad_y_metodos(self):
        """Verifica que el webhook rechace peticiones no autorizadas o métodos no permitidos."""
        url = reverse('telegram_webhook')

        # GET no permitido (405)
        resp_get = self.client.get(url)
        self.assertEqual(resp_get.status_code, 405)

        # POST sin firma secreta (403)
        resp_no_secret = self.client.post(url, data=json.dumps({}), content_type='application/json')
        self.assertEqual(resp_no_secret.status_code, 403)

        # POST con firma secreta incorrecta (403)
        resp_wrong_secret = self.client.post(
            url,
            data=json.dumps({}),
            content_type='application/json',
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN='clave_erronea'
        )
        self.assertEqual(resp_wrong_secret.status_code, 403)

        # POST con firma correcta y JSON inválido (400)
        resp_bad_json = self.client.post(
            url,
            data="Esto no es json",
            content_type='application/json',
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN='clave_secreta_test'
        )
        self.assertEqual(resp_bad_json.status_code, 400)

    @override_settings(TELEGRAM_WEBHOOK_SECRET='clave_secreta_test')
    @patch('reclutamiento.telegram_service.TelegramService.api_call')
    def test_webhook_flujo_vinculacion_start(self, mock_api):
        """Verifica la vinculación en 1-clic a través del comando /start <token>."""
        mock_api.return_value = {'ok': True}
        from reclutamiento.telegram_service import TelegramService
        token, _ = TelegramService.generar_token_vinculacion(self.directora)

        payload = {
            'message': {
                'chat': {'id': 123456789},
                'from': {'username': 'patricia_tg'},
                'text': f'/start {token}'
            }
        }
        url = reverse('telegram_webhook')
        resp = self.client.post(
            url,
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN='clave_secreta_test'
        )
        self.assertEqual(resp.status_code, 200)

        self.directora.perfilusuario.refresh_from_db()
        self.assertEqual(self.directora.perfilusuario.telegram_chat_id, '123456789')
        self.assertTrue(mock_api.called)

    @override_settings(TELEGRAM_WEBHOOK_SECRET='clave_secreta_test')
    @patch('reclutamiento.telegram_service.TelegramService.api_call')
    def test_webhook_comandos_interactivos(self, mock_api):
        """Verifica la respuesta a comandos interactivos como /resumen, /sla y /excel."""
        mock_api.return_value = {'ok': True}
        # Vincular a la directora
        perfil = self.directora.perfilusuario
        perfil.telegram_chat_id = '998877'
        perfil.save()

        url = reverse('telegram_webhook')
        headers = {'HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN': 'clave_secreta_test'}

        # Comando /resumen
        resp = self.client.post(
            url,
            data=json.dumps({'message': {'chat': {'id': 998877}, 'text': '/resumen'}}),
            content_type='application/json',
            **headers
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(mock_api.called)

        # Callback query cmd_excel
        mock_api.reset_mock()
        resp_cb = self.client.post(
            url,
            data=json.dumps({
                'callback_query': {
                    'id': 'cb_test_1',
                    'data': 'cmd_excel',
                    'message': {'chat': {'id': 998877}, 'message_id': 42}
                }
            }),
            content_type='application/json',
            **headers
        )
        self.assertEqual(resp_cb.status_code, 200)
        self.assertTrue(mock_api.called)

        # Flujo de filtros interactivos vía Callback Queries
        # 1. Scorecard Global de Asesoras (cmd_scorecard_global)
        mock_api.reset_mock()
        resp_sc = self.client.post(
            url,
            data=json.dumps({
                'callback_query': {
                    'id': 'cb_test_sc',
                    'data': 'cmd_scorecard_global',
                    'message': {'chat': {'id': 998877}, 'message_id': 42}
                }
            }),
            content_type='application/json',
            **headers
        )
        self.assertEqual(resp_sc.status_code, 200)
        self.assertTrue(mock_api.called)

        # 2. Panorama de Ciudades (cmd_ciudades_panorama)
        mock_api.reset_mock()
        resp_cd = self.client.post(
            url,
            data=json.dumps({
                'callback_query': {
                    'id': 'cb_test_cd',
                    'data': 'cmd_ciudades_panorama',
                    'message': {'chat': {'id': 998877}, 'message_id': 42}
                }
            }),
            content_type='application/json',
            **headers
        )
        self.assertEqual(resp_cd.status_code, 200)
        self.assertTrue(mock_api.called)

        # 3. Focos Rojos (cmd_focos_rojos)
        mock_api.reset_mock()
        resp_focos = self.client.post(
            url,
            data=json.dumps({
                'callback_query': {
                    'id': 'cb_test_focos',
                    'data': 'cmd_focos_rojos',
                    'message': {'chat': {'id': 998877}, 'message_id': 42}
                }
            }),
            content_type='application/json',
            **headers
        )
        self.assertEqual(resp_focos.status_code, 200)
        self.assertTrue(mock_api.called)

        # 4. Detalle de Culiacán (flt_cd:CUL)
        mock_api.reset_mock()
        resp_cul = self.client.post(
            url,
            data=json.dumps({
                'callback_query': {
                    'id': 'cb_test_cul',
                    'data': 'flt_cd:CUL',
                    'message': {'chat': {'id': 998877}, 'message_id': 42}
                }
            }),
            content_type='application/json',
            **headers
        )
        self.assertEqual(resp_cul.status_code, 200)
        self.assertTrue(mock_api.called)

        # 5. Comandos de texto inteligentes (/scorecard, /ciudad culiacan y búsqueda natural "culiacan")
        mock_api.reset_mock()
        resp_cmd_sc = self.client.post(
            url,
            data=json.dumps({'message': {'chat': {'id': 998877}, 'text': '/scorecard'}}),
            content_type='application/json',
            **headers
        )
        self.assertEqual(resp_cmd_sc.status_code, 200)
        self.assertTrue(mock_api.called)

        mock_api.reset_mock()
        resp_cmd_cd = self.client.post(
            url,
            data=json.dumps({'message': {'chat': {'id': 998877}, 'text': 'culiacan'}}),
            content_type='application/json',
            **headers
        )
        self.assertEqual(resp_cmd_cd.status_code, 200)
        self.assertTrue(mock_api.called)

    def test_fichas_filtradas_por_dimension(self):
        """Verifica la generación de micro-fichas especializadas por Ciudad, Asesora y Agencia."""
        from reclutamiento.telegram_service import TelegramService

        # 1. Scorecard Global del Equipo
        sc_global = TelegramService.generar_scorecard_global_asesoras_texto(self.directora)
        self.assertIn("SCORECARD DE ASESORAS", sc_global)

        # 2. Panorama Geográfico de Plazas
        panorama_cd = TelegramService.generar_panorama_ciudades_texto(self.directora)
        self.assertIn("PANORAMA POR CIUDADES", panorama_cd)

        # 3. Focos Rojos
        focos = TelegramService.generar_focos_rojos_texto(self.directora)
        self.assertIn("FOCOS ROJOS", focos)

        # 4. Ficha de Ciudad Culiacán
        ficha_cd = TelegramService.generar_ficha_ciudad_texto('CUL', self.directora)
        self.assertIn("FICHA DE CIUDAD: CULIACÁN", ficha_cd)
        self.assertIn("Toyota Culiacán", ficha_cd)

        # 5. Scorecard de Asesora
        scorecard_as = TelegramService.generar_scorecard_asesora_texto(self.asesora.id, self.directora)
        self.assertIn("SCORECARD:", scorecard_as)
        self.assertIn("vacantes asignadas", scorecard_as)

        # 6. Ficha de Agencia
        ficha_ag = TelegramService.generar_ficha_agencia_texto('Toyota', self.directora)
        self.assertIn("FICHA AGENCIA: TOYOTA CULIACÁN", ficha_ag)

        # 7. Excel filtrado
        buf_flt, fname_flt = TelegramService.generar_excel_filtrado_buffer('ciudad', 'CUL', self.directora)
        self.assertTrue(fname_flt.endswith('.xlsx'))
        self.assertGreater(buf_flt.getbuffer().nbytes, 1000)

    def test_metricas_coinciden_exactamente_con_reportes_service(self):
        """
        Valida que el cálculo de contrataciones (Count('id')) y plazas pendientes
        en Telegram coincide exactamente con ReportesService (única fuente de verdad).
        """
        from reclutamiento.services import ReportesService
        from reclutamiento.telegram_service import TelegramService

        # Crear vacante con 4 plazas solicitadas
        puesto_extra = Puesto.objects.create(
            titulo=self.puesto_cat,
            marca=self.marca,
            agencia=self.agencia.nombre,
            ciudad='CUL',
            area='VTAS',
            estatus_autorizacion=Puesto.EstatusAutorizacion.AUTORIZADO,
            esta_abierto=True,
            cantidad_vacantes=4,
            asesora_encargada=self.asesora,
            dias_meta=20
        )

        # Crear 1 candidato contratado previamente para que plazas_cubiertas sea 1
        cand_previo = Candidato.objects.create(nombres='Previo', apellidos='Uno', email='previo@test.com')
        Proceso.objects.create(
            puesto=puesto_extra,
            candidato=cand_previo,
            asesora_asignada=self.asesora,
            estatus_proceso=Proceso.Estatus.CONTRATADO
        )
        self.assertEqual(puesto_extra.plazas_cubiertas, 1)
        self.assertEqual(puesto_extra.plazas_pendientes, 3)

        # Crear 2 contrataciones para la asesora
        candidato1 = Candidato.objects.create(nombres='Ana', apellidos='López', email='ana@test.com')
        candidato2 = Candidato.objects.create(nombres='Beto', apellidos='Reyes', email='beto@test.com')

        Proceso.objects.create(
            puesto=puesto_extra,
            candidato=candidato1,
            asesora_asignada=self.asesora,
            estatus_proceso=Proceso.Estatus.CONTRATADO
        )
        Proceso.objects.create(
            puesto=puesto_extra,
            candidato=candidato2,
            asesora_asignada=self.asesora,
            estatus_proceso=Proceso.Estatus.CONTRATADO
        )

        puestos = list(ReportesService.get_base_queryset(self.directora))
        kpis = ReportesService.compute_kpis(puestos)
        sc = ReportesService.compute_asesoras_scorecard(puestos)

        # 1. Validar plazas pendientes
        resumen_txt = TelegramService.generar_resumen_ejecutivo_texto(self.directora)
        self.assertIn(f"<b>{kpis['plazas_activas_pendientes']}</b> plazas pendientes", resumen_txt)

        # 2. Validar conteo de contrataciones en scorecard (cuenta registros de Proceso, nunca suma cantidad_vacantes)
        asesora_entry = next((a for a in sc if a['asesora_id'] == self.asesora.id), None)
        self.assertIsNotNone(asesora_entry)
        self.assertEqual(asesora_entry['contratados'], 3)

        sc_txt = TelegramService.generar_scorecard_global_asesoras_texto(self.directora)
        self.assertIn("<b>3</b> contrataciones concretadas", sc_txt)

    def test_teclados_callback_data_longitud_maxima_64_bytes(self):
        """
        Valida rigurosamente que NINGÚN callback_data generado por los teclados de navegación
        supere los 64 bytes permitidos por la API de Telegram (codificación UTF-8).
        """
        from reclutamiento.telegram_service import TelegramService

        teclados_a_probar = [
            TelegramService.obtener_teclado_principal(),
            TelegramService.obtener_teclado_filtros(),
            TelegramService.obtener_teclado_focos_rojos(),
            TelegramService.obtener_teclado_lista_asesoras(self.directora),
            TelegramService.obtener_teclado_lista_agencias(self.directora),
            TelegramService.obtener_teclado_lista_ciudades(self.directora),
            TelegramService.obtener_teclado_detalle('as', self.asesora.id),
            TelegramService.obtener_teclado_detalle('ag', self.agencia.id),
            TelegramService.obtener_teclado_detalle('cd', 'CUL'),
            TelegramService.obtener_teclado_tipos_excel(),
            TelegramService.obtener_teclado_periodos_excel('resumen'),
            TelegramService.obtener_teclado_periodos_excel('bono'),
            TelegramService.obtener_teclado_periodos_excel('sabana'),
        ]

        for teclado in teclados_a_probar:
            self.assertIn('inline_keyboard', teclado)
            for fila in teclado['inline_keyboard']:
                for boton in fila:
                    cb = boton.get('callback_data', '')
                    tamano_bytes = len(cb.encode('utf-8'))
                    self.assertGreater(tamano_bytes, 0, f"Botón '{boton.get('text')}' tiene callback_data vacío")
                    self.assertLessEqual(
                        tamano_bytes, 64,
                        f"callback_data '{cb}' ({tamano_bytes} bytes) excede el límite de 64 bytes de Telegram"
                    )

    def test_escape_seguro_caracteres_especiales_html(self):
        """
        Valida que nombres con &, < o > en agencias, puestos, candidatos y asesoras
        se escapen adecuadamente para no corromper parse_mode='HTML' de Telegram.
        """
        from reclutamiento.telegram_service import TelegramService, _esc

        # Test unitario directo del helper _esc
        self.assertEqual(_esc("Toyota & Lexus <Norte>"), "Toyota &amp; Lexus &lt;Norte&gt;")
        self.assertEqual(_esc(None), "")

        # Puesto con caracteres especiales
        puesto_especial = Puesto.objects.create(
            titulo=self.puesto_cat,
            marca=self.marca,
            agencia="Hojalatería & Pintura <Matriz>",
            ciudad='CUL',
            area='HYP',
            estatus_autorizacion=Puesto.EstatusAutorizacion.AUTORIZADO,
            esta_abierto=True,
            cantidad_vacantes=1,
            asesora_encargada=self.asesora,
            dias_meta=10
        )
        cand_especial = Candidato.objects.create(
            nombres="José & María",
            apellidos="García <Junior>",
            email="jose.maria@test.com"
        )
        Proceso.objects.create(
            puesto=puesto_especial,
            candidato=cand_especial,
            asesora_asignada=self.asesora,
            estatus_proceso=Proceso.Estatus.ENT_CH
        )

        ficha_txt = TelegramService.generar_ficha_agencia_texto("Hojalatería & Pintura <Matriz>", self.directora)
        self.assertIn("HOJALATERÍA &amp; PINTURA &lt;MATRIZ&gt;", ficha_txt)
        self.assertNotIn("<Matriz>", ficha_txt)

    @override_settings(TELEGRAM_WEBHOOK_SECRET='clave_secreta_test')
    @patch('reclutamiento.telegram_service.TelegramService.api_call')
    def test_webhook_enrutamiento_nuevos_prefijos_y_flujo_2_pasos(self, mock_api):
        """
        Valida el enrutamiento completo de los nuevos prefijos nav:, flist:, f:, xls_t:, xls:p: y xls:res:todo:
        confirmando que el webhook siempre responde con answerCallbackQuery y actualiza in-place.
        """
        mock_api.return_value = {'ok': True}
        perfil = self.directora.perfilusuario
        perfil.telegram_chat_id = '998877'
        perfil.save()

        url = reverse('telegram_webhook')
        headers = {'HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN': 'clave_secreta_test'}

        prefijos_a_probar = [
            'nav:resumen',
            'nav:focos',
            'nav:filtros',
            'nav:excels',
            'flist:as',
            'flist:ag',
            'flist:cd',
            f'f:as:{self.asesora.id}',
            'f:cd:CUL',
            f'f:ag:{self.agencia.id}',
            'xls_t:resumen',
            'xls_t:bono',
            'xls:p:resumen:mes_actual',
            'xls:p:bono:semana',
            f'xls:res:todo:as:{self.asesora.id}',
        ]

        for prefijo in prefijos_a_probar:
            mock_api.reset_mock()
            resp = self.client.post(
                url,
                data=json.dumps({
                    'callback_query': {
                        'id': f'cb_{prefijo}',
                        'data': prefijo,
                        'message': {'chat': {'id': 998877}, 'message_id': 100}
                    }
                }),
                content_type='application/json',
                **headers
            )
            self.assertEqual(resp.status_code, 200)
            self.assertTrue(mock_api.called, f"Fallo al invocar API de Telegram para prefijo {prefijo}")
            # Validar que answerCallbackQuery fue llamado
            llamadas = [call[0][0] for call in mock_api.call_args_list]
            self.assertIn('answerCallbackQuery', llamadas, f"answerCallbackQuery no fue invocado para {prefijo}")

    @override_settings(TELEGRAM_BOT_TOKEN='123456789:ABCDefghIJKlmnoPQRstuvwxYZ')
    @patch('reclutamiento.telegram_service.TelegramService.api_call')
    def test_management_commands_pulse_y_flash(self, mock_api):
        """Verifica que los cron jobs de Pulse Matutino y Flash Semanal se ejecuten sin excepciones."""
        mock_api.return_value = {'ok': True}
        perfil = self.directora.perfilusuario
        perfil.telegram_chat_id = '123456'
        perfil.recibir_pulse_matutino = True
        perfil.save()

        # Ejecución forzada de Pulse Matutino
        out = StringIO()
        call_command('telegram_pulse_matutino', force=True, stdout=out)
        self.assertIn("Pulse Matutino concluido", out.getvalue())

        # Ejecución forzada de Flash Semanal
        out2 = StringIO()
        call_command('telegram_flash_semanal', force=True, stdout=out2)
        self.assertIn("Flash Semanal concluido", out2.getvalue())

        # Configuración / consulta de Webhook
        out3 = StringIO()
        mock_api.return_value = {'ok': True, 'result': {'url': 'https://aguzmaninz.pythonanywhere.com/api/telegram/webhook/'}}
        call_command('telegram_setup_webhook', info=True, stdout=out3)
        self.assertIn("Consultando estado del webhook", out3.getvalue())

    def test_panel_administracion_acciones_telegram(self):
        """Verifica las acciones POST de Telegram en el panel de administración."""
        url = reverse('panel_administracion')
        self.client.login(username='patricia_arechiga', password='password123')

        # 1. Generar token vía AJAX / JSON
        resp_token = self.client.post(
            url,
            {'action': 'generar_token_telegram', 'user_id': self.directora.id},
            HTTP_ACCEPT='application/json'
        )
        self.assertEqual(resp_token.status_code, 200)
        data_token = resp_token.json()
        self.assertEqual(data_token.get('status'), 'ok')
        self.assertTrue(bool(data_token.get('token')))
        self.assertIn('t.me', data_token.get('enlace'))

        # 1.b Generar token vía envío estándar de formulario navegador (debe redirigir directamente a Telegram)
        resp_redirect = self.client.post(
            url,
            {'action': 'generar_token_telegram', 'user_id': self.directora.id}
        )
        self.assertEqual(resp_redirect.status_code, 302)
        self.assertIn('https://t.me/', resp_redirect.url)

        # Asignar chat_id simulado
        perfil = self.directora.perfilusuario
        perfil.telegram_chat_id = '334455'
        perfil.save()

        # 2. Desvincular cuenta
        resp_desvincular = self.client.post(
            url,
            {'action': 'desvincular_telegram', 'user_id': self.directora.id},
            HTTP_ACCEPT='application/json'
        )
        self.assertEqual(resp_desvincular.status_code, 200)
        data_desv = resp_desvincular.json()
        self.assertEqual(data_desv.get('status'), 'ok')
        perfil.refresh_from_db()
        self.assertIsNone(perfil.telegram_chat_id)

    @override_settings(TELEGRAM_BOT_TOKEN='123456789:ABCDefghIJKlmnoPQRstuvwxYZ')
    @patch('reclutamiento.telegram_service.TelegramService.api_call')
    def test_notificaciones_eventos_tiempo_real(self, mock_api):
        """Verifica que las alertas de eventos críticos (requisición creada y plaza cubierta) se envíen."""
        mock_api.return_value = {'ok': True}
        from reclutamiento.telegram_service import TelegramService

        perfil = self.directora.perfilusuario
        perfil.telegram_chat_id = '999888'
        perfil.recibir_alertas_criticas = True
        perfil.save()

        # Alerta requisición creada
        TelegramService.notificar_requisicion_creada(self.vacante)
        self.assertTrue(mock_api.called)

        # Alerta plaza cubierta
        mock_api.reset_mock()
        TelegramService.notificar_plaza_cubierta(self.proceso)
        self.assertTrue(mock_api.called)









