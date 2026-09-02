#!/usr/bin/env python3
"""
Safe font integration - replaces ALL_FONTS completely
"""

import json
from pathlib import Path


def json_to_js_literal(obj, indent=0):
    """Convert Python object to JavaScript literal format."""
    if isinstance(obj, dict):
        if not obj:
            return '{}'
        
        items = []
        for key, value in obj.items():
            # ALWAYS quote keys for JavaScript compatibility
            # This works for both object literal access (obj.key) and bracket access (obj["key"])
            key_str = f'"{key}"'
            
            val_str = json_to_js_literal(value, indent + 1)
            items.append(f'{key_str}:{val_str}')
        
        return '{' + ','.join(items) + '}'
    
    elif isinstance(obj, list):
        if not obj:
            return '[]'
        items = [json_to_js_literal(item, indent + 1) for item in obj]
        return '[' + ','.join(items) + ']'
    
    elif isinstance(obj, float):
        return f"{obj:.4f}".rstrip('0').rstrip('.')
    
    elif isinstance(obj, bool):
        return 'true' if obj else 'false'
    
    elif obj is None:
        return 'null'
    
    else:
        return json.dumps(obj)


def integrate_fonts_safe(font_data_file, html_file, fonts_to_add=None):
    """Safely integrate all fonts by replacing entire ALL_FONTS object."""
    
    print("Loading font data...")
    with open(font_data_file, 'r', encoding='utf-8') as f:
        font_data = json.load(f)
    
    if fonts_to_add is None:
        fonts_to_add = list(font_data.keys())
    
    # Filter to only fonts in the JSON file
    fonts_to_add = [f for f in fonts_to_add if f in font_data]
    
    print(f"Integrating {len(fonts_to_add)} fonts: {', '.join(sorted(fonts_to_add))}")
    
    # Convert to JavaScript literal
    print("Converting to JavaScript literal...")
    all_fonts_js = json_to_js_literal(font_data)
    
    # Read HTML
    print("Reading HTML...")
    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # Find and replace ALL_FONTS
    import re
    
    # Find the entire ALL_FONTS = {...}; block
    pattern = r'const ALL_FONTS = \{.*?\};'
    match = re.search(pattern, html_content, re.DOTALL)
    
    if not match:
        print("✗ Could not find ALL_FONTS in HTML")
        return False
    
    # Replace with new version
    new_all_fonts = f'const ALL_FONTS = {all_fonts_js};'
    html_content = html_content[:match.start()] + new_all_fonts + html_content[match.end():]
    
    # Update dropdown options
    print("Updating dropdown options...")
    
    # Find font selector
    dropdown_pattern = r'(<select id="font-select">)(.*?)(</select>)'
    dropdown_match = re.search(dropdown_pattern, html_content, re.DOTALL)
    
    if dropdown_match:
        # Keep existing special characters but add new fonts
        dropdown_content = dropdown_match.group(2)
        
        # Remove old Google Font options
        dropdown_content = re.sub(r'\s*<option value="(Yesteryear|Molle|Ranchers|Creepster|Spicy Rice|Coiny)">.*?</option>', '', dropdown_content, flags=re.DOTALL)
        
        # Add new options for all Google Fonts
        new_options = []
        for font_name in sorted(fonts_to_add):
            new_options.append(f'            <option value="{font_name}">{font_name}</option>')
        
        new_dropdown = dropdown_match.group(1) + dropdown_content + '\n' + '\n'.join(new_options) + '\n' + dropdown_match.group(3)
        html_content = html_content[:dropdown_match.start()] + new_dropdown + html_content[dropdown_match.end():]
        print(f"✓ Updated dropdown with {len(fonts_to_add)} fonts")
    
    # Write back
    print(f"Writing HTML ({len(html_content):,} bytes)...")
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print("✓ Integration complete!")
    return True


if __name__ == '__main__':
    import sys
    font_data = Path(__file__).parent / 'font_data.json'
    html_file = Path(__file__).parent / 'index.html'
    fonts = sys.argv[1:] if len(sys.argv) > 1 else None
    integrate_fonts_safe(str(font_data), str(html_file), fonts)
