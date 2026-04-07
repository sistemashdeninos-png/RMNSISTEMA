import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import io
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# 1. Configuración de la interfaz
st.set_page_config(page_title="Sistema RMN", page_icon="🏥", layout="centered")

# ==========================================
# ⚠️ PON TUS DATOS AQUÍ
# ==========================================
URL_HOJA = "https://docs.google.com/spreadsheets/d/1gT3RbP6uZB2buAedGGlTHpVCr600LRzXooZrVOH8Bjs/edit?usp=sharing"
ID_CARPETA_DRIVE = "1F0o2lI-eNZCz8IXYGsIYTfh5T-0vWSv9"
# ==========================================

# 2. Conexión a las APIs (Sheets y Drive)
@st.cache_resource
def obtener_credenciales():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    skey = st.secrets["gcp_service_account"]
    return Credentials.from_service_account_info(skey, scopes=scopes)

@st.cache_resource
def conectar_sheets():
    return gspread.authorize(obtener_credenciales())

def conectar_drive():
    return build('drive', 'v3', credentials=obtener_credenciales())

# 3. Traer los datos
try:
    cliente = conectar_sheets()
    hoja = cliente.open_by_url(URL_HOJA).worksheet("Respuestas de formulario 1")
    datos = hoja.get_all_records()
    df = pd.DataFrame(datos)
except Exception as e:
    st.error(f"Error técnico al conectar: {e}")
    st.stop()

# 4. MENÚ LATERAL
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/3004/3004451.png", width=100)
st.sidebar.title("Navegación")
opcion = st.sidebar.radio("Seleccione el módulo:", ["Buscador Administrativo", "Carga de Informes (Médicos)"])

# ==========================================
# MÓDULO 1: BUSCADOR ADMINISTRATIVO
# ==========================================
if opcion == "Buscador Administrativo":
    st.title("🏥 Buscador de Pacientes")
    st.markdown("---")
    
    dni_input = st.text_input("Ingrese el DNI del paciente:")

    if st.button("Buscar Paciente"):
        if dni_input:
            resultado = df[df['DNI / Documento'].astype(str).str.strip() == str(dni_input).strip()]
            
            if not resultado.empty:
                st.success("✅ Paciente encontrado")
                paciente = resultado.iloc[0]
                
                st.info(f"**Nombre y apellido:** {paciente['Nombre y apellido del paciente']}")
                st.write(f"**DNI / Documento:** {paciente['DNI / Documento']}")
                st.write(f"**Edad:** {paciente['Edad:']}")
                st.write(f"**Peso (kg):** {paciente['Peso (kg)']}")
                st.write(f"**Altura:** {paciente['Altura']}")
                st.write(f"**Teléfonos:** {paciente['Teléfonos de contacto (familiar del paciente)']}")
                
                st.divider()
                st.subheader("👨‍⚕️ Datos de la Solicitud")
                st.write(f"**Solicitado como:** {paciente['Solicitado como']}")
                st.write(f"**Profesional:** {paciente['Nombre del Profesional']}")
                st.write(f"**Especialidad:** {paciente['Especialidad']}")
                st.write(f"**Fecha de carga:** {paciente['Marca temporal']}")
                
                st.divider()
                st.subheader("🏥 Detalles del Estudio Clínico")
                st.write(f"**Tipo de RMN:** {paciente['Tipo de RMN CON ANESTESIA requerida']}")
                st.write(f"**Requiere contraste:** {paciente['¿Requiere contraste?']}")
                st.write(f"**Reacción a contraste:** {paciente['¿Antecedentes de reacción a contraste?']}")
                st.write(f"**Motivo anestesia:** {paciente['MOTIVO DE ANESTESIA']}")
                st.write(f"**Diagnóstico:** {paciente['DIAGNÓSTICO PRESUNTIVO']}")
                st.write(f"**Dispositivos médicos:** {paciente['¿Dispositivos médicos?']}")
                
                # Mostrar link del informe si existe
                if 'Informe Médico PDF' in paciente and str(paciente['Informe Médico PDF']).startswith('http'):
                    st.divider()
                    st.success("📄 Este paciente ya cuenta con un informe subido.")
                    st.markdown(f"[Haga clic aquí para ver/descargar el Informe PDF]({paciente['Informe Médico PDF']})")
                
            else:
                st.error("❌ No se encontró ningún paciente con el DNI ingresado.")
        else:
            st.warning("⚠️ Por favor, ingrese un DNI válido.")

# ==========================================
# MÓDULO 2: CARGA DE INFORMES (MÉDICOS)
# ==========================================
elif opcion == "Carga de Informes (Médicos)":
    st.title("🩺 Carga de Informes Médicos")
    st.markdown("---")
    
    dni_medico = st.text_input("Ingrese el DNI del paciente para adjuntar informe:")
    
    if dni_medico:
        resultado = df[df['DNI / Documento'].astype(str).str.strip() == str(dni_medico).strip()]
        
        if not resultado.empty:
            paciente = resultado.iloc[0]
            st.success(f"Paciente seleccionado: **{paciente['Nombre y apellido del paciente']}**")
            
            # Subidor de archivos
            archivo_pdf = st.file_uploader("Seleccione el informe en PDF", type=["pdf"])
            
            if archivo_pdf is not None:
                if st.button("Subir y Guardar Informe"):
                    with st.spinner("Subiendo a Google Drive y actualizando base de datos..."):
                        try:
                            # 1. Subir a Drive
                            drive_service = conectar_drive()
                            file_metadata = {
                                'name': f"INFORME_{paciente['DNI / Documento']}_{paciente['Nombre y apellido del paciente']}.pdf",
                                'parents': [ID_CARPETA_DRIVE]
                            }
                            media = MediaIoBaseUpload(io.BytesIO(archivo_pdf.getvalue()), mimetype='application/pdf', resumable=True)
                            
                            archivo_subido = drive_service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink').execute()
                            link_pdf = archivo_subido.get('webViewLink')
                            
                            # Dar permiso de lectura al link
                            drive_service.permissions().create(
                                fileId=archivo_subido.get('id'),
                                body={'type': 'anyone', 'role': 'reader'}
                            ).execute()
                            
                            # 2. Actualizar el Excel
                            fila_excel = int(resultado.index[0]) + 2 
                            columna_informe = df.columns.get_loc("Informe Médico PDF") + 1
                            
                            hoja.update_cell(fila_excel, columna_informe, link_pdf)
                            
                            st.success("✅ ¡Informe guardado y vinculado al paciente con éxito!")
                            st.markdown(f"[Ver archivo subido]({link_pdf})")
                            
                        except Exception as e:
                            st.error(f"Ocurrió un error al subir el archivo: {e}")
        else:
            st.error("No hay registros para este DNI.")
