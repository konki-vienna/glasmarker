#!/usr/bin/env python3
"""
Integrate converted font data into index.html with proper JavaScript object literal format.
"""

import json
import re
from pathlib import Path


def json_to_js_literal(obj):
    """Convert dict/list to JavaScript object literal (no quotes around property names)."""
    if isinstance(obj, dict):
        items = []
        for key, value in obj.items():
            # Keep single-char keys (letters) quoted, unquote property names
            key_str = f'"{key}"' if len(key) == 1 else key
            val_str = json_to_js_literal(value)
            items.append(f'{key_str}:{val_str}')
        return '{' + ','.join(items) + '}'
    elif isinstance(obj, list):
        return '[' + ','.join(json_to_js_literal(item) for item in obj) + ']'
    elif isinstance(obj, float):
        return str(obj)
    elif isinstance(obj, bool):
        return 'true' if obj else 'false'
    else:
        return json.dumps(obj)


def integrate_fonts(font_data_file: str, html_file: str, fonts_to_add: list = None):
    """Integrate font data from JSON into index.html."""
    
    with open(font_data_file, 'r', encoding='utf-8') as f:
        font_data = json.load(f)
    
    if fonts_to_add is None:
        fonts_to_add = list(font_data.keys())
    
    print(f"Fonts to integrate: {fonts_to_add}")
    
    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    all_fonts_match = re.search(r'const ALL_FONTS = \{(.*?)\};', html_content, re.DOTALL)
    if not all_fonts_match:
        raise Exception("Could not find ALL_FONTS object in HTML")
    
    all_fonts_obj = all_fonts_match.group(1)
    existing_fonts = set(re.findall(r'\n\s+"([^"]+)":\s*\{', all_fonts_obj))
    print(f"Existing fonts in HTML: {sorted(existing_fonts)}")
    
    new_font_entries = []
    for font_name in fonts_to_add:
        if font_name not in font_data:
            print(f"  ⚠ {font_name} not in JSON, skipping")
            continue
        if font_name in existing_fonts:
            print(f"  {font_name} already exists, skipping")
            continue
        
        font_obj = font_data[font_name]
        js_repr = json_to_js_literal(font_obj)
        new_font_entries.append(f'        "{font_name}": {js_repr}')
        print(f"  ✓ {font_name} ({len(js_repr):,} bytes)")
    
    if not new_font_entries:
        print("No new fonts to add")
        return
    
    closing_match = re.search(r'(\n\s+)\};(\s+let FONT_DATA)', html_content)
    if not closing_match:
        raise Exception("Could not find ALL_FONTS closing pattern")
    
    # Insert new fonts WITHOUT leading comma (the previous font already has a trailing comma)
    new_text = '\n' + ',\n'.join(new_font_entries) + closing_match.group(0)
    new_html = html_content[:closing_match.start()] + new_text + html_content[closing_match.end():]
    
    dropdown_match = re.search(r'(<option value="Vegan Style">Vegan Style</option>)', new_html)
    if dropdown_match:
        for font_name in fonts_to_add:
            if font_name not in existing_fonts:
                option = f'            <option value="{font_name}">{font_name}</option>'
                new_html = new_html[:dropdown_match.end()] + '\n' + option + new_html[dropdown_match.end():]
                print(f"  ✓ Added {font_name} to dropdown")
    
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(new_html)
    
    print(f"\n✓ Integrated {len(new_font_entries)} fonts ({len(new_html):,} bytes total)")


if __name__ == '__main__':
    import sys
    font_data = Path(__file__).parent / 'font_data.json'
    html_file = Path(__file__).parent / 'index.html'
    fonts = sys.argv[1:] if len(sys.argv) > 1 else None
    integrate_fonts(str(font_data), str(html_file), fonts)
