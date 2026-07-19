import os
print("Does template.pdf exist?", os.path.exists("template.pdf"))

import csv
import io
import os
import textwrap  # ADDED THIS
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

# Define the structure for the phases
PHASES = {
    1: {"title": "Phase 1: Foundation", "days": "Days 01-10", "focus": "Awareness & Acceptance"},
    2: {"title": "Phase 2: Growth", "days": "Days 11-20", "focus": "Empowerment & Action"},
    3: {"title": "Phase 3: Integration", "days": "Days 21-30", "focus": "Resilience & Radiance"}
}


def create_phase_page(phase_num):
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=(432, 648))
    can.setFont("Helvetica-Bold", 24)
    can.drawString(50, 400, PHASES[phase_num]["title"])
    can.setFont("Helvetica", 16)
    can.drawString(50, 370, PHASES[phase_num]["days"])
    can.drawString(50, 340, f"Focus: {PHASES[phase_num]['focus']}")
    can.save()
    packet.seek(0)
    return packet


def create_reflection_page():
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=(432, 648))
    can.setFont("Helvetica-Bold", 20)
    can.drawString(50, 600, "Monthly Reflection")
    can.setFont("Helvetica", 12)
    can.drawString(50, 560, "1. What was your biggest win this month?")
    can.drawString(50, 530, "2. What challenge did you overcome?")
    can.drawString(50, 500, "3. What do you want to carry forward?")
    can.save()
    packet.seek(0)
    return packet


# FIXED: Added text wrapping here
def create_text_page(prompt):
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=(432, 648))
    can.setFont("Helvetica", 12)

    # Wrap text to 60 characters wide
    lines = textwrap.wrap(prompt, width=60)

    text = can.beginText(50, 500)
    text.setFont("Helvetica", 12)
    for line in lines:
        text.textLine(line)

    can.drawText(text)
    can.save()
    packet.seek(0)
    return packet


def run_master_publisher(csv_path, output_name):
    writer = PdfWriter()
    template_reader = PdfReader("template.pdf")
    template_page = template_reader.pages[0]

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = list(csv.DictReader(f))

        for index, row in enumerate(reader):
            day = index + 1
            prompt = row.get("Prompt", "")

            # 1. Add Phase Intro Page
            if day in [1, 11, 21]:
                phase_num = 1 if day <= 10 else 2 if day <= 20 else 3
                phase_packet = create_phase_page(phase_num)
                writer.add_page(PdfReader(phase_packet).pages[0])

            # 2. Add Day Page with Merged Text
            text_packet = create_text_page(prompt)
            text_page = PdfReader(text_packet).pages[0]

            # Create new blank page and merge layers
            page_to_add = writer.add_blank_page(width=template_page.mediabox.width,
                                                height=template_page.mediabox.height)
            page_to_add.merge_page(template_page)
            page_to_add.merge_page(text_page)

            # 3. Add Monthly Reflection every 10 iterations
            if day % 10 == 0:
                reflection_packet = create_reflection_page()
                writer.add_page(PdfReader(reflection_packet).pages[0])

    with open(output_name, "wb") as f:
        writer.write(f)
    print(f"Successfully created {output_name}")