# Transport Icons for Entur SX Integration

This folder contains SVG icons for transport modes used in the integration.

## Downloaded Icons

✅ **The following Entur Design System icons have been successfully downloaded:**

| Icon | Size | Brand Color | Transport Mode |
|------|------|-------------|----------------|
| Bus.svg | 2.7 KB | #C5044E | Bus services |
| Train.svg | 1.7 KB | #00367F | Train/rail services |
| Tram.svg | 2.6 KB | #642E88 | Tram/light rail (Bybanen) |
| Ferry.svg | 3.4 KB | #0C6693 | Ferry services |
| Carferry.svg | 3.5 KB | #0C6693 | Car ferry services |
| Metro.svg | 865 B | #BF5826 | Metro/T-bane |
| Mobility.svg | 1.6 KB | #388F76 | E-scooters/micromobility |
| Bicycle.svg | 2.2 KB | #181C56 | Bicycle/bike share |
| Walk.svg | 2.4 KB | #8D8E9C | Walking/pedestrian |
| Plane.svg | 2.1 KB | #800664 | Air travel |
| Helicopter.svg | 1.5 KB | #800664 | Helicopter |
| Taxi.svg | 2.1 KB | #3D3E40 | Taxi services |

All icons are 16x16px SVGs with embedded Entur brand colors.

## Source

Official transport icons from the [Entur Design System](https://github.com/entur/design-system)
- Repository: https://github.com/entur/design-system
- Path: `packages/icons/src/svgs/Transport/`
- License: [EUPL-1.2](https://github.com/entur/design-system/blob/main/LICENSE)

## Download Additional Icons

To download more icons from the Transport folder:
```powershell
cd icons
$icon = "Funicular"
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/entur/design-system/main/packages/icons/src/svgs/Transport/$icon.svg" -OutFile "$icon.svg"
```

### Alternative: Material Design Icons (MIT/Apache Licensed)

If additional icons are needed, Material Design Icons provide good alternatives:
- From: https://pictogrammers.com/library/mdi/
- Examples: `mdi:bus`, `mdi:train`, `mdi:tram`, `mdi:ferry`, `mdi:subway-variant`, `mdi:bike`

## Attribution & License

- **License:** EUPL-1.2 (European Union Public License v1.2)  
- **Source:** Entur Design System  
- **Copyright:** © Entur AS  
- **Repository:** https://github.com/entur/design-system

The EUPL-1.2 license is compatible with MIT, Apache 2.0, and GPL licenses.

## Usage

Icons will be converted to base64 data URLs in `const.py` for use as Home Assistant `entity_picture` attributes. This approach:
- Avoids external file dependencies
- Works cleanly with Home Assistant's UI
- Doesn't require additional HTTP serving configuration
