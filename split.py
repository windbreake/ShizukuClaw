with open('src/static/control_panel.html', encoding='utf-8') as f:
    text = f.read()

start_p = text.find('<!-- Persona Tab')
end_p = text.find('<!-- Config Tab')
start_c = text.find('<!-- Character Config')

print(f"start_p={start_p} end_p={end_p} start_c={start_c}")
