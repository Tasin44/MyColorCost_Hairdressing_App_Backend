import os
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from django.conf import settings

BASE_URL = "http://10.10.12.14:8000"

def generate_mix_pdf(mix):
    folder = os.path.join(settings.MEDIA_ROOT, "mix_pdfs")
    os.makedirs(folder, exist_ok=True)

    file_name = f"mix_{mix.id}.pdf"
    file_path = os.path.join(folder, file_name)

    doc = SimpleDocTemplate(file_path, pagesize=A4)
    styles = getSampleStyleSheet()

    pink = colors.HexColor("#F8BBD0")
    soft_pink = colors.HexColor("#FCE4EC")

    title_style = ParagraphStyle(
        "title",
        parent=styles["Heading1"],
        textColor=colors.HexColor("#AD1457"),
        alignment=1
    )

    elements = []
    elements.append(Paragraph("Mix Details", title_style))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph(f"<b>Mix Name:</b> {mix.mix_name}", styles["Normal"]))
    elements.append(Paragraph(f"<b>Service:</b> {mix.service_type}", styles["Normal"]))
    elements.append(Paragraph(f"<b>Charged:</b> {mix.charged_amount}", styles["Normal"]))
    elements.append(Paragraph(f"<b>Total Cost:</b> {mix.total_cost}", styles["Normal"]))
    elements.append(Paragraph(f"<b>Profit:</b> {mix.profit}", styles["Normal"]))
    elements.append(Spacer(1, 14))

    table_data = [
        ["Product", "Used(g)", "User Price", "Cost", "Bleach Timer"]
    ]

    for p in mix.mix_products.all():
        table_data.append([
            p.product_name,
            str(p.used_weight),
            str(p.user_price),
            str(p.each_item_cost),
            p.bleach_timer_duration or "-"
        ])

    table = Table(table_data, colWidths=[120, 70, 80, 70, 90])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), pink),
        ("BACKGROUND", (0, 1), (-1, -1), soft_pink),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ]))

    elements.append(table)
    doc.build(elements)

    return f"{BASE_URL}/media/mix_pdfs/{file_name}"
