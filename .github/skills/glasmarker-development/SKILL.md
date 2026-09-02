---
name: glasmarker-development
description: "Manage Glasmarker 3D text renderer. Use for: adding Google Fonts, modifying dropdown UI, integrating fonts into HTML, debugging font rendering, font quality optimization. Handles 11 pre-computed font glyphs in single 7.4MB HTML file using Three.js r128."
argument-hint: "Font management task (add fonts, fix dropdown, debug rendering)"
---

# Glasmarker Development Guide

## Project Overview

**Glasmarker** is a single-file 3D text rendering web application (~7.4 MB HTML file).

### Technology Stack

- **3D Graphics**: Three.js r128 (WebGL)
- **Font Data**: Pre-computed glyph outlines (not actual font files)
- **Fonts**: 11 total (5 original + 6 Google Fonts)
- **Python Tools**: fontTools for font conversion, Three.js rendering pipeline

### Architecture

#### Data Model: Font Structure

```javascript
ALL_FONTS = {
  "FontName": {
    "A": {           // Unquoted glyph keys (A, B, C, 0-9, a-z)
      "shapes": [
        {
          "outer": [[x,y], [x,y], ...],  // Outer contour
          "holes": [[[x,y], ...], ...]   // Inner holes (optional)
        }
      ],
      "advance": 0.601  // Width normalized by EM-square
    }
  }
}
```

#### Coordinate System

- **Normalized range**: 0-1 scale
- **Calculation**: `coords / font_em_square` (typically 1000-2048 units)
- **Key insight**: Normalized by EM-square (not per-glyph bounding box) to preserve natural letter proportions

#### Font Processing Pipeline

1. **Download**: Google Fonts TTF from GitHub CDN
2. **Extract**: fontTools extracts glyph contours + metrics
3. **Normalize**: Coordinates divided by EM-square, curve sampling
4. **Detect Holes**: Winding order (CCW=outer, CW=inner) + point-in-polygon
5. **Integrate**: Merge into `index.html` ALL_FONTS constant
6. **Render**: Three.js ExtrudeGeometry converts 2D shapes to 3D

---

## When to Use This Skill

✓ Adding new Google Fonts to the collection  
✓ Modifying font dropdown UI (sorting, descriptions)  
✓ Fixing font rendering issues (jagged glyphs, overlap, holes)  
✓ Debugging font integration  
✓ Optimizing glyph quality

✗ General 3D graphics questions (use Three.js docs)  
✗ Font file format specifications (use fontTools docs)

---

## Common Errors & Solutions

### 🚨 Error 1: Font Keys Mismatch

**Problem**: New fonts use quoted keys `"A": {...}` while original fonts use unquoted `A: {...}` → mixed access patterns fail

**Root Cause**: Integration script (integrate_fonts_safe.py) generated incompatible structure

**Prevention**:

- Always use `integrate_fonts.py` (original, working version)
- Preserve existing font structure when merging
- Never quote glyph keys unless ALL fonts use quotes consistently

**Fix**: Reset HTML to original state, re-integrate fonts using original script

---

### 🚨 Error 2: Missing Original Fonts

**Problem**: After integration, original 5 fonts (Poppins Bold, Serif Bold, etc.) disappear from ALL_FONTS

**Root Cause**: Integration script replaced instead of appended new fonts

**Prevention**:

- Use regex-based insertion: find `const ALL_FONTS = {...};`
- Insert new fonts BEFORE closing `};`
- Verify all 11 fonts present after each integration: `python3 verify_fonts.py`

**Verify Command**:

```bash
cd /Users/H13S6VB/Development/glasmarker
python3 << 'EOF'
with open('index.html') as f:
    html = f.read()
fonts = ['Poppins Bold', 'Serif Bold', 'Brush Script', 'Liberation Serif',
         'Vegan Style', 'Yesteryear', 'Molle', 'Ranchers', 'Creepster',
         'Spicy Rice', 'Coiny']
for font in fonts:
    status = "✓" if f'"{font}"' in html else "✗"
    print(f"{status} {font}")
EOF
```

---

### 🚨 Error 3: Jagged/Zacky Glyph Rendering

**Problem**: 3D glyphs appear blocky or pixelated

**Root Cause**: Insufficient Bezier curve sampling (3 segments too low, need 15+)

**Prevention**:

- Set `CURVE_SEGMENTS = 15` in font_converter.py
- Higher values (15-20) for smoother curves, lower (5-10) for faster processing
- Test conversion: `python3 font_converter.py Coiny`

---

### 🚨 Error 4: Letters Overlap Excessively

**Problem**: Text appears bunched together, letters overlap

**Root Cause**: Coordinates normalized by glyph bounding box instead of EM-square

**Prevention**:

- **Correct**: `normalized = coord / font['head'].unitsPerEm`
- **Wrong**: `normalized = (coord - min) / (max - min)`
- EM-square normalization preserves natural proportions across all glyphs

---

### 🚨 Error 5: Glyphs with Holes Don't Render

**Problem**: Letters like "e", "Q", "d" render as solid instead of showing inner holes

**Root Cause**: Missing hole detection algorithm

**Solution in font_converter.py**:

```python
def extract_glyph_contours(font_path, glyph_name):
    # 1. Detect winding order (signed area): CCW=outer, CW=inner
    # 2. Use point-in-polygon test to separate holes
    # 3. Return: [{"outer": contour, "holes": [...]}, ...]
```

---

### 🚨 Error 6: Default Font Not Found

**Problem**: App crashes on load if default font doesn't exist

**Prevention**:

- Always set default to existing font: `FONT_DATA = ALL_FONTS["Poppins Bold"];`
- Never use font names that aren't in ALL_FONTS
- Test after each change: Open browser console, verify no errors

---

## Workflows

### Workflow 1: Add New Google Font

**Prerequisites**:

- Font available on Google Fonts
- Python environment: `/Users/H13S6VB/Development/glasmarker/.venv`

**Steps**:

1. **Convert Font** (creates glyph JSON)

   ```bash
   cd /Users/H13S6VB/Development/glasmarker
   python3 font_converter.py "FontName"
   ```

   ✓ Creates `fontname_data.json`

2. **Verify Glyph Quality**

   ```bash
   python3 << 'EOF'
   import json
   with open('fontname_data.json') as f:
       data = json.load(f)
   print(f"Glyphs: {len(data['FontName'])}")
   print(f"A shape points: {len(data['FontName']['A']['shapes'][0]['outer'])}")
   EOF
   ```

3. **Integrate into HTML** (merges into ALL_FONTS)

   ```bash
   python3 integrate_fonts.py fontname_data.json index.html "FontName"
   ```

4. **Verify Integration**

   ```bash
   grep -c "FontName" index.html  # Should return non-zero
   ```

5. **Test in Browser**
   - Open `index.html` in browser
   - Check dropdown for new font
   - Select font, render text, verify 3D display

6. **Update Dropdown Description** (line ~451)
   - Find: `<option value="FontName">FontName</option>`
   - Add 1-2 word description: `FontName (Style Description)`
   - Ensure alphabetical order in dropdown

### Workflow 2: Modify Font Dropdown

**Task**: Update descriptions, reorder, add/remove fonts

**File**: `index.html` lines 451-465 (font-select)

**Process**:

1. **Locate Dropdown**

   ```bash
   grep -n "id=\"font-select\"" index.html  # Find line number
   ```

2. **Edit Options**
   - Ensure value attribute matches key in ALL_FONTS
   - Display text can include descriptions: `FontName (Description)`
   - Maintain alphabetical order for UX

3. **Verify Syntax**
   - Check for matching closing `</select>`
   - Ensure no broken HTML tags

4. **Test Changes**
   - Reload browser (Cmd+Shift+R hard refresh)
   - Verify dropdown populated
   - Try selecting each font

### Workflow 3: Debug Font Rendering Issues

**Common Investigation Steps**:

1. **Check Browser Console**
   - Open DevTools (F12)
   - Look for JavaScript errors
   - Check if `renderText()` is called

2. **Verify Font Data Structure**

   ```bash
   python3 << 'EOF'
   with open('index.html') as f:
       html = f.read()

   # Find ALL_FONTS
   start = html.find('const ALL_FONTS = {')
   snippet = html[start:start+2000]

   # Check structure
   if 'A:{' in snippet or '"A":{' in snippet:
       print("✓ Glyph keys found")
   if 'shapes' in snippet and 'advance' in snippet:
       print("✓ Data structure correct")
   EOF
   ```

3. **Verify renderText Function**

   ```bash
   grep -n "function renderText" index.html
   ```

4. **Clear Cache & Reload**
   - Browser: Cmd+Shift+Delete (cache clearing)
   - Reload: Cmd+Shift+R (hard refresh)

---

## File Reference

| File                      | Purpose                       | Key Lines                             |
| ------------------------- | ----------------------------- | ------------------------------------- |
| `index.html`              | Single-file app (7.4 MB)      | 451-465: font-select, 674+: ALL_FONTS |
| `font_converter.py`       | Convert TTF → glyph JSON      | extract_glyph_contours()              |
| `integrate_fonts.py`      | Merge fonts into HTML         | Original working version              |
| `integrate_fonts_safe.py` | ⚠️ Incompatible version       | Do not use                            |
| `batch_convert_fonts.py`  | Convert multiple fonts        | For bulk operations                   |
| `font_data.json`          | Converted font data (1.76 MB) | Intermediate file                     |

---

## Python Environment

**Location**: `/Users/H13S6VB/Development/glasmarker/.venv`

**Dependencies**:

- fontTools (for TTF parsing)
- requests (for downloads)

**Activate**:

```bash
cd /Users/H13S6VB/Development/glasmarker
source .venv/bin/activate
```

---

## Current Font List (11 Total)

### Original (5)

1. Poppins Bold
2. Serif Bold
3. Brush Script
4. Liberation Serif
5. Vegan Style

### Google Fonts (6)

6. Coiny
7. Creepster
8. Molle
9. Ranchers
10. Spicy Rice
11. Yesteryear

---

## Testing Checklist

After any changes:

- [ ] File size < 8 MB
- [ ] All 11 fonts present in ALL_FONTS
- [ ] Dropdown populates correctly
- [ ] Font switching works for all fonts
- [ ] 3D rendering displays text
- [ ] No console errors
- [ ] OBJ export includes positioned letters
