import os
from PIL import Image, ImageDraw

def create_dummy(filename, color, text):
    img = Image.new('RGB', (800, 600), color=color)
    d = ImageDraw.Draw(img)
    d.text((300, 280), text, fill=(255,255,255))
    img.save(filename)

create_dummy('source/fachada1.jpg', (100, 0, 0), "Fachada 1")
create_dummy('source/fachada2.jpg', (100, 0, 0), "Fachada 2")
create_dummy('source/cocina1.jpg', (0, 100, 0), "Cocina 1")
create_dummy('source/exterior.jpg', (0, 0, 100), "Exterior Solo")

print("Imágenes de prueba creadas en source/")
