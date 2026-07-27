import streamlit as st
import pandas as pd
from src.etl import loader
from src.logic import metrics
from src.ui import cards, charts

# --- 1. CONFIGURACIÓN BÁSICA DE PÁGINA ---
st.set_page_config(
    page_title="CNDC - Monitoreo de Demanda Eléctrica",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)


# --- 2. INTERFAZ PRINCIPAL (UI) ---
def main():
    # --- BARRA LATERAL (SIDEBAR) ---
    st.sidebar.title("⚡ CNDC Bolivia")
    st.sidebar.caption("Sistema de Monitoreo de Carga Eléctrica y Clima")

    # Navegación Principal
    modo_vista = st.sidebar.radio(
        "Selecciona una vista:",
        [
            "🌐 Panorama General (SIN)",
            "⚡ Análisis por Subestación",
            "📈 Comparativa Multisubestación",
        ],
        index=0,
    )

    st.sidebar.divider()

    # Botón para Re-scraping / Actualizar datos
    if st.sidebar.button(
        "🔄 Actualizar Datos CNDC",
        help="Descarga e integra los datos más recientes del CNDC y clima",
        use_container_width=True,
    ):
        with st.spinner("Actualizando datos del CNDC y clima..."):
            try:
                import actualizar_datos

                actualizar_datos.main()
                st.cache_data.clear()
                st.sidebar.success("¡Datos actualizados con éxito!")
                st.rerun()
            except Exception as e:
                st.sidebar.error(f"Error al actualizar: {e}")

    # Obtener lista de subestaciones disponibles
    lista_subs = loader.obtener_subestaciones()

    if not lista_subs:
        st.error(
            "No se encontraron archivos de datos en la carpeta data/SE_Carga_3min_parquet."
        )
        return

    # ==========================================
    # VISTA 1: PANORAMA GENERAL DEL SIN
    # ==========================================
    if modo_vista == "🌐 Panorama General (SIN)":
        st.title("🌐 Monitoreo Global del Sistema Interconectado Nacional (SIN)")
        st.markdown(
            "Visión consolidada de demanda eléctrica y ubicación de las 61 subestaciones de Bolivia."
        )

        df_resumen = loader.cargar_resumen_sistema()

        if df_resumen is not None and not df_resumen.empty:
            # Fila de Métricas Globales Nativas
            col1, col2, col3, col4 = st.columns(4)

            total_subs = len(df_resumen)
            demanda_total = df_resumen["Ultimo_MW"].sum()
            max_demanda_historica = df_resumen["Pico_Historico_MW"].sum()
            id_top = df_resumen["Pico_Historico_MW"].idxmax()
            sub_mayor_demanda = df_resumen.loc[id_top]["Subestacion"]
            max_valor_top = df_resumen.loc[id_top]["Pico_Historico_MW"]

            cards.mostrar_tarjeta_metrica(
                col1,
                "Total Subestaciones",
                total_subs,
                "SE",
                "Monitoreadas activamente",
            )
            cards.mostrar_tarjeta_metrica(
                col2,
                "Demanda Última Registrada",
                demanda_total,
                "MW",
                "Suma del SIN",
            )
            cards.mostrar_tarjeta_metrica(
                col3,
                "Pico Histórico Consolidado",
                max_demanda_historica,
                "MW",
                "Capacidad pico acumulada",
            )
            cards.mostrar_tarjeta_metrica(
                col4,
                "Subestación Mayor Pico",
                sub_mayor_demanda,
                "",
                f"Pico: {max_valor_top:.2f} MW",
            )

            st.divider()

            # Mapa + Gráfico Top 10
            col_mapa, col_top = st.columns([1.2, 1])

            with col_mapa:
                fig_mapa = charts.crear_mapa_subestaciones(df_resumen)
                if fig_mapa:
                    st.plotly_chart(fig_mapa, use_container_width=True)

            with col_top:
                fig_top = charts.crear_grafico_top_subestaciones(df_resumen, top_n=10)
                if fig_top:
                    st.plotly_chart(fig_top, use_container_width=True)

            # Tabla Consolidada
            with st.expander(
                "📋 Tabla Consolidada de Subestaciones", expanded=False
            ):
                st.dataframe(
                    df_resumen.sort_values("Pico_Historico_MW", ascending=False),
                    column_config={
                        "Subestacion": "Subestación",
                        "Ultimo_MW": st.column_config.NumberColumn(
                            "Última Carga (MW)", format="%.2f MW"
                        ),
                        "Pico_Historico_MW": st.column_config.NumberColumn(
                            "Pico Histórico (MW)", format="%.2f MW"
                        ),
                        "Ultimo_Registro": st.column_config.DatetimeColumn(
                            "Último Registro", format="DD MMM YYYY, HH:mm"
                        ),
                    },
                    use_container_width=True,
                    height=350,
                )

    # ==========================================
    # VISTA 2: ANÁLISIS DETALLADO POR SUBESTACIÓN
    # ==========================================
    elif modo_vista == "⚡ Análisis por Subestación":
        seleccion = st.sidebar.selectbox("Selecciona una Subestación:", lista_subs)

        st.title(f"⚡ Análisis Detallado — Subestación {seleccion}")

        df_carga = loader.cargar_datos_subestacion(seleccion)
        df_clima = loader.cargar_datos_clima(seleccion)
        df_meta = loader.cargar_metadatos_trafos()

        if df_carga is not None and not df_carga.empty:
            # Métricas Nativas Nivel Subestación
            col1, col2, col3, col4 = st.columns(4)

            max_mw, fecha_pico, hora_pico, dias_desde = (
                metrics.calcular_pico_historico(df_carga)
            )
            ultimo_max, fecha_ultimo, hora_ultimo = (
                metrics.calcular_ultimo_pico_diario(df_carga)
            )
            capacidad_mva, pct_carga = metrics.calcular_estado_carga(
                df_meta, seleccion, ultimo_max
            )

            temp_actual = "N/A"
            if df_clima is not None and not df_clima.empty:
                temp_actual = f"{df_clima.iloc[-1]['Temperatura_C']:.1f} °C"

            cards.mostrar_tarjeta_metrica(
                col1,
                "Pico Histórico",
                max_mw,
                "MW",
                f"{fecha_pico} {hora_pico}",
                delta=f"Hace {dias_desde} días",
            )
            cards.mostrar_tarjeta_metrica(
                col2,
                "Último Pico Diario",
                ultimo_max,
                "MW",
                f"{fecha_ultimo} {hora_ultimo}",
            )
            cards.mostrar_tarjeta_metrica(
                col3,
                "Capacidad Instalada",
                capacidad_mva if capacidad_mva > 0 else "N/A",
                "MVA",
                f"Carga: {pct_carga:.1f}%"
                if capacidad_mva > 0
                else "Sin metadatos MVA",
            )
            cards.mostrar_tarjeta_metrica(
                col4, "Temperatura Local", temp_actual, "", "Open-Meteo SIN"
            )

            st.divider()

            # Pestañas de Análisis
            tab_grafico, tab_datos, tab_detalles = st.tabs(
                [
                    "📈 Curva de Carga y Clima",
                    "📊 Registro de Datos",
                    "ℹ️ Información Técnica",
                ]
            )

            with tab_grafico:
                fig_doble = charts.crear_grafico_doble_eje(
                    df_carga, df_clima, seleccion, capacidad_mva
                )
                st.plotly_chart(fig_doble, use_container_width=True)

            with tab_datos:
                st.subheader("Explorador de Registros (Resolución 3 minutos)")
                col_search, col_export = st.columns([3, 1])
                with col_export:
                    csv_data = df_carga.to_csv(index=False, encoding="utf-8-sig")
                    st.download_button(
                        label="📥 Descargar CSV",
                        data=csv_data,
                        file_name=f"{seleccion}_carga_3min.csv",
                        mime="text/csv",
                        use_container_width=True,
                    )

                st.dataframe(
                    df_carga,
                    column_config={
                        "Timestamp": st.column_config.DatetimeColumn(
                            "Fecha/Hora", format="DD MMM YYYY, HH:mm"
                        ),
                        "MW": st.column_config.NumberColumn(
                            "Potencia (MW)", format="%.2f MW"
                        ),
                        "Max_Diario_MW": st.column_config.NumberColumn(
                            "Máx Diario (MW)", format="%.2f MW"
                        ),
                        "Hora_Pico_Reg": "Hora Pico Registrada",
                    },
                    use_container_width=True,
                    height=450,
                )

            with tab_detalles:
                st.subheader("Ficha Técnica de la Subestación")
                col_d1, col_d2 = st.columns(2)
                with col_d1:
                    st.json(
                        {
                            "Subestación": seleccion,
                            "Registros Totales Carga": len(df_carga),
                            "Fecha Inicio": str(df_carga["Timestamp"].min()),
                            "Fecha Cierre": str(df_carga["Timestamp"].max()),
                            "Resolución Temporal": "3 minutos",
                        }
                    )
                with col_d2:
                    if df_clima is not None and not df_clima.empty:
                        st.json(
                            {
                                "Registros Clima Totales": len(df_clima),
                                "Temp Mínima Historica": f"{df_clima['Temperatura_C'].min():.1f} °C",
                                "Temp Máxima Historica": f"{df_clima['Temperatura_C'].max():.1f} °C",
                                "Temp Promedio": f"{df_clima['Temperatura_C'].mean():.1f} °C",
                            }
                        )

    # ==========================================
    # VISTA 3: COMPARATIVA MULTISUBESTACIÓN
    # ==========================================
    elif modo_vista == "📈 Comparativa Multisubestación":
        st.title("📈 Comparativa Multisubestaciones")
        st.markdown(
            "Selecciona varias subestaciones para comparar sus curvas de demanda superpuestas en el mismo gráfico."
        )

        subs_seleccionadas = st.multiselect(
            "Selecciona subestaciones a comparar:",
            lista_subs,
            default=lista_subs[:3] if len(lista_subs) >= 3 else lista_subs,
        )

        if subs_seleccionadas:
            dict_subs = {}
            for sub in subs_seleccionadas:
                dict_subs[sub] = loader.cargar_datos_subestacion(sub)

            fig_comp = charts.crear_grafico_comparativo(dict_subs)
            if fig_comp:
                st.plotly_chart(fig_comp, use_container_width=True)
        else:
            st.info(
                "Por favor selecciona al menos una subestación para generar la comparativa."
            )


# --- 3. PUNTO DE ENTRADA ---
if __name__ == "__main__":
    main()
