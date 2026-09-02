#!/usr/bin/env python3
"""
Batch convert multiple Google Fonts and combine into single JSON.
"""

import json
import subprocess
import tempfile
from pathlib import Path
from fontTools.ttLib import TTFont
import sys

# Import from font_converter
import importlib.util
spec = importlib.util.spec_from_file_location("font_converter", "font_converter.py")
font_converter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(font_converter)

def batch_convert_fonts(fonts_list, output_file='font_data.json'):
    """Convert multiple fonts and combine into single JSON file."""
    
    all_fonts = {}
    
    print("="*60)
    print(f"Batch Converting {len(fonts_list)} Fonts")
    print("="*60)
    
    for font_name in fonts_list:
        print(f"\n▶ Converting {font_name}...")
        try:
            font_json = font_converter.convert_font_to_json(font_name)
            all_fonts.update(font_json)
            
            # Count glyphs in this font
            glyph_count = len(list(font_json.values())[0]) if font_json else 0
            print(f"  ✓ {glyph_count} glyphs added")
            
        except Exception as e:
            print(f"  ✗ Error: {str(e)[:100]}")
    
    # Save combined data
    print("\n" + "="*60)
    print("Saving combined font data...")
    
    output_path = Path(output_file)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_fonts, f, separators=(',', ':'))
    
    size_kb = output_path.stat().st_size / 1024
    font_count = len(all_fonts)
    print(f"✓ Combined {font_count} fonts into {output_file} ({size_kb:.1f} KB)")
    print("="*60)
    
    return all_fonts

if __name__ == '__main__':
    fonts = sys.argv[1:] if len(sys.argv) > 1 else ['Yesteryear', 'Molle', 'Chango', 'Ranchers', 'Chewy']
    batch_convert_fonts(fonts)
