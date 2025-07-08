import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
import io
import re

st.set_page_config(page_title="Reservas de Viaje", layout="wide")
st.title("📅 Gestor privado de reservas de viaje")

# Inicializar datos si no existen
def init_session():
    if "data" not in st.session_state:
        st.session_state.data = []
    if "df" not in st.session_state:
        st.session_state.df = pd.DataFrame(columns=[
            "Fecha", "Lugar / Hotel", "Check-in / Check-out", "Enlace de reserva", "Enlace cómo llegar"
        ])

init_session()

# PDF uploader
st.header("📎 Subir reservas en PDF")
pdf_files = st.file_uploader("Sube uno o varios PDFs de reservas de hotel", type="pdf", accept_multiple_files=True)

# Text input (para Airbnb u otros)
st.header("✍️ Pegado manual de reserva")
raw_text = st.text_area("Pega aquí el contenido de un correo de confirmación (ej. Airbnb)")

# Función para extraer texto de PDF
def extract_text_from_pdf(file):
    doc = fitz.open(stream=file.read(), filetype="pdf")
    text = "\n".join(page.get_text() for page in doc)
    return text

# Función de parsing básico
@st.cache_data
def parse_text_to_entry(text):
    # Solo procesamos si parece ser una reserva de hotel
    if "hotel" not in text.lower() and "property" not in text.lower():
        return None

    # Buscar nombre del hotel
    lugar_match = re.search(r"(?i)(Property|Establecimiento)\s*:\s*(.+)", text)
    lugar = lugar_match.group(2).strip() if lugar_match else ""

    # Buscar fechas de check-in y check-out
    fechas = re.findall(r"([A-Z][a-z]+ \d{1,2}, \d{4})", text)
    fecha_checkin = fechas[0] if len(fechas) >= 1 else ""
    fecha_checkout = fechas[1] if len(fechas) >= 2 else ""
    check_range = f"{fecha_checkin} – {fecha_checkout}" if fecha_checkin and fecha_checkout else ""

    return {
        "Fecha": fecha_checkin,
        "Lugar / Hotel": lugar,
        "Check-in / Check-out": check_range,
        "Enlace de reserva": "",
        "Enlace cómo llegar": ""
    }

# Procesar PDFs
if pdf_files:
    for file in pdf_files:
        text = extract_text_from_pdf(file)
        entry = parse_text_to_entry(text)
        if entry:
            st.session_state.data.append(entry)

# Procesar texto pegado
if raw_text:
    entry = parse_text_to_entry(raw_text)
    if entry:
        st.session_state.data.append(entry)

# Convertir a DataFrame
if st.session_state.data:
    st.session_state.df = pd.DataFrame(st.session_state.data)

# Mostrar tabla editable
st.header("🧾 Tabla de reservas")
st.session_state.df = st.data_editor(st.session_state.df, num_rows="dynamic", use_container_width=True)

# Exportar CSV
st.download_button(
    "⬇️ Descargar CSV",
    data=st.session_state.df.to_csv(index=False),
    file_name="reservas.csv",
    mime="text/csv"
) 
