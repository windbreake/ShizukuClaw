import re

with open('src/static/control_panel.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Extract character config block from config tab
char_block_match = re.search(r'<!-- Character Config \(Persona Manager\) -->\s*<div class=\"col-md-6\">(.*?)</div>\s*<!-- OneBot 11 Connection Settings -->', html, re.DOTALL)
if char_block_match:
    char_block = char_block_match.group(1)
    
    # We want to redesign the char block for its own tab
    # Let's make a beautiful split view: Left list of personas, Right form.
    # Actually, let's keep it simple first just wide layout.
    
    char_html = f'''
            <h3 class="mb-4"><i class="fas fa-masks me-2"></i> 预设词与人格管理 (Persona)</h3>
            <div class="row">
                <div class="col-lg-10 mx-auto">
                    {char_block}
                </div>
            </div>
    '''
    # Remove it from config tab
    html = html.replace(char_block_match.group(0), '<!-- OneBot 11 Connection Settings -->')
    
    # Replace the placeholder in v-persona
    persona_placeholder_match = re.search(r'<!-- Persona Tab \(Placeholder\) -->\s*<div class=\"tab-pane fade\" id=\"v-persona\" role=\"tabpanel\">.*?</div>\s*</div>', html, re.DOTALL)
    if persona_placeholder_match:
        html = html.replace(persona_placeholder_match.group(0), f'<!-- Persona Tab -->\n        <div class="tab-pane fade" id="v-persona" role="tabpanel">\n{char_html}\n        </div>')
        
    with open('src/static/control_panel.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print("Extracted and formatted Persona tab!")
else:
    print("Could not find Character Config block")
