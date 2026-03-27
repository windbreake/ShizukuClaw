from bs4 import BeautifulSoup
with open('src/static/control_panel.html', 'r', encoding='utf-8') as f:
    soup = BeautifulSoup(f.read(), 'html.parser')

for tab in soup.find_all('div', class_='tab-pane'):
    print(f"\n--- TAB: {tab.get('id')} ---")
    for child in tab.contents:
        if child.name == 'div' and 'row' in child.get('class', []):
            print(f"Row found")
            for col in child.find_all('div', recursive=False):
                if 'col' in ' '.join(col.get('class', [])):
                    print(f"  Col: {' '.join(col.get('class', []))}")
                    for inner_card in col.find_all('div', class_='card', recursive=False):
                        header = inner_card.find('div', class_='card-header')
                        header_text = header.text.strip() if header else 'No Header'
                        print(f"    Card: {header_text}")
