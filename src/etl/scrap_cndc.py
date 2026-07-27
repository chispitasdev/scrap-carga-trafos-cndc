import requests
from pathlib import Path
from datetime import datetime, timedelta
import time

# --- CONFIGURACIÓN ---
# Definir raíz del proyecto (2 niveles arriba: src/etl -> src -> root)
PROJECT_ROOT = Path(__file__).resolve().parents[2]

RUTA_BASE = PROJECT_ROOT / "data" / "cndc"

# Patrón 1: WordPress 2026 XLSX directo (sin compresión)
NEW_BASE_URL = "https://www.cndc.bo/wp-content/uploads/mem/estadisticas/diaria/{year}/{month}/deener_{ddmmyy}.xlsx"
# Patrón 2: WordPress 2025 ZIP (sin subcarpeta de mes)
WP_ZIP_2025_URL = "https://www.cndc.bo/wp-content/uploads/mem/estadisticas/diaria/{year}/deener_{ddmmyy}.zip"
# Patrón 3: Antiguo directo ZIP
OLD_BASE_URL = "https://www.cndc.bo/media/archivos/boletindiario/deener_{ddmmyy}.zip"


def obtener_fechas_faltantes_cndc():
    """
    Escanea desde 2024-09-01 hasta hoy y retorna una lista de fechas (datetime)
    cuyas carpetas en data/cndc/ no existen o están vacías.
    """
    fecha_inicio = datetime(2024, 9, 1)
    fecha_fin = datetime.now()
    cur = fecha_inicio
    faltantes = []

    while cur <= fecha_fin:
        fecha_dir = RUTA_BASE / cur.strftime("%Y-%m-%d")
        if not fecha_dir.exists() or not any(fecha_dir.iterdir()):
            faltantes.append(cur)
        cur += timedelta(days=1)

    return faltantes


def descargar_incremental():
    print("[INFO] ACTUALIZANDO CNDC (SCANNER DE FECHAS FALTANTES)...")

    RUTA_BASE.mkdir(parents=True, exist_ok=True)

    fechas_a_descargar = obtener_fechas_faltantes_cndc()
    print(f"[DATE] Detectadas {len(fechas_a_descargar)} fechas pendientes por descargar.")

    if not fechas_a_descargar:
        print("[OK] Todos los días requeridos ya están descargados en data/cndc.")
        return

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    })

    count_ok = 0

    for fecha_actual in fechas_a_descargar:
        year_4d = fecha_actual.strftime("%Y")
        month_2d = fecha_actual.strftime("%m")
        ddmmyy = fecha_actual.strftime("%d%m%y")
        fecha_dir = fecha_actual.strftime("%Y-%m-%d")

        urls_a_probar = [
            (NEW_BASE_URL.format(year=year_4d, month=month_2d, ddmmyy=ddmmyy), f"deener_{ddmmyy}.xlsx"),
            (NEW_BASE_URL.format(year=year_4d, month=month_2d, ddmmyy=ddmmyy).replace(".xlsx", ".xls"), f"deener_{ddmmyy}.xls"),
            (WP_ZIP_2025_URL.format(year=year_4d, ddmmyy=ddmmyy), f"deener_{ddmmyy}.zip"),
            (OLD_BASE_URL.format(ddmmyy=ddmmyy), f"deener_{ddmmyy}.zip"),
        ]

        descargado = False

        for url, nombre_archivo in urls_a_probar:
            try:
                resp = session.get(url, stream=True, timeout=12)
                if resp.status_code == 200 and len(resp.content) > 1000:
                    carpeta = RUTA_BASE / fecha_dir
                    carpeta.mkdir(exist_ok=True)
                    archivo_path = carpeta / nombre_archivo

                    with open(archivo_path, "wb") as f:
                        f.write(resp.content)

                    print(f" [DOWN] {fecha_dir} -> [OK {nombre_archivo}]")
                    descargado = True
                    count_ok += 1
                    break
            except Exception:
                continue

        if not descargado:
            print(f" [DOWN] {fecha_dir} -> [X No disponible]")

        time.sleep(0.1)

    print(f"[FIN] Descarga de CNDC terminada. Se descargaron {count_ok} días nuevos.")


if __name__ == "__main__":
    descargar_incremental()
