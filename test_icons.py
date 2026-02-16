"""Test script to validate all TRANSPORT_ICONS can be decod."""
import base64
import re

# Read the icon_constants.py file and extract TRANSPORT_ICONS manually
with open(r'custom_components\entur_sx\icon_constants.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Extract all icon entries using regex
icon_pattern = r'"(\w+)":\s*"(data:image/svg\+xml;base64,[^"]+)"'
icons = dict(re.findall(icon_pattern, content))

print(f"Found {len(icons)} transport icons\n")
print("Testing all transport icons for base64 validity:\n")

for mode, icon_data_url in icons.items():
    prefix = "data:image/svg+xml;base64,"
    if not icon_data_url.startswith(prefix):
        print(f"❌ {mode}: Missing prefix")
        continue
    
    icon_base64 = icon_data_url[len(prefix):]
    
    # Check length and padding
    b64_len = len(icon_base64)
    padding_needed = (4 - b64_len % 4) % 4
    
    print(f"{mode}:")
    print(f"  Base64 length: {b64_len}")
    print(f"  Length mod 4: {b64_len % 4}")
    print(f"  Padding needed: {padding_needed}")
    
    # Try decode
    try:
        svg_content = base64.b64decode(icon_base64).decode('utf-8')
        print(f"  ✅ Decoded successfully, SVG length: {len(svg_content)}")
    except Exception as e:
        print(f"  ❌ Decode failed: {e}")
        # Try with padding normalization
        try:
            normalized = icon_base64.strip()
            normalized += '=' * ((4 - len(normalized) % 4) % 4)
            svg_content = base64.b64decode(normalized).decode('utf-8')
            print(f"  ✅ Decoded with padding fix, SVG length: {len(svg_content)}")
        except Exception as e2:
            print(f"  ❌ Still failed with padding: {e2}")
    
    print()
