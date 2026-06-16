import os
import sys
import json
import shutil
from PIL import Image
from jinja2 import Environment, FileSystemLoader
from google import genai
from google.genai import types

def procesar_imagenes_con_gemini(archivos_imagenes, texto_contexto=""):
    print("Iniciando clasificación con Gemini...")
    # Intentar obtener API KEY
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ADVERTENCIA: No se encontró GEMINI_API_KEY. Usando fallback...")
        return []

    client = genai.Client(api_key=api_key)
    
    # Preparar el contenido para Gemini (lista mixta de texto e imagenes)
    contents = []
    
    prompt = """Actúa como un organizador inteligente de presentaciones de relevamientos técnicos de locales. 
A continuación te enviaré una serie de imágenes (cada una precedida por su nombre de archivo).
Tu tarea es clasificar y agrupar estas imágenes en diapositivas (slides) basándote en su temática, similitud o lógica visual, ordenándolas bajo una estructura específica.

Reglas ESTRICTAS de clasificación y orden:
1. Divide el contenido en dos categorías macro:
   - **Equipamiento**: Todo lo relacionado con maquinaria, pantallas, freidoras, heladeras, cocinas, etc. Estas diapositivas deben ir al PRINCIPIO de la presentación.
   - **Infraestructura / Edificio**: Todo lo relacionado con paredes, techos, pisos, fachadas, baños, detalles edilicios, etc. Estas diapositivas deben ir al FINAL de la presentación.
2. Agrupa un máximo de 4 imágenes por diapositiva dentro de cada temática específica (por ejemplo, agrupa dos fotos del mismo equipo, o dos fotos del mismo daño edilicio).
3. **Regla de No Mezclar Equipos Principales**: No mezcles equipos de distinta índole en una misma diapositiva si tienen fotos propias. Por ejemplo: mantén las fotos del horno juntas en su propio slide (ej. 'Horno'), y las de la freidora en su propio slide separado (ej. 'Freidora'). ¡No los mezcles!
4. **Optimización de Equipos Solitarios**: Si hay equipos que solo tienen 1 foto huérfana (ej. una cafetera y una heladera), agrúpalos en una misma diapositiva bajo una temática general (ej. 'Otros Equipos' o 'Equipamiento Varios') para no generar slides casi vacíos.
5. **Agrupación en Infraestructura**: Agrupa elementos del mismo tipo de infraestructura hasta 4 por diapositiva (ej. todas las fotos de puertas juntas, todas las fotos de baños juntas, techos juntos, etc.).
6. Devuelve ÚNICAMENTE un JSON con el siguiente formato, sin markdown ni explicaciones:
{
  "slides": [
    {
      "theme": "Título corto de la temática (ej. 'Hornos', 'Freidoras', 'Puertas', 'Baños')",
      "images": ["nombre_archivo1.jpg", "nombre_archivo2.jpg"]
    }
  ]
}
"""
    if texto_contexto:
        prompt += f"\n\nContexto adicional del usuario: {texto_contexto}\n"
    
    contents.append(prompt)
    
    # Cargar imágenes
    for img_path in archivos_imagenes:
        nombre_archivo = os.path.basename(img_path)
        contents.append(f"Archivo: {nombre_archivo}")
        img = Image.open(img_path)
        contents.append(img)
        
    print(f"Llamando a Gemini con {len(archivos_imagenes)} imágenes...")
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=contents,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            )
        )
        
        # Parsear respuesta JSON
        try:
            # Eliminar posibles bloques de markdown en la respuesta si Gemini los incluye ignorando la directiva
            texto_resp = response.text.strip()
            if texto_resp.startswith("```json"):
                texto_resp = texto_resp[7:]
            if texto_resp.endswith("```"):
                texto_resp = texto_resp[:-3]
                
            data = json.loads(texto_resp)
            return data.get("slides", [])
        except json.JSONDecodeError:
            print("Error: Gemini no devolvió un JSON válido. Respuesta en crudo:")
            print(response.text)
            return []
    except Exception as e:
        print(f"Error al comunicar con Gemini: {e}")
        return []

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    source_dir = os.path.join(base_dir, "source")
    output_dir = os.path.join(base_dir, "docs")
    slides_json_path = os.path.join(output_dir, "slides.json")
    
    # Crear carpetas si no existen
    os.makedirs(source_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)
    
    # Extensiones validas
    exts_validas = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
    
    archivos_imagenes = []
    texto_contexto = ""
    
    for filename in os.listdir(source_dir):
        ext = os.path.splitext(filename)[1].lower()
        path_completo = os.path.join(source_dir, filename)
        
        if ext in exts_validas:
            archivos_imagenes.append(path_completo)
        elif ext == '.txt':
            with open(path_completo, 'r', encoding='utf-8') as f:
                texto_contexto += f.read() + "\n"
                
    if not archivos_imagenes:
        print("No se encontraron imágenes en la carpeta 'source'.")
        sys.exit(0)

    # Verificar si se quiere refrescar o si no existe slides.json
    refresh = "--refresh" in sys.argv or "-r" in sys.argv
    
    if os.path.exists(slides_json_path) and not refresh:
        print(f"Cargando estructura de diapositivas existente desde: {slides_json_path}")
        with open(slides_json_path, 'r', encoding='utf-8') as f:
            slides = json.load(f)
    else:
        # 1. Llamar a Gemini para agrupar
        slides = procesar_imagenes_con_gemini(archivos_imagenes, texto_contexto)
        
        # Si Gemini falló o devolvió vacío, fallback
        if not slides:
            print("Usando fallback de agrupación simple (1 imagen por slide).")
            for img in archivos_imagenes:
                slides.append({
                    "theme": "Sin clasificar",
                    "images": [os.path.basename(img)]
                })
        else:
            print("Clasificación exitosa.")
            
        # Guardar la estructura en JSON para permitir ediciones manuales
        with open(slides_json_path, 'w', encoding='utf-8') as f:
            json.dump(slides, f, indent=2, ensure_ascii=False)
        print(f"Estructura guardada en: {slides_json_path}")

    # 2. Copiar imágenes al output para que el HTML pueda leerlas usando rutas relativas
    output_assets_dir = os.path.join(output_dir, "assets")
    os.makedirs(output_assets_dir, exist_ok=True)
    
    for img_path in archivos_imagenes:
        shutil.copy2(img_path, output_assets_dir)
        
    # Ajustar rutas en la estructura `slides` para el HTML
    for slide in slides:
        rutas_relativas = []
        for img_name in slide.get("images", []):
            rutas_relativas.append(f"assets/{img_name}")
        slide["images"] = rutas_relativas
        
    # 3. Generar HTML con Jinja2
    print("Generando HTML...")
    env = FileSystemLoader(base_dir)
    jinja_env = Environment(loader=env)
    template = jinja_env.get_template('template.html')
    
    html_output = template.render(slides=slides)
    
    output_path = os.path.join(output_dir, 'index.html')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_output)
        
    print(f"¡Éxito! Presentación generada en: {output_path}")

if __name__ == "__main__":
    main()
