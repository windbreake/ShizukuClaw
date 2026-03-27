with open('original_control_panel.html', 'r', encoding='utf-16') as f:
    try:
        text = f.read()
        print('length:', len(text))
        print('OneBot in it?', 'OneBot' in text)
    except:
        pass
with open('original_control_panel.html', 'r', encoding='utf-8') as f:
    try:
        text = f.read()
        print('length utf8:', len(text))
        print('OneBot in it?', 'OneBot' in text)
    except Exception as e:
        print(e)
