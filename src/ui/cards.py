import streamlit as st


def mostrar_tarjeta_metrica(
    container, titulo, valor, unidad="", subtitulo="", delta=None, help_text=None
):
    """
    Renderiza una tarjeta de métrica elegante utilizando ÚNICAMENTE componentes nativos de Streamlit.
    """
    with container:
        with st.container(border=True):
            if isinstance(valor, (int, float)):
                valor_fmt = f"{valor:.2f} {unidad}".strip()
            else:
                valor_fmt = f"{valor} {unidad}".strip()

            st.metric(
                label=titulo,
                value=valor_fmt,
                delta=delta,
                help=help_text or subtitulo,
            )
            if subtitulo:
                st.caption(subtitulo)
