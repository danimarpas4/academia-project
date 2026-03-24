import os
import django
import PyPDF2
import sys

# Configurar el entorno de Django
sys.path.append('/home/usuario/ProMilitar/academia_project')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'academia_project.settings')
django.setup()

from simulador.models import Tema

def extraer_texto_pdf(pdf_path):
    texto = ""
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            for page_num in range(len(reader.pages)):
                page = reader.pages[page_num]
                texto += page.extract_text() + "\n"
    except Exception as e:
        print(f"Error leyendo {pdf_path}: {e}")
    return texto

def procesar_temas():
    temas = Tema.objects.exclude(archivo_pdf='')
    print(f"Procesando {temas.count()} temas con PDF...")
    
    for tema in temas:
        if tema.archivo_pdf:
            path_completo = tema.archivo_pdf.path
            if os.path.exists(path_completo):
                print(f"Extrayendo texto de: {tema.nombre}")
                texto_extraido = extraer_texto_pdf(path_completo)
                if texto_extraido.strip():
                    tema.contenido_texto = texto_extraido
                    tema.save()
                    print(f"✅ Texto guardado para {tema.nombre}")
                else:
                    print(f"⚠️ No se pudo extraer texto de {tema.nombre}")
            else:
                print(f"❌ Archivo no encontrado: {path_completo}")

if __name__ == "__main__":
    procesar_temas()
