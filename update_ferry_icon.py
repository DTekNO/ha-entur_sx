#!/usr/bin/env python3
"""Update the ferry icon in icon_constants.py with the correct white-filled version."""

import json

# Read the correct ferry data from transport_icons.json
with open('transport_icons.json', 'r') as f:
    icons = json.load(f)

ferry_data = icons['ferry']

# Read the icon_constants.py file
constants_file = 'custom_components/entur_sx/icon_constants.py'
with open(constants_file, 'r') as f:
    lines = f.readlines()

# Find and update the ferry line
for i, line in enumerate(lines):
    if line.strip().startswith('"ferry":'):
        # Replace the ferry line
        lines[i] = f'    "ferry": "{ferry_data}",\n'
        print(f"Updated line {i+1}: ferry icon")
        break

# Write back lines
with open(constants_file, 'w') as f:
    f.writelines(lines)

print(f"✓ Updated {constants_file}")
print(f"✓ Ferry icon now has {len(ferry_data)} characters")
