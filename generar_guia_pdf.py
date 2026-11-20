"""
Generador de Guía Visual en PDF del Sistema de Reclutamiento y Selección
Premier Automotriz - Documento para usuarios no técnicos y personal nuevo en RH.
"""

import os
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    """Agrega encabezados limpios y numeración automática 'Página X de Y'."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_decorations(self, page_count):
        self.saveState()
        # Encabezado (a partir de la página 2)
        if self._pageNumber > 1:
            self.setFont("Helvetica-Bold", 7.5)
            self.setFillColor(colors.HexColor("#1d2d3e"))
            self.drawString(46, 11 * 72 - 32, "PREMIER AUTOMOTRIZ")
            self.setFont("Helvetica", 7.5)
            self.setFillColor(colors.HexColor("#64748b"))
            self.drawString(155, 11 * 72 - 32, "|   Guía Fácil del Sistema de Reclutamiento y Selección")
            self.setStrokeColor(colors.HexColor("#e2e8f0"))
            self.setLineWidth(0.6)
            self.line(46, 11 * 72 - 38, 8.5 * 72 - 46, 11 * 72 - 38)

        # Pie de página (en todas las páginas)
        self.setStrokeColor(colors.HexColor("#e2e8f0"))
        self.setLineWidth(0.6)
        self.line(46, 40, 8.5 * 72 - 46, 40)

        self.setFont("Helvetica", 7.5)
        self.setFillColor(colors.HexColor("#64748b"))
        self.drawString(46, 28, "Uso Interno de Capital Humano • Sistema 100% RH")
        page_str = f"Página {self._pageNumber} de {page_count}"
        self.drawRightString(8.5 * 72 - 46, 28, page_str)
        self.restoreState()


def crear_guia_pdf(output_filename):
    doc = SimpleDocTemplate(
        output_filename,
        pagesize=letter,
        leftMargin=46,
        rightMargin=46,
        topMargin=46,
        bottomMargin=46
    )

    styles = getSampleStyleSheet()

    # Estilos de tipografía personalizados
    c_primary = colors.HexColor("#1d2d3e")
    c_accent = colors.HexColor("#0070f2")
    c_dark = colors.HexColor("#0f172a")
    c_gray = colors.HexColor("#475569")

    style_title = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=c_primary,
        spaceAfter=4
    )

    style_subtitle = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10.5,
        leading=14,
        textColor=c_accent,
        spaceAfter=12
    )

    style_h1 = ParagraphStyle(
        'Heading1_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=17,
        textColor=c_primary,
        spaceBefore=14,
        spaceAfter=6,
        keepWithNext=True
    )

    style_h2 = ParagraphStyle(
        'Heading2_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=14,
        textColor=c_accent,
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True
    )

    style_body = ParagraphStyle(
        'Body_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12.5,
        textColor=c_dark,
        spaceAfter=6
    )

    style_body_bold = ParagraphStyle(
        'Body_Bold_Custom',
        parent=style_body,
        fontName='Helvetica-Bold'
    )

    style_callout_text = ParagraphStyle(
        'CalloutText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#1e293b")
    )

    style_step_num = ParagraphStyle(
        'StepNum',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=13,
        textColor=colors.HexColor("#ffffff"),
        alignment=1
    )

    style_step_title = ParagraphStyle(
        'StepTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=13,
        textColor=c_primary
    )

    style_step_desc = ParagraphStyle(
        'StepDesc',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11.5,
        textColor=c_gray
    )

    style_table_header = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#ffffff"),
        alignment=0
    )

    style_table_cell = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.2,
        leading=11,
        textColor=c_dark
    )

    story = []

    # =========================================================================
    # 1. ENCABEZADO Y PORTADA
    # =========================================================================
    logo_path = r"c:\Users\jorge.guzman\PycharmProjects\HR_Management\reclutamiento\static\reclutamiento\img\Logo_Premier.png"
    if os.path.exists(logo_path):
        img = Image(logo_path, width=120, height=35)
        img.hAlign = 'LEFT'
        story.append(img)
        story.append(Spacer(1, 8))

    story.append(Paragraph("Manual Sencillo del Sistema de Reclutamiento", style_title))
    story.append(Paragraph("Guía práctica paso a paso para Asesoras y Directores de Capital Humano", style_subtitle))
    story.append(HRFlowable(width="100%", thickness=1.5, color=c_primary, spaceBefore=2, spaceAfter=10))

    # Tarjeta de bienvenida
    bienvenida_html = (
        "<strong>¿Qué es este sistema y para qué sirve?</strong><br/>"
        "Es la herramienta de trabajo del departamento de Capital Humano de Premier Automotriz. "
        "Su objetivo es muy claro: <strong>ayudarte a encontrar a las personas que necesitan nuestras agencias "
        "y contratarlas a tiempo</strong>, llevando un control fácil y sin papeles perdidos."
    )
    t_bienvenida = Table([[Paragraph(bienvenida_html, style_callout_text)]], colWidths=[520])
    t_bienvenida.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f8fafc")),
        ('BORDER', (0,0), (-1,-1), 1, colors.HexColor("#cbd5e1")),
        ('LEFTPADDING', (0,0), (-1,-1), 12),
        ('RIGHTPADDING', (0,0), (-1,-1), 12),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t_bienvenida)
    story.append(Spacer(1, 10))

    # =========================================================================
    # 2. CÓMO ENTRAR AL SISTEMA
    # =========================================================================
    story.append(Paragraph("1. Cómo Entrar al Sistema (Acceso en 1 Clic)", style_h1))
    story.append(Paragraph(
        "No necesitas memorizar usuarios raros ni contraseñas difíciles. "
        "En la pantalla inicial verás un recuadro llamado <strong>'⚡ Entrar con 1 Clic'</strong>:",
        style_body
    ))

    login_steps = [
        ["1", Paragraph("<strong>Haz clic sobre tu nombre:</strong><br/>"
                        "• <strong>Arely Trujillo</strong> o <strong>Sofía Navarro</strong> (para Asesoras de Selección).<br/>"
                        "• <strong>Patricia Aréchiga</strong> (para Gerencia de Capital Humano).<br/>"
                        "• <strong>Jorge Guzmán</strong> (Control Total / Administrador).", style_body)],
        ["2", Paragraph("<strong>El sistema entra de inmediato:</strong> Llena tu usuario y contraseña automáticamente y te lleva directo a tu área de trabajo.", style_body)]
    ]
    t_login = Table(login_steps, colWidths=[24, 496])
    t_login.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,-1), c_accent),
        ('TEXTCOLOR', (0,0), (0,-1), colors.white),
        ('ALIGN', (0,0), (0,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_login)
    story.append(Spacer(1, 10))

    # =========================================================================
    # 3. LAS 5 HERRAMIENTAS PRINCIPALES
    # =========================================================================
    story.append(Paragraph("2. Las 5 Herramientas que Usarás Todos los Días", style_h1))
    story.append(Paragraph(
        "En la barra superior de la pantalla siempre tendrás a la mano las 5 secciones de trabajo:",
        style_body
    ))

    modulos_data = [
        [
            Paragraph("Botón / Sección", style_table_header),
            Paragraph("¿Para qué sirve?", style_table_header),
            Paragraph("¿Cuándo debes usarlo?", style_table_header)
        ],
        [
            Paragraph("<strong>📝 Registrar Vacante</strong>", style_table_cell),
            Paragraph("Captura la hoja de requisición física que firmó el gerente.", style_table_cell),
            Paragraph("Cuando te llega una solicitud de una agencia para contratar a alguien.", style_table_cell)
        ],
        [
            Paragraph("<strong>📋 Mis Vacantes</strong>", style_table_cell),
            Paragraph("Tu lista de puestos pendientes con contador de días y meta de bono.", style_table_cell),
            Paragraph("Tu pantalla principal de trabajo. Aquí ves cuánto tiempo te queda.", style_table_cell)
        ],
        [
            Paragraph("<strong>👥 Mis Candidatos</strong>", style_table_cell),
            Paragraph("Lista de todas las personas que estás entrevistando y evaluando.", style_table_cell),
            Paragraph("Para registrar avances: exámenes, citas con jefes o contrataciones.", style_table_cell)
        ],
        [
            Paragraph("<strong>🗄️ Bolsa de Trabajo</strong>", style_table_cell),
            Paragraph("El archivero de currículums de personas que buscan empleo.", style_table_cell),
            Paragraph("Cuando abras una vacante y quieras jalar candidatos ya registrados.", style_table_cell)
        ],
        [
            Paragraph("<strong>📊 Reportes Excel</strong>", style_table_cell),
            Paragraph("Descarga con 1 solo clic los informes ejecutivos listos para enviar.", style_table_cell),
            Paragraph("Al cierre de semana, mes o cuando dirección te pida resultados.", style_table_cell)
        ]
    ]

    t_modulos = Table(modulos_data, colWidths=[120, 200, 200])
    t_modulos.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), c_primary),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#f8fafc")]),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(t_modulos)
    story.append(Spacer(1, 14))

    # =========================================================================
    # 4. EL CAMINITO DE UN CANDIDATO (PASO A PASO)
    # =========================================================================
    story.append(Paragraph("3. El Caminito de un Candidato (De que llega a que firma)", style_h1))
    story.append(Paragraph(
        "Cuando asignas una persona a una vacante, el sistema te permite llevarlo paso a paso "
        "con botones muy sencillos. Solo tienes que hacer clic en la etapa donde va:",
        style_body
    ))

    etapas = [
        ("1", "Contacto", "Le marcas por teléfono o le mandas WhatsApp para saber si sigue interesado."),
        ("2", "Pruebas", "Aplica sus evaluaciones psicométricas (Integridad y Pyxoom). Marcas 'Aprobado' o 'No Aprobado'."),
        ("3", "Entrevista RH", "Tu plática con el candidato para evaluar su actitud, experiencia y ganas de trabajar."),
        ("4", "Referencias", "Hablas a sus trabajos anteriores para confirmar cómo fue su desempeño."),
        ("5", "Entrevista con Jefe", "Envías al candidato con el jefe de la agencia. <em>(¡Ojo! Enviar 3 candidatos aquí cuenta para tu bono).</em>"),
        ("6", "Confirmado por Jefe", "El gerente de la agencia te avisa que sí le gustó y que desea que se quede."),
        ("7", "Médico y Papeles", "Se hace el chequeo médico y te entrega acta, comprobante de domicilio, RFC y constancias."),
        ("8", "¡Contratado!", "Firma su contrato y queda dado de alta. La vacante se suma como cubierta.")
    ]

    etapas_rows = []
    for num, titulo, desc in etapas:
        badge = Table([[Paragraph(num, style_step_num)]], colWidths=[18], rowHeights=[18])
        badge.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), c_accent),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING', (0,0), (-1,-1), 1),
            ('BOTTOMPADDING', (0,0), (-1,-1), 1),
        ]))
        etapas_rows.append([
            badge,
            Paragraph(f"<strong>{titulo}</strong>", style_step_title),
            Paragraph(desc, style_step_desc)
        ])

    t_etapas = Table(etapas_rows, colWidths=[24, 130, 366])
    t_etapas.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('LINEBELOW', (0,0), (-1,-1), 0.5, colors.HexColor("#f1f5f9")),
    ]))
    story.append(t_etapas)
    story.append(Spacer(1, 10))

    # =========================================================================
    # 5. QUÉ HACER SI UN CANDIDATO NO SE QUEDA
    # =========================================================================
    story.append(Paragraph("¿Qué hacer si un candidato ya no sigue en el proceso?", style_h2))

    alert_box_html = (
        "• <strong>Si no te gustó o no pasó los exámenes:</strong> Haz clic en el botón <strong>'Descartar'</strong> y escribe brevemente por qué (ej: <em>'No aprobó examen de integridad'</em>).<br/>"
        "• <strong>Si ya no contestó el teléfono:</strong> Haz clic en <strong>'Marcar Abandono'</strong> (ej: <em>'Aceptó otra oferta'</em>).<br/>"
        "• <strong>Si cometió una falta grave:</strong> Haz clic en <strong>'No Contratable'</strong>. El sistema le pondrá una etiqueta roja permanente para que nadie en Premier lo contrate por error."
    )
    t_alert = Table([[Paragraph(alert_box_html, style_callout_text)]], colWidths=[520])
    t_alert.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#fef2f2")),
        ('BORDER', (0,0), (-1,-1), 1, colors.HexColor("#fecaca")),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_alert)
    story.append(Spacer(1, 14))

    # =========================================================================
    # 6. LAS DOS METAS Y TU BONO
    # =========================================================================
    story.append(Paragraph("4. Las Reglas del Juego: El Tiempo y Tu Bono", style_h1))
    story.append(Paragraph(
        "En Premier tenemos un estándar claro para atender las vacantes:",
        style_body
    ))

    reglas_data = [
        [
            Paragraph("⏱️ La Meta de Tiempo (20 días)", style_step_title),
            Paragraph("Cada vacante nace con un reloj de <strong>20 días meta</strong> (puedes cambiarlo si es un puesto especial como hojalatero o chofer que son de 12 días). "
                      "En la pantalla verás un contador claro: <em>'Días transcurridos vs Meta'</em>.", style_body)
        ],
        [
            Paragraph("🎯 ¿Cómo Cumples la Meta de Bono?", style_step_title),
            Paragraph("El sistema calcula automáticamente si cumples con tu bono mensual. <strong>Ganaste tu meta si:</strong><br/>"
                      "<strong>Opción A:</strong> Cubres y contratas todas las plazas de la vacante dentro de los días meta.<br/>"
                      "<strong>Opción B:</strong> Envías al menos <strong>3 candidatos aptos</strong> a entrevista con el jefe antes de que se acaben los días.", style_body)
        ],
        [
            Paragraph("🔄 ¿Qué pasa si la vacante vence?", style_step_title),
            Paragraph("Si pasan los 20 días y no se cubrió, la vacante se marcará en rojo como <strong>'Vencida'</strong>. "
                      "Aparecerá un botón amarillo llamado <strong>'Reiniciar conteo'</strong>. Al presionarlo, el reloj vuelve a 0 días para que sigas buscando, "
                      "y el sistema anota que inició el Ciclo #2 para transparencia de auditoría.", style_body)
        ]
    ]

    t_reglas = Table(reglas_data, colWidths=[170, 350])
    t_reglas.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,-1), colors.HexColor("#f8fafc")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(t_reglas)
    story.append(Spacer(1, 14))

    # =========================================================================
    # 7. LOS 3 REPORTES EN EXCEL
    # =========================================================================
    story.append(Paragraph("5. Los 3 Reportes en Excel (Listos con 1 Clic)", style_h1))
    story.append(Paragraph(
        "En la sección <strong>Reportes Excel</strong>, arriba tienes filtros sencillos por fechas o agencia, "
        "y 3 botones grandes para descargar archivos de Excel (.xlsx) que ya tienen los cálculos hechos:",
        style_body
    ))

    reportes_info = [
        [
            Paragraph("Reporte", style_table_header),
            Paragraph("¿Qué contiene?", style_table_header),
            Paragraph("¿Quién lo pide y para qué sirve?", style_table_header)
        ],
        [
            Paragraph("<strong>Reporte 1:<br/>Resumen Ejecutivo</strong>", style_table_cell),
            Paragraph("• Cuántas requisiciones llegaron en el mes.<br/>"
                      "• Cuántas personas ya ingresaron.<br/>"
                      "• Cuántas vacantes siguen pendientes y cuántas vencidas.<br/>"
                      "• Hoja 2 con desglose exacto por agencia y puesto.", style_table_cell),
            Paragraph("Es el resumen perfecto para presentar a Dirección General de Capital Humano o en juntas de resultados.", style_table_cell)
        ],
        [
            Paragraph("<strong>Reporte 2:<br/>Auditoría y Bono</strong>", style_table_cell),
            Paragraph("• Cuántas vacantes atendió cada asesora.<br/>"
                      "• Cuántas cumplieron la regla de bono (>= 3 candidatos o cubierta en tiempo).<br/>"
                      "• Embudo completo: cuántos aprobaron Integridad, cuántos Pyxoom y cuántos contrataron.", style_table_cell),
            Paragraph("Es el soporte para calcular el pago de bonos de las asesoras y medir su efectividad de reclutamiento.", style_table_cell)
        ],
        [
            Paragraph("<strong>Reporte 3:<br/>Sábana Histórica</strong>", style_table_cell),
            Paragraph("• La lista renglón por renglón de absolutamente todo lo que ha pasado.<br/>"
                      "• Qué día y a qué hora exacta se movió cada candidato, quién lo atendió y cuántos días duró en cada etapa.", style_table_cell),
            Paragraph("Tu respaldo total. Si un gerente pregunta <em>'¿por qué tardó mi vacante?'</em>, aquí tienes la bitácora con fechas exactas.", style_table_cell)
        ]
    ]

    t_reportes = Table(reportes_info, colWidths=[120, 240, 160])
    t_reportes.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), c_primary),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#f8fafc")]),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(t_reportes)
    story.append(Spacer(1, 10))

    # =========================================================================
    # 8. LOS SEMÁFOROS VISUALES
    # =========================================================================
    story.append(Paragraph("Los 3 Semáforos Visuales de la Pantalla de Reportes", style_h2))
    story.append(Paragraph(
        "Para que no tengas que leer números difíciles, la pantalla de reportes tiene 3 semáforos de colores:",
        style_body
    ))

    semaforos_data = [
        [
            Paragraph("🔴 <strong>Vacantes Vencidas (+20 días):</strong> Te avisa qué puestos ya superaron el plazo meta para que les des prioridad inmediata.", style_body)
        ],
        [
            Paragraph("🔵 <strong>Puestos Más Solicitados:</strong> Te muestra cuáles puestos son los que más piden las agencias (ej: Asesores de Ventas).", style_body)
        ],
        [
            Paragraph("🟠 <strong>Vacantes con Mayor Antigüedad:</strong> Te enlista las vacantes más viejas que tienen más de 30 o 45 días abiertas sin cubrir.", style_body)
        ]
    ]
    t_sem = Table(semaforos_data, colWidths=[520])
    t_sem.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f1f5f9")),
        ('BORDER', (0,0), (-1,-1), 1, colors.HexColor("#cbd5e1")),
        ('LEFTPADDING', (0,0), (-1,-1), 12),
        ('RIGHTPADDING', (0,0), (-1,-1), 12),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_sem)
    story.append(Spacer(1, 14))

    # =========================================================================
    # 9. RESUMEN EN 4 PASOS PARA EMPEZAR HOY
    # =========================================================================
    story.append(Paragraph("6. Tu Rutina Diaria en 4 Pasos Sencillos", style_h1))

    rutina = [
        ["1", Paragraph("<strong>En la mañana:</strong> Entra a <em>Mis Vacantes</em> y revisa cuáles tienen el reloj en amarillo o rojo.", style_body)],
        ["2", Paragraph("<strong>En el día:</strong> Entrevistas candidatos y en <em>Mis Candidatos</em> le das clic a la etapa donde avanzaron.", style_body)],
        ["3", Paragraph("<strong>Si necesitas gente:</strong> Entras a <em>Bolsa de Trabajo</em>, buscas por puesto o ciudad, y los asignas a tu vacante con un clic.", style_body)],
        ["4", Paragraph("<strong>Al cierre de semana:</strong> Vas a <em>Reportes Excel</em> y descargas el Resumen Ejecutivo para tu reporte de avances.", style_body)]
    ]
    t_rutina = Table(rutina, colWidths=[24, 496])
    t_rutina.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,-1), colors.HexColor("#107e3e")),
        ('TEXTCOLOR', (0,0), (0,-1), colors.white),
        ('ALIGN', (0,0), (0,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('LINEBELOW', (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
    ]))
    story.append(t_rutina)

    # Construir PDF
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"PDF generado exitosamente en: {output_filename}")

if __name__ == "__main__":
    pdf_path = r"c:\Users\jorge.guzman\PycharmProjects\HR_Management\Guia_Rapida_Sistema_RH_Premier.pdf"
    crear_guia_pdf(pdf_path)
