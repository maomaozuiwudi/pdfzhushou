import os
import io
import pikepdf
import fitz

SUPPORTED_EXT = (".pdf",)


def get_pdf_info(pdf_path):
    try:
        doc = fitz.open(pdf_path)
        size_mb = os.path.getsize(pdf_path) / (1024 * 1024)
        info = {
            "pages": doc.page_count,
            "size_mb": round(size_mb, 2),
            "format": doc.metadata.get("format", "PDF"),
            "version": doc.metadata.get("version", ""),
            "encrypted": doc.needs_pass,
            "title": doc.metadata.get("title", os.path.basename(pdf_path)),
        }
        doc.close()
        return info
    except Exception as e:
        raise RuntimeError(f"无法读取PDF: {os.path.basename(pdf_path)} - {str(e)}")


def get_page_count(pdf_path):
    doc = fitz.open(pdf_path)
    count = doc.page_count
    doc.close()
    return count


def merge_pdfs(pdf_paths, output_path):
    merged = pikepdf.Pdf.new()
    total_pages = 0
    for path in pdf_paths:
        src = pikepdf.Pdf.open(path)
        merged.pages.extend(src.pages)
        total_pages += len(src.pages)
        src.close()
    merged.save(output_path)
    merged.close()
    return {"output_path": output_path, "page_count": total_pages, "file_count": len(pdf_paths)}


def split_pdf_by_range(pdf_path, page_ranges, output_dir):
    doc = fitz.open(pdf_path)
    results = []
    for idx, (start, end) in enumerate(page_ranges):
        out_doc = fitz.open()
        out_doc.insert_pdf(doc, from_page=start, to_page=end)
        out_name = f"{os.path.splitext(os.path.basename(pdf_path))[0]}_part{idx + 1}.pdf"
        out_path = os.path.join(output_dir, out_name)
        out_doc.save(out_path)
        out_doc.close()
        results.append(out_path)
    doc.close()
    return results


def split_pdf_every_n(pdf_path, n, output_dir):
    doc = fitz.open(pdf_path)
    results = []
    total = doc.page_count
    for i in range(0, total, n):
        end = min(i + n - 1, total - 1)
        out_doc = fitz.open()
        out_doc.insert_pdf(doc, from_page=i, to_page=end)
        out_name = f"{os.path.splitext(os.path.basename(pdf_path))[0]}_part{i // n + 1}.pdf"
        out_path = os.path.join(output_dir, out_name)
        out_doc.save(out_path)
        out_doc.close()
        results.append(out_path)
    doc.close()
    return results


def extract_pages(pdf_path, pages, output_path):
    doc = fitz.open(pdf_path)
    out_doc = fitz.open()
    for p in sorted(pages):
        out_doc.insert_pdf(doc, from_page=p, to_page=p)
    out_doc.save(output_path)
    out_doc.close()
    doc.close()
    return {"output_path": output_path, "extracted_pages": len(pages)}


def pdf_to_images(pdf_path, output_dir, fmt="PNG", dpi=150, quality=85):
    doc = fitz.open(pdf_path)
    results = []
    base = os.path.splitext(os.path.basename(pdf_path))[0]
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    for i in range(doc.page_count):
        page = doc[i]
        pix = page.get_pixmap(matrix=mat)
        if fmt.upper() == "JPEG":
            img_bytes = pix.tobytes("jpeg")
            ext = ".jpg"
        else:
            img_bytes = pix.tobytes("png")
            ext = ".png"
        out_name = f"{base}_page{i + 1}{ext}"
        out_path = os.path.join(output_dir, out_name)
        with open(out_path, "wb") as f:
            f.write(img_bytes)
        results.append(out_path)
    doc.close()
    return results


def encrypt_pdf(pdf_path, output_path, user_pwd, owner_pwd=None):
    if owner_pwd is None:
        owner_pwd = user_pwd
    pdf = pikepdf.Pdf.open(pdf_path)
    encryption = pikepdf.Encryption(owner=owner_pwd, user=user_pwd, R=6)
    pdf.save(output_path, encryption=encryption)
    pdf.close()
    return {"output_path": output_path}


def decrypt_pdf(pdf_path, output_path, password):
    pdf = pikepdf.Pdf.open(pdf_path, password=password)
    pdf.save(output_path)
    pdf.close()
    return {"output_path": output_path}


def compress_pdf(pdf_path, output_path, level="标准"):
    pdf = pikepdf.Pdf.open(pdf_path)
    level_config = {
        "轻度": {"compress_streams": True, "object_stream_mode": pikepdf.ObjectStreamMode.preserve},
        "标准": {"compress_streams": True, "object_stream_mode": pikepdf.ObjectStreamMode.generate},
        "极限": {"compress_streams": True, "object_stream_mode": pikepdf.ObjectStreamMode.generate},
    }
    cfg = level_config.get(level, level_config["标准"])
    pdf.save(output_path, **cfg)

    if level == "极限":
        pdf2 = pikepdf.Pdf.open(output_path)
        for page in pdf2.pages:
            for name, image in page.images.items():
                try:
                    raw = image.read_raw_bytes()
                    img = pikepdf.PdfImage(pikepdf.Stream(pdf2, raw))
                    img_dict = pikepdf.Dictionary({
                        "/Type": "/XObject",
                        "/Subtype": "/Image",
                        "/Width": img.width,
                        "/Height": img.height,
                        "/ColorSpace": img.colorspace or pikepdf.Name.DeviceRGB,
                        "/BitsPerComponent": img.bits_per_component,
                        "/Filter": pikepdf.Name("DCTDecode"),
                    })
                    page.images[name] = img_dict
                except Exception:
                    pass
        pdf2.save(output_path, compress_streams=True, object_stream_mode=pikepdf.ObjectStreamMode.generate)
        pdf2.close()

    original = os.path.getsize(pdf_path)
    compressed = os.path.getsize(output_path)
    pdf.close()
    return {
        "output_path": output_path,
        "original_size_mb": round(original / (1024 * 1024), 2),
        "compressed_size_mb": round(compressed / (1024 * 1024), 2),
        "ratio": round((1 - compressed / original) * 100, 1) if original > 0 else 0,
    }


def get_thumbnail(pdf_path, page=0, width=120):
    doc = fitz.open(pdf_path)
    if page >= doc.page_count:
        page = 0
    page_obj = doc[page]
    zoom = width / page_obj.rect.width
    mat = fitz.Matrix(zoom, zoom)
    pix = page_obj.get_pixmap(matrix=mat)
    img_bytes = pix.tobytes("png")
    doc.close()
    return img_bytes


def get_page_thumbnails(pdf_path, width=120):
    doc = fitz.open(pdf_path)
    thumbs = []
    for i in range(doc.page_count):
        page = doc[i]
        zoom = width / page.rect.width
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        thumbs.append(pix.tobytes("png"))
    doc.close()
    return thumbs


def add_text_watermark_pdf(pdf_path, output_path, text, position="居中",
                           font_size=36, opacity=128, color="#FF0000"):
    doc = fitz.open(pdf_path)
    for page in doc:
        rect = page.rect
        if position == "平铺":
            cols = int(rect.width / 200)
            rows = int(rect.height / 150)
            for r in range(rows):
                for c in range(cols):
                    x = c * (rect.width / cols) + 20
                    y = r * (rect.height / rows) + 40
                    _insert_watermark_text(page, text, x, y, font_size, opacity, color)
        else:
            pos_map = {
                "居中": (rect.width / 2, rect.height / 2),
                "左上": (rect.width * 0.05, rect.height * 0.05),
                "右上": (rect.width * 0.95, rect.height * 0.05),
                "左下": (rect.width * 0.05, rect.height * 0.95),
                "右下": (rect.width * 0.95, rect.height * 0.95),
            }
            x, y = pos_map.get(position, (rect.width / 2, rect.height / 2))
            _insert_watermark_text(page, text, x, y, font_size, opacity, color)
    doc.save(output_path)
    doc.close()
    return {"output_path": output_path}


def _insert_watermark_text(page, text, x, y, font_size, opacity, color):
    try:
        r, g, b = int(color[1:3], 16) / 255, int(color[3:5], 16) / 255, int(color[5:7], 16) / 255
    except Exception:
        r, g, b = 1, 0, 0
    alpha = opacity / 255.0
    sr, sg, sb = r + (1-r) * (1-alpha), g + (1-g) * (1-alpha), b + (1-b) * (1-alpha)
    rect = fitz.Rect(x - 200, y - font_size * 1.5, x + 200, y + font_size * 0.5)
    page.insert_textbox(
        rect,
        text,
        fontsize=font_size,
        color=(sr, sg, sb),
        fontname="china-s",
        align=fitz.TEXT_ALIGN_CENTER,
        overlay=True,
    )


def add_image_watermark_pdf(pdf_path, output_path, img_path, position="居中", scale=0.15):
    doc = fitz.open(pdf_path)
    for page in doc:
        rect = page.rect
        img_w = rect.width * scale
        if position == "平铺":
            cols = max(1, int(rect.width / img_w))
            img_h = img_w
            rows = max(1, int(rect.height / img_h))
            for r in range(rows):
                for c in range(cols):
                    x = c * (rect.width / cols)
                    y = r * (rect.height / rows)
                    r2 = fitz.Rect(x, y, x + img_w, y + img_h)
                    page.insert_image(r2, filename=img_path, overlay=True)
        else:
            pos_map = {
                "居中": ((rect.width - img_w) / 2, (rect.height - img_w) / 2),
                "左上": (rect.width * 0.02, rect.height * 0.02),
                "右上": (rect.width * 0.98 - img_w, rect.height * 0.02),
                "左下": (rect.width * 0.02, rect.height * 0.98 - img_w),
                "右下": (rect.width * 0.98 - img_w, rect.height * 0.98 - img_w),
            }
            x, y = pos_map.get(position, ((rect.width - img_w) / 2, (rect.height - img_w) / 2))
            r2 = fitz.Rect(x, y, x + img_w, y + img_w)
            page.insert_image(r2, filename=img_path, overlay=True)
    doc.save(output_path)
    doc.close()
    return {"output_path": output_path}


def _get_tesseract_path():
    import sys
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS
        candidate = os.path.join(base, "tesseract.exe")
        if os.path.exists(candidate):
            return candidate
    candidates = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return "tesseract"


def ocr_pdf_to_text(pdf_path, output_path, lang="chi_sim+eng"):
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = _get_tesseract_path()

    doc = fitz.open(pdf_path)
    lines = []
    for i in range(doc.page_count):
        page = doc[i]
        zoom = 3.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        img_data = pix.tobytes("png")
        from PIL import Image
        img = Image.open(io.BytesIO(img_data))
        text = pytesseract.image_to_string(img, lang=lang, config="--psm 6")
        lines.append(f"=== 第 {i + 1} 页 ===\n{text}\n")
    doc.close()
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return {"output_path": output_path, "pages": len(lines)}


def pdf_to_word(pdf_path, output_path):
    from pdf2docx import Converter
    cv = Converter(pdf_path)
    cv.convert(output_path)
    cv.close()
    return {"output_path": output_path}


def images_to_pdf(image_paths, output_path):
    doc = fitz.open()
    for img_path in image_paths:
        from PIL import Image
        img = Image.open(img_path)
        w, h = img.size
        page = doc.new_page(width=w, height=h)
        page.insert_image(page.rect, filename=img_path)
    doc.save(output_path)
    doc.close()
    return {"output_path": output_path, "pages": len(image_paths)}
