import plotly.express as px
import plotly.graph_objects as gg
from plotly.subplots import make_subplots
import pandas as pd


def crear_grafico_doble_eje(df_carga, df_clima, nombre_subestacion, capacidad_mva=None):
    """
    Crea un gráfico interactivo con doble eje Y:
    - Eje Principal (Izquierdo): Potencia Activa (MW)
    - Eje Secundario (Derecho): Temperatura Ambiental (°C)
    """
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # 1. Trazo de Carga Eléctrica (MW)
    if df_carga is not None and not df_carga.empty:
        fig.add_trace(
            gg.Scatter(
                x=df_carga["Timestamp"],
                y=df_carga["MW"],
                name="Demanda Eléctrica (MW)",
                mode="lines",
                line=dict(color="#00D2D3", width=1.5),
                hovertemplate="%{x|%d %b %Y %H:%m}<br><b>%{y:.2f} MW</b>",
            ),
            secondary_y=False,
        )

        # Línea de Capacidad Nominal si está disponible
        if capacidad_mva and capacidad_mva > 0:
            fig.add_hline(
                y=capacidad_mva,
                line_dash="dash",
                line_color="#FF6B6B",
                annotation_text=f"Capacidad Nominal: {capacidad_mva} MVA",
                annotation_position="top right",
            )

    # 2. Trazo de Temperatura (°C)
    if df_clima is not None and not df_clima.empty:
        fig.add_trace(
            gg.Scatter(
                x=df_clima["Timestamp"],
                y=df_clima["Temperatura_C"],
                name="Temperatura (°C)",
                mode="lines",
                line=dict(color="#FF9F43", width=1.2, dash="dot"),
                opacity=0.8,
                hovertemplate="%{x|%d %b %Y %H:%m}<br><b>%{y:.1f} °C</b>",
            ),
            secondary_y=True,
        )

    # Configuración de Layout Oscuro y Elegante
    fig.update_layout(
        title=dict(
            text=f"⚡ Curva de Carga y Clima — Subestación {nombre_subestacion}",
            font=dict(size=18, color="#FFFFFF"),
        ),
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(14,17,23,0.7)",
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(color="#CCCCCC"),
        ),
        margin=dict(l=40, r=40, t=60, b=40),
        xaxis=dict(
            showgrid=True,
            gridcolor="#222733",
            rangeslider=dict(visible=True, thickness=0.05),
            type="date",
        ),
    )

    fig.update_yaxes(
        title_text="Potencia (MW)",
        title_font=dict(color="#00D2D3"),
        tickfont=dict(color="#00D2D3"),
        showgrid=True,
        gridcolor="#222733",
        secondary_y=False,
    )

    fig.update_yaxes(
        title_text="Temperatura (°C)",
        title_font=dict(color="#FF9F43"),
        tickfont=dict(color="#FF9F43"),
        showgrid=False,
        secondary_y=True,
    )

    return fig


def crear_mapa_subestaciones(df_resumen):
    """
    Crea un mapa interactivo de dispersión con las subestaciones de Bolivia en Plotly.
    """
    if df_resumen is None or df_resumen.empty:
        return None

    df_mapa = df_resumen.dropna(subset=["Latitud", "Longitud"]).copy()
    if df_mapa.empty:
        return None

    fig = px.scatter_mapbox(
        df_mapa,
        lat="Latitud",
        lon="Longitud",
        size="Pico_Historico_MW",
        color="Ultimo_MW",
        hover_name="Subestacion",
        hover_data={
            "Latitud": False,
            "Longitud": False,
            "Pico_Historico_MW": ":.2f MW",
            "Ultimo_MW": ":.2f MW",
        },
        color_continuous_scale=px.colors.sequential.Tealgrn,
        size_max=22,
        zoom=5,
        center={"lat": -17.0, "lon": -65.0},
        mapbox_style="carto-darkmatter",
        title="<b>🗺️ Ubicación Geográfica de Subestaciones del SIN</b>",
    )

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=40, b=10),
        coloraxis_colorbar=dict(title="Potencia (MW)"),
        height=500,
    )

    return fig


def crear_grafico_top_subestaciones(df_resumen, top_n=10):
    """
    Crea un gráfico de barras horizontales con el Top N de subestaciones con mayor pico histórico.
    """
    if df_resumen is None or df_resumen.empty:
        return None

    df_top = df_resumen.sort_values("Pico_Historico_MW", ascending=True).tail(top_n)

    fig = px.bar(
        df_top,
        x="Pico_Historico_MW",
        y="Subestacion",
        orientation="h",
        text_auto=".2f",
        title=f"<b>🏆 Top {top_n} Subestaciones con Mayor Demanda Histórica (MW)</b>",
        color="Pico_Historico_MW",
        color_continuous_scale=px.colors.sequential.Viridis,
    )

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(14,17,23,0.7)",
        xaxis_title="Pico Máximo (MW)",
        yaxis_title="",
        coloraxis_showscale=False,
        margin=dict(l=20, r=20, t=50, b=20),
        height=450,
    )

    return fig


def crear_grafico_comparativo(dict_subestaciones):
    """
    Toma un diccionario {nombre_sub: df_carga} y genera una curva comparativa superpuesta.
    """
    if not dict_subestaciones:
        return None

    fig = gg.Figure()

    colores = ["#00D2D3", "#FF9F43", "#54A0FF", "#5F27CD", "#FF6B6B", "#10AC84"]

    for idx, (nombre, df) in enumerate(dict_subestaciones.items()):
        if df is not None and not df.empty:
            color = colores[idx % len(colores)]
            fig.add_trace(
                gg.Scatter(
                    x=df["Timestamp"],
                    y=df["MW"],
                    name=nombre,
                    mode="lines",
                    line=dict(width=1.5, color=color),
                )
            )

    fig.update_layout(
        title="<b>📈 Comparativa Multisubestaciones en Tiempo Real</b>",
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(14,17,23,0.7)",
        hovermode="x unified",
        margin=dict(l=20, r=20, t=50, b=20),
        xaxis=dict(showgrid=True, gridcolor="#222733"),
        yaxis=dict(title="Potencia (MW)", showgrid=True, gridcolor="#222733"),
        height=450,
    )

    return fig
