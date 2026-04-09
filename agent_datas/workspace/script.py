import os
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from reportlab.lib.units import inch

# 读取介绍小雫.txt的内容
with open('./介绍小雫.txt', 'r', encoding='utf-8') as f:
 content = f.read()

# 创建PDF文档
pdf_path = './介绍小雫.pdf'
doc = SimpleDocTemplate(pdf_path, pagesize=letter)

# 设置样式
styles = getSampleStyleSheet()
title_style = ParagraphStyle(
 'CustomTitle',
 parent=styles['Heading1'],
 fontSize=24,
 spaceAfter=30,
 alignment=1 # 居中
)
heading_style = ParagraphStyle(
 'CustomHeading',
 parent=styles['Heading2'],
 fontSize=18,
 spaceBefore=20,
 spaceAfter=10
)
normal_style = ParagraphStyle(
 'CustomNormal',
 parent=styles['Normal'],
 fontSize=12,
 spaceAfter=10
)

# 构建内容
story = []

# 标题
title = Paragraph('小雫 (NekoShizuku) 介绍文档', title_style)
story.append(title)
story.append(Spacer(1, 0.5*inch))

# 按行处理内容
lines = content.split('\n')
for line in lines:
 if not line.strip():
 continue
 
 if line.startswith('# '):
 # 主标题
 para = Paragraph(line[2:], title_style)
 story.append(para)
 elif line.startswith('## '):
 # 副标题
 para = Paragraph(line[3:], heading_style)
 story.append(para)
 else:
 # 普通文本
 para = Paragraph(line, normal_style)
 story.append(para)
 
 story.append(Spacer(1, 0.1*inch))

# 生成PDF
doc.build(story)

print(f"PDF已生成: {pdf_path}")
print(f"文件大小: {os.path.getsize(pdf_path)} 字节")