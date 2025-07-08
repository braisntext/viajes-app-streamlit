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
    # Preprocesar texto
    text = text.replace("\n", " ").replace("  ", " ").strip()

    # Lugar / Hotel
    lugar_match = re.search(r"(?i)Property\s*:\s*(.*?)\s*(Address|Dirección)\s*:", text)
    lugar = lugar_match.group(1).strip() if lugar_match else ""

    # Fechas
    arrival_match = re.search(r"(?i)Arrival\s*:\s*(\w+ \d{1,2}, \d{4})", text)
    departure_match = re.search(r"(?i)Departure\s*:\s*(\w+ \d{1,2}, \d{4})", text)

    fecha_checkin = arrival_match.group(1) if arrival_match else ""
    fecha_checkout = departure_match.group(1) if departure_match else ""
    check_range = f"{fecha_checkin} – {fecha_checkout}" if fecha_checkin and fecha_checkout else ""

    if not lugar or not fecha_checkin:
        return None  # Descartar si falta algo clave

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
