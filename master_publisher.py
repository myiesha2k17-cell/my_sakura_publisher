import csv
import io
import textwrap
from PyPDF2 import PdfWriter, PdfReader
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

# Define phase structure
PHASES = {
    1: {"title": "Phase 1: Foundation", "days": "Days 01-10", "focus": "Awareness & Acceptance"},
    2: {"title": "Phase 2: Growth", "days": "Days 11-20", "focus": "Empowerment & Action"},
    3: {"title": "Phase 3: Integration", "days": "Days 21-30", "focus": "Resilience & Radiance"}
}


def create_page():
    # Standard 6x9 inch journal size (432 x 648 points)
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=(432, 648))
    return can, packet


def run_master_publisher(csv_path, output_name):
    writer = PdfWriter()

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = list(csv.DictReader(f))

        for index, row in enumerate(reader):
            day = index + 1
            prompt = row.get("Prompt", "")

            # 1. Add Phase Intro Page
            if day in [1, 11, 21]:
                phase_num = 1 if day <= 10 else 2 if day <= 20 else 3
                can, packet = create_page()
                can.setFont("Helvetica-Bold", 24)
                can.drawString(50, 500, PHASES[phase_num]["title"])
                can.setFont("Helvetica", 16)
                can.drawString(50, 470, PHASES[phase_num]["days"])
                can.drawString(50, 440, f"Focus: {PHASES[phase_num]['focus']}")
                can.save()
                writer.add_page(PdfReader(packet).pages[0])

            # 2. Add Day Page (Clean & Text Focused)
            can, packet = create_page()
            can.setFont("Helvetica-Bold", 14)
            can.drawString(50, 600, f"Day {day}")

            can.setFont("Helvetica", 12)
            lines = textwrap.wrap(prompt, width=60)
            text = can.beginText(50, 560)
            for line in lines:
                text.textLine(line)
            can.drawText(text)
            can.save()
            writer.add_page(PdfReader(packet).pages[0])

            # 3. Monthly Reflection
            if day % 10 == 0:
                can, packet = create_page()
                can.setFont("Helvetica-Bold", 20)
                can.drawString(50, 600, "Monthly Reflection")
                can.setFont("Helvetica", 12)
                can.drawString(50, 560, "1. Biggest win this month?")
                can.drawString(50, 530, "2. Challenge overcome?")
                can.drawString(50, 500, "3. What to carry forward?")
                can.save()
                writer.add_page(PdfReader(packet).pages[0])

    with open(output_name, "wb") as f:
        writer.write(f)