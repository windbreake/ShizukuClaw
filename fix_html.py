import re

html_path = 'src/static/control_panel.html'
with open(html_path, 'r', encoding='utf-8') as f:
    text = f.read()

# Fix garbled text based on original text
replacements = {
    '在此处配?OneBot 11': '在此处配置 OneBot 11',
    '设置与群聊连?': '设置与群聊连接',
    '提示词设?': '提示词设置',
    '启?': '启用',
    '模?': '模型',
    '最大上下?': '最大上下文',
    '温度（Temperature?': '温度（Temperature）',
    '回复长度限?': '回复长度限制',
    '请求超?': '请求超时',
    '设?': '设置',
    '提?': '提示'
}

for k, v in replacements.items():
    text = text.replace(k, v)

# Fix remaining general garbled characters if there's any obvious ones missing
# Actually, the best way to handle this is to restore from the latest working backup, but doing replacements for the specific issues might be quicker.
text = re.sub(r'在此处配\?OneBot 11', '在此处配置 OneBot 11', text)
text = re.sub(r'设置与群聊连\?', '设置与群聊连接', text)
text = re.sub(r'提示词设\?', '提示词设置', text)

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(text)

print('Fixed HTML encoding!')
