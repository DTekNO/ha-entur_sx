# Entur Alert Card

A custom Lovelace card bundled with the Entur SX integration that displays transport disruptions in a collapsible timeline format.

**The card is automatically installed when you install the integration!** No manual setup required.

## Features

- **Timeline view** - Shows current and future disruptions arranged by start time
- **Collapsible details** - Click any alert to expand/collapse full description
- **Smart time formatting** - Shows "Today", "Tomorrow", or formatted dates
- **Visual indicators** - Color-coded for active (blue) vs planned (orange) disruptions
- **Configurable** - Control what's displayed and how many items to show
- **Auto-updating** - Card automatically updates when integration updates

## Installation

### Automatic (Recommended)

**The card installs automatically!** When you install or update the Entur SX integration:

1. The card is copied to `/config/www/entur-alert-card.js`
2. It's automatically registered as a Lovelace resource
3. You can start using it immediately in your dashboards

After installation or updates, you may need to:
- Hard refresh your browser (Ctrl+F5 or Cmd+Shift+R)
- Clear browser cache

### Manual Verification

To verify the card is installed:
1. Go to **Settings** → **Dashboards** 
2. Click the three dots (⋮) → **Resources**
3. You should see `/local/entur-alert-card.js` in the list

If it's not there, restart Home Assistant and check again.

## Configuration

### Basic Configuration

```yaml
type: custom:entur-alert-card
entity: sensor.skyss_sky_disruption_summary
```

### Full Configuration Options

```yaml
type: custom:entur-alert-card
entity: sensor.skyss_sky_disruption_summary  # Required
title: Transport Alerts                       # Optional, default: "Transport Alerts"
show_timeline: true                           # Optional, default: true
show_only_new: false                          # Optional, default: false (shows all)
max_items: 10                                 # Optional, default: 10
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `entity` | string | **Required** | Entity ID of your Entur summary sensor |
| `title` | string | `"Transport Alerts"` | Card header title |
| `show_timeline` | boolean | `true` | Show timeline dots and line |
| `show_only_new` | boolean | `false` | Only show new disruptions (from `new_disruptions` attribute) |
| `max_items` | number | `10` | Maximum number of alerts to display |

## Examples

### Minimal - Just the essentials
```yaml
type: custom:entur-alert-card
entity: sensor.skyss_sky_disruption_summary
```

### Compact - No timeline, only new disruptions
```yaml
type: custom:entur-alert-card
entity: sensor.skyss_sky_disruption_summary
title: 🚨 New Alerts
show_timeline: false
show_only_new: true
max_items: 5
```

### Dashboard integration with visibility
```yaml
type: vertical-stack
cards:
  - type: custom:entur-alert-card
    entity: sensor.skyss_sky_disruption_summary
    title: Active Disruptions
    
  - type: markdown
    content: >
      Last updated: {{ relative_time(states.sensor.skyss_sky_disruption_summary.last_updated) }}
```

## Features in Detail

### Timeline View
The timeline shows:
- **Blue dots** for active disruptions  
- **Orange dots** for planned future disruptions
- Vertical line connecting all events

### Time Display
- **Today** - Shows "Today at HH:MM"
- **Tomorrow** - Shows "Tomorrow at HH:MM"
- **Future** - Shows "Day, Mon DD at HH:MM"

### Expandable Details
Click any alert card to toggle the full description with HTML formatting preserved.

## Troubleshooting

### Card not showing up
1. Check that the resource is added correctly in **Settings** → **Dashboards** → **Resources**
2. Hard refresh your browser (Ctrl+F5 or Cmd+Shift+R)
3. Check browser console for errors (F12)

### "Entity not found"
Make sure your Entur summary sensor exists and is named correctly:
```yaml
sensor.your_entur_summary
```

### Styles look wrong
The card uses Home Assistant CSS variables. Make sure you're using a recent version of HA (2023.11+).

## Development

To modify the card:
1. Edit `custom_components/entur_sx/www/entur-alert-card.js`
2. Hard refresh browser to see changes
3. For development, you can use browser dev tools to inspect and test

## Future Enhancements

Potential features to add:
- Filter by line
- Search/filter alerts
- Export to calendar
- Sorting options (by line, severity, time)
- Compact vs detailed view modes
