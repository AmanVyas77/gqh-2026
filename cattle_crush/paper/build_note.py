"""Reporting-only renderer. Reads editable HTML and a committed chart; no project imports."""
from pathlib import Path
import xml.etree.ElementTree as ET
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, PageBreak, Spacer, Flowable
from reportlab.lib.utils import ImageReader
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
for name,file in [('Arial','Arial.ttf'),('Arial-Bold','Arial Bold.ttf'),('Arial-Italic','Arial Italic.ttf')]:
    pdfmetrics.registerFont(TTFont(name,'/System/Library/Fonts/Supplemental/'+file))
pdfmetrics.registerFontFamily('Arial',normal='Arial',bold='Arial-Bold',italic='Arial-Italic',boldItalic='Arial-Bold')
styles={
'p':ParagraphStyle('body',fontName='Arial',fontSize=11,leading=12.7,spaceAfter=5),
'h1':ParagraphStyle('title',fontName='Arial-Bold',fontSize=16,leading=18,spaceAfter=8),
'h2':ParagraphStyle('heading',fontName='Arial-Bold',fontSize=13,leading=15,spaceBefore=5,spaceAfter=6),
'cap':ParagraphStyle('caption',fontName='Arial',fontSize=11,leading=12.4,spaceAfter=5),
'cell':ParagraphStyle('cell',fontName='Arial',fontSize=11,leading=12.3),
}
class ArchivedCurve(Flowable):
    """Reuse plot pixels unchanged; clip out original small text, typeset new labels at 11 pt."""
    def __init__(self):
        super().__init__(); self.width=456; self.height=190
    def draw(self):
        c=self.canv; x,y,w,h=36,28,420,130
        # Clip original plot region only: no title, legend, axis text or endpoint labels.
        sx,sy,sw,sh=101,92,1302,616
        c.saveState(); p=c.beginPath();p.rect(x,y,w,h);c.clipPath(p,stroke=0)
        c.drawImage(ImageReader(str(OUT/'archived_equity.png')),
                    x-sx*w/sw,y-(754-sy-sh)*h/sh,width=1557*w/sw,height=754*h/sh)
        c.restoreState();c.setFont('Arial',11);c.setFillColor(colors.HexColor('#444444'))
        for val,py in [(0,207),(-10,335),(-20,463),(-30,590)]:
            c.drawRightString(x-6,y+(708-py)*h/sh-4,str(val))
        for year,px in [(2014,210),(2016,396),(2018,583),(2020,770),(2022,957),(2024,1145),(2026,1332)]:
            c.drawCentredString(x+(px-sx)*w/sw,y-15,str(year))
        c.drawString(0,175,'Cumulative net return (% of fixed capital); shaded = holdout')
        for label,col,lx,ly in [('H1 A primary','#297cda',36,162),('H2 primary','#fa6332',176,162),('H1 B secondary','#16ad7a',36,0),('H1 C secondary','#efa400',249,0)]:
            c.setStrokeColor(colors.HexColor(col));c.setLineWidth(1.8);c.line(lx,ly+4,lx+16,ly+4)
            c.setFillColor(colors.black);c.drawString(lx+21,ly,label)

def inner(e):
    return (e.text or '')+''.join(ET.tostring(ch,encoding='unicode') for ch in e)
def footer(c,d):
    c.setFont('Arial',11);c.setFillColor(colors.HexColor('#555555'))
    c.drawRightString(540,58,f'{d.page}' if d.page<=5 else 'References')
def build():
    root=ET.parse(OUT/'research_note_edited.html').getroot();flow=[]
    pages=root.findall('./body/section')
    for i,section in enumerate(pages):
        if i:flow.append(PageBreak())
        for e in section:
            if e.tag in ['p','h1','h2']:
                flow.append(Paragraph(inner(e),styles['cap' if e.get('class')=='cap' else e.tag]))
            elif e.tag=='table':
                rows=[[Paragraph(inner(cell),styles['cell']) for cell in row] for row in e]
                widths=[float(x)*456/468 for x in e.get('widths').split(',')]
                t=Table(rows,colWidths=widths,hAlign='LEFT',repeatRows=1)
                t.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),4),('RIGHTPADDING',(0,0),(-1,-1),4),('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3),('BACKGROUND',(0,0),(-1,0),colors.HexColor('#eef2f5')),('LINEBELOW',(0,0),(-1,0),.6,colors.HexColor('#333333')),('LINEBELOW',(0,1),(-1,-1),.25,colors.HexColor('#cccccc'))]))
                flow.extend([t,Spacer(1,6)])
            elif e.tag=='figure':flow.extend([ArchivedCurve(),Spacer(1,4)])
    doc=SimpleDocTemplate(str(OUT/'research_note_edited.pdf'),pagesize=(612,792),rightMargin=72,leftMargin=72,topMargin=72,bottomMargin=72,title='Feedlot Margins, Cattle Prices and Beef-Exposed Equities',author='Aman Vyas, Zhicheng Li, Nicolas Slenko',allowSplitting=0)
    doc.build(flow,onFirstPage=footer,onLaterPages=footer)
if __name__=='__main__':build()
