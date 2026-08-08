from pathlib import Path
import sys

import pypdfium2 as pdfium
from PIL import Image, ImageOps, ImageDraw


pdf_path = Path(sys.argv[1])
out_dir = Path(sys.argv[2])
out_dir.mkdir(parents=True, exist_ok=True)

pdf = pdfium.PdfDocument(str(pdf_path))
thumbs = []
for index in range(len(pdf)):
    page = pdf[index]
    bitmap = page.render(scale=2.0)
    image = bitmap.to_pil().convert("RGB")
    output = out_dir / f"page-{index + 1}.png"
    image.save(output, quality=95)
    thumb = image.copy()
    thumb.thumbnail((420, 594))
    canvas = Image.new("RGB", (440, 635), "white")
    canvas.paste(thumb, ((440 - thumb.width) // 2, 18))
    ImageDraw.Draw(canvas).text((12, 610), f"Page {index + 1}", fill="black")
    thumbs.append(canvas)

cols = 3
rows = (len(thumbs) + cols - 1) // cols
sheet = Image.new("RGB", (cols * 440, rows * 635), "#d9dde2")
for i, thumb in enumerate(thumbs):
    sheet.paste(thumb, ((i % cols) * 440, (i // cols) * 635))
sheet.save(out_dir / "contact-sheet.png", quality=92)
print(f"PAGES={len(pdf)}")
