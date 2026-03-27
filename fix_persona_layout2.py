import re

with open('src/static/control_panel.html', 'r', encoding='utf-8') as f:
    html = f.read()

start_str = '<!-- Character Config (Persona Manager) -->'
end_str = '<!-- OneBot 11 Connection Settings -->'

start_idx = html.find(start_str)
end_idx = html.find(end_str)

if start_idx != -1 and end_idx != -1:
    char_block = html[start_idx:end_idx]
    
    # Needs to strip the first <div class="col-md-6"> and its closing tag, or just use as is in a col-lg-10.
    char_block = char_block.replace('<div class="col-md-6">', '<div class="col-lg-12">', 1)
    
    char_html = f'''
            <h3 class="mb-4"><i class="fas fa-masks me-2"></i> 预设词与人格管理 (Persona)</h3>
            <div class="row">
                <div class="col-lg-10 mx-auto">
                    {char_block}
                </div>
            </div>
    '''
    
    html = html[:start_idx] + end_str + html[end_idx + len(end_str):]
    
    persona_placeholder_match = re.search(r'<!-- Persona Tab \(Placeholder\) -->\s*<div class=\"tab-pane fade\" id=\"v-persona\" role=\"tabpanel\">.*?</div>\s*</div>', html, re.DOTALL)
    if persona_placeholder_match:
        html = html.replace(persona_placeholder_match.group(0), f'<!-- Persona Tab -->\n        <div class="tab-pane fade" id="v-persona" role="tabpanel">\n{char_html}\n        </div>')
        print("Replaced persona correctly")
    
    with open('src/static/control_panel.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print("Format applied.")
