import pandas as pd
import streamlit as st
from sqlalchemy import create_engine
from datetime import datetime

# ==============================================================================
# CONFIGURATION Y SQL (Sin cambios)
# ==============================================================================
DB_USER = "readonly_user"
DB_PASSWORD = "GrupoPremi3r25$"
DB_HOST = "recursos-humanos.ckgrykmwkt91.us-east-1.rds.amazonaws.com"
DB_PORT = "5432"
DB_NAME = "recursos_humanos"

SQL_QUERY = """
SELECT
    proc.id AS id_movimiento,
    cand.nombres || ' ' || cand.apellidos AS candidato,
    p.agencia AS agencia,
    p.ciudad AS ciudad,
    cp.nombre AS puesto,
    p.id AS id_puesto,
    p.motivo_requisicion,
    p.fecha_solicitud AS fecha_requisicion,
    asesora.first_name || ' ' || asesora.last_name AS asesora,
    proc.estatus_proceso AS estatus,
    proc.fecha_inicio_etapa AS fecha_del_estatus,
    proc.retroalimentacion,
    pub.monto_inversion,
    cand.medio_conocimiento
FROM
    public.reclutamiento_proceso AS proc
LEFT JOIN
    public.reclutamiento_candidato AS cand ON proc.candidato_id = cand.id
LEFT JOIN
    public.reclutamiento_puesto AS p ON proc.puesto_id = p.id
LEFT JOIN
    public.reclutamiento_catalogopuesto AS cp ON p.titulo_id = cp.id
LEFT JOIN
    public.auth_user AS asesora ON proc.asesora_asignada_id = asesora.id
LEFT JOIN
    public.reclutamiento_publicacion AS pub ON p.id = pub.puesto_id;
"""

# ==============================================================================
# DICCIONARIO DE DÍAS META POR PUESTO (NUEVO)
# ==============================================================================
METAS_POR_PUESTO_DEFAULT = {
    'Asesor(a) de ventas': 20, 'Asesor(a) de ventas de flotillas': 20, 'Asesor de servicio': 20,
    'Vendedor Ecommerce': 12, 'Vendedor de Mayoreo Colisión': 12, 'Vendedor de Mayoreo Foráneo': 12,
    'Vendedor de Mayoreo Partes': 12, 'Asesor de ventas accesorios': 12, 'Vendedor de Mostrador': 12,
    'Previador': 12, 'Asesor(a) leads': 12, 'Intercambios': 12, 'Guardia de seguridad': 12,
    'Lavador de autos': 12, 'Chofer': 12, 'Chofer/Almacenisa': 12, 'Ayudante de Técnico': 12,
    'Hojalatero': 12, 'Pintor': 12, 'Preparador': 12, 'Pulidor': 12, 'Asesor de HYP': 12,
    'Despachador de Body shop': 12, 'Despachador de Ventanilla': 12, 'Encargado de patio': 12,
    'Encargado de Exhibición y Demos': 12, 'Encargado de Previas': 12, 'Jefe de lavado': 12,
    'Responding': 12, 'Especialista de marketing Digital': 12, 'Auxiliar contable': 20,
    'Auxiliar de F&I': 12, 'Administradora de ventas': 12, 'Facturista': 12,
    'Comprador(a) de autos': 12, 'Asistente de dirección': 12, 'Auxiliar de Citas': 12,
    'Administrador(a) de garantías': 12, 'Auxiliar de Garantías': 12, 'Auxiliar administrativo': 12,
    'Auxiliar administrativo HYP': 12, 'Almacenista': 12, 'Conmutador': 12,
    'Encargado(a) de Caja general': 12, 'Asesor(a) de capital humano': 12,
    'Auxiliar Crédito y Cobranza': 12, 'Cobrador': 12, 'Encargado(a) de Crédito y cobranza': 12,
    'Contador(a) general': 12, 'Office boy': 12, 'Subcontador(a)': 12, 'Practicante': 10,
    'Asesor de sistemas': 20, 'Control de Calidad': 20, 'Técnico en Diagnóstico': 20,
    'Técnico en Mantenimiento': 20, 'Técnico en Reparación': 20, 'Técnico Master': 20,
    'Técnico de HyP': 20, 'Valuador': 20, 'Auditor Interno': 20, 'Capacitador': 20,
    'Auditor(a) de marca': 20, 'Asesor(a) de Mejora Continua': 20, 'Especialista en contenido': 20,
    'Diseñador(a) Sr.': 20, 'Diseñador(a) training': 20, 'Ejecutivo(a) de Responding': 20,
    'Ejecutiva de Imagen': 20, 'Especialista en Paid Media': 20,
    'Especialista en Paid Media Training': 20, 'Productor(a) Audiovisual': 20,
    'User Experience Jr': 20, 'Ejecutivo(a) BTL': 20, 'Médico general': 20,
    'Técnico de motos': 20, 'Técnico de autos': 20, 'Asesor(a) de Normatividad': 20,
    'Encargado de mantenimiento': 20, 'Coord Gastos Médicos Mayores': 20,
    'Subgerente de Capital Humano': 20, 'Coord. Desarrollo y Bienestar': 20,
    'Coord. Vinculación con la Comunidad': 20, 'Coord. Comunicación interna': 20,
    'Coord. De Clima y Mentoring': 20, 'Gerente de ATL y Digital': 20, 'Gerente de BTL': 20,
    'Gerente de Hospitalidad': 20, 'Subgerente de ventas': 20,
    'Encargado(a) de Mejora continua': 20, 'Encargado(a) de Mercadotecnia': 20,
    'Encargado de Sistemas': 20, 'Coordinador de Seguridad': 20, 'Supervisor de seguridad': 20,
    'Coordinador(a) de Hospitalidad y Responding': 20, 'Coordinador(a) de Publicidad': 20,
    'Coordinador(a) ETA': 20, 'Coordinador(a) Digital': 20, 'Jefe de taller HyP': 20,
    'Jefe de taller ': 20, 'Coordinador de HYP': 20, 'Encargado de compras': 20,
    'Jefe de almacén': 20, 'Jefe de Mayoreo de Colisión': 20, 'Jefe de Mayoreo Partes': 20,
    'Jefe de ventas Mostrador': 20, 'Subgerente de refacciones': 20, 'Subgerente de Sistemas': 20,
    'Coordinador(a) de Leds': 20, 'Encargado(a) de Inventarios': 20,
    'Coordinador(a) de Citas': 20, 'Coordinador(a) de asesores de servicio': 20,
    'Encargado(a) de F&I': 20, 'Gerente General / Comercial / Director': 30,
    'Gerente de servicio / ventas /  refacciones / administrativo / seminuevos / HYP': 25,
    'Gerente Corporativo': 25
}


# ==============================================================================
# FUNCIÓN DE CARGA DE DATOS (MODIFICADA)
# ==============================================================================
@st.cache_data(ttl=600)
def load_data():
    """Conecta a la BD y ejecuta la consulta, retorna un DataFrame limpio."""
    connection_string = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    engine = create_engine(connection_string)
    df = pd.read_sql(SQL_QUERY, engine)

    # Limpieza y preparación de datos
    df['fecha_requisicion'] = pd.to_datetime(df['fecha_requisicion'], errors='coerce').dt.tz_localize(None)
    df['fecha_del_estatus'] = pd.to_datetime(df['fecha_del_estatus'], errors='coerce').dt.tz_localize(None)
    df.dropna(subset=['fecha_requisicion', 'fecha_del_estatus'], inplace=True)
    return df


# ==============================================================================
# CONSTRUCCIÓN DEL DASHBOARD
# ==============================================================================
st.set_page_config(page_title="Dashboard de Reclutamiento", layout="wide")
st.title("📊 Dashboard de Rendimiento de Reclutamiento")

# --- INICIALIZACIÓN DEL SESSION STATE PARA METAS EDITABLES ---
if 'metas_puestos' not in st.session_state:
    st.session_state.metas_puestos = METAS_POR_PUESTO_DEFAULT.copy()

try:
    df_completo = load_data()

    if not df_completo.empty:
        # --- EDITOR DE METAS EN LA BARRA LATERAL ---
        with st.sidebar.expander("📝 Editar Días Meta por Puesto"):
            for puesto, dias in st.session_state.metas_puestos.items():
                # La clave única es crucial para que Streamlit sepa qué input corresponde a qué puesto
                st.session_state.metas_puestos[puesto] = st.number_input(
                    label=puesto,
                    value=dias,
                    min_value=1,
                    max_value=90,
                    step=1,
                    key=f"meta_{puesto}"
                )

        # --- APLICAR LAS METAS ACTUALES (del session_state) AL DATAFRAME ---
        df_completo['dias_maximos'] = df_completo['puesto'].map(st.session_state.metas_puestos).fillna(20)
        df_completo['fecha_vencimiento'] = df_completo['fecha_requisicion'] + pd.to_timedelta(
            df_completo['dias_maximos'], unit='d')
        df_completo['dias_transcurridos'] = (datetime.now() - df_completo['fecha_requisicion']).dt.days
        estatus_de_cierre = ['CONTRATADO']
        df_completo['vencida'] = (datetime.now() > df_completo['fecha_vencimiento']) & (
            ~df_completo['estatus'].isin(estatus_de_cierre))

        # --- FILTROS EN LA BARRA LATERAL (Sin cambios) ---
        st.sidebar.header("Filtros Generales")
        asesoras_disponibles = ['Todas'] + sorted(df_completo['asesora'].dropna().unique())
        asesora_seleccionada = st.sidebar.selectbox("Selecciona una Asesora:", options=asesoras_disponibles)
        min_fecha = df_completo['fecha_requisicion'].min().date()
        max_fecha = df_completo['fecha_requisicion'].max().date()
        fecha_inicio = st.sidebar.date_input("Fecha de inicio", min_fecha, min_value=min_fecha, max_value=max_fecha)
        fecha_fin = st.sidebar.date_input("Fecha de fin", max_fecha, min_value=min_fecha, max_value=max_fecha)
        agencias_disponibles = sorted(df_completo['agencia'].dropna().unique())
        agencia_seleccionada = st.sidebar.multiselect("Selecciona Agencias:", options=agencias_disponibles,
                                                      default=agencias_disponibles)

        # --- APLICACIÓN DE FILTROS (Sin cambios) ---
        df_filtrado_fecha_agencia = df_completo[
            (df_completo['fecha_requisicion'].dt.date >= fecha_inicio) &
            (df_completo['fecha_requisicion'].dt.date <= fecha_fin) &
            (df_completo['agencia'].isin(agencia_seleccionada))
            ]
        if asesora_seleccionada == 'Todas':
            df_filtrado = df_filtrado_fecha_agencia
            titulo_principal = "Global (Todas las Asesoras)"
        else:
            df_filtrado = df_filtrado_fecha_agencia[df_filtrado_fecha_agencia['asesora'] == asesora_seleccionada]
            titulo_principal = f"para: {asesora_seleccionada}"
        df_vacantes = df_filtrado.sort_values('fecha_del_estatus').groupby('id_puesto').last().reset_index()

        # --- PESTAÑAS DE VISUALIZACIÓN (Sin cambios en su lógica interna) ---
        tab1, tab2 = st.tabs(["Dashboard de KPIs", "Reporte Detallado por Vacante"])

        # Pestaña 1: KPIs
        with tab1:
            st.header(f"Indicadores Clave {titulo_principal}")
            # ... (El resto del código de la pestaña 1 no necesita cambios)
            st.markdown(f"Periodo: **{fecha_inicio.strftime('%d/%m/%Y')}** al **{fecha_fin.strftime('%d/%m/%Y')}**")
            if df_vacantes.empty:
                st.warning("No se encontraron datos con los filtros seleccionados.")
            else:
                total_vacantes = df_vacantes['id_puesto'].nunique()
                vacantes_vencidas = df_vacantes[df_vacantes['vencida'] == True]['id_puesto'].nunique()
                vacantes_activas = total_vacantes - vacantes_vencidas
                estatus_contratacion = st.text_input("Escribe el estatus que significa 'Contratado'",
                                                     value='CONTRATADO')
                vacantes_cerradas = df_vacantes[df_vacantes['estatus'] == estatus_contratacion]['id_puesto'].nunique()
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Total Vacantes Asignadas", f"{total_vacantes}")
                col2.metric("Vacantes Vencidas", f"{vacantes_vencidas}")
                col3.metric("Vacantes Activas", f"{vacantes_activas}")
                col4.metric("Vacantes Cerradas (Contratación)", f"{vacantes_cerradas}")
                st.markdown("---")
                col_graf1, col_graf2 = st.columns(2)
                with col_graf1:
                    st.subheader("Vacantes por Motivo de Requisición")
                    motivos = df_vacantes['motivo_requisicion'].value_counts()
                    st.bar_chart(motivos)
                    st.subheader("Contrataciones por Ubicación")
                    contratados_df = df_vacantes[df_vacantes['estatus'] == estatus_contratacion]
                    if not contratados_df.empty:
                        contratados_df['ubicacion'] = contratados_df['ciudad'].apply(
                            lambda x: 'Culiacán' if 'culiacan' in str(x).lower() else 'Foránea')
                        ubicacion_counts = contratados_df['ubicacion'].value_counts()
                        st.bar_chart(ubicacion_counts)
                    else:
                        st.info("No hay contrataciones en el periodo seleccionado.")
                with col_graf2:
                    st.subheader("Estado de Vacantes por Agencia")
                    vencidas_por_agencia = df_vacantes.groupby('agencia')['vencida'].sum().astype(int)
                    st.bar_chart(vencidas_por_agencia)
                    st.subheader("Origen de Candidatos (Procesos)")
                    origen_candidatos = df_filtrado['medio_conocimiento'].value_counts()
                    if not origen_candidatos.empty:
                        st.bar_chart(origen_candidatos)
                    else:
                        st.info("No hay datos de origen de candidatos.")
                total_inversion = df_vacantes['monto_inversion'].sum()
                st.metric("Inversión Total en Publicaciones (periodo seleccionado)", f"${total_inversion:,.2f}")

        # Pestaña 2: Reporte Detallado
        with tab2:
            st.header(f"Reporte Detallado {titulo_principal}")
            # ... (El resto del código de la pestaña 2 no necesita cambios)
            if df_vacantes.empty:
                st.warning("No se encontraron vacantes con los filtros seleccionados.")
            else:
                df_reporte = df_vacantes[[
                    'agencia', 'puesto', 'fecha_requisicion', 'fecha_vencimiento', 'dias_maximos',
                    'vencida', 'estatus', 'retroalimentacion', 'id_puesto'
                ]].rename(columns={
                    'agencia': 'Agencia', 'puesto': 'Puesto', 'fecha_requisicion': 'Fecha Requisición',
                    'fecha_vencimiento': 'Fecha Vencimiento', 'dias_maximos': 'Días Meta',
                    'vencida': 'Vencida', 'estatus': 'Último Estatus', 'retroalimentacion': 'Última Observación'
                })


                @st.cache_data
                def convert_df_to_csv(df):
                    return df.to_csv(index=False).encode('utf-8')


                csv = convert_df_to_csv(df_reporte)
                st.download_button(
                    label="📥 Descargar Reporte a Excel (CSV)",
                    data=csv,
                    file_name=f'reporte_detallado_{asesora_seleccionada}_{fecha_inicio}_a_{fecha_fin}.csv',
                    mime='text/csv',
                )
                st.dataframe(df_reporte, use_container_width=True)

except Exception as e:
    st.error(f"Error al conectar a la base de datos o procesar los datos: {e}")
    st.error("Detalles del error: " + str(e))