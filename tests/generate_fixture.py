"""Generate a realistic test invoice image fixture for OCR and extraction testing."""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

def generate_fixture():
    fixtures_dir = Path(__file__).resolve().parent / "fixtures"
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    out_path = fixtures_dir / "sample_invoice.png"

    # Create high-contrast document image
    img = Image.new("RGB", (700, 450), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Document Header
    draw.text((40, 30), "ACME SUPPLIES & LOGISTICS", fill=(0, 0, 0))
    draw.text((40, 55), "INVOICE: INV-2026-9042", fill=(0, 0, 0))
    draw.text((40, 75), "DATE: September 19, 2026", fill=(0, 0, 0))
    draw.text((40, 95), "BILL TO: Global Logistics Corp", fill=(0, 0, 0))

    # Divider line
    draw.line([(40, 125), (660, 125)], fill=(100, 100, 100), width=2)

    # Table Header
    draw.text((40, 140), "ITEM DESCRIPTION", fill=(0, 0, 0))
    draw.text((340, 140), "QTY", fill=(0, 0, 0))
    draw.text((440, 140), "UNIT PRICE", fill=(0, 0, 0))
    draw.text((560, 140), "TOTAL", fill=(0, 0, 0))

    draw.line([(40, 165), (660, 165)], fill=(150, 150, 150), width=1)

    # Table Rows
    draw.text((40, 180), "High-Speed Industrial Sensor", fill=(0, 0, 0))
    draw.text((350, 180), "5", fill=(0, 0, 0))
    draw.text((450, 180), "$120.00", fill=(0, 0, 0))
    draw.text((570, 180), "$600.00", fill=(0, 0, 0))

    draw.text((40, 210), "Fiber Optic Interface Cable 2m", fill=(0, 0, 0))
    draw.text((350, 210), "10", fill=(0, 0, 0))
    draw.text((450, 210), "$25.00", fill=(0, 0, 0))
    draw.text((570, 210), "$250.00", fill=(0, 0, 0))

    draw.text((40, 240), "Standard Mounting Bracket Kit", fill=(0, 0, 0))
    draw.text((350, 240), "5", fill=(0, 0, 0))
    draw.text((450, 240), "$15.00", fill=(0, 0, 0))
    draw.text((570, 240), "$75.00", fill=(0, 0, 0))

    draw.line([(40, 275), (660, 275)], fill=(150, 150, 150), width=1)

    # Summary Totals
    draw.text((420, 290), "SUBTOTAL:", fill=(0, 0, 0))
    draw.text((570, 290), "$925.00", fill=(0, 0, 0))

    draw.text((420, 315), "TAX (8%):", fill=(0, 0, 0))
    draw.text((570, 315), "$74.00", fill=(0, 0, 0))

    draw.text((420, 345), "TOTAL AMOUNT DUE:", fill=(0, 0, 0))
    draw.text((570, 345), "$999.00", fill=(0, 0, 0))

    # Footer note
    draw.text((40, 390), "Payment terms: Net 30 days. Thank you for your business!", fill=(100, 100, 100))
    img.save(out_path, format="PNG")
    return out_path


def generate_sample_page():
    fixtures_dir = Path(__file__).resolve().parent.parent / "data" / "fixtures"
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    out_path = fixtures_dir / "sample_page.png"
    img = Image.new("RGB", (800, 600), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    text = "Invoice 1042 Total 26.00 Line A 10.00 Line B 16.00"
    draw.text((50, 50), text, fill=(0, 0, 0))
    img.save(out_path, format="PNG")
    return out_path


if __name__ == "__main__":
    generate_fixture()
    generate_sample_page()

