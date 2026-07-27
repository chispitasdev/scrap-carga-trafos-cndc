import re
import streamlit as st
import pandas as pd
from src.config import PROJECT_ROOT, RUTA_DATOS, RUTA_TRANSFORMADORES

RUTA_CLIMA = PROJECT_ROOT / "data" / "SE_Clima_3min_parquet"
RUTA_COORDENADAS = PROJECT_ROOT / "data" / "SUBESTACIONES" / "subestacion_con_coordenadas.csv"


def sanitizar_nombre(nombre):
    return re.sub(r"[^\w\s-]", "", str(nombre)).strip()


@st.cache_data
def obtener_subestaciones():
    """Busca los archivos parquet en la carpeta de datos de carga."""
    if not RUTA_DATOS.exists():
        return []
    archivos = list(RUTA_DATOS.glob("*_3min.parquet"))
    nombres = [f.name.replace("_3min.parquet", "") for f in archivos]
    return sorted(nombres)


@st.cache_data
def cargar_datos_subestacion(nombre):
    """Carga los datos de carga eléctrica de una subestación específica."""
    safe_name = sanitizar_nombre(nombre)
    archivo = RUTA_DATOS / f"{safe_name}_3min.parquet"
    if not archivo.exists():
        archivo = RUTA_DATOS / f"{nombre}_3min.parquet"

    if archivo.exists():
        return pd.read_parquet(archivo)
    return None


@st.cache_data
def cargar_datos_clima(nombre):
    """Carga los datos meteorológicos de una subestación específica."""
    if not RUTA_CLIMA.exists():
        return None

    safe_name = sanitizar_nombre(nombre)
    archivo = RUTA_CLIMA / f"{safe_name}_clima.parquet"
    if not archivo.exists():
        archivo = RUTA_CLIMA / f"{nombre}_clima.parquet"

    if archivo.exists():
        return pd.read_parquet(archivo)
    return None


@st.cache_data
def cargar_coordenadas_subestaciones():
    """Carga la ubicación geográfica (Latitud/Longitud) de las subestaciones."""
    if RUTA_COORDENADAS.exists():
        try:
            return pd.read_csv(RUTA_COORDENADAS)
        except Exception:
            return None
    return None


@st.cache_data
def cargar_metadatos_trafos():
    """Carga los metadatos de los transformadores si están disponibles."""
    ruta_meta = RUTA_TRANSFORMADORES / "metadatos_ATRs.csv"
    if ruta_meta.exists():
        try:
            return pd.read_csv(ruta_meta)
        except Exception:
            return None
    return None


@st.cache_data
def cargar_resumen_sistema():
    """
    Genera un resumen consolidado de las 61 subestaciones:
    Última carga registrada (MW), Pico histórico (MW), Latitud, Longitud.
    """
    df_coords = cargar_coordenadas_subestaciones()
    subs = obtener_subestaciones()

    resumen = []

    for sub in subs:
        df_carga = cargar_datos_subestacion(sub)
        if df_carga is not None and not df_carga.empty:
            ultimo_mw = df_carga.iloc[-1]["MW"]
            max_pico = df_carga["Max_Diario_MW"].max()
            ultimo_ts = df_carga["Timestamp"].max()

            lat, lon = None, None
            if df_coords is not None and not df_coords.empty:
                match = df_coords[df_coords["Subestacion"] == sub]
                if not match.empty:
                    lat = match.iloc[0]["Latitud"]
                    lon = match.iloc[0]["Longitud"]

            resumen.append(
                {
                    "Subestacion": sub,
                    "Ultimo_MW": round(ultimo_mw, 2),
                    "Pico_Historico_MW": round(max_pico, 2),
                    "Ultimo_Registro": ultimo_ts,
                    "Latitud": lat,
                    "Longitud": lon,
                }
            )

    if resumen:
        return pd.DataFrame(resumen)
    return None
