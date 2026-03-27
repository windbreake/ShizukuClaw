with open('original_control_panel.html', 'r', encoding='utf-8') as f:
    text = f.read()
    if 'OneBot' in text:
        print('OneBot found in original_control_panel.html')
    else:
        print('OneBot NOT found in original_control_panel.html')
