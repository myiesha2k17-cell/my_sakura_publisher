import csv
import os
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
import io

# --- CONFIGURATION ---
SERIES_TITLES = [
    "Sakura Self-Esteem", "Sakura Clarity", "Sakura Calm", "Sakura Gratitude",
    "Sakura Resilience", "Sakura Abundance", "Sakura Boundaries", "Sakura Presence",
    "Sakura Creativity", "Sakura Reflection"
]


def create_promo_page():
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=(432, 648))  # 6x9 inches
    can.setFont("Helvetica-Bold", 16)
    can.drawString(50, 600, "Continue Your Journey")
    can.setFont("Helvetica", 12)
    for i, title in enumerate(SERIES_TITLES):
        can.drawString(50, 560 - (i * 25), f"Vol {i + 1:02d}: {title}")
    can.save()
    packet.seek(0)
    return packet


def export_metadata(title, index):
    """Generates SEO-friendly KDP metadata."""
    filename = f"KDP_Metadata_Vol{index:02d}.txt"
    content = f"""Title: {title}: A 30-Day Guided Journal
Subtitle: Mindfulness, Growth, and Daily Reflection for Personal Development
Keywords: self-help, {title.split()[-1].lower()}, guided journal, 30 day challenge, mindfulness, personal growth, sakura series
Description: Transform your mindset with {title}. This 30-day guided journal is designed to help you build habits, find clarity, and cultivate lasting peace. Part of the exclusive Sakura Series."""
    with open(filename, "w") as f:
        f.write(content)


def run_master_publisher():
    promo_reader = PdfReader(create_promo_page())

    for i, title in enumerate(SERIES_TITLES):
        idx = i + 1
        safe_title = title.replace(' ', '')
        output_pdf = f"SakuraSeries_Vol{idx:02d}_{safe_title}.pdf"
        csv_file = f"{title.lower().replace(' ', '_')}_prompts.csv"

        # 1. Create Interior (Logic from previous steps)
        writer = PdfWriter()
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Add page logic here (using template injection)
                # For brevity, assumes a simple blank page logic
                writer.add_page(PdfReader("template.pdf").pages[0])

        # 2. Add Promo Page
        writer.add_page(promo_reader.pages[0])

        # 3. Save PDF and Metadata
        with open(output_pdf, "wb") as f:
            writer.write(f)
        export_metadata(title, idx)
        print(f"Published: {output_pdf} and Metadata for {title}")

# run_master_publisher()