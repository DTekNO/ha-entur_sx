# GitHub Copilot Instructions for Entur SX Integration

## Project Overview

This is a Home Assistant custom integration that monitors real-time transit disruptions from Entur's SIRI-SX API for Norwegian public transport operators.

## Core Architecture

### Components
- **API Client** (`api.py`): Handles communication with Entur SIRI-SX REST API
- **Coordinator** (`coordinator.py`): Manages data updates and disruption tracking
- **Sensors** (`sensor.py`): Two types of sensors:
  - **Line Sensors**: One per monitored line with TravelTag badges
  - **Summary Sensor**: Aggregates all lines with numeric disruption count
- **Config Flow** (`config_flow.py`): UI-based configuration with operator/line discovery
- **Badge Generation** (`sensor.py`): SVG badge creation with Entur Design System styling

### Key Files
- `icon_constants.py`: Transport mode icons (12 modes) and brand colors from Entur Design System
- `templates/formatted_content.j2`: English markdown template with badges
- `templates/formatted_content_no.j2`: Norwegian markdown template with badges
- `const.py`: Constants including `normalize_language()` function

## Coding Conventions

### Language Support
- Always use `normalize_language(hass.config.language)` for automatic language detection
- Language codes: `"no"` (Norwegian: nb, nn, se) or `"en"` (English, default)
- Templates exist for both languages - select using `_async_load_template(hass, lang)`
- Date formatting uses locale-aware functions: `_format_datetime_norwegian()` for Norwegian

### Badge Generation
- Uses `_create_badge_svg(transport_mode, line_name)` to create TravelTag-style badges
- Proportional scaling: base font 14pt, icon 26.25px (1.875×), badge height 31.5px (2.25×)
- Transport modes: bus, train, tram, ferry, carferry, metro, mobility, bicycle, walk, plane, helicopter, taxi
- Colors from `TRANSPORT_COLORS` in `icon_constants.py` (official Entur brand colors)
- Icons from `TRANSPORT_ICONS` as base64-encoded white SVGs

### Sensor Design
- **Line sensors**: `entity_picture` shows badge, `formatted_content` has markdown with badges
- **Summary sensor**: State is numeric (0, 1, 2, etc.) for easy conditional visibility
- All timestamps formatted with locale awareness
- API text selection handles multiple XML formats: `xml:lang`, `lang`, `<Language>` elements

### Status Types
- `open`: Active disruption happening now
- `planned`: Scheduled future disruption
- `expired`: Disruption that has ended

### API Handling
- Rate limiting with exponential backoff (429 errors)
- Pagination support using `MoreData` flag
- Lowercase-safe progress detection for API variations
- Multi-language text selection with fallback logic in `_select_text_by_language()`

## Important Patterns

### Adding New Features
1. Consider language support from the start - add to both templates
2. Use the summary sensor for aggregate information
3. Maintain the TravelTag badge styling consistency
4. Always provide locale-aware date formatting

### Testing Badge Changes
- Use `badge_generator.py` standalone tool for visual testing
- Outputs to `badge_samples/` directory with HTML preview
- Test all 12 transport modes before integrating

### Configuration
- No language configuration option - always follows HA's language setting
- Device name is user-configurable (used in sensor entity IDs)
- Summary sensor creation is optional (can be disabled)

## Dependencies
- Entur SIRI-SX REST API: https://api.entur.io/realtime/v1/rest/sx
- Entur Design System for icons and colors (EUPL-1.2 licensed)
- Home Assistant core (sensor platform, coordinator pattern)
- Jinja2 for markdown templates

## Common Tasks

### Adding Transport Modes
1. Add icon SVG to `custom_components/entur_sx/icons/{Mode}_white.svg`
2. Update `icon_constants.py` with color in `TRANSPORT_COLORS`
3. Regenerate icon constants or add manually
4. Update detection heuristics in `_detect_transport_mode()`

### Modifying Templates
- Edit both `formatted_content.j2` (English) and `formatted_content_no.j2` (Norwegian)
- Use `{{ badge_markup | safe }}` for badge HTML
- Maintain consistent formatting between languages

### Debugging API Issues
- Enable disruption tracking: `custom_components.entur_sx.coordinator.disruptions: info`
- Check for rate limiting (429 errors) in logs
- Verify operator codes match Entur's authority IDs

## Design Principles
- Automatic over manual: Language from HA, operators/lines from API discovery
- Visual consistency: Follow Entur Design System exactly
- User-friendly: Numeric states for easy automation, clean markdown for display
- Robust: Handle API inconsistencies, rate limits, and missing data gracefully
- Bilingual: Always support Norwegian and English equally
