from pathlib import Path

# --- RUTAS DE ARCHIVOS (RAMA PRUEBA1 - RAW ISOLATED) ---
PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUTA_DATOS = PROJECT_ROOT / "data" / "SE_Carga_RAW_parquet"
RUTA_CLIMA = PROJECT_ROOT / "data" / "SE_Clima_RAW_parquet"
RUTA_TRANSFORMADORES = PROJECT_ROOT / "data" / "TRANSFORMADORES"
