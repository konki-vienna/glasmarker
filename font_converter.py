#!/usr/bin/env python3
"""
Google Fonts to Glyph JSON Converter

Converts Google Fonts (TTF) to normalized glyph data for 3D text rendering.
Extracts contours, normalizes to 0-1 range, identifies holes, and calculates advance widths.
"""

import json
import subprocess
import tempfile
from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools.pens.pointPen import PointToSegmentPen, AbstractPointPen
from fontTools.misc.transform import Transform
from fontTools.misc.bezierTools import splitCubic, splitQuadratic
import math


def download_google_font(font_name: str) -> bytes:
    """
    Download a Google Font TTF file using curl from GitHub source.
    
    Args:
        font_name: Font name as it appears on Google Fonts (e.g., "Yesteryear")
    
    Returns:
        TTF file content as bytes
    """
    print(f"Downloading {font_name} from GitHub (Google Fonts source)...")
    
    # GitHub raw content URL (most reliable)
    # Font naming convention: capitalize-separated, e.g., "Yesteryear" -> "Yesteryear-Regular.ttf"
    font_slug = font_name.lower().replace(' ', '')
    # Filename should match repo structure (spaces removed in filename too)
    font_filename = f"{font_name.replace(' ', '')}-Regular.ttf"
    
    url = f"https://raw.githubusercontent.com/google/fonts/main/ofl/{font_slug}/{font_filename}"
    
    try:
        # Use curl with SSL verification disabled (-k flag)
        result = subprocess.run(
            ['curl', '-k', '-s', '-L', url],  # -L for following redirects
            capture_output=True,
            timeout=10,
            check=False
        )
        
        if result.returncode == 0 and len(result.stdout) > 1000:
            print(f"  ✓ Downloaded {len(result.stdout)} bytes")
            return result.stdout
        else:
            print(f"  ✗ Failed: curl returned {result.returncode}, {len(result.stdout)} bytes")
            raise Exception(f"Failed to download {font_name}")
            
    except Exception as e:
        print(f"  ✗ Error: {e}")
        raise


def extract_glyph_contours(font_path: str, glyph_name: str) -> tuple:
    """
    Extract contour data for a single glyph with smooth curve approximation.
    Bezier curves are split into multiple line segments for smooth rendering.
    
    Args:
        font_path: Path to TTF font file
        glyph_name: Name of the glyph (e.g., "A")
    
    Returns:
        (outer_contours, holes, advance_width)
    """
    font = TTFont(font_path)
    glyf = font['glyf']
    cmap = font.getBestCmap()
    hmtx = font['hmtx']
    
    # Get advance width
    if glyph_name in hmtx.metrics:
        advance = hmtx.metrics[glyph_name][0]
    else:
        advance = font['head'].unitsPerEm
    
    # Normalize advance width
    em_square = font['head'].unitsPerEm
    advance_normalized = advance / em_square
    
    # Get glyph
    if glyph_name not in glyf:
        return [], [], advance_normalized
    
    glyph = glyf[glyph_name]
    
    if not hasattr(glyph, 'coordinates') or glyph.numberOfContours <= 0:
        return [], [], advance_normalized  # Empty shapes
    
    # Use RecordingPen and parse the operations manually with correct qCurveTo handling
    from fontTools.pens.recordingPen import RecordingPen
    
    rec_pen = RecordingPen()
    glyph.draw(rec_pen, glyf)
    
    outer_contours = []
    current_contour = []
    current_point = (0, 0)
    
    for op, args in rec_pen.value:
        if op == 'moveTo':
            if current_contour:
                outer_contours.append(current_contour)
            current_contour = [args[0]]
            current_point = args[0]
        
        elif op == 'lineTo':
            current_contour.append(args[0])
            current_point = args[0]
        
        elif op == 'curveTo':
            # Cubic Bezier: (cp1, cp2, endpoint)
            cp1, cp2, endpoint = args
            # Sample the curve
            for t in [i / 15 for i in range(1, 16)]:
                pt = _cubic_bezier(current_point, cp1, cp2, endpoint, t)
                current_contour.append(pt)
            current_point = endpoint
        
        elif op == 'qCurveTo':
            # Quadratic Bezier chain. Points: off-curve, on-curve OR off-curve, off-curve (implicit on-curve midpoint)
            points = args
            i = 0
            while i < len(points):
                if i == len(points) - 1:
                    # Last point is always on-curve
                    ep = points[i]
                    for t in [j / 15 for j in range(1, 16)]:
                        pt = _quad_bezier(current_point, current_point, ep, t)
                        current_contour.append(pt)
                    current_point = ep
                    i += 1
                elif i + 1 < len(points):
                    cp = points[i]
                    next_point = points[i + 1]
                    
                    # Check if next_point is followed by another point (to detect implicit on-curve)
                    if i + 2 < len(points):
                        # Implicit on-curve between cp and next_point
                        ep = ((cp[0] + next_point[0]) / 2, (cp[1] + next_point[1]) / 2)
                    else:
                        # next_point is the final on-curve
                        ep = next_point
                    
                    # Sample quadratic Bezier
                    for t in [j / 15 for j in range(1, 16)]:
                        pt = _quad_bezier(current_point, cp, ep, t)
                        current_contour.append(pt)
                    current_point = ep
                    i += 1 if i + 2 < len(points) else 2
                else:
                    i += 1
        
        elif op == 'closePath':
            if current_contour:
                outer_contours.append(current_contour)
            current_contour = []
    
    if current_contour:
        outer_contours.append(current_contour)
    
    # Get EM square size for proper normalization
    em_square = font['head'].unitsPerEm
    
    # Normalize all contours
    all_contours_normalized = []
    for contour in outer_contours:
        normalized_contour = [
            [round(pt[0] / em_square, 4), round(pt[1] / em_square, 4)]
            for pt in contour
        ]
        all_contours_normalized.append(normalized_contour)
    
    # Separate outer contours from holes based on winding order and containment
    if not all_contours_normalized:
        return [], [], advance_normalized
    
    # Calculate signed area for each contour (positive = CCW, negative = CW)
    contour_areas = [_calculate_contour_area(c) for c in all_contours_normalized]
    
    # Typically: largest area = outer, others might be holes
    # Use winding order: if areas have different signs, one is a hole
    outer_shapes = []
    
    for i, (contour, area) in enumerate(zip(all_contours_normalized, contour_areas)):
        if area > 0:  # CCW = outer contour
            # Find all holes inside this outer contour
            holes = []
            for j, (other_contour, other_area) in enumerate(zip(all_contours_normalized, contour_areas)):
                if i != j and other_area < 0:  # CW = potential hole
                    # Verify that other_contour is inside this contour
                    if other_contour and _point_in_polygon(other_contour[0], contour):
                        holes.append(other_contour)
            
            outer_shapes.append({
                'outer': contour,
                'holes': holes
            })
    
    # If no CCW contours found, treat largest contour as outer
    if not outer_shapes and all_contours_normalized:
        largest_idx = max(range(len(contour_areas)), key=lambda i: abs(contour_areas[i]))
        outer_contour = all_contours_normalized[largest_idx]
        holes = []
        
        for j in range(len(all_contours_normalized)):
            if j != largest_idx:
                if all_contours_normalized[j] and _point_in_polygon(all_contours_normalized[j][0], outer_contour):
                    holes.append(all_contours_normalized[j])
        
        outer_shapes.append({
            'outer': outer_contour,
            'holes': holes
        })
    
    # outer_shapes is list of {outer: [...], holes: [...]}
    return outer_shapes, [], advance_normalized


def _calculate_contour_area(contour):
    """Calculate signed area of polygon. Positive=CCW, Negative=CW"""
    if len(contour) < 3:
        return 0
    area = 0
    for i, pt in enumerate(contour):
        next_pt = contour[(i + 1) % len(contour)]
        area += (next_pt[0] - pt[0]) * (next_pt[1] + pt[1])
    return area / 2


def _point_in_polygon(point, polygon):
    """Test if point is inside polygon using ray casting"""
    x, y = point
    n = len(polygon)
    inside = False
    
    p1x, p1y = polygon[0]
    for i in range(1, n + 1):
        p2x, p2y = polygon[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y
    
    return inside
    """Evaluate cubic Bezier curve at parameter t (0-1)"""
    mt = 1 - t
    mt2 = mt * mt
    mt3 = mt2 * mt
    t2 = t * t
    t3 = t2 * t
    
    x = mt3 * p0[0] + 3 * mt2 * t * p1[0] + 3 * mt * t2 * p2[0] + t3 * p3[0]
    y = mt3 * p0[1] + 3 * mt2 * t * p1[1] + 3 * mt * t2 * p2[1] + t3 * p3[1]
    return (x, y)


def _quad_bezier(p0, p1, p2, t):
    """Evaluate quadratic Bezier curve at parameter t (0-1)"""
    mt = 1 - t
    mt2 = mt * mt
    t2 = t * t
    
    x = mt2 * p0[0] + 2 * mt * t * p1[0] + t2 * p2[0]
    y = mt2 * p0[1] + 2 * mt * t * p1[1] + t2 * p2[1]
    return (x, y)
    
    return [], [], advance_normalized


def convert_font_to_json(font_name: str, glyphs: list = None) -> dict:
    """
    Convert a Google Font to glyph JSON format.
    
    Args:
        font_name: Font name (e.g., "Yesteryear")
        glyphs: List of glyphs to include (default: A-Z, a-z, 0-9, .,!?,-)
    
    Returns:
        Dictionary with format: {"FontName": {"A": {"shapes": [...], "advance": 0.5}, ...}}
    """
    if glyphs is None:
        # Minimal set: letters and digits only (compact file size)
        glyphs = (
            list('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789')
        )
    
    # Download font
    font_data = download_google_font(font_name)
    
    # Save to temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix='.ttf') as tmp:
        tmp.write(font_data)
        font_path = tmp.name
    
    try:
        font = TTFont(font_path)
        cmap = font.getBestCmap()
        
        result = {}
        
        for char in glyphs:
            char_code = ord(char)
            
            # Get glyph name from character code
            if char_code in cmap:
                glyph_name = cmap[char_code]
            else:
                # Use character as glyph name (common in some fonts)
                glyph_name = char
            
            print(f"  Processing: {char} (U+{char_code:04X}) -> {glyph_name}")
            
            shapes, _, advance = extract_glyph_contours(font_path, glyph_name)
            
            # shapes is now a list of {"outer": [...], "holes": [...]}
            result[char] = {
                "shapes": shapes if shapes else [{"outer": [], "holes": []}],
                "advance": round(advance, 4)
            }
        
        return {font_name: result}
    
    finally:
        # Cleanup
        Path(font_path).unlink(missing_ok=True)


def main():
    """Main entry point."""
    fonts = ["Yesteryear"]  # POC: start with one font
    
    all_fonts_data = {}
    
    for font_name in fonts:
        print(f"\n{'='*60}")
        print(f"Converting: {font_name}")
        print('='*60)
        
        try:
            font_json = convert_font_to_json(font_name)
            all_fonts_data.update(font_json)
            print(f"✓ Successfully converted {font_name}")
        except Exception as e:
            print(f"✗ Error converting {font_name}: {e}")
            import traceback
            traceback.print_exc()
    
    # Output JSON
    output_path = Path(__file__).parent / "font_data.json"
    with open(output_path, 'w') as f:
        json.dump(all_fonts_data, f, indent=2)
    
    print(f"\n{'='*60}")
    print(f"✓ Conversion complete!")
    print(f"  Output: {output_path}")
    print(f"  Size: {output_path.stat().st_size / 1024:.1f} KB")
    print('='*60)


if __name__ == '__main__':
    main()
