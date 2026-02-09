"""Badge generator for testing Entur TravelTag designs.

Adjust the parameters below and run this script to generate test badges.
Opens an HTML file in your default browser showing the badges.
"""

import base64
import re
import webbrowser
import tempfile
import os

# Import icon constants from the integration
import sys
sys.path.insert(0, 'custom_components/entur_sx')
from icon_constants import TRANSPORT_ICONS, TRANSPORT_COLORS

# ===== ADJUST THESE PARAMETERS =====
# Base font size - all other dimensions scale from this
TEXT_FONT_SIZE = 14

# Scale factors relative to font size
BADGE_HEIGHT_SCALE = 2.25      # Badge height = 36px at font size 16
ICON_SIZE_SCALE = 1.875         # Icon size = 30px at font size 16
PADDING_LEFT_SCALE = 0.625      # Left padding = 10px at font size 16
PADDING_RIGHT_SCALE = 0.75      # Right padding = 12px at font size 16
GAP_SCALE = 0.5                 # Gap between icon and text = 8px at font size 16
BORDER_RADIUS_SCALE = 0.375     # Border radius = 6px at font size 16
TEXT_VERTICAL_OFFSET_SCALE = 0.125  # Text offset = 2px at font size 16

# Other settings
TEXT_FONT_WEIGHT = "500"
ICON_VERTICAL_OFFSET_SCALE = 0   # Adjust icon position (as fraction of font size)

# Calculate actual values
BADGE_HEIGHT = TEXT_FONT_SIZE * BADGE_HEIGHT_SCALE
ICON_SIZE = TEXT_FONT_SIZE * ICON_SIZE_SCALE
PADDING_LEFT = TEXT_FONT_SIZE * PADDING_LEFT_SCALE
PADDING_RIGHT = TEXT_FONT_SIZE * PADDING_RIGHT_SCALE
GAP_BETWEEN_ICON_AND_TEXT = TEXT_FONT_SIZE * GAP_SCALE
BORDER_RADIUS = TEXT_FONT_SIZE * BORDER_RADIUS_SCALE
ICON_VERTICAL_OFFSET = TEXT_FONT_SIZE * ICON_VERTICAL_OFFSET_SCALE
TEXT_VERTICAL_OFFSET = TEXT_FONT_SIZE * TEXT_VERTICAL_OFFSET_SCALE
# ====================================

def create_badge_svg(transport_mode: str, line_name: str) -> str:
    """Create a complete SVG badge as a data URL."""
    
    icon_data_url = TRANSPORT_ICONS.get(transport_mode, TRANSPORT_ICONS["bus"])
    bg_color = TRANSPORT_COLORS.get(transport_mode, TRANSPORT_COLORS["bus"])
    
    # Extract the base64 content from icon data URL
    icon_match = re.search(r'data:image/svg\+xml;base64,(.+)', icon_data_url)
    if not icon_match:
        return ""
    
    icon_base64 = icon_match.group(1)
    icon_svg = base64.b64decode(icon_base64).decode('utf-8')
    
    # Extract just the SVG content (remove XML declaration and svg wrapper)
    icon_content = ""
    path_matches = re.findall(r'<(path|g|rect|circle|polygon)[^>]*>.*?</\1>|<(path|rect|circle|polygon)[^>]*/>', icon_svg, re.DOTALL)
    if path_matches:
        for pattern in [r'<path[^>]*>.*?</path>', r'<path[^>]*/>',
                       r'<g[^>]*>.*?</g>', r'<rect[^>]*/>',
                       r'<circle[^>]*/>',  r'<polygon[^>]*/>', r'<polygon[^>]*>.*?</polygon>']:
            found = re.search(pattern, icon_svg, re.DOTALL)
            if found:
                content = found.group(0)
                # Replace any fill colors with white
                content = re.sub(r'fill="[^"]*"', 'fill="#FFFFFF"', content)
                icon_content += content
    
    # Measure text width (approximate)
    text_width = len(line_name) * (TEXT_FONT_SIZE * 0.56)  # ~0.56 * font-size per character
    
    # Calculate badge dimensions
    badge_width = PADDING_LEFT + ICON_SIZE + GAP_BETWEEN_ICON_AND_TEXT + text_width + PADDING_RIGHT
    
    # Calculate positions with offsets
    icon_y = (BADGE_HEIGHT - ICON_SIZE) / 2 + ICON_VERTICAL_OFFSET
    text_y = BADGE_HEIGHT / 2 + TEXT_VERTICAL_OFFSET
    
    # Create the complete badge SVG
    badge_svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{badge_width}" height="{BADGE_HEIGHT}" viewBox="0 0 {badge_width} {BADGE_HEIGHT}">
  <rect width="{badge_width}" height="{BADGE_HEIGHT}" rx="{BORDER_RADIUS}" fill="{bg_color}"/>
  <g transform="translate({PADDING_LEFT}, {icon_y}) scale({ICON_SIZE / 16})">
    {icon_content}
  </g>
  <text x="{PADDING_LEFT + ICON_SIZE + GAP_BETWEEN_ICON_AND_TEXT}" y="{text_y}" font-family="system-ui, -apple-system, sans-serif" font-size="{TEXT_FONT_SIZE}" font-weight="{TEXT_FONT_WEIGHT}" fill="#FFFFFF" dominant-baseline="middle">{line_name}</text>
</svg>'''
    
    # Encode as data URL
    badge_base64 = base64.b64encode(badge_svg.encode('utf-8')).decode('utf-8')
    return f"data:image/svg+xml;base64,{badge_base64}"


def generate_test_page():
    """Generate an HTML page with test badges."""
    
    # Test cases
    badges = [
        ("bus", "73", "Skyss bus line 73"),
        ("tram", "1", "Tram line 1"),
        ("bus", "600", "Bus line 600"),
    ]
    
    html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Entur TravelTag Badge Generator</title>
    <style>
        body {
            font-family: system-ui, -apple-system, sans-serif;
            padding: 40px;
            background: #f5f5f5;
        }
        h1 {
            color: #333;
        }
        .params {
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 30px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .params h2 {
            margin-top: 0;
            color: #666;
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .params table {
            width: 100%;
            border-collapse: collapse;
        }
        .params td {
            padding: 8px;
            border-bottom: 1px solid #eee;
        }
        .params td:first-child {
            font-weight: 500;
            color: #333;
        }
        .params td:last-child {
            text-align: right;
            color: #666;
            font-family: monospace;
        }
        .badge-container {
            background: white;
            padding: 30px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .badge-label {
            color: #666;
            font-size: 14px;
            margin-bottom: 15px;
            font-weight: 500;
        }
        .badge-display {
            display: flex;
            align-items: center;
            gap: 20px;
        }
        .info {
            color: #999;
            font-size: 12px;
            margin-top: 30px;
            padding: 15px;
            background: #fff;
            border-radius: 8px;
            border-left: 4px solid #4caf50;
        }
    </style>
</head>
<body>
    <h1>🚌 Entur TravelTag Badge Generator</h1>
    
    <div class="params">
        <h2>Current Parameters (All scaled from font size)</h2>
        <table>
            <tr>
                <td>Text Font Size (base)</td>
                <td>""" + str(TEXT_FONT_SIZE) + """px</td>
            </tr>
            <tr>
                <td>Badge Height</td>
                <td>""" + f"{BADGE_HEIGHT:.1f}" + """px (×""" + str(BADGE_HEIGHT_SCALE) + """)</td>
            </tr>
            <tr>
                <td>Icon Size</td>
                <td>""" + f"{ICON_SIZE:.1f}" + """px (×""" + str(ICON_SIZE_SCALE) + """)</td>
            </tr>
            <tr>
                <td>Padding Left</td>
                <td>""" + f"{PADDING_LEFT:.1f}" + """px (×""" + str(PADDING_LEFT_SCALE) + """)</td>
            </tr>
            <tr>
                <td>Padding Right</td>
                <td>""" + f"{PADDING_RIGHT:.1f}" + """px (×""" + str(PADDING_RIGHT_SCALE) + """)</td>
            </tr>
            <tr>
                <td>Gap (Icon ↔ Text)</td>
                <td>""" + f"{GAP_BETWEEN_ICON_AND_TEXT:.1f}" + """px (×""" + str(GAP_SCALE) + """)</td>
            </tr>
            <tr>
                <td>Border Radius</td>
                <td>""" + f"{BORDER_RADIUS:.1f}" + """px (×""" + str(BORDER_RADIUS_SCALE) + """)</td>
            </tr>
            <tr>
                <td>Text Vertical Offset</td>
                <td>""" + f"{TEXT_VERTICAL_OFFSET:.1f}" + """px (×""" + str(TEXT_VERTICAL_OFFSET_SCALE) + """)</td>
            </tr>
            <tr>
                <td>Icon Vertical Offset</td>
                <td>""" + f"{ICON_VERTICAL_OFFSET:.1f}" + """px (×""" + str(ICON_VERTICAL_OFFSET_SCALE) + """)</td>
            </tr>
            <tr>
                <td>Text Font Weight</td>
                <td>""" + str(TEXT_FONT_WEIGHT) + """</td>
            </tr>
        </table>
    </div>
"""
    
    for transport_mode, line_name, description in badges:
        badge_url = create_badge_svg(transport_mode, line_name)
        html += f"""
    <div class="badge-container">
        <div class="badge-label">{description}</div>
        <div class="badge-display">
            <img src="{badge_url}" alt="{transport_mode} {line_name}">
            <span style="color: #999;">← {transport_mode.upper()} line {line_name}</span>
        </div>
    </div>
"""
    
    html += """
    <div class="info">
        <strong>Proportional Scaling System</strong><br>
        All dimensions are scaled from <code>TEXT_FONT_SIZE</code>. Change the font size, and everything scales proportionally!<br><br>
        <strong>How to use:</strong><br>
        1. Edit <code>TEXT_FONT_SIZE</code> at the top of <code>badge_generator.py</code> (try 14, 18, 20, etc.)<br>
        2. Optionally adjust scale factors if you want different proportions<br>
        3. Run the script again: <code>python badge_generator.py</code><br>
        4. This page will refresh with your new settings
    </div>
</body>
</html>
"""
    
    return html


if __name__ == "__main__":
    print("Generating badge test page...")
    html_content = generate_test_page()
    
    # Create temporary HTML file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
        f.write(html_content)
        temp_path = f.name
    
    print(f"Opening in browser: {temp_path}")
    webbrowser.open('file://' + os.path.abspath(temp_path))
    print("\nBadge generator complete!")
    print("Adjust parameters at the top of badge_generator.py and run again to see changes.")
