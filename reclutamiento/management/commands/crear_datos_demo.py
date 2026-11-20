from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User, Group
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from reclutamiento.models import (
    Marca, CatalogoPuesto, Puesto, Candidato, Proceso, Aviso, RegistroActividad
)

class Command(BaseCommand):
    help = 'Genera datos de prueba realistas para la herramienta exclusiva de RH en entornos de desarrollo.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            default=False,
            help='Borra y regenera limpiamente los datos demo de RH (por defecto False por seguridad).'
        )
        parser.add_argument(
            '--confirm-production-reset',
            action='store_true',
            default=False,
            help='Confirmación requerida si se ejecuta en entornos donde DEBUG=False.'
        )

    def handle(self, *args, **options):
        reset = options.get('reset', False)
        confirm_prod = options.get('confirm_production_reset', False)

        # Protección estricta contra borrado accidental en entornos de producción
        if not getattr(settings, 'DEBUG', False) and reset and not confirm_prod:
            raise CommandError(
                "SEGURIDAD: No se permite ejecutar --reset con DEBUG=False sin la bandera explícita --confirm-production-reset."
            )
        if reset:
            self.stdout.write("Limpiando registros demo anteriores...")
            RegistroActividad.objects.all().delete()
            Proceso.objects.all().delete()
            Candidato.objects.all().delete()
            Puesto.objects.all().delete()
            Aviso.objects.all().delete()

            # Eliminar usuarios y grupos externos legados
            User.objects.filter(username__in=['gerente.operativo', 'gerente.marca']).delete()
            Group.objects.filter(name__in=['Gerentes Operativos', 'Gerente General de Marca']).delete()

        self.stdout.write("Creando roles y equipo exclusivo de Capital Humano (RH)...")

        # 1. GRUPOS Y ROLES EXCLUSIVOS DE RH
        grupos_nombres = [
            'Gerentes de Capital Humano',
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

        # 3. USUARIOS PARA ACCESO RÁPIDO Y OPERACIÓN (Contraseña: admin)
        def crear_usuario_rh(username, email, first, last, group_name=None, is_staff=True, is_super=False):
            user, created = User.objects.get_or_create(username=username, defaults={'email': email})
            user.email = email
            user.first_name = first
            user.last_name = last
            user.is_staff = is_staff
            user.is_superuser = is_super
            user.set_password('admin')
            user.save()
            if group_name and group_name in grupos:
                user.groups.clear()
                user.groups.add(grupos[group_name])
            return user

        # Administrador / Superuser
        jg = User.objects.filter(username='jorge.guzman').first()
        if jg:
            jg.set_password('admin')
            jg.is_staff = True
            jg.is_superuser = True
            jg.first_name = 'Jorge'
            jg.last_name = 'Guzmán'
            jg.save()
        else:
            jg = crear_usuario_rh('jorge.guzman', 'jorge@gmail.com', 'Jorge', 'Guzmán', is_staff=True, is_super=True)

        # Gerente de RH
        u_ch = crear_usuario_rh('gerente.ch', 'ch.director@premier.com', 'Patricia', 'Aréchiga', 'Gerentes de Capital Humano', is_staff=True)

        # Roles operativos adicionales de acceso rápido
        crear_usuario_rh('gerente.operativo', 'roberto.mendoza@premier.com', 'Roberto', 'Mendoza', is_staff=True)
        crear_usuario_rh('gerente.marca', 'carlos.villanueva@premier.com', 'Carlos', 'Villanueva', is_staff=True)

        # Asesoras de Selección
        u_as1 = crear_usuario_rh('asesora.arely', 'arely.trujillo@premier.com', 'Arely', 'Trujillo', 'Asesoras', is_staff=True)
        u_as2 = crear_usuario_rh('asesora.sofia', 'sofia.navarro@premier.com', 'Sofía', 'Navarro', 'Asesoras', is_staff=True)

        # 4. CATÁLOGO DE PUESTOS
        def get_puesto_cat(nom, dias_meta=20):
            obj, _ = CatalogoPuesto.objects.get_or_create(nombre=nom.strip(), defaults={'dias_meta': dias_meta})
            return obj

        p_ventas = get_puesto_cat('Asesor(a) de ventas', 20)
        p_servicio = get_puesto_cat('Asesor de servicio', 20)
        p_diagnostico = get_puesto_cat('Técnico en Diagnóstico', 20)
        p_hojalatero = get_puesto_cat('Hojalatero', 12)
        p_contable = get_puesto_cat('Auxiliar contable', 20)
        p_mostrador = get_puesto_cat('Vendedor de Mostrador', 12)
        p_chofer = get_puesto_cat('Chofer/Almacenista', 12)

        ahora = timezone.now()

        # ==============================================================================
        # 5. VACANTES OPERADAS POR RH (Nacen autorizadas y activas directamente)
        # ==============================================================================

        # VACANTE 1: Activa en Selección Temprana (Filtros y Evaluaciones RH)
        p1 = Puesto.objects.create(
            titulo=p_ventas,
            marca=marcas['Toyota Premier'],
            agencia='Toyota Culiacán Aeropuerto',
            ciudad='CUL',
            area='VTAS',
            cantidad_vacantes=1,
            jefe_inmediato_nombre='Roberto Mendoza',
            jefe_inmediato_puesto='Gerente de Ventas Nuevos',
            nombre_jefe_inmediato='Roberto Mendoza',
            puesto_jefe_inmediato='Gerente de Ventas Nuevos',
            motivo_requisicion='ROT',
            reemplaza_a='Edgar Beltrán',
            objetivo_puesto='Lograr metas mensuales de venta y atención a clientes de piso y leads digitales.',
            funciones_puesto='1. Prospección de clientes\n2. Realización de pruebas de manejo\n3. Elaboración de cotizaciones',
            indicador_puesto='Venta mínima de 8 unidades mensuales',
            experiencia_minima=2,
            carrera_sugerida='Mercadotecnia, Administración o afín',
            horario='Lunes a Viernes 8:30 - 18:30, Sábados 9:00 - 14:00',
            sueldo_base=Decimal('10000.00'),
            esquema_comisiones='Comisiones por unidad facturada y bonos por financiamiento F&I.',
            estatus_autorizacion=Puesto.EstatusAutorizacion.AUTORIZADO,
            esta_abierto=True,
            dias_meta=20,
            fecha_solicitud=ahora - timedelta(days=6),
            asesora_encargada=u_as1,
            comentarios="Vacante asignada para reclutamiento activo. Buenas referencias del perfil solicitado."
        )

        # Candidato en CONTACTO
        c1 = Candidato.objects.create(
            nombres='Mateo', apellidos='Morales Castro', email='mateo.morales@gmail.com', telefono='6621458970',
            ciudad_residencia='CUL', nivel_educativo='LIC', años_de_experiencia=2, ultimo_puesto='Vendedor Jr',
            ultima_empresa='Autos de Culiacán', puesto_de_interes=p1
        )
        Proceso.objects.create(
            candidato=c1, puesto=p1, asesora_asignada=u_as1,
            estatus_proceso=Proceso.Estatus.CONTACTO,
            fecha_inicio_etapa=ahora - timedelta(days=2),
            retroalimentacion='Contactado vía WhatsApp y llamada. Muy interesado en el puesto.'
        )

        # Candidato en PRUEBAS (Aprobado en Integridad y Óptimo en Pyxoom)
        c2 = Candidato.objects.create(
            nombres='Fernando', apellidos='Ruiz Bernal', email='fernando.ruiz@hotmail.com', telefono='6622894512',
            ciudad_residencia='CUL', nivel_educativo='LIC', años_de_experiencia=3, ultimo_puesto='Asesor Comercial',
            ultima_empresa='Grupo Sur', puesto_de_interes=p1
        )
        Proceso.objects.create(
            candidato=c2, puesto=p1, asesora_asignada=u_as1,
            estatus_proceso=Proceso.Estatus.PRUEBAS,
            fecha_inicio_etapa=ahora - timedelta(days=1),
            resultado_integridad=Proceso.ResultadoIntegridad.APROBADO,
            resultado_pyxoom=Proceso.ResultadoPyxoom.OPTIMO,
            retroalimentacion='Pruebas psicométricas completas. Resultados muy favorables para perfil comercial.'
        )

        # VACANTE 2: Cumplimiento de META BONO (Envió 3 candidatos a Entrevista con Jefe Inmediato dentro de plazo)
        p2 = Puesto.objects.create(
            titulo=p_servicio,
            marca=marcas['Honda Premier'],
            agencia='Honda Mazatlán Marina',
            ciudad='MZT',
            area='SERV',
            cantidad_vacantes=1,
            jefe_inmediato_nombre='Marcos Quintero',
            jefe_inmediato_puesto='Gerente de Servicio',
            nombre_jefe_inmediato='Marcos Quintero',
            puesto_jefe_inmediato='Gerente de Servicio',
            motivo_requisicion='ROT',
            objetivo_puesto='Recepción de unidades, asesoría técnica de mantenimiento y entrega a clientes.',
            sueldo_base=Decimal('12000.00'),
            estatus_autorizacion=Puesto.EstatusAutorizacion.AUTORIZADO,
            esta_abierto=True,
            dias_meta=20,
            fecha_solicitud=ahora - timedelta(days=10),
            asesora_encargada=u_as2,
            comentarios="Meta de bono alcanzada: 3 candidatos aptos enviados a entrevista con jefe dentro del plazo."
        )

        # 3 candidatos enviados a ENT_JF dentro del plazo para calificar bono
        for i, (nom, ape, mail, tel) in enumerate([
            ('Juan Pablo', 'Rivas Beltrán', 'jp.rivas@gmail.com', '6671895623'),
            ('Mariana', 'Ochoa Lizárraga', 'mariana.ochoa@outlook.com', '6699451230'),
            ('Gustavo', 'López Salazar', 'gustavo.lopez@gmail.com', '6691238945')
        ], 1):
            cand = Candidato.objects.create(
                nombres=nom, apellidos=ape, email=mail, telefono=tel,
                ciudad_residencia='MZT', nivel_educativo='LIC', años_de_experiencia=3,
                ultimo_puesto='Asesor de Servicio', ultima_empresa='Agencia Automotriz',
                puesto_de_interes=p2
            )
            # 2 en ENT_JF y 1 que ya avanzó a CONF_JF
            st = Proceso.Estatus.CONF_JF if i == 1 else Proceso.Estatus.ENT_JF
            Proceso.objects.create(
                candidato=cand, puesto=p2, asesora_asignada=u_as2,
                estatus_proceso=st,
                fecha_inicio_etapa=ahora - timedelta(days=7 - i),
                resultado_integridad=Proceso.ResultadoIntegridad.APROBADO,
                resultado_pyxoom=Proceso.ResultadoPyxoom.IDEAL,
                retroalimentacion=f'Candidato #{i} evaluado favorablemente y turnado a Marcos Quintero para entrevista física.'
            )

        # VACANTE 3: Con REINICIO DE SLA (Venció previamente y RH reinició conteo)
        p3 = Puesto.objects.create(
            titulo=p_diagnostico,
            marca=marcas['Hyundai Premier'],
            agencia='Hyundai Los Mochis Centro',
            ciudad='LMM',
            area='SERV',
            cantidad_vacantes=1,
            jefe_inmediato_nombre='Ignacio Valenzuela',
            jefe_inmediato_puesto='Jefe de Taller',
            nombre_jefe_inmediato='Ignacio Valenzuela',
            puesto_jefe_inmediato='Jefe de Taller',
            motivo_requisicion='INC',
            sueldo_base=Decimal('16000.00'),
            estatus_autorizacion=Puesto.EstatusAutorizacion.AUTORIZADO,
            esta_abierto=True,
            dias_meta=20,
            fecha_solicitud=ahora - timedelta(days=28),
            fecha_inicio_sla_custom=ahora - timedelta(days=4), # Reiniciado hace 4 días
            numero_reinicios=1,
            asesora_encargada=u_as1,
            comentarios="Reinicio de SLA #1 autorizado por Dirección CH: Reajuste salarial en tabulador para atraer técnicos con certificación máster."
        )

        c_diag = Candidato.objects.create(
            nombres='Ernesto', apellidos='Barajas Parra', email='ernesto.barajas@hotmail.com', telefono='6688123456',
            ciudad_residencia='LMM', nivel_educativo='TEC', años_de_experiencia=5,
            ultimo_puesto='Técnico Automotriz', ultima_empresa='Taller Especializado Hyundai',
            puesto_de_interes=p3
        )
        Proceso.objects.create(
            candidato=c_diag, puesto=p3, asesora_asignada=u_as1,
            estatus_proceso=Proceso.Estatus.ENT_CH,
            fecha_inicio_etapa=ahora - timedelta(days=2),
            resultado_integridad=Proceso.ResultadoIntegridad.APROBADO,
            resultado_pyxoom=Proceso.ResultadoPyxoom.OPTIMO,
            retroalimentacion='Excelente perfil técnico. Turnado a entrevista con RH.'
        )

        # VACANTE 4: Caso con CANDIDATO ESTANCADO (Lleva más de 30 días en la misma etapa)
        p4 = Puesto.objects.create(
            titulo=p_contable,
            marca=marcas['Kia Premier'],
            agencia='Kia Tijuana Río',
            ciudad='TIJ',
            area='ADM',
            cantidad_vacantes=1,
            jefe_inmediato_nombre='Claudia Lizárraga',
            jefe_inmediato_puesto='Contadora General',
            nombre_jefe_inmediato='Claudia Lizárraga',
            puesto_jefe_inmediato='Contadora General',
            motivo_requisicion='ROT',
            sueldo_base=Decimal('13500.00'),
            estatus_autorizacion=Puesto.EstatusAutorizacion.AUTORIZADO,
            esta_abierto=True,
            dias_meta=20,
            fecha_solicitud=ahora - timedelta(days=36),
            asesora_encargada=u_as2,
            comentarios="Alerta operativa: proceso detenido a la espera de confirmación de documentos."
        )

        c_estancado = Candidato.objects.create(
            nombres='Lucía', apellidos='Alvarado Méndez', email='lucia.alvarado@gmail.com', telefono='6641238974',
            ciudad_residencia='TIJ', nivel_educativo='LIC', años_de_experiencia=2,
            ultimo_puesto='Auxiliar Contable', ultima_empresa='Despacho Fiscal Tijuana',
            puesto_de_interes=p4
        )
        # 34 días en etapa DOCS -> esta_estancado = True
        Proceso.objects.create(
            candidato=c_estancado, puesto=p4, asesora_asignada=u_as2,
            estatus_proceso=Proceso.Estatus.DOCS,
            fecha_inicio_etapa=ahora - timedelta(days=34),
            resultado_integridad=Proceso.ResultadoIntegridad.APROBADO,
            resultado_pyxoom=Proceso.ResultadoPyxoom.BAJO,
            retroalimentacion='Pendiente constancia fiscal y carta de no antecedentes penales. Candidata no responde mensajes.'
        )

        # VACANTE 5: En Trámites Finales de Ingreso (MEDICO / INGRESO_PROG)
        p5 = Puesto.objects.create(
            titulo=p_mostrador,
            marca=marcas['Toyota Premier'],
            agencia='Toyota Culiacán Tres Ríos',
            ciudad='CUL',
            area='REF',
            cantidad_vacantes=1,
            jefe_inmediato_nombre='Jaime Gastélum',
            jefe_inmediato_puesto='Gerente de Refacciones',
            nombre_jefe_inmediato='Jaime Gastélum',
            puesto_jefe_inmediato='Gerente de Refacciones',
            motivo_requisicion='ROT',
            sueldo_base=Decimal('11000.00'),
            estatus_autorizacion=Puesto.EstatusAutorizacion.AUTORIZADO,
            esta_abierto=True,
            dias_meta=12,
            fecha_solicitud=ahora - timedelta(days=8),
            asesora_encargada=u_as1,
            comentarios="Candidato aprobado por jefe de refacciones. En trámite de alta e ingreso."
        )

        c_prog = Candidato.objects.create(
            nombres='David', apellidos='Zazueta Rangel', email='david.zazueta@gmail.com', telefono='6672345678',
            ciudad_residencia='CUL', nivel_educativo='TEC', años_de_experiencia=3,
            ultimo_puesto='Ventas Mostrador', ultima_empresa='Refaccionaria del Norte',
            puesto_de_interes=p5
        )
        Proceso.objects.create(
            candidato=c_prog, puesto=p5, asesora_asignada=u_as1,
            estatus_proceso=Proceso.Estatus.INGRESO_PROG,
            fecha_inicio_etapa=ahora - timedelta(days=1),
            resultado_integridad=Proceso.ResultadoIntegridad.APROBADO,
            resultado_pyxoom=Proceso.ResultadoPyxoom.OPTIMO,
            retroalimentacion='Examen médico apto. Programado para inducción corporativa y cursos en Universidad Premier el lunes.'
        )

        # VACANTE 6: CUBIERTA / CERRADA (100% de plazas cubiertas con candidato contratado)
        p6 = Puesto.objects.create(
            titulo=p_chofer,
            marca=marcas['Toyota Premier'],
            agencia='Toyota Culiacán Aeropuerto',
            ciudad='CUL',
            area='REF',
            cantidad_vacantes=1,
            jefe_inmediato_nombre='Jaime Gastélum',
            jefe_inmediato_puesto='Gerente de Refacciones',
            nombre_jefe_inmediato='Jaime Gastélum',
            puesto_jefe_inmediato='Gerente de Refacciones',
            motivo_requisicion='ROT',
            sueldo_base=Decimal('9500.00'),
            estatus_autorizacion=Puesto.EstatusAutorizacion.AUTORIZADO,
            esta_abierto=False, # Vacante cerrada
            dias_meta=12,
            fecha_solicitud=ahora - timedelta(days=15),
            asesora_encargada=u_as1,
            comentarios="Vacante cerrada con éxito en 10 días hábiles. Cumplió meta de bono."
        )

        c_contratado = Candidato.objects.create(
            nombres='Carlos Mario', apellidos='Gastélum Urías', email='carlos.gastelum@gmail.com', telefono='6677894512',
            ciudad_residencia='CUL', nivel_educativo='SEC', años_de_experiencia=4,
            ultimo_puesto='Chofer Repartidor', ultima_empresa='Paquetería Express',
            puesto_de_interes=p6
        )
        Proceso.objects.create(
            candidato=c_contratado, puesto=p6, asesora_asignada=u_as1,
            estatus_proceso=Proceso.Estatus.CONTRATADO,
            fecha_inicio_etapa=ahora - timedelta(days=5),
            resultado_integridad=Proceso.ResultadoIntegridad.APROBADO,
            resultado_pyxoom=Proceso.ResultadoPyxoom.OPTIMO,
            retroalimentacion='Contratado e ingresado a nómina. Plaza cerrada exitosamente.'
        )

        # VACANTE 7: Procesos con Descartes y Abandonos (Terminales de RH)
        p7 = Puesto.objects.create(
            titulo=p_hojalatero,
            marca=marcas['Chevrolet Premier'],
            agencia='Chevrolet Hermosillo Kino',
            ciudad='HMO',
            area='SERV',
            cantidad_vacantes=1,
            jefe_inmediato_nombre='Ernesto Barajas',
            jefe_inmediato_puesto='Jefe de Taller HyP',
            nombre_jefe_inmediato='Ernesto Barajas',
            puesto_jefe_inmediato='Jefe de Taller HyP',
            motivo_requisicion='ROT',
            sueldo_base=Decimal('14000.00'),
            estatus_autorizacion=Puesto.EstatusAutorizacion.AUTORIZADO,
            esta_abierto=True,
            dias_meta=12,
            fecha_solicitud=ahora - timedelta(days=9),
            asesora_encargada=u_as2
        )

        # Descartado por No Aprobar Integridad
        c_descartado1 = Candidato.objects.create(
            nombres='Ramón', apellidos='Valdez Solís', email='ramon.valdez@gmail.com', telefono='6629988776',
            ciudad_residencia='HMO', nivel_educativo='TEC', años_de_experiencia=1,
            ultimo_puesto='Hojalatero', ultima_empresa='Taller Independiente',
            puesto_de_interes=p7
        )
        Proceso.objects.create(
            candidato=c_descartado1, puesto=p7, asesora_asignada=u_as2,
            estatus_proceso=Proceso.Estatus.NO_PRUEBAS,
            fecha_inicio_etapa=ahora - timedelta(days=3),
            resultado_integridad=Proceso.ResultadoIntegridad.NO_APROBADO,
            resultado_pyxoom=Proceso.ResultadoPyxoom.REPROBADO,
            motivo_descarte='No aprobó evaluación de integridad corporativa.',
            retroalimentacion='Resultado no aprobatorio en plataforma de integridad. Proceso descartado.'
        )

        # Descartado por Perfil (DESCARTADO_CH)
        c_descartado2 = Candidato.objects.create(
            nombres='Sergio', apellidos='Cárdenas Lugo', email='sergio.cardenas@gmail.com', telefono='6621122334',
            ciudad_residencia='HMO', nivel_educativo='SEC', años_de_experiencia=0,
            ultimo_puesto='Ayudante General', ultima_empresa='Ferretería del Noroeste',
            puesto_de_interes=p7
        )
        Proceso.objects.create(
            candidato=c_descartado2, puesto=p7, asesora_asignada=u_as2,
            estatus_proceso=Proceso.Estatus.DESCARTADO_CH,
            fecha_inicio_etapa=ahora - timedelta(days=4),
            motivo_descarte='No cumple experiencia mínima de 2 años en enderezado de chasís.',
            retroalimentacion='Descartado en filtro curricular por falta de experiencia requerida.'
        )

        # ==============================================================================
        # 6. CANDIDATOS NO CONTRATABLES (VETADOS / BOLETINADOS)
        # ==============================================================================
        c_vetado1 = Candidato.objects.create(
            nombres='Héctor', apellidos='Camacho Félix', email='hector.camacho@yahoo.com', telefono='6691456789',
            rfc='CAFH880415XYZ', ciudad_residencia='MZT', nivel_educativo='TEC', años_de_experiencia=5,
            ultimo_puesto='Mecánico Automotriz', ultima_empresa='Taller Multimarca',
            es_no_contratable=True,
            motivo_no_contratable='Antecedente grave: Abandono intempestivo de puesto y demanda laboral previa en filial Mazatlán en 2024.'
        )

        c_vetado2 = Candidato.objects.create(
            nombres='Guillermo', apellidos='Paredes Ruelas', email='guillermo.paredes@gmail.com', telefono='6671203040',
            rfc='PARG901010ABC', ciudad_residencia='CUL', nivel_educativo='LIC', años_de_experiencia=4,
            ultimo_puesto='Vendedor de Flotillas', ultima_empresa='Distribuidora Automotriz',
            es_no_contratable=True,
            motivo_no_contratable='Falsificación de documentos y comprobantes de comisiones en proceso de 2025.'
        )

        # 7. CANDIDATOS LIBRES EN BOLSA DE TRABAJO (APTOS)
        candidatos_bolsa = [
            ("Valeria", "Montoya Serna", "valeria.montoya@hotmail.com", "6678901234", "CUL", "LIC", 2, "Auxiliar Administrativo", "Agroindustrias", "SAP, Excel intermedio, Facturación 4.0"),
            ("Andrea", "Bojórquez Castro", "andrea.bojorquez@gmail.com", "6681234567", "LMM", "LIC", 1, "Recepcionista / Hostess", "Hotel Fiesta", "Atención a clientes, Conmutador, Excelente presencia"),
            ("Ricardo", "Zamudio Meza", "ricardo.zamudio@gmail.com", "6647890123", "TIJ", "SEC", 4, "Lavador y Detallador", "Auto Spa Culiacán", "Pulido, Encerado, Detallado de interiores, Manejo estándar"),
            ("Daniela", "Salazar Peñuelas", "daniela.salazar@outlook.com", "6623456789", "HMO", "LIC", 4, "Coordinadora de Mercadotecnia", "Agencia Digital", "Meta Ads, Google Ads, Diseño Canva, Estrategia Leads")
        ]
        for nom, ape, em, tel, ciu, niv, exp, ult_p, ult_e, hab in candidatos_bolsa:
            Candidato.objects.get_or_create(
                email=em,
                defaults={
                    'nombres': nom, 'apellidos': ape, 'telefono': tel, 'ciudad_residencia': ciu,
                    'nivel_educativo': niv, 'años_de_experiencia': exp, 'ultimo_puesto': ult_p,
                    'ultima_empresa': ult_e, 'habilidades': hab, 'expectativa_salarial': Decimal('15000.00'),
                    'es_no_contratable': False
                }
            )

        # 8. AVISOS GENERALES DEL DASHBOARD
        Aviso.objects.get_or_create(
            titulo='Nuevo Modelo Operativo de Capital Humano',
            defaults={
                'contenido': 'El sistema ahora opera exclusivamente para el equipo de Capital Humano. Las vacantes nacen autorizadas y activas directamente sin requerir aprobaciones externas. Monitorea tus SLAs y metas de bono directamente desde el panel.',
                'creado_por': u_ch,
                'esta_activo': True
            }
        )

        self.stdout.write(self.style.SUCCESS("¡Datos demo de RH creados exitosamente!"))
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write("USUARIOS EXCLUSIVOS DE CAPITAL HUMANO (Contraseña: password123):")
        self.stdout.write(" - Superusuario / Admin:    jorge.guzman")
        self.stdout.write(" - Gerente Capital Humano:  gerente.ch (Patricia Aréchiga)")
        self.stdout.write(" - Asesora de Selección:    asesora.arely (Arely Trujillo)")
        self.stdout.write(" - Asesora de Selección:    asesora.sofia (Sofía Navarro)")
        self.stdout.write(self.style.SUCCESS("=" * 60))
