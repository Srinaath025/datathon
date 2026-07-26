import csv
import io
from analytics.geo import get_district_summary
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

def generate_csv_export():
    """Generates a CSV string containing district summaries with a synthetic data disclaimer."""
    districts = get_district_summary()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["# DISCLAIMER: Synthetic demonstration data — not derived from real case records."])
    writer.writerow(["District ID", "Name", "Total Crimes", "Violent Crimes"])
    for d in districts:
        writer.writerow([d["district_id"], d["name"], d["total_crimes"], d["violent_crimes"]])
    return output.getvalue()

def generate_pdf_export():
    """Generates a PDF byte string containing district summaries with a synthetic data disclaimer header."""
    districts = get_district_summary()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    
    styles = getSampleStyleSheet()
    
    disclaimer_style = ParagraphStyle(
        'DisclaimerStyle',
        parent=styles['Normal'],
        textColor=colors.HexColor('#dc2626'),
        fontSize=10,
        leading=12,
        alignment=1, # Center
        spaceAfter=12
    )
    elements.append(Paragraph("<b>WARNING: Synthetic demonstration data — not derived from real case records.</b>", disclaimer_style))
    elements.append(Paragraph("District Crime Summary Report", styles['Title']))
    
    data = [["District ID", "Name", "Total Crimes", "Violent Crimes"]]
    for d in districts:
        data.append([str(d["district_id"]), d["name"], str(d["total_crimes"]), str(d["violent_crimes"])])
        
    t = Table(data)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.grey),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 12),
        ('BACKGROUND', (0,1), (-1,-1), colors.beige),
        ('GRID', (0,0), (-1,-1), 1, colors.black)
    ]))
    
    elements.append(t)
    doc.build(elements)
    
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes

