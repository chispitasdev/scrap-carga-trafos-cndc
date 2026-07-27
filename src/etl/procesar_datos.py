import zipfile
import pandas as pd
from pathlib import Path
import warnings
import re

from datetime import datetime, timedelta

# --- CONFIGURACIÓN ---
# Definir raíz del proyecto (2 niveles arriba: src/etl -> src -> root)
PROJECT_ROOT = Path(__file__).resolve().parents[2]

RUTA_DATOS_RAW = PROJECT_ROOT / "data" / "cndc"
RUTA_SALIDA = PROJECT_ROOT / "data" / "SE_Carga_3min"
ARCHIVO_SUBESTACIONES = (
    PROJECT_ROOT / "data" / "SUBESTACIONES" / "subestacion_con_coordenadas.csv"
)
KEYWORD_HEADER = "RETIROS (MWh)"

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")


def cargar_subestaciones_objetivo():
    """Carga la lista de subestaciones a procesar desde un CSV."""
    if not ARCHIVO_SUBESTACIONES.exists():
        print(
            f"[WARN] No se encontró {ARCHIVO_SUBESTACIONES}. Se procesarán TODAS (No recomendado)."
        )
        return None

    try:
        df = pd.read_csv(ARCHIVO_SUBESTACIONES)
        # Asumimos que la columna se llama 'Subestacion' o es la primera
        col = "Subestacion" if "Subestacion" in df.columns else df.columns[0]
        lista = df[col].astype(str).str.strip().unique().tolist()
        print(f"[TARGET] Objetivo: {len(lista)} subestaciones cargadas.")
        return lista
    except Exception as e:
        print(f"[X] Error al leer subestaciones: {e}")
        return None


def obtener_fechas_ya_procesadas():
    """
    Retorna un conjunto (set) de fechas que ya han sido procesadas
    y consolidadas en los Parquets de salida.
    """
    RUTA_SALIDA_PARQUET = PROJECT_ROOT / "data" / "SE_Carga_3min_parquet"
    if not RUTA_SALIDA_PARQUET.exists():
        return set()
    parquets = list(RUTA_SALIDA_PARQUET.glob("*.parquet"))
    if not parquets:
        return set()
    try:
        # Leemos el primer Parquet para extraer el set de fechas existentes
        df_sample = pd.read_parquet(parquets[0], columns=["Timestamp"])
        fechas = set(pd.to_datetime(df_sample["Timestamp"]).dt.date.unique())
        return fechas
    except Exception:
        return set()


def obtener_ultima_fecha_procesada():
    """
    Busca en los CSVs de salida la fecha más reciente procesada.
    Retorna datetime o None.
    """
    if not RUTA_SALIDA.exists():
        return None

    fechas_maximas = []
    csvs = list(RUTA_SALIDA.glob("*.csv"))

    if not csvs:
        return None

    for csv in csvs[:5]:
        try:
            df = pd.read_csv(csv)
            if "Timestamp" in df.columns and not df.empty:
                ts = pd.to_datetime(df["Timestamp"]).max()
                fechas_maximas.append(ts)
        except Exception:
            continue

    if fechas_maximas:
        ultima = max(fechas_maximas)
        return ultima.replace(hour=0, minute=0, second=0)

    return None


def procesar_excel_a_tidy(f_handle, fecha_carpeta, subestaciones_target):
    """Procesa un Excel individual y filtra por subestaciones."""
    try:
        df_raw = pd.read_excel(f_handle, header=None, engine="openpyxl")
    except Exception:
        return None

    # Buscar header
    fila_header = None
    for idx, row in df_raw.head(50).iterrows():
        if row.astype(str).str.contains(KEYWORD_HEADER, regex=False).any():
            fila_header = idx
            break

    if fila_header is None:
        return None

    # Limpieza básica
    df_data = df_raw.iloc[fila_header + 1 :].copy()
    df_data.columns = df_raw.iloc[fila_header]

    # Renombrar columnas
    cols_map = {}
    for c in df_data.columns:
        c_str = str(c).strip()
        if c_str == KEYWORD_HEADER:
            cols_map[c] = "Subestacion"
        elif "MAXIMA" in c_str.upper():
            cols_map[c] = "Max_Diario_MW"
        elif c_str.upper() == "HORA":
            cols_map[c] = "Hora_Pico_Reg"

    df_data.rename(columns=cols_map, inplace=True)

    if "Subestacion" not in df_data.columns:
        return None

    # Filtrar Subestaciones
    df_data["Subestacion"] = df_data["Subestacion"].astype(str).str.strip()

    if subestaciones_target:
        # Filtro estricto
        df_data = df_data[df_data["Subestacion"].isin(subestaciones_target)].copy()

    if df_data.empty:
        return None

    # Inyectar Fecha Base
    df_data["Fecha"] = fecha_carpeta

    # Melt
    id_vars = ["Fecha", "Subestacion", "Max_Diario_MW", "Hora_Pico_Reg"]
    value_vars = [
        c
        for c in df_data.columns
        if c not in id_vars and re.match(r"^\d{2}:\d{2}$", str(c).strip())
    ]

    df_melted = df_data.melt(
        id_vars=id_vars, value_vars=value_vars, var_name="Hora_Str", value_name="MW"
    )

    return df_melted


def corregir_fechas_y_tipos(df):
    """Maneja la lógica de 24:00 -> 00:00 del día siguiente."""
    df["MW"] = pd.to_numeric(df["MW"], errors="coerce").fillna(0)

    # Detectar 24:00
    es_24 = df["Hora_Str"].astype(str).str.contains("24:00")
    df.loc[es_24, "Hora_Str"] = "00:00"

    # Crear Timestamp
    df["Timestamp"] = pd.to_datetime(
        df["Fecha"].astype(str) + " " + df["Hora_Str"].astype(str), errors="coerce"
    )

    # Sumar día a las que eran 24:00
    df.loc[es_24, "Timestamp"] += timedelta(days=1)

    # Columnas auxiliares
    df["Fecha_Real"] = df["Timestamp"].dt.date
    df["Hora_Real"] = df["Timestamp"].dt.time

    cols = [
        "Timestamp",
        "Subestacion",
        "MW",
        "Max_Diario_MW",
        "Hora_Pico_Reg",
        "Fecha_Real",
        "Hora_Real",
    ]
    return df[cols].sort_values("Timestamp")


def resamplear_dataframe(df):
    """
    Toma un DataFrame de una subestación, crea grilla de 3 min e interpola (PCHIP).
    """
    if df.empty:
        return df

    # Asegurar índice
    df = df.set_index("Timestamp").sort_index()

    # Resampleo a 3 min
    try:
        df_resampled = df.resample("3min").asfreq()
    except ValueError:
        # Si hay duplicados en el índice, no se puede resamplear directo.
        # Nos quedamos con el último valor.
        df = df[~df.index.duplicated(keep="last")]
        df_resampled = df.resample("3min").asfreq()

    # Interpolación PCHIP
    # Requiere scipy
    try:
        df_resampled["MW"] = df_resampled["MW"].interpolate(
            method="pchip", limit_direction="both"
        )
    except ImportError:
        print("[X] Error: Falta 'scipy'. Instala con: pip install scipy")
        return df.reset_index()  # Devolvemos sin cambios si falla
    except Exception as e:
        print(f"[WARN] Error interpolando: {e}")
        # Fallback a lineal si falla pchip
        df_resampled["MW"] = df_resampled["MW"].interpolate(method="linear")

    # Relleno de metadatos (Corrección robusta para 00:00)
    # 1. Recalcular Fecha_Real para todas las filas
    df_resampled["Fecha_Real"] = df_resampled.index.date

    # 2. Propagar metadatos usando el último valor válido del día
    cols_estaticas = ["Subestacion", "Max_Diario_MW", "Hora_Pico_Reg"]
    cols_a_usar = [c for c in cols_estaticas if c in df_resampled.columns]

    for col in cols_a_usar:
        df_resampled[col] = df_resampled.groupby("Fecha_Real")[col].transform("last")

    # Limpieza
    df_resampled.dropna(subset=["Subestacion"], inplace=True)
    df_resampled["Hora_Real"] = df_resampled.index.time

    return df_resampled.reset_index()


def main_procesamiento(forzar_reproceso=False):
    RUTA_SALIDA.mkdir(parents=True, exist_ok=True)
    print("[START] INICIANDO PROCESAMIENTO RAW (SIN RESAMPLEO)...")

    # 1. Cargar Configuración
    target_subs = cargar_subestaciones_objetivo()
    fechas_existentes = set() if forzar_reproceso else obtener_fechas_ya_procesadas()

    if fechas_existentes and not forzar_reproceso:
        print(f"[DATE] Detectadas {len(fechas_existentes)} fechas ya presentes en el dataset procesado.")
    else:
        print("[INIT] Procesamiento RAW desde cero o forzado.")

    nuevos_datos = []
    archivos_procesados = 0

    # 2. Escanear Archivos Raw
    # Ordenamos carpetas para procesar cronológicamente
    carpetas = sorted(
        [d for d in RUTA_DATOS_RAW.iterdir() if d.is_dir()], key=lambda x: x.name
    )

    for carpeta in carpetas:
        try:
            fecha_dt = datetime.strptime(carpeta.name, "%Y-%m-%d")
            fecha_carpeta = fecha_dt.date()
        except ValueError:
            continue  # Ignorar carpetas que no sean fecha

        # FILTRO INCREMENTAL EXACTO:
        # Si la fecha de la carpeta ya está en el dataset final, la saltamos.
        # Si falta (como los 34 días de Diciembre 2025), ¡LA PROCESAMOS!
        if fechas_existentes and fecha_carpeta in fechas_existentes:
            continue

        print(f"   [DIR] Procesando: {carpeta.name}...", end=" ")

        # 1. Archivos zip (formato clásico)
        zips = list(carpeta.glob("*.zip"))
        for zip_file in zips:
            try:
                with zipfile.ZipFile(zip_file, "r") as z:
                    excels = [f for f in z.namelist() if f.endswith((".xlsx", ".xls"))]
                    for excel in excels:
                        with z.open(excel) as f:
                            df_part = procesar_excel_a_tidy(
                                f, carpeta.name, target_subs
                            )
                            if df_part is not None:
                                nuevos_datos.append(df_part)
            except Exception as e:
                print(f"[X] Error zip {zip_file.name}: {e}")

        # 2. Archivos Excel directos (.xlsx, .xls) sin comprimir (nuevo formato WordPress)
        direct_excels = [
            f for f in carpeta.glob("*")
            if f.is_file() and f.suffix.lower() in [".xlsx", ".xls"]
        ]
        for excel_file in direct_excels:
            try:
                with open(excel_file, "rb") as f:
                    df_part = procesar_excel_a_tidy(
                        f, carpeta.name, target_subs
                    )
                    if df_part is not None:
                        nuevos_datos.append(df_part)
            except Exception as e:
                print(f"[X] Error excel {excel_file.name}: {e}")

        print("OK")
        archivos_procesados += 1

    if not nuevos_datos:
        print("[SLEEP] No hay datos nuevos para procesar.")
        return

    print(f"[PKG] Consolidando {len(nuevos_datos)} fragmentos...")
    df_total = pd.concat(nuevos_datos, ignore_index=True)
    df_final = corregir_fechas_y_tipos(df_total)

    # 3. Guardado Directo de Datos Raw (Sin resamplear)
    print("[SAVE] Actualizando archivos Parquet y CSV con datos RAW directos...")

    for subestacion, df_new in df_final.groupby("Subestacion"):
        safe_name = re.sub(r"[^\w\s-]", "", str(subestacion)).strip()
        if not safe_name:
            continue

        ruta_csv = RUTA_SALIDA / f"{safe_name}_3min.csv"

        if ruta_csv.exists() and not forzar_reproceso:
            try:
                df_old = pd.read_csv(ruta_csv)
                df_old["Timestamp"] = pd.to_datetime(df_old["Timestamp"])
                df_combined = pd.concat([df_old, df_new], ignore_index=True)
            except Exception:
                df_combined = df_new
        else:
            df_combined = df_new

        df_combined.drop_duplicates(subset=["Timestamp"], keep="last", inplace=True)
        df_combined.sort_values("Timestamp", inplace=True)

        df_combined["Fecha_Real"] = df_combined["Timestamp"].dt.date
        cols_meta = ["Subestacion", "Max_Diario_MW", "Hora_Pico_Reg"]
        for col in [c for c in cols_meta if c in df_combined.columns]:
            df_combined[col] = df_combined.groupby("Fecha_Real")[col].transform("last")

        df_combined.to_csv(ruta_csv, index=False, encoding="utf-8-sig")

        # Guardar en Parquet (Optimizado)
        RUTA_SALIDA_PARQUET = PROJECT_ROOT / "data" / "SE_Carga_3min_parquet"
        RUTA_SALIDA_PARQUET.mkdir(parents=True, exist_ok=True)

        ruta_parquet = RUTA_SALIDA_PARQUET / f"{safe_name}_3min.parquet"
        if "Hora_Real" in df_combined.columns:
            df_combined["Hora_Real"] = df_combined["Hora_Real"].astype(str)
        df_combined.to_parquet(ruta_parquet, index=False)

    print(f"[DONE] ¡Listo! Se procesaron {archivos_procesados} días nuevos.")

    # 4. Verificación Final de Consistencia (CSV vs Parquet)
    verificar_consistencia_parquet()


def verificar_consistencia_parquet():
    """
    Asegura que para cada CSV exista un Parquet actualizado.
    Si el CSV es más nuevo que el Parquet (o el Parquet no existe), lo regenera.
    """
    print("[SYNC] Verificando consistencia CSV -> Parquet...")
    RUTA_SALIDA_PARQUET = PROJECT_ROOT / "data" / "SE_Carga_3min_parquet"
    RUTA_SALIDA_PARQUET.mkdir(parents=True, exist_ok=True)

    csvs = list(RUTA_SALIDA.glob("*_3min.csv"))
    count_fixed = 0

    for csv_path in csvs:
        parquet_path = RUTA_SALIDA_PARQUET / csv_path.name.replace(".csv", ".parquet")

        necesita_update = False
        if not parquet_path.exists():
            necesita_update = True
        else:
            # Si el CSV es más nuevo que el Parquet (con un margen de 1 min)
            if csv_path.stat().st_mtime > parquet_path.stat().st_mtime + 60:
                necesita_update = True

        if necesita_update:
            try:
                print(f"   [FIX] Regenerando Parquet para: {csv_path.name}")
                df = pd.read_csv(csv_path)
                # Asegurar tipos
                if "Timestamp" in df.columns:
                    df["Timestamp"] = pd.to_datetime(df["Timestamp"])
                # Fix PyArrow: Convert time objects to string
                if "Hora_Real" in df.columns:
                    df["Hora_Real"] = df["Hora_Real"].astype(str)
                df.to_parquet(parquet_path, index=False)
                count_fixed += 1
            except Exception as e:
                print(f"   [X] Error regenerando {csv_path.name}: {e}")

    if count_fixed > 0:
        print(f"[SYNC] Se repararon {count_fixed} archivos Parquet desactualizados.")
    else:
        print("[SYNC] Todo en orden. Parquet sincronizado.")


if __name__ == "__main__":
    main_procesamiento()
