import re
text = open('src/static/control_panel.html', encoding='utf-8').read()
import io, os
import sys
result = re.sub(r'<!-- Persona Tab \(New\).*?<!-- Config Tab \(Merged Editor\) -->', '<!-- Config Tab (Merged Editor) -->', text, flags=re.DOTALL)
open('src/static/control_panel.html', 'w', encoding='utf-8').write(result)
