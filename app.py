import streamlit as st
import pandas as pd
from src.etl import loader
from src.logic import metrics
from src.ui import cards, charts

# --- 1. CONFIGURACIÓN BÁSICA DE PÁGINA (RAMA PRUEBA1 - MINIMAL) ---
st.set_page_config(
    page_title="CNDC RAW Stream — Prueba 1",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)


def main():
    # --- BARRA LATERAL MINIMALISTA ---
    st.sidebar.markdown("### 📌 Rama: `prueba1`")
    st.sidebar.caption("⚡ **Modo SCADA RAW Nativo** (Sin resampleo)")

    st.sidebar.info(
        "💡 Esta rama opera de forma 100% aislada sobre datos RAW en `data/SE_Carga_RAW_parquet`."
    )

    st.sidebar.divider()

    # Selector de Subestación
    lista_subs = loader.obtener_subestaciones()
    if not lista_subs:
        st.sidebar.warning("Cargando base de datos RAW...")
        st.error("No se encontraron archivos en la carpeta de datos RAW.")
        return

    seleccion = st.sidebar.selectbox("🎯 Subestación Objetivo:", lista_subs, index=0)

    st.sidebar.divider()

    if st.sidebar.button("🔄 Sincronizar Datos RAW", width="stretch"):
        with st.spinner("Actualizando flujo RAW..."):
            try:
                import actualizar_datos
                actualizar_datos.main()
                st.cache_data.clear()
                st.sidebar.success("¡Datos RAW sincronizados!")
                st.rerun()
            except Exception as e:
                st.sidebar.error(f"Error: {e}")

    # --- ENCABEZADO MINIMALISTA ---
    st.title(f"⚡ CNDC SCADA RAW — Subestación {seleccion}")
    st.caption("🔍 Visualización directa sin interpolación temporal | Datos nátivos del CNDC Bolivia")

    # Cargar datos
    df_carga = loader.cargar_datos_subestacion(seleccion)
    df_clima = loader.cargar_datos_clima(seleccion)
    df_meta = loader.cargar_metadatos_trafos()

    if df_carga is not None and not df_carga.empty:
        # --- FILA DE MÉTRICAS MINIMALISTAS NATIVAS ---
        col1, col2, col3, col4 = st.columns(4)

        max_mw, fecha_pico, hora_pico, dias_desde = metrics.calcular_pico_historico(df_carga)
        ultimo_mw = df_carga.iloc[-1]["MW"]
        capacidad_mva, pct_carga = metrics.calcular_estado_carga(df_meta, seleccion, max_mw)

        temp_str = "N/A"
        if df_clima is not None and not df_clima.empty:
            temp_str = f"{df_clima.iloc[-1]['Temperatura_C']:.1f} °C"

        cards.mostrar_tarjeta_metrica(col1, "Última Carga RAW", ultimo_mw, "MW", f"Lectura directa SCADA")
        cards.mostrar_tarjeta_metrica(col2, "Pico Histórico RAW", max_mw, "MW", f"{fecha_pico} {hora_pico}")
        cards.mostrar_tarjeta_metrica(col3, "Temperatura Horaria", temp_str, "", "Open-Meteo SIN")
        cards.mostrar_tarjeta_metrica(col4, "Total Lecturas RAW", len(df_carga), "puntos", "Sin resampleo 3-min")

        st.divider()

        # --- SECCIÓN PRINCIPAL: GRÁFICO ULTRA CLEAN ---
        st.markdown("### 📈 Curva de Carga y Clima Nativa")
        fig_doble = charts.crear_grafico_doble_eje(df_carga, df_clima, seleccion, capacidad_mva)
        if fig_doble:
            st.plotly_chart(fig_doble, width="stretch")

        # --- SECCIÓN SECUNDARIA: EXPLORADOR RAW MINIMALISTA ---
        with st.expander("📋 Explorar Registros RAW Directos (CSV / Tabla)", expanded=False):
            col_info, col_dl = st.columns([3, 1])
            with col_dl:
                csv_data = df_carga.to_csv(index=False, encoding="utf-8-sig")
                st.download_button(
                    label="📥 Exportar CSV RAW",
                    data=csv_data,
                    file_name=f"{seleccion}_SCADA_RAW.csv",
                    mime="text/csv",
                    width="stretch",
                )

            st.dataframe(
                df_carga,
                column_config={
                    "Timestamp": st.column_config.DatetimeColumn("Marca de Tiempo SCADA", format="DD MMM YYYY, HH:mm"),
                    "MW": st.column_config.NumberColumn("Potencia (MW)", format="%.2f MW"),
                    "Max_Diario_MW": st.column_config.NumberColumn("Máx Diario (MW)", format="%.2f MW"),
                },
                width="stretch",
                height=350,
            )
    else:
        st.info("No se encontraron registros RAW para esta subestación.")


if __name__ == "__main__":
    main()
