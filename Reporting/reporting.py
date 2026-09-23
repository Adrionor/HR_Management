import os
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine
from datetime import datetime

# Cargar .env si existe en el directorio raíz
env_path = Path(__file__).resolve().parent.parent / '.env'
if env_path.exists():
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip())

# ==============================================================================
# CONFIGURATION: Lectura segura desde variables de entorno
# ==============================================================================
DB_USER = os.environ.get("DB_USER", "readonly_user")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
DB_HOST = os.environ.get("DB_HOST", "recursos-humanos.ckgrykmwkt91.us-east-1.rds.amazonaws.com")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "recursos_humanos")

# ==============================================================================
# CONSULTA SQL: Esta es la consulta final que construimos.
# ==============================================================================
SQL_QUERY = """
SELECT
    proc.id AS id_movimiento,
    cand.nombres || ' ' || cand.apellidos AS candidato,
    p.agencia AS agencia,
    cp.nombre AS puesto,
    p.id AS id_puesto,
    m.nombre AS marca,
    p.fecha_solicitud AS fecha_requisicion,
    asesora.first_name || ' ' || asesora.last_name AS asesora,
    proc.estatus_proceso AS estatus,
    proc.fecha_inicio_etapa AS fecha_del_estatus,
    proc.retroalimentacion
FROM
    public.reclutamiento_proceso AS proc
LEFT JOIN
    public.reclutamiento_candidato AS cand ON proc.candidato_id = cand.id
LEFT JOIN
    public.reclutamiento_puesto AS p ON proc.puesto_id = p.id
LEFT JOIN
    public.reclutamiento_catalogopuesto AS cp ON p.titulo_id = cp.id
LEFT JOIN
    public.reclutamiento_marca AS m ON p.marca_id = m.id
LEFT JOIN
    public.auth_user AS asesora ON proc.asesora_asignada_id = asesora.id;
"""


# ==============================================================================
# FUNCIÓN DE REPORTE: Esta función no cambia, procesa los datos una vez cargados.
# ==============================================================================
def generar_reporte_por_asesora(nombre_asesora, df_original):
    """
    Genera un reporte de vacantes y procesos para una asesora específica.
    """
    # 1. Filtrar los datos para la asesora seleccionada
    df_asesora = df_original[df_original['asesora'] == nombre_asesora].copy()

    if df_asesora.empty:
        print(f"No se encontraron datos para la asesora: {nombre_asesora}")
        return pd.DataFrame()

    # 2. Encontrar el estatus y retroalimentación más reciente para cada proceso
    df_asesora_sorted = df_asesora.sort_values(by='fecha_del_estatus', ascending=False)
    df_procesos_recientes = df_asesora_sorted.groupby(['id_puesto', 'candidato']).first().reset_index()

    # 3. Calcular los días transcurridos desde la requisición
    hoy = datetime.now()
    df_procesos_recientes['dias_transcurridos'] = (hoy - df_procesos_recientes['fecha_requisicion']).dt.days

    # 4. Agrupar por agencia y puesto para contar las vacantes únicas
    reporte_agregado = df_procesos_recientes.groupby(['agencia', 'puesto']).agg(
        cantidad_vacantes=('id_puesto', 'nunique'),
        fecha_requisicion_mas_antigua=('fecha_requisicion', 'min')
    ).reset_index()

    # 5. Obtener los detalles del último proceso para ese grupo
    df_final = df_procesos_recientes.sort_values(by='fecha_del_estatus', ascending=False).groupby(
        ['agencia', 'puesto']).first().reset_index()

    # 6. Unir los conteos con los detalles
    reporte_final = pd.merge(
        reporte_agregado,
        df_final[['agencia', 'puesto', 'estatus', 'retroalimentacion', 'dias_transcurridos']],
        on=['agencia', 'puesto']
    )

    # 7. Renombrar y ordenar columnas para la presentación final
    reporte_final = reporte_final.rename(columns={
        'agencia': 'Agencia',
        'puesto': 'Puesto Vacante',
        'cantidad_vacantes': 'Cantidad de Vacantes',
        'fecha_requisicion_mas_antigua': 'Fecha Requisición (más antigua)',
        'dias_transcurridos': 'Días Transcurridos (último proceso)',
        'estatus': 'Estatus Más Reciente',
        'retroalimentacion': 'Última Observación'
    })

    columnas_ordenadas = [
        'Agencia', 'Puesto Vacante', 'Cantidad de Vacantes', 'Fecha Requisición (más antigua)',
        'Días Transcurridos (último proceso)', 'Estatus Más Reciente', 'Última Observación'
    ]

    return reporte_final[columnas_ordenadas]


# ==============================================================================
# BLOQUE PRINCIPAL DE EJECUCIÓN
# ==============================================================================
if __name__ == "__main__":
    try:
        # 1. Crear la cadena de conexión y el motor de SQLAlchemy
        connection_string = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        engine = create_engine(connection_string)

        # 2. Ejecutar la consulta y cargar los datos directamente en un DataFrame
        print("Conectando a la base de datos y extrayendo datos...")
        df_completo = pd.read_sql(SQL_QUERY, engine)
        print("¡Datos extraídos con éxito!")
        print("-" * 40)

        # 3. Preparar los datos (convertir fechas)
        df_completo['fecha_requisicion'] = pd.to_datetime(df_completo['fecha_requisicion'], errors='coerce')
        df_completo['fecha_del_estatus'] = pd.to_datetime(df_completo['fecha_del_estatus'], errors='coerce')

        # --- AJUSTE CLAVE AQUÍ ---
        # Le quitamos la información de zona horaria a las columnas para hacerlas "naive"
        df_completo['fecha_requisicion'] = df_completo['fecha_requisicion'].dt.tz_localize(None)
        df_completo['fecha_del_estatus'] = df_completo['fecha_del_estatus'].dt.tz_localize(None)

        df_completo.dropna(subset=['fecha_requisicion', 'fecha_del_estatus'], inplace=True)

        # 4. (Opcional) Ver la lista de asesoras disponibles
        asesoras_disponibles = df_completo['asesora'].dropna().unique()
        print("Asesoras disponibles para generar reporte:")
        print(asesoras_disponibles)
        print("-" * 40)

        # 5. Elige una asesora y genera su reporte
        nombre_de_la_asesora = 'Arely Mireya Trujillo Zamudio'  # <--- CAMBIA ESTE NOMBRE

        if nombre_de_la_asesora in asesoras_disponibles:
            reporte = generar_reporte_por_asesora(nombre_de_la_asesora, df_completo)

            # 6. Muestra el reporte final en formato de tabla
            print(f"REPORTE PARA: {nombre_de_la_asesora}")
            print(reporte.to_string())
        else:
            print(f"Error: La asesora '{nombre_de_la_asesora}' no se encuentra en los datos.")
            print("Por favor, elige un nombre de la lista de asesoras disponibles.")

    except Exception as e:
        print(f"Ha ocurrido un error al conectar o procesar los datos: {e}")