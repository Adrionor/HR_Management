from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from reclutamiento.models import (
    Marca, CatalogoPuesto, Puesto, Candidato, Proceso, PerfilDePuesto, PerfilUsuario, Aviso, RegistroActividad
)

class Command(BaseCommand):
    help = 'Genera datos de prueba realistas para revisar el ciclo completo de vacantes y la suite de reportería.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            default=True,
            help='Borra y regenera limpiamente todos los datos demo (por defecto True).'
        )
        parser.add_argument(
            '--no-reset',
            dest='reset',
            action='store_false',
            help='No borra los registros previos antes de sembrar.'
        )

    def handle(self, *args, **options):
        reset = options.get('reset', True)
        if reset:
            self.stdout.write("Limpiando registros demo anteriores...")
            RegistroActividad.objects.all().delete()
            Proceso.objects.all().delete()
            Candidato.objects.all().delete()
            PerfilDePuesto.objects.all().delete()
            Puesto.objects.all().delete()
            Aviso.objects.all().delete()

        self.stdout.write("Creando roles, usuarios y datos demo...")

        # 1. GRUPOS Y ROLES
        grupos_nombres = [
            'Gerentes Operativos',
            'Gerentes de Capital Humano',
            'Gerente General de Marca',
            'Asesoras'
        ]
        grupos = {}
        for g_nom in grupos_nombres:
            grp, _ = Group.objects.get_or_create(name=g_nom)
            grupos[g_nom] = grp

        # 2. MARCAS
        marcas_nombres = ['Toyota Premier', 'Honda Premier', 'Hyundai Premier', 'Kia Premier', 'Chevrolet Premier']
        marcas = {}
        for m_nom in marcas_nombres:
            m, _ = Marca.objects.get_or_create(nombre=m_nom)
            marcas[m_nom] = m

        # 3. USUARIOS CON CONTRASEÑA "password123"
        def crear_usuario(username, email, first, last, group_name=None, is_staff=False, is_super=False, marcas_list=None):
            user, created = User.objects.get_or_create(username=username, defaults={'email': email})
            user.first_name = first
            user.last_name = last
            user.is_staff = is_staff
            user.is_superuser = is_super
            user.set_password('password123')
            user.save()
            if group_name and group_name in grupos:
                user.groups.add(grupos[group_name])
            if marcas_list and hasattr(user, 'perfilusuario'):
                user.perfilusuario.marcas.set(marcas_list)
            return user

        # Actualizar o crear jorge.guzman
        jg = User.objects.filter(username='jorge.guzman').first()
        if jg:
            jg.set_password('password123')
            jg.is_staff = True
            jg.is_superuser = True
            jg.first_name = 'Jorge'
            jg.last_name = 'Guzmán'
            jg.save()
        else:
            jg = crear_usuario('jorge.guzman', 'jorge@gmail.com', 'Jorge', 'Guzmán', is_staff=True, is_super=True)

        u_go = crear_usuario('gerente.operativo', 'operativo@premier.com', 'Roberto', 'Mendoza', 'Gerentes Operativos')
        u_gm = crear_usuario('gerente.marca', 'gm.toyota@premier.com', 'Carlos', 'Villanueva', 'Gerente General de Marca', marcas_list=[marcas['Toyota Premier'], marcas['Honda Premier']])
        u_ch = crear_usuario('gerente.ch', 'ch.director@premier.com', 'Patricia', 'Aréchiga', 'Gerentes de Capital Humano', is_staff=True)
        u_as1 = crear_usuario('asesora.arely', 'arely.trujillo@premier.com', 'Arely', 'Trujillo', 'Asesoras')
        u_as2 = crear_usuario('asesora.sofia', 'sofia.navarro@premier.com', 'Sofía', 'Navarro', 'Asesoras')

        # 4. PUESTOS DE CATÁLOGO
        def get_puesto_cat(nom):
            obj, _ = CatalogoPuesto.objects.get_or_create(nombre=nom.strip())
            return obj

        p_ventas = get_puesto_cat('Asesor(a) de ventas')
        p_servicio = get_puesto_cat('Asesor de servicio')
        p_diagnostico = get_puesto_cat('Técnico en Diagnóstico')
        p_hojalatero = get_puesto_cat('Hojalatero')
        p_contable = get_puesto_cat('Auxiliar contable')
        p_mostrador = get_puesto_cat('Vendedor de Mostrador')
        p_chofer = get_puesto_cat('Chofer/Almacenisa')
        p_gte_ventas = get_puesto_cat('Gerente de ventas')

        # 5. REQUISICIONES / PUESTOS EN DIFERENTES ETAPAS
        ahora = timezone.now()

        # VACANTE 1: 1. En Aprobación GM (Fase 1)
        p1 = Puesto.objects.create(
            titulo=p_ventas,
            marca=marcas['Toyota Premier'],
            agencia='Toyota Culiacán Aeropuerto',
            ciudad='CUL',
            area='VTAS',
            cantidad_vacantes=1,
            solicitado_por=u_go,
            nombre_jefe_inmediato='Roberto Mendoza',
            puesto_jefe_inmediato='Gerente de Ventas Nuevos',
            motivo_requisicion='ROT',
            reemplaza_a='Edgar Beltrán',
            objetivo_puesto='Lograr metas mensuales de venta y atención a clientes de piso y leads digitales.',
            funciones_puesto='1. Prospección de clientes\n2. Realización de pruebas de manejo\n3. Elaboración de cotizaciones\n4. Seguimiento postventa\n5. Entrega de unidades',
            indicador_puesto='Venta mínima de 8 unidades mensuales',
            experiencia_minima=2,
            carrera_sugerida='Mercadotecnia, Administración o afín',
            horario='Lunes a Viernes 8:30 - 18:30, Sábados 9:00 - 14:00',
            sueldo_base=Decimal('10000.00'),
            esquema_comisiones='Comisiones por unidad facturada y bonos por financiamiento F&I.',
            estatus_autorizacion=Puesto.EstatusAutorizacion.PENDIENTE,
            fecha_solicitud=ahora - timedelta(days=2),
            esta_abierto=False
        )

        # VACANTE 2: 1. En Aprobación Dirección (Fase 2)
        p2 = Puesto.objects.create(
            titulo=p_servicio,
            marca=marcas['Honda Premier'],
            agencia='Honda Mazatlán Marina',
            ciudad='MZT',
            area='SERV',
            cantidad_vacantes=1,
            solicitado_por=u_go,
            nombre_jefe_inmediato='Marcos Quintero',
            puesto_jefe_inmediato='Gerente de Servicio',
            motivo_requisicion='ROT',
            objetivo_puesto='Recepción de unidades, asesoría técnica de mantenimiento y entrega a clientes.',
            funciones_puesto='1. Recepción en rampa\n2. Presupuestos y órdenes de servicio\n3. Seguimiento con taller\n4. Entrega de vehículo\n5. Encuestas CSI',
            indicador_puesto='Índice de satisfacción de servicio CSI >= 94%',
            experiencia_minima=1,
            horario='Lunes a Viernes 8:00 - 18:00',
            sueldo_base=Decimal('12000.00'),
            estatus_autorizacion=Puesto.EstatusAutorizacion.PENDIENTE_DIR,
            aprobado_por_gerente_marca=u_gm,
            fecha_aprobacion_gerente_marca=ahora - timedelta(days=1),
            fecha_solicitud=ahora - timedelta(days=3),
            esta_abierto=False
        )

        # VACANTE 3: 2. Por Asignar Asesora (Autorizada pendiente de mesa de RH)
        p3 = Puesto.objects.create(
            titulo=p_diagnostico,
            marca=marcas['Hyundai Premier'],
            agencia='Hyundai Los Mochis Centro',
            ciudad='LMM',
            area='SERV',
            cantidad_vacantes=1,
            solicitado_por=u_go,
            nombre_jefe_inmediato='Ignacio Valenzuela',
            puesto_jefe_inmediato='Jefe de Taller',
            motivo_requisicion='INC',
            objetivo_puesto='Diagnóstico electrónico y mecánico especializado en escáner de marca.',
            funciones_puesto='1. Diagnóstico de fallas complejas\n2. Calibración de módulos\n3. Boletines de servicio\n4. Pruebas de ruta\n5. Soporte a mecánicos',
            indicador_puesto='Efectividad de reparación a la primera (Fix-it-Right) >= 96%',
            experiencia_minima=3,
            horario='Lunes a Viernes 8:00 - 18:00',
            sueldo_base=Decimal('16000.00'),
            estatus_autorizacion=Puesto.EstatusAutorizacion.AUTORIZADO,
            aprobado_por_gerente_marca=u_gm,
            fecha_aprobacion_gerente_marca=ahora - timedelta(days=4),
            aprobado_por_director=u_ch,
            fecha_aprobacion_director=ahora - timedelta(days=3),
            fecha_solicitud=ahora - timedelta(days=5),
            esta_abierto=True,
            asesora_encargada=None
        )

        # VACANTE 4: 3. Por Definir Perfil (Asignada a asesora pero sin perfil detallado)
        p4 = Puesto.objects.create(
            titulo=p_contable,
            marca=marcas['Kia Premier'],
            agencia='Kia Tijuana Río',
            ciudad='TIJ',
            area='ADM',
            cantidad_vacantes=1,
            solicitado_por=u_go,
            nombre_jefe_inmediato='Claudia Lizárraga',
            puesto_jefe_inmediato='Contadora General',
            motivo_requisicion='ROT',
            objetivo_puesto='Registro contable, conciliaciones bancarias y pólizas de egreso.',
            funciones_puesto='1. Conciliaciones bancarias\n2. Pólizas contables\n3. Cuentas por pagar\n4. Archivo fiscal\n5. Cierre mensual',
            indicador_puesto='Entrega de pólizas y conciliaciones antes del día 5 de cada mes',
            experiencia_minima=1,
            carrera_sugerida='Contaduría Pública',
            horario='Lunes a Viernes 9:00 - 18:00',
            sueldo_base=Decimal('13500.00'),
            estatus_autorizacion=Puesto.EstatusAutorizacion.AUTORIZADO,
            aprobado_por_gerente_marca=u_gm,
            aprobado_por_director=u_ch,
            fecha_solicitud=ahora - timedelta(days=4),
            esta_abierto=True,
            asesora_encargada=u_as1
        )

        # VACANTE 5: 4. En Búsqueda (Perfil listo, aún sin candidatos asignados)
        p5 = Puesto.objects.create(
            titulo=p_mostrador,
            marca=marcas['Toyota Premier'],
            agencia='Toyota Culiacán Tres Ríos',
            ciudad='CUL',
            area='REF',
            cantidad_vacantes=1,
            solicitado_por=u_go,
            nombre_jefe_inmediato='Jaime Gastélum',
            puesto_jefe_inmediato='Gerente de Refacciones',
            motivo_requisicion='ROT',
            objetivo_puesto='Venta y cotización de refacciones originales a mostrador y talleres externos.',
            funciones_puesto='1. Atención en mostrador\n2. Catálogo electrónico EPC\n3. Facturación de partes\n4. Inventario cíclico\n5. Pedidos de urgencia',
            indicador_puesto='Cumplimiento de presupuesto de venta de refacciones al 100%',
            experiencia_minima=1,
            horario='Lunes a Sábado',
            sueldo_base=Decimal('11000.00'),
            estatus_autorizacion=Puesto.EstatusAutorizacion.AUTORIZADO,
            fecha_solicitud=ahora - timedelta(days=6),
            esta_abierto=True,
            asesora_encargada=u_as1
        )
        PerfilDePuesto.objects.create(
            puesto=p5,
            rango_edad='22-38',
            preferencia_sexo='I',
            area_experiencia_enfoque='VTAS',
            importancia_apariencia='BAJA',
            feedback_anterior='Buscamos alguien proactivo y ordenado.',
            requiere_licencia='SI',
            creado_por=u_as1
        )

        # VACANTE 6: 5. En Filtros y Evaluaciones (Psicometría / Integridad)
        p6 = Puesto.objects.create(
            titulo=p_hojalatero,
            marca=marcas['Chevrolet Premier'],
            agencia='Chevrolet Hermosillo Kino',
            ciudad='HMO',
            area='SERV',
            cantidad_vacantes=1,
            solicitado_por=u_go,
            nombre_jefe_inmediato='Ernesto Barajas',
            puesto_jefe_inmediato='Jefe de Taller HyP',
            motivo_requisicion='ROT',
            objetivo_puesto='Enderezado y laminado de carrocerías automotrices siniestradas.',
            funciones_puesto='1. Desarmado y armado\n2. Cuadratura en banco\n3. Soldadura microalambre\n4. Hojalatería fina\n5. Calidad de terminados',
            indicador_puesto='Horas producidas semanales >= 45h',
            experiencia_minima=2,
            horario='Lunes a Viernes 8:00 - 18:00, Sábados 8:00 - 13:00',
            sueldo_base=Decimal('14000.00'),
            estatus_autorizacion=Puesto.EstatusAutorizacion.AUTORIZADO,
            fecha_solicitud=ahora - timedelta(days=8),
            esta_abierto=True,
            asesora_encargada=u_as2
        )
        PerfilDePuesto.objects.create(
            puesto=p6,
            rango_edad='25-48',
            preferencia_sexo='I',
            area_experiencia_enfoque='OPE',
            importancia_apariencia='BAJA',
            feedback_anterior='Experiencia en banco de estiraje.',
            requiere_licencia='SI',
            creado_por=u_as2
        )

        # Candidatos para Vacante 6
        c1 = Candidato.objects.create(
            nombres='Mateo', apellidos='Morales Castro', email='mateo.morales@gmail.com', telefono='6621458970',
            nivel_educativo='TEC', años_de_experiencia=3, ultimo_puesto='Laminador Jr', ultima_empresa='Taller Los Ángeles',
            puesto_de_interes=p6
        )
        Proceso.objects.create(candidato=c1, puesto=p6, asesora_asignada=u_as2, estatus_proceso=Proceso.Estatus.INTEGRIDAD, retroalimentacion='En espera de resultados de examen de integridad.')

        c2 = Candidato.objects.create(
            nombres='Fernando', apellidos='Ruiz Bernal', email='fernando.ruiz@hotmail.com', telefono='6622894512',
            nivel_educativo='TEC', años_de_experiencia=4, ultimo_puesto='Hojalatero', ultima_empresa='Carrocerías del Noroeste',
            puesto_de_interes=p6
        )
        Proceso.objects.create(candidato=c2, puesto=p6, asesora_asignada=u_as2, estatus_proceso=Proceso.Estatus.PSICOMETRICOS, retroalimentacion='Examen psicométrico programado para hoy.')

        # VACANTE 7: 6. En Entrevista con Jefe Inmediato (¡ESENCIAL PARA PRUEBA DE GERENTE OPERATIVO!)
        p7 = Puesto.objects.create(
            titulo=p_ventas,
            marca=marcas['Toyota Premier'],
            agencia='Toyota Culiacán Aeropuerto',
            ciudad='CUL',
            area='VTAS',
            cantidad_vacantes=1,
            solicitado_por=u_go,
            nombre_jefe_inmediato='Roberto Mendoza',
            puesto_jefe_inmediato='Gerente de Ventas Nuevos',
            motivo_requisicion='ROT',
            objetivo_puesto='Venta de autos nuevos en sala de exhibición y prospección externa.',
            funciones_puesto='1. Atención de clientes en piso\n2. Pruebas de manejo\n3. Cotización de crédito\n4. Cierre de ventas\n5. Entrega de unidad',
            indicador_puesto='Mínimo 8 unidades mensuales',
            experiencia_minima=2,
            horario='Lunes a Domingo con día de descanso entre semana',
            sueldo_base=Decimal('10000.00'),
            estatus_autorizacion=Puesto.EstatusAutorizacion.AUTORIZADO,
            fecha_solicitud=ahora - timedelta(days=9),
            esta_abierto=True,
            asesora_encargada=u_as1
        )
        PerfilDePuesto.objects.create(
            puesto=p7, rango_edad='24-38', preferencia_sexo='I', area_experiencia_enfoque='VTAS',
            importancia_apariencia='ALTA', justificacion_apariencia='Trato directo con clientes corporativos y de lujo.',
            feedback_anterior='Dinamismo y enfoque en metas.', requiere_licencia='SI', creado_por=u_as1
        )

        c_entrevista = Candidato.objects.create(
            nombres='Juan Pablo', apellidos='Rivas Beltrán', email='jp.rivas@gmail.com', telefono='6671895623',
            rfc='RIBJ940512AB3', fecha_nacimiento='1994-05-12', nivel_educativo='LIC', años_de_experiencia=4,
            ultimo_puesto='Ejecutivo Comercial Sr.', ultima_empresa='Distribuidora Nissan',
            puesto_de_interes=p7, habilidades='Negociación, Prospección en frío, CRM Salesforce, Cierre de ventas',
            expectativa_salarial=Decimal('22000.00')
        )
        proc_entrevista = Proceso.objects.create(
            candidato=c_entrevista, puesto=p7, asesora_asignada=u_as1,
            estatus_proceso=Proceso.Estatus.ENTREVISTA_JEFE,
            retroalimentacion='Superó psicometría (percentil 92) e integridad aprobada. Listo para entrevista técnica con Roberto Mendoza.'
        )
        RegistroActividad.objects.create(
            usuario=u_as1, accion="Postulación Registrada",
            tipo_objeto="Proceso", id_objeto=proc_entrevista.id,
            detalles="Candidato recibido e integrado al proceso de selección de Toyota Aeropuerto."
        )
        RegistroActividad.objects.create(
            usuario=u_as1, accion="Psicometría e Integridad Aprobada",
            tipo_objeto="Proceso", id_objeto=proc_entrevista.id,
            detalles="Pruebas psicométricas con percentil 92. Apto para perfil comercial."
        )
        RegistroActividad.objects.create(
            usuario=u_as1, accion="Envío a Entrevista con Jefe Inmediato",
            tipo_objeto="Proceso", id_objeto=proc_entrevista.id,
            detalles="Cita programada con Roberto Mendoza (Gerente de Ventas)."
        )

        # VACANTE 8: 7. En Trámites de Ingreso
        p8 = Puesto.objects.create(
            titulo=p_servicio,
            marca=marcas['Honda Premier'],
            agencia='Honda Mazatlán Marina',
            ciudad='MZT',
            area='SERV',
            cantidad_vacantes=1,
            solicitado_por=u_go,
            nombre_jefe_inmediato='Marcos Quintero',
            puesto_jefe_inmediato='Gerente de Servicio',
            motivo_requisicion='ROT',
            objetivo_puesto='Asesoría de servicio al cliente y seguimiento de taller.',
            funciones_puesto='1. Recepción\n2. Presupuesto\n3. Trámite de garantías\n4. Entrega',
            indicador_puesto='CSI >= 95%',
            experiencia_minima=2,
            horario='Lunes a Viernes',
            sueldo_base=Decimal('12500.00'),
            estatus_autorizacion=Puesto.EstatusAutorizacion.AUTORIZADO,
            fecha_solicitud=ahora - timedelta(days=12),
            esta_abierto=True,
            asesora_encargada=u_as2
        )
        PerfilDePuesto.objects.create(
            puesto=p8, rango_edad='25-40', preferencia_sexo='I', area_experiencia_enfoque='SERV',
            importancia_apariencia='ALTA', justificacion_apariencia='Atención al cliente en mostrador.',
            feedback_anterior='N/A', requiere_licencia='SI', creado_por=u_as2
        )
        c_tramite = Candidato.objects.create(
            nombres='Mariana', apellidos='Ochoa Lizárraga', email='mariana.ochoa@outlook.com', telefono='6699451230',
            nivel_educativo='LIC', años_de_experiencia=3, ultimo_puesto='Asesora de Servicio', ultima_empresa='Volkswagen Mazatlán',
            puesto_de_interes=p8
        )
        Proceso.objects.create(
            candidato=c_tramite, puesto=p8, asesora_asignada=u_as2,
            estatus_proceso=Proceso.Estatus.EXAMENES_MEDICOS,
            retroalimentacion='Entrevista aprobada por gerente. En proceso de exámenes de laboratorio.'
        )

        # VACANTE 9: Plazas Múltiples (3 plazas: 1 contratada, 1 en trámites, 1 pendiente de cubrir)
        p9 = Puesto.objects.create(
            titulo=p_ventas,
            marca=marcas['Toyota Premier'],
            agencia='Toyota Culiacán Tres Ríos',
            ciudad='CUL',
            area='VTAS',
            cantidad_vacantes=3,
            solicitado_por=u_go,
            nombre_jefe_inmediato='Roberto Mendoza',
            puesto_jefe_inmediato='Gerente de Ventas',
            motivo_requisicion='INC',
            objetivo_puesto='Expansión de equipo comercial para apertura de nuevo showroom.',
            funciones_puesto='Ventas, atención digital, cotizaciones.',
            indicador_puesto='Venta por asesor 8 autos',
            experiencia_minima=1,
            horario='Lunes a Sábado',
            sueldo_base=Decimal('10000.00'),
            estatus_autorizacion=Puesto.EstatusAutorizacion.AUTORIZADO,
            fecha_solicitud=ahora - timedelta(days=14),
            esta_abierto=True,
            asesora_encargada=u_as1
        )
        PerfilDePuesto.objects.create(
            puesto=p9, rango_edad='23-35', preferencia_sexo='I', area_experiencia_enfoque='VTAS',
            importancia_apariencia='BAJA', feedback_anterior='Ganas de aprender y actitud.',
            requiere_licencia='SI', creado_por=u_as1
        )

        # Contratado 1 (plaza 1 de 3)
        c_hired = Candidato.objects.create(
            nombres='Roberto', apellidos='Beltrán Corona', email='roberto.beltran@gmail.com', telefono='6671239874',
            nivel_educativo='LIC', años_de_experiencia=3, ultimo_puesto='Vendedor Autos', ultima_empresa='Ford Culiacán'
        )
        Proceso.objects.create(
            candidato=c_hired, puesto=p9, asesora_asignada=u_as1,
            estatus_proceso=Proceso.Estatus.CONTRATADO_CERRADO,
            retroalimentacion='¡Contratado exitosamente! Ingreso día 1 del mes.'
        )

        # Candidato en firma (plaza 2)
        c_firma = Candidato.objects.create(
            nombres='Ana Lucía', apellidos='Torres Espinoza', email='ana.torres@gmail.com', telefono='6679541289',
            nivel_educativo='LIC', años_de_experiencia=2, ultimo_puesto='Asesora Comercial', ultima_empresa='KIA Culiacán'
        )
        Proceso.objects.create(
            candidato=c_firma, puesto=p9, asesora_asignada=u_as1,
            estatus_proceso=Proceso.Estatus.FIRMA_CONTRATO,
            retroalimentacion='Expediente completo. Firma programada para el viernes.'
        )

        # VACANTE 10: Vacante VENCIDA (🔴 Fuera de SLA - Chofer/Almacenista meta: 12d, lleva 19d)
        p10 = Puesto.objects.create(
            titulo=p_chofer,
            marca=marcas['Toyota Premier'],
            agencia='Toyota Culiacán Aeropuerto',
            ciudad='CUL',
            area='REF',
            cantidad_vacantes=1,
            solicitado_por=u_go,
            nombre_jefe_inmediato='Jaime Gastélum',
            puesto_jefe_inmediato='Gerente de Refacciones',
            motivo_requisicion='ROT',
            objetivo_puesto='Traslado de partes y refacciones entre sucursales y clientes mayoreo.',
            funciones_puesto='1. Manejo de camioneta de 3.5 tons\n2. Carga y descarga\n3. Entrega con remisión\n4. Inventarios',
            indicador_puesto='Entregas a tiempo 100%',
            experiencia_minima=2,
            horario='Lunes a Viernes 8:30 - 18:30',
            sueldo_base=Decimal('9500.00'),
            estatus_autorizacion=Puesto.EstatusAutorizacion.AUTORIZADO,
            fecha_solicitud=ahora - timedelta(days=19),
            esta_abierto=True,
            asesora_encargada=u_as1
        )
        PerfilDePuesto.objects.create(
            puesto=p10, rango_edad='25-45', preferencia_sexo='H', motivo_preferencia_sexo='DES',
            area_experiencia_enfoque='OPE', importancia_apariencia='BAJA',
            feedback_anterior='Chofer responsable con licencia de chofer vigente.',
            requiere_licencia='SI', creado_por=u_as1
        )

        # VACANTE 11: Vacante POR VENCER (🟡 Le faltan 2 días para el SLA de 20 días)
        p11 = Puesto.objects.create(
            titulo=p_contable,
            marca=marcas['Kia Premier'],
            agencia='Kia Tijuana Río',
            ciudad='TIJ',
            area='ADM',
            cantidad_vacantes=1,
            solicitado_por=u_go,
            nombre_jefe_inmediato='Claudia Lizárraga',
            puesto_jefe_inmediato='Contadora General',
            motivo_requisicion='ROT',
            objetivo_puesto='Apoyo en auditorías internas y registros fiscales.',
            funciones_puesto='Contabilidad, facturación, conciliaciones.',
            indicador_puesto='Puntualidad en declaraciones',
            experiencia_minima=2,
            horario='Lunes a Viernes',
            sueldo_base=Decimal('14000.00'),
            estatus_autorizacion=Puesto.EstatusAutorizacion.AUTORIZADO,
            fecha_solicitud=ahora - timedelta(days=18),
            esta_abierto=True,
            asesora_encargada=u_as2
        )
        PerfilDePuesto.objects.create(
            puesto=p11, rango_edad='24-38', preferencia_sexo='I', area_experiencia_enfoque='ADM',
            importancia_apariencia='BAJA', feedback_anterior='Conocimientos de SAT y Excel.',
            requiere_licencia='NO', creado_por=u_as2
        )

        # VACANTE 12: Vacante CUBIERTA AL 100% (⚪ Cerrada)
        p12 = Puesto.objects.create(
            titulo=p_servicio,
            marca=marcas['Toyota Premier'],
            agencia='Toyota Culiacán Tres Ríos',
            ciudad='CUL',
            area='SERV',
            cantidad_vacantes=1,
            solicitado_por=u_go,
            nombre_jefe_inmediato='Jesús Valenzuela',
            puesto_jefe_inmediato='Gerente de Servicio',
            motivo_requisicion='ROT',
            objetivo_puesto='Asesoría técnica de servicio.',
            funciones_puesto='Recepción de autos, cotización, seguimiento.',
            indicador_puesto='Satisfacción CSI 95%',
            experiencia_minima=2,
            horario='Lunes a Viernes',
            sueldo_base=Decimal('13000.00'),
            estatus_autorizacion=Puesto.EstatusAutorizacion.AUTORIZADO,
            fecha_solicitud=ahora - timedelta(days=25),
            esta_abierto=False,
            asesora_encargada=u_as1
        )
        PerfilDePuesto.objects.create(
            puesto=p12, rango_edad='25-40', preferencia_sexo='I', area_experiencia_enfoque='SERV',
            importancia_apariencia='ALTA', justificacion_apariencia='Imagen de marca en sala de servicio.',
            feedback_anterior='N/A', requiere_licencia='SI', creado_por=u_as1
        )
        c_closed = Candidato.objects.create(
            nombres='Carlos Mario', apellidos='Gastélum Urías', email='carlos.gastelum@gmail.com', telefono='6677894512',
            nivel_educativo='LIC', años_de_experiencia=4, ultimo_puesto='Asesor de Servicio', ultima_empresa='Mazda Culiacán'
        )
        Proceso.objects.create(
            candidato=c_closed, puesto=p12, asesora_asignada=u_as1,
            estatus_proceso=Proceso.Estatus.CONTRATADO_CERRADO,
            fecha_inicio_etapa=ahora - timedelta(days=8),
            retroalimentacion='Candidato contratado. Vacante cerrada formalmente con 17 días de cobertura.'
        )

        # VACANTE 13: Vacante RECHAZADA CON MOTIVO FORMAL
        p13 = Puesto.objects.create(
            titulo=p_gte_ventas,
            marca=marcas['Chevrolet Premier'],
            agencia='Chevrolet Hermosillo Kino',
            ciudad='HMO',
            area='VTAS',
            cantidad_vacantes=1,
            solicitado_por=u_go,
            nombre_jefe_inmediato='Gerardo Leyva',
            puesto_jefe_inmediato='Director Comercial',
            motivo_requisicion='INC',
            objetivo_puesto='Dirección de fuerza de ventas seminuevos.',
            funciones_puesto='Liderazgo comercial, inventarios, fijación de precios.',
            indicador_puesto='Margen bruto por unidad y volumen mensual',
            experiencia_minima=5,
            horario='Tiempo Completo',
            sueldo_base=Decimal('35000.00'),
            estatus_autorizacion=Puesto.EstatusAutorizacion.RECHAZADO,
            motivo_rechazo='Presupuesto de plantilla para nuevas gerencias congelado por Dirección General para el segundo semestre.',
            aprobado_por_director=u_ch,
            fecha_aprobacion_director=ahora - timedelta(days=5),
            fecha_solicitud=ahora - timedelta(days=7),
            esta_abierto=False
        )

        # 6. CANDIDATOS ADICIONALES LIBRES EN BOLSA DE TRABAJO
        candidatos_bolsa = [
            ("Guillermo", "Paredes Ruelas", "guillermo.paredes@gmail.com", "6671203040", "LIC", 3, "Vendedor de Flotillas", "Ford", "Ventas corporativas, B2B, Licitaciones"),
            ("Valeria", "Montoya Serna", "valeria.montoya@hotmail.com", "6678901234", "LIC", 2, "Auxiliar Administrativo", "Agroindustrias", "SAP, Excel intermedio, Facturación 4.0"),
            ("Héctor", "Camacho Félix", "hector.camacho@yahoo.com", "6691456789", "TEC", 5, "Mecánico Automotriz", "Taller Multimarca", "Frenos, Suspensión, Ajuste de motor, Escáner Launch"),
            ("Andrea", "Bojórquez Castro", "andrea.bojorquez@gmail.com", "6681234567", "LIC", 1, "Recepcionista / Hostess", "Hotel Fiesta", "Atención a clientes, Conmutador, Excelente presencia"),
            ("Ricardo", "Zamudio Meza", "ricardo.zamudio@gmail.com", "6647890123", "SEC", 4, "Lavador y Detallador", "Auto Spa Culiacán", "Pulido, Encerado, Detallado de interiores, Manejo estándar"),
            ("Daniela", "Salazar Peñuelas", "daniela.salazar@outlook.com", "6623456789", "LIC", 4, "Coordinadora de Mercadotecnia", "Agencia Digital", "Meta Ads, Google Ads, Diseño Canva, Estrategia Leads")
        ]
        for nom, ape, em, tel, niv, exp, ult_p, ult_e, hab in candidatos_bolsa:
            Candidato.objects.get_or_create(
                email=em,
                defaults={
                    'nombres': nom, 'apellidos': ape, 'telefono': tel, 'nivel_educativo': niv,
                    'años_de_experiencia': exp, 'ultimo_puesto': ult_p, 'ultima_empresa': ult_e,
                    'habilidades': hab, 'expectativa_salarial': Decimal('15000.00')
                }
            )

        # 7. AVISOS GENERALES DEL DASHBOARD
        Aviso.objects.get_or_create(
            titulo='Nuevo Módulo de SLAs de Cobertura y Reportería 360°',
            defaults={
                'contenido': 'Se encuentra habilitada la nueva suite ejecutiva de reportería y Business Intelligence. Ahora puedes consultar el cumplimiento de metas por puesto (10, 12, 20, 25 y 30 días) y dar seguimiento puntual al embudo de cada vacante.',
                'creado_por': u_ch,
                'esta_activo': True
            }
        )
        Aviso.objects.get_or_create(
            titulo='Revisión de Candidatos en Entrevista con Jefe Inmediato',
            defaults={
                'contenido': 'Recordatorio a todos los Gerentes Operativos: favor de ingresar a su portal para revisar y retroalimentar a los candidatos en etapa de entrevista técnica.',
                'creado_por': u_ch,
                'esta_activo': True
            }
        )

        self.stdout.write(self.style.SUCCESS("¡Datos demo creados con éxito!"))
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write("USUARIOS GENERADOS PARA PRUEBAS (Contraseña: password123):")
        self.stdout.write(" - Superusuario / Admin:    jorge.guzman")
        self.stdout.write(" - Gerente Operativo:       gerente.operativo")
        self.stdout.write(" - Gerente General Marca:   gerente.marca (Toyota y Honda)")
        self.stdout.write(" - Gerente Capital Humano:  gerente.ch (Staff / Dirección)")
        self.stdout.write(" - Asesoras Reclutamiento:  asesora.arely | asesora.sofia")
        self.stdout.write(self.style.SUCCESS("=" * 60))
