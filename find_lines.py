lines=open('src/static/control_panel.html', encoding='utf-8').readlines()
for i,l in enumerate(lines):
  if 'Character Config' in l or 'v-config' in l:
    print(i, l.strip()[:80])
