# Dashboard Card Examples

This document provides ready-to-use dashboard card configurations for displaying Entur disruptions in your Home Assistant UI.

## Table of Contents
- [Summary Sensor (Automatic)](#summary-sensor-automatic)
- [Basic Markdown Card](#basic-markdown-card)
- [Multi-Line Markdown Card](#multi-line-markdown-card)
- [Entities Card](#entities-card)
- [Conditional Card](#conditional-card)
- [Template Helper Sensors](#template-helper-sensors)
- [Advanced: Auto-generating Cards](#advanced-auto-generating-cards-for-all-lines)

---

## Summary Sensor (Automatic)

**⭐ Recommended Approach** - The easiest way to display all disruptions!

If you enabled "Create markdown summary sensor" during setup, the integration automatically creates a text sensor with pre-formatted markdown content.

> **💡 Key Feature:** The summary sensor provides **two separate markdown attributes**:
> - `markdown_active` - Active/current disruptions (status: "open") with **red alert**
> - `markdown_planned` - Planned/upcoming disruptions (status: "planned") with **blue info**
> 
> This gives you **full control** over what to display - active only, planned only, or both!

### Features
- ✅ **Zero configuration** - works out of the box
- ✅ Shows disruptions for all monitored lines in one card
- ✅ Automatically formatted with your chosen icon
- ✅ Only visible when there are disruptions
- ✅ Includes validity times, status, and full descriptions
- ✅ **Separate active and planned disruptions** - choose which to display
- ✅ **Filters out expired disruptions** - only shows current and upcoming alerts

### Configuration

The summary sensor provides **two separate markdown attributes**:
- `markdown_active` - Active (open) disruptions with red alert banner
- `markdown_planned` - Planned disruptions with blue info banner

**Important:** Replace `sensor.skyss_disruption_summary` with your actual entity ID (e.g., `sensor.skyss_disruption_summary`)

#### Option 1: Show Active Disruptions Only (Recommended)

```yaml
type: markdown
content: "{{ state_attr('sensor.skyss_disruption_summary', 'markdown_active') }}"
visibility:
  - condition: state
    entity: sensor.skyss_disruption_summary
    state_not: Normal service
```

#### Option 2: Show Planned Disruptions Only

**Option 2a: Without visibility (always shows)**
```yaml
type: markdown
content: "{{ state_attr('sensor.skyss_disruption_summary', 'markdown_planned') }}"
```

**Option 2b: With visibility using helper sensor (recommended)**

First, create a helper template sensor to track planned disruptions:

Go to **Settings → Devices & Services → Helpers → Create Helper → Template → Template a binary sensor**

- **Name**: Skyss Has Planned Disruptions
- **State template**:
  ```jinja
  {{ state_attr('sensor.skyss_disruption_summary', 'planned_disruptions') | int(0) > 0 }}
  ```

Then use it in your card:
```yaml
type: markdown
content: "{{ state_attr('sensor.skyss_disruption_summary', 'markdown_planned') }}"
visibility:
  - condition: state
    entity: binary_sensor.skyss_has_planned_disruptions
    state: "on"
```

#### Option 3: Show Both Active and Planned (Separate Cards)

**Requirements**: Create the helper sensor from Option 2b above.

```yaml
type: vertical-stack
cards:
  # Active disruptions card
  - type: markdown
    content: "{{ state_attr('sensor.skyss_disruption_summary', 'markdown_active') }}"
    visibility:
      - condition: state
        entity: sensor.skyss_disruption_summary
        state_not: Normal service
  
  # Planned disruptions card
  - type: markdown
    content: "{{ state_attr('sensor.skyss_disruption_summary', 'markdown_planned') }}"
    visibility:
      - condition: state
        entity: binary_sensor.skyss_has_planned_disruptions
        state: "on"
```

> **🔧 Troubleshooting Tip:** 
> - Use **state** condition with `state_not: Normal service` for active disruptions ✅
> - For planned disruptions, **create a helper binary sensor** - attribute conditions aren't supported in card visibility
> - Template conditions are NOT supported in card visibility - only state conditions work
> - **Find your entity ID**: Go to Developer Tools → States and search for "summary"
> - The entity ID format is usually: `sensor.{device_name}_summary`
>   - Example: `sensor.skyss_disruption_summary` for device "Skyss Disruption"
>   - Example: `sensor.ruter_disruption_summary` for device "Ruter Disruption"

### What It Looks Like

#### Active Disruptions (`markdown_active` attribute)

```markdown
**<ha-alert alert-type="error"><ha-icon icon="mdi:bus-alert"></ha-icon> Skyss - Active Disruptions</ha-alert>**

### SKY:Line:1

**Delay due to traffic**

Expect 10-15 minute delays on Line 1 between Bergen sentrum and Fyllingsdalen

*From: 2025-10-17T08:00:00* • *To: 2025-10-17T12:00:00*

*Status: open* • *Progress: published*

---

*2 line(s) with normal service*
```

#### Planned Disruptions (`markdown_planned` attribute)

```markdown
**<ha-alert alert-type="info"><ha-icon icon="mdi:bus-alert"></ha-icon> Skyss - Planned Disruptions</ha-alert>**

### SKY:Line:2

**Bus replacement service**

Line 2 will operate with bus for rail between Nesttun and Lagunen this weekend

*From: 2025-10-19T06:00:00* • *To: 2025-10-21T23:00:00*

*Status: planned* • *Progress: published*

---

*2 line(s) with normal service*
```

**Benefits:**
- ✅ **Flexible**: Choose to display active, planned, or both
- ✅ **Simple**: No nested template evaluation needed
- ✅ **No length limits**: Content stored in attributes
- ✅ **Auto-updates**: Refreshes when coordinator updates
- ✅ **Smart filtering**: Expired disruptions automatically excluded
- ✅ **Color-coded**: Red for active (urgent), blue for planned (informational)

> **Note:** 
> - The sensor **state** shows only **active (open)** disruption count
> - `markdown_active` includes disruptions with status `"open"` (red alert)
> - `markdown_planned` includes disruptions with status `"planned"` (blue info)
> - Expired disruptions are automatically filtered out
> - Individual line sensors still show all deviations in their attributes
> 
> **💡 Visibility Tips:**
> - Use `| int(0)` in visibility conditions to handle unavailable/unknown states gracefully
> - Check attribute counts (`active_disruptions`, `planned_disruptions`) rather than state
> - This prevents errors when the sensor is still initializing

### Sensor Attributes

The summary sensor provides detailed attributes for both active and planned disruptions:

```yaml
total_lines: 3
active_disruptions: 1
planned_disruptions: 1
normal_lines: 1
active_line_refs:
  - "SKY:Line:1"
planned_line_refs:
  - "SKY:Line:2"
normal_line_refs:
  - "SKY:Line:3"
markdown_active: "**<ha-alert...>** ..."
markdown_planned: "**<ha-alert...>** ..."
```

Use these in visibility conditions:

```yaml
# Example: Show card only if there are active disruptions (simplest - recommended!)
visibility:
  - condition: state
    entity: sensor.skyss_disruption_summary
    state_not: Normal service

# Example: Show card only if there are planned disruptions (requires helper sensor)
visibility:
  - condition: state
    entity: binary_sensor.skyss_has_planned_disruptions
    state: "on"

# Example: Show card if there are ANY disruptions (active or planned)
visibility:
  - condition: or
    conditions:
      - condition: state
        entity: sensor.skyss_disruption_summary
        state_not: Normal service
      - condition: state
        entity: binary_sensor.skyss_has_planned_disruptions
        state: "on"
```

---

## Basic Markdown Card

A simple markdown card that shows a single line's disruption status with an alert banner.

### Features
- Alert banner with icon
- Shows disruption summary and description
- Only visible when there's an active disruption

### Configuration

```yaml
type: markdown
content: >-
  **<ha-alert alert-type="warning"><ha-icon icon="mdi:tram-side"></ha-icon>
  Bybanen</ha-alert>**

  {{ state_attr('sensor.skyss_disruption_sky_line_1', 'description') }}
visibility:
  - condition: state
    entity: sensor.skyss_disruption_sky_line_1
    state_not: Normal service
```

### Customization Tips
- Change `mdi:tram-side` to match your transit type:
  - `mdi:bus` - Bus lines
  - `mdi:ferry` - Ferry lines
  - `mdi:train` - Train lines
  - `mdi:subway-variant` - Metro/subway
- Change `alert-type` to:
  - `"warning"` - Yellow/orange (default for disruptions)
  - `"error"` - Red (for severe disruptions)
  - `"info"` - Blue (for planned maintenance)

---

## Multi-Line Markdown Card

Shows disruptions for multiple lines in a single card.

### Features
- Combines multiple lines into one card
- Each line shown conditionally
- Compact display with separators

### Configuration

```yaml
type: markdown
content: >-
  {% set lines = [
    'sensor.skyss_disruption_sky_line_1',
    'sensor.skyss_disruption_sky_line_2',
    'sensor.skyss_disruption_sky_line_3'
  ] %}

  **<ha-alert alert-type="warning"><ha-icon icon="mdi:bus-alert"></ha-icon>
  Skyss Disruptions</ha-alert>**

  {% for line in lines %}
    {% if not is_state(line, 'Normal service') %}
  
  ### {{ state_attr(line, 'line_ref') }}
  
  **{{ states(line) }}**
  
  {{ state_attr(line, 'description') }}
  
  *Valid: {{ state_attr(line, 'valid_from') | as_timestamp | timestamp_custom('%d.%m %H:%M') }} - {{ state_attr(line, 'valid_to') | as_timestamp | timestamp_custom('%d.%m %H:%M') if state_attr(line, 'valid_to') else 'Until further notice' }}*
  
  ---
    {% endif %}
  {% endfor %}

  {% if lines | select('is_state', 'Normal service') | list | length == lines | length %}
  Normal service
  {% endif %}
visibility:
  - condition: or
    conditions:
      - condition: state
        entity: sensor.skyss_disruption_sky_line_1
        state_not: Normal service
      - condition: state
        entity: sensor.skyss_disruption_sky_line_2
        state_not: Normal service
      - condition: state
        entity: sensor.skyss_disruption_sky_line_3
        state_not: Normal service
```

---

## Entities Card

A cleaner entities card approach showing all disruptions.

### Features
- Native HA entities card styling
- Automatic icon coloring
- Tap for more details

### Configuration

```yaml
type: entities
title: Transit Disruptions
icon: mdi:bus-alert
entities:
  - entity: sensor.skyss_disruption_sky_line_1
    name: Line 1
    secondary_info: last-changed
  - entity: sensor.skyss_disruption_sky_line_2
    name: Line 2
    secondary_info: last-changed
  - entity: sensor.skyss_disruption_sky_line_3
    name: Line 3
    secondary_info: last-changed
state_color: true
show_header_toggle: false
```

---

## Conditional Card

Only shows the card when there are active disruptions.

### Features
- Card completely hidden when all services normal
- Multiple lines in one conditional block
- Customizable appearance

### Configuration

```yaml
type: conditional
conditions:
  - condition: or
    conditions:
      - condition: state
        entity: sensor.skyss_disruption_sky_line_1
        state_not: Normal service
      - condition: state
        entity: sensor.skyss_disruption_sky_line_2
        state_not: Normal service
card:
  type: markdown
  content: >-
    ## ⚠️ Transit Disruptions

  {% if not is_state('sensor.skyss_disruption_sky_line_1', 'Normal service') %}
  **Line 1:** {{ states('sensor.skyss_disruption_sky_line_1') }}
    
  {{ state_attr('sensor.skyss_disruption_sky_line_1', 'description') }}
    
    ---
    {% endif %}

  {% if not is_state('sensor.skyss_disruption_sky_line_2', 'Normal service') %}
  **Line 2:** {{ states('sensor.skyss_disruption_sky_line_2') }}
    
  {{ state_attr('sensor.skyss_disruption_sky_line_2', 'description') }}
    {% endif %}
```

---

## Template Helper Sensors

Home Assistant's Template Helper can create aggregated sensors that combine multiple lines or provide a summary status.

### Option 1: Manual Template Helper

You can create these manually via **Settings → Devices & Services → Helpers → Create Helper → Template**.

#### ⭐ Planned Disruptions Helper (Required for Visibility)

**Important:** Card visibility doesn't support checking attributes, so you need this helper to show/hide the planned disruptions card.

**Template Type:** Binary Sensor

**Name:** Skyss Has Planned Disruptions

**State Template:**
```jinja
{{ state_attr('sensor.skyss_disruption_summary', 'planned_disruptions') | int(0) > 0 }}
```

**Device Class:** `problem`

This creates `binary_sensor.skyss_has_planned_disruptions` which you can use in visibility conditions:
```yaml
visibility:
  - condition: state
    entity: binary_sensor.skyss_has_planned_disruptions
    state: "on"
```

---

#### Example: Any Disruption Binary Sensor

**Template Type:** Binary Sensor

**Name:** Skyss Has Disruptions

**State Template:**
```jinja
{{ not is_state('sensor.skyss_disruption_sky_line_1', 'Normal service') 
  or not is_state('sensor.skyss_disruption_sky_line_2', 'Normal service') 
  or not is_state('sensor.skyss_disruption_sky_line_3', 'Normal service') }}
```

**Device Class:** `problem`

This creates a binary sensor that's "on" when any line has a disruption.

#### Example: Disruption Count Sensor

**Template Type:** Sensor

**Name:** Skyss Active Disruptions

**State Template:**
```jinja
{{ [
  states('sensor.skyss_disruption_sky_line_1'),
  states('sensor.skyss_disruption_sky_line_2'),
  states('sensor.skyss_disruption_sky_line_3')
] | reject('eq', 'Normal service') | list | count }}
```

**Unit of Measurement:** `disruptions`

This creates a sensor showing the number of lines with active disruptions.

#### Example: Disruption Summary Sensor

**Template Type:** Sensor

**Name:** Skyss Disruption Summary

**State Template:**
```jinja
  {% set lines = [
    'sensor.skyss_disruption_sky_line_1',
    'sensor.skyss_disruption_sky_line_2',
    'sensor.skyss_disruption_sky_line_3'
  ] %}
{% set disrupted = lines | reject('is_state', 'Normal service') | list %}
{% if disrupted | length == 0 %}
  Normal service
{% elif disrupted | length == 1 %}
  1 disruption
{% else %}
  {{ disrupted | length }} disruptions
{% endif %}
```

**Attributes Template:**
```jinja
  {% set lines = {
  'sensor.skyss_disruption_sky_line_1': 'Line 1',
  'sensor.skyss_disruption_sky_line_2': 'Line 2',
  'sensor.skyss_disruption_sky_line_3': 'Line 3'
} %}
  {% set disrupted = {} %}
  {% for entity, name in lines.items() %}
  {% if not is_state(entity, 'Normal service') %}
    {% set disrupted = dict(disrupted, **{name: states(entity)}) %}
  {% endif %}
{% endfor %}
{{ disrupted }}
```

### Option 2: YAML Configuration

Add to your `configuration.yaml`:

```yaml
template:
  # Helper for planned disruptions visibility (REQUIRED for card visibility)
  - binary_sensor:
      - name: "Skyss Has Planned Disruptions"
        unique_id: skyss_has_planned_disruptions
        device_class: problem
        state: >
          {{ state_attr('sensor.skyss_disruption_summary', 'planned_disruptions') | int(0) > 0 }}
        icon: >
          {% if this.state == 'on' %}
            mdi:calendar-alert
          {% else %}
            mdi:calendar-check
          {% endif %}

  # Optional: Helper for any disruptions across individual line sensors
  - binary_sensor:
      - name: "Skyss Has Disruptions"
        unique_id: skyss_has_disruptions
        device_class: problem
        state: >
       {{ not is_state('sensor.skyss_disruption_sky_line_1', 'Normal service') 
         or not is_state('sensor.skyss_disruption_sky_line_2', 'Normal service') 
         or not is_state('sensor.skyss_disruption_sky_line_3', 'Normal service') }}
        icon: >
          {% if this.state == 'on' %}
            mdi:bus-alert
          {% else %}
            mdi:bus-check
          {% endif %}

  - sensor:
      - name: "Skyss Active Disruptions"
        unique_id: skyss_active_disruptions
        unit_of_measurement: "disruptions"
        state: >
          {{ [
            states('sensor.skyss_disruption_sky_line_1'),
            states('sensor.skyss_disruption_sky_line_2'),
            states('sensor.skyss_disruption_sky_line_3')
          ] | reject('eq', 'Normal service') | list | count }}
        icon: mdi:counter
```

### Future: Automatic Template Helpers

> **Note:** The integration could potentially create these template helpers automatically in a future version. This would allow users to have a single "has disruptions" binary sensor per operator without manual configuration.

**If you'd like this feature**, please open an issue on GitHub with your use case!

---

## Advanced: Auto-generating Cards for All Lines

Use this template to automatically create cards for all lines in a device without manually listing entities.

### Configuration

```yaml
type: vertical-stack
cards:
  - type: markdown
    content: >-
      ## 🚌 Skyss Disruptions
      
      {% set ns = namespace(has_disruptions=false) %}
      {% for entity in integration_entities('entur_sx') %}
        {% if 'skyss' in entity.lower() and not is_state(entity, 'Normal service') and not is_state(entity, 'unavailable') %}
          {% set ns.has_disruptions = true %}
          
      ### {{ state_attr(entity, 'line_ref') or entity.split('.')[-1] }}
      
      **{{ states(entity) }}**
      
      {{ state_attr(entity, 'description') }}
      
      *Status: {{ state_attr(entity, 'status') }} | Progress: {{ state_attr(entity, 'progress') }}*
      
      ---
        {% endif %}
      {% endfor %}
      
      {% if not ns.has_disruptions %}
      Normal service
      {% endif %}
```

---

## Tips and Tricks

### Icon Selection by Transit Mode
- **Bus**: `mdi:bus`, `mdi:bus-alert`, `mdi:bus-side`
- **Tram/Light Rail**: `mdi:tram`, `mdi:tram-side`
- **Train**: `mdi:train`, `mdi:train-variant`
- **Metro**: `mdi:subway-variant`, `mdi:subway`
- **Ferry**: `mdi:ferry`, `mdi:ferry-boat`
- **General**: `mdi:alert-circle`, `mdi:information`, `mdi:transit-connection-variant`

### Status-based Coloring

Use these conditions to color-code by status attribute:

```yaml
{% set status = state_attr('sensor.skyss_disruption_sky_line_1', 'status') %}
{% if status == 'open' %}
  <ha-alert alert-type="error">  <!-- Red for active disruptions -->
{% elif status == 'planned' %}
  <ha-alert alert-type="info">  <!-- Blue for planned work -->
{% elif status == 'expired' %}
  <ha-alert alert-type="success">  <!-- Green for resolved -->
{% else %}
  <ha-alert alert-type="warning">  <!-- Yellow/orange for other -->
{% endif %}
```

### Formatting Dates

Format the validity times nicely:

```jinja
Valid from: {{ state_attr('sensor.skyss_disruption_sky_line_1', 'valid_from') | as_timestamp | timestamp_custom('%d.%m.%Y %H:%M') }}
Valid to: {{ state_attr('sensor.skyss_disruption_sky_line_1', 'valid_to') | as_timestamp | timestamp_custom('%d.%m.%Y %H:%M') if state_attr('sensor.skyss_disruption_sky_line_1', 'valid_to') else 'Until further notice' }}
```

### Mobile-Friendly Cards

For mobile dashboards, use more compact formatting:

```yaml
type: markdown
content: >-
  {% if not is_state('sensor.skyss_disruption_sky_line_1', 'Normal service') %}
  🚌 **Line 1**: {{ states('sensor.skyss_disruption_sky_line_1') }}
  {% endif %}
```

### Notification Automation Example

Create an automation to notify you of new disruptions:

```yaml
automation:
  # Notify on new active disruptions
  - alias: "Notify on Active Transit Disruption"
    trigger:
      - platform: state
  entity_id: sensor.skyss_disruption_summary
        attribute: active_disruptions
    condition:
      - condition: template
        value_template: "{{ trigger.to_state.attributes.active_disruptions | int > trigger.from_state.attributes.active_disruptions | int }}"
    action:
      - service: notify.mobile_app
        data:
          title: "⚠️ Active Transit Disruption"
          message: >
            {{ trigger.to_state.attributes.active_disruptions }} active disruption(s) on Skyss lines
          data:
            tag: "skyss_active_disruptions"
            group: "transit"

  # Notify on new planned disruptions
  - alias: "Notify on Planned Transit Disruption"
    trigger:
      - platform: state
  entity_id: sensor.skyss_disruption_summary
        attribute: planned_disruptions
    condition:
      - condition: template
        value_template: "{{ trigger.to_state.attributes.planned_disruptions | int > trigger.from_state.attributes.planned_disruptions | int }}"
    action:
      - service: notify.mobile_app
        data:
          title: "ℹ️ Planned Transit Disruption"
          message: >
            {{ trigger.to_state.attributes.planned_disruptions }} planned disruption(s) on Skyss lines
          data:
            tag: "skyss_planned_disruptions"
            group: "transit"
            
  # Or notify on individual line disruptions
  - alias: "Notify on Individual Line Disruption"
    trigger:
      - platform: state
  entity_id: sensor.skyss_disruption_sky_line_1
        to: ~
    condition:
      - condition: template
        value_template: "{{ trigger.to_state.state != 'Normal service' }}"
    action:
      - service: notify.mobile_app
        data:
          title: "Transit Disruption"
          message: >
            {{ state_attr(trigger.entity_id, 'line_ref') }}: 
            {{ trigger.to_state.state }}
          data:
            tag: "transit_disruption_{{ trigger.entity_id }}"
            group: "transit"
```

---

## Need Help?

- Check the [main README](README.md) for integration setup
- Report issues on [GitHub](https://github.com/DTekNO/ha-entur_sx/issues)
- The entity attributes available:
  - `line_ref` - The line reference (e.g., "SKY:Line:1")
  - `valid_from` - When the disruption starts
  - `valid_to` - When the disruption ends (null if ongoing)
  - `description` - Full description of the disruption
  - `status` - Status: "open", "planned", or "expired"
  - `progress` - Progress: "open", "closed", "published"
  - `all_deviations` - List of all active disruptions for the line (if multiple)
  - `total_deviations` - Count of active disruptions
  - `deviations_by_status` - Count grouped by status

