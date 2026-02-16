"""Convert SVG icon files to base64 data URLs."""
import base64
import json
from pathlib import Path

def convert_icons():
    icons_dir = Path('icons')
    transport_icons = {}

    # Map file names to transport mode keys
    icon_files = {
        'bicycle': 'Bicycle_white.svg',
        'bus': 'Bus_white.svg',
        'carferry': 'Carferry_white.svg',
        'ferry': 'Ferry_white.svg',
        'helicopter': 'Helicopter_white.svg',
        'metro': 'Metro_white.svg',
        'mobility': 'Mobility_white.svg',
        'plane': 'Plane_white.svg',
        'taxi': 'Taxi_white.svg',
        'train': 'Train_white.svg',
        'tram': 'Tram_white.svg',
        'walk': 'Walk_white.svg',
    }

    for mode, filename in sorted(icon_files.items()):
        filepath = icons_dir / filename
        if filepath.exists():
            with open(filepath, 'r', encoding='utf-8') as f:
                svg_content = f.read()
            # Encode to base64
            svg_bytes = svg_content.encode('utf-8')
            b64_encoded = base64.b64encode(svg_bytes).decode('utf-8')
            data_url = f'data:image/svg+xml;base64,{b64_encoded}'
            transport_icons[mode] = data_url
            print(f'✓ {mode}: {len(svg_content)} bytes -> {len(data_url)} chars')
        else:
            print(f'✗ {mode}: File not found - {filename}')

    # Write to JSON file
    with open('transport_icons.json', 'w', encoding='utf-8') as f:
        json.dump(transport_icons, f, indent=4)

    print(f'\n✓ Generated {len(transport_icons)} icon entries in transport_icons.json')
    return transport_icons

if __name__ == '__main__':
    convert_icons()
