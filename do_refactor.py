import re
import sys

with open('src/static/control_panel.html', 'r', encoding='utf-8') as f:
    text = f.read()

start_idx = text.find('<!-- Character Config (Persona Manager) -->')
end_idx = text.find('<!-- OneBot 11 Connection Settings -->')

if start_idx == -1 or end_idx == -1:
    print('Indices not found!', start_idx, end_idx)
    sys.exit(1)

char_block = text[start_idx:end_idx]

# Remove the char_block from text
text = text[:start_idx] + text[end_idx:]

print(f"Extracted block length: {len(char_block)}")
print(f"Block tail: {repr(char_block[-50:])}")

# Let's clean up the layout in the char block. Using col-lg-10 mx-auto to center it and make it wide.
char_block_formatted = char_block.replace('<div class="col-md-6">', '<div class="col-lg-10 mx-auto">', 1)

# Modify the other configs to make them centered and wide too, addressing the untidy UI feedback.
text = text.replace('<div class="col-md-6">', '<div class="col-lg-10 mx-auto mb-4">')

new_persona_tab = f'''<!-- Persona Tab (Standalone) -->
        <div class="tab-pane fade" id="v-persona" role="tabpanel">
            <div class="row">
{char_block_formatted}
            </div>
        </div>'''

text = re.sub(r'<!-- Persona Tab \(Placeholder\).*?(?=<!-- System Logs Tab -->)', new_persona_tab + '\n\n        ', text, count=1, flags=re.DOTALL)

with open('src/static/control_panel.html', 'w', encoding='utf-8') as f:
    f.write(text)

print("HTML modified successfully!")
