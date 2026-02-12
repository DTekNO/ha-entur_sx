"""Sensor platform for Entur Situation Exchange."""

from __future__ import annotations

from datetime import datetime
from html.parser import HTMLParser
import logging
import os
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_DEVICE_NAME,
    CONF_LINE_TRANSPORT_MODES,
    CONF_SUMMARY_ICON,
    DEFAULT_SUMMARY_ICON,
    DOMAIN,
    STATE_NORMAL,
    STATUS_EXPIRED,
    STATUS_OPEN,
    STATUS_PLANNED,
    normalize_language,
)
from .coordinator import EnturSXDataUpdateCoordinator
from .icon_constants import TRANSPORT_COLORS, TRANSPORT_ICONS

_LOGGER = logging.getLogger(__name__)


class HTMLSanitizer(HTMLParser):
    """Simple HTML parser to fix unclosed tags."""
    
    def __init__(self):
        super().__init__()
        self.result = []
        self.open_tags = []
        # Block-level tags that should be closed
        self.block_tags = {'ul', 'ol', 'li', 'div', 'p', 'table', 'tr', 'td', 'th', 'tbody', 'thead'}
        # Inline tags that should be auto-closed when parent block closes
        self.inline_tags = {'b', 'strong', 'i', 'em', 'u', 'a', 'span', 'code', 'small'}
        # Self-closing tags
        self.self_closing = {'br', 'img', 'hr', 'input', 'meta', 'link'}
        # All tags we track
        self.closing_tags = self.block_tags | self.inline_tags
    
    def handle_starttag(self, tag, attrs):
        """Handle opening tag."""
        attr_str = ''.join(f' {name}="{value}"' for name, value in attrs)
        self.result.append(f'<{tag}{attr_str}>')
        if tag in self.closing_tags:
            self.open_tags.append(tag)
    
    def handle_endtag(self, tag):
        """Handle closing tag."""
        if tag in self.closing_tags:
            # If this is a block tag closing, first close any open inline tags
            if tag in self.block_tags:
                # Close inline tags that are inside this block
                inline_to_close = []
                for open_tag in reversed(self.open_tags):
                    if open_tag == tag:
                        break
                    if open_tag in self.inline_tags:
                        inline_to_close.append(open_tag)
                
                # Close the inline tags
                for inline_tag in inline_to_close:
                    self.result.append(f'</{inline_tag}>')
                    self.open_tags.remove(inline_tag)
            
            # Now close the actual tag
            if tag in self.open_tags:
                # Close this tag and any improperly nested tags
                while self.open_tags and self.open_tags[-1] != tag:
                    unclosed = self.open_tags.pop()
                    self.result.append(f'</{unclosed}>')
                if self.open_tags and self.open_tags[-1] == tag:
                    self.open_tags.pop()
                    self.result.append(f'</{tag}>')
    
    def handle_data(self, data):
        """Handle text data."""
        self.result.append(data)
    
    def close_all(self):
        """Close any remaining open tags."""
        while self.open_tags:
            tag = self.open_tags.pop()
            self.result.append(f'</{tag}>')
    
    def get_result(self):
        """Get sanitized HTML."""
        self.close_all()
        return ''.join(self.result)


def _sanitize_html(html: str) -> str:
    """Sanitize HTML by closing any unclosed tags."""
    if not html or '<' not in html:
        return html
    
    try:
        parser = HTMLSanitizer()
        parser.feed(html)
        return parser.get_result()
    except Exception as err:
        _LOGGER.debug("Failed to sanitize HTML, returning original: %s", err)
        return html


async def _async_load_template(hass: HomeAssistant, lang: str = "no") -> str | None:
    """Load Jinja2 template asynchronously based on language."""
    try:
        # Choose template based on language
        template_name = "formatted_content_no.j2" if lang == "no" else "formatted_content.j2"
        
        # Get the directory where this module is located
        module_dir = os.path.dirname(__file__)
        template_path = os.path.join(module_dir, "templates", template_name)

        # Read template file asynchronously
        def _read_template():
            with open(template_path, encoding="utf-8") as f:
                return f.read()

        template_content = await hass.async_add_executor_job(_read_template)
        _LOGGER.debug("Successfully loaded formatted_content template")
        return template_content
    except FileNotFoundError:
        _LOGGER.warning(
            "Template file not found: %s. Formatted content will not be available.",
            template_path,
        )
        return None
    except Exception as err:
        _LOGGER.error(
            "Failed to load formatted_content template: %s. Formatted content will not be available.",
            err,
            exc_info=True,
        )
        return None


def _format_datetime_norwegian(dt: datetime) -> str:
    """Format datetime in Norwegian.
    
    Args:
        dt: datetime object to format
        
    Returns:
        Formatted string like "Mandag, 19. januar kl. 12:00"
    """
    # Norwegian day names
    norwegian_days = {
        0: "mandag",
        1: "tirsdag",
        2: "onsdag",
        3: "torsdag",
        4: "fredag",
        5: "lørdag",
        6: "søndag"
    }
    
    # Norwegian month names
    norwegian_months = {
        1: "januar",
        2: "februar",
        3: "mars",
        4: "april",
        5: "mai",
        6: "juni",
        7: "juli",
        8: "august",
        9: "september",
        10: "oktober",
        11: "november",
        12: "desember"
    }
    
    day_name = norwegian_days[dt.weekday()].capitalize()
    month_name = norwegian_months[dt.month]
    
    return f"{day_name}, {dt.day:02d}. {month_name} kl. {dt.strftime('%H:%M')}"


def _detect_transport_mode(line_ref: str) -> str:
    """Detect transport mode from line reference.
    
    Entur line references follow pattern: Authority:Line:LineNumber
    Examples:
    - RUT:Line:1 (Oslo tram line 1)
    - ATB:Line:3 (Trondheim bus line 3)
    - NSB:Line:L1 (train)
    
    For now, use simple heuristics based on line number patterns.
    Future: Could query Entur API for line details.
    """
    # Default to bus if uncertain
    transport_mode = "bus"
    
    # Tram lines in Norway are typically numbered 11-19 or single digits 1-9 in Oslo
    # Train lines often have 'L' prefix or are in higher ranges
    # Ferry lines often contain 'F' or specific patterns
    
    line_parts = line_ref.split(":")
    if len(line_parts) >= 3:
        line_number = line_parts[-1].upper()
        
        # Train patterns
        if line_number.startswith("L") or line_number.startswith("R"):
            transport_mode = "train"
        # Tram patterns (Oslo/Bergen)
        elif line_number.isdigit() and 11 <= int(line_number) <= 19:
            transport_mode = "tram"
        # Metro patterns
        elif line_number.isdigit() and 1 <= int(line_number) <= 6:
            # Could be tram or metro - check authority
            if "RUT" in line_ref:
                transport_mode = "metro"
            else:
                transport_mode = "tram"
    
    return transport_mode


def _create_badge_svg(transport_mode: str, line_name: str) -> str:
    """Create a complete SVG badge as a data URL.
    
    Creates an Entur TravelTag-style badge with:
    - Colored rounded rectangle background
    - Transport mode icon (embedded from data URL)
    - Line number text
    
    Uses proportional scaling system where all dimensions scale from text font size.
    """
    import base64
    import re
    
    # Get icon and color from constants
    icon_data_url = TRANSPORT_ICONS.get(transport_mode, TRANSPORT_ICONS["bus"])
    bg_color = TRANSPORT_COLORS.get(transport_mode, TRANSPORT_COLORS["bus"])
    
    # Proportional scaling parameters - all dimensions scale from font size
    TEXT_FONT_SIZE = 14
    BADGE_HEIGHT_SCALE = 2.25
    ICON_SIZE_SCALE = 1.875
    PADDING_LEFT_SCALE = 0.625
    PADDING_RIGHT_SCALE = 0.75
    GAP_SCALE = 0.5
    BORDER_RADIUS_SCALE = 0.375
    TEXT_VERTICAL_OFFSET_SCALE = 0.125
    ICON_VERTICAL_OFFSET_SCALE = 0
    TEXT_FONT_WEIGHT = "500"
    
    # Calculate actual dimensions
    badge_height = TEXT_FONT_SIZE * BADGE_HEIGHT_SCALE
    icon_size = TEXT_FONT_SIZE * ICON_SIZE_SCALE
    padding_left = TEXT_FONT_SIZE * PADDING_LEFT_SCALE
    padding_right = TEXT_FONT_SIZE * PADDING_RIGHT_SCALE
    gap = TEXT_FONT_SIZE * GAP_SCALE
    border_radius = TEXT_FONT_SIZE * BORDER_RADIUS_SCALE
    icon_vertical_offset = TEXT_FONT_SIZE * ICON_VERTICAL_OFFSET_SCALE
    text_vertical_offset = TEXT_FONT_SIZE * TEXT_VERTICAL_OFFSET_SCALE
    
    # Extract the base64 content from icon data URL
    icon_match = re.search(r'data:image/svg\+xml;base64,(.+)', icon_data_url)
    if not icon_match:
        return ""
    
    icon_base64 = icon_match.group(1)
    icon_svg = base64.b64decode(icon_base64).decode('utf-8')
    
    # Extract just the SVG content (remove XML declaration and svg wrapper)
    # We'll embed the paths directly
    icon_content = ""
    path_matches = re.findall(r'<(path|g|rect|circle|polygon)[^>]*>.*?</\1>|<(path|rect|circle|polygon)[^>]*/>', icon_svg, re.DOTALL)
    if path_matches:
        for match in path_matches:
            # Find the full match in original string
            for pattern in [r'<path[^>]*>.*?</path>', r'<path[^>]*/>',
                           r'<g[^>]*>.*?</g>', r'<rect[^>]*/>',
                           r'<circle[^>]*/>',  r'<polygon[^>]*/>', r'<polygon[^>]*>.*?</polygon>']:
                found = re.search(pattern, icon_svg, re.DOTALL)
                if found:
                    content = found.group(0)
                    # Replace any fill colors with white
                    content = re.sub(r'fill="[^"]*"', 'fill="#FFFFFF"', content)
                    icon_content += content
    
    # Calculate text width (approximate - proportional to font size)
    char_width_ratio = 0.5625  # Characters are ~56.25% of font size width
    text_width = len(line_name) * TEXT_FONT_SIZE * char_width_ratio
    
    # Calculate badge dimensions
    badge_width = padding_left + icon_size + gap + text_width + padding_right
    
    # Calculate vertical positions with offsets for alignment
    icon_y = (badge_height - icon_size) / 2 + icon_vertical_offset
    text_y = badge_height / 2 + text_vertical_offset
    
    # Create the complete badge SVG
    badge_svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{badge_width}" height="{badge_height}" viewBox="0 0 {badge_width} {badge_height}">
  <rect width="{badge_width}" height="{badge_height}" rx="{border_radius}" fill="{bg_color}"/>
  <g transform="translate({padding_left}, {icon_y}) scale({icon_size / 16})">
    {icon_content}
  </g>
  <text x="{padding_left + icon_size + gap}" y="{text_y}" font-family="system-ui, -apple-system, sans-serif" font-size="{TEXT_FONT_SIZE}" font-weight="{TEXT_FONT_WEIGHT}" fill="#FFFFFF" dominant-baseline="middle">{line_name}</text>
</svg>'''
    
    # Encode as data URL
    badge_base64 = base64.b64encode(badge_svg.encode('utf-8')).decode('utf-8')
    return f"data:image/svg+xml;base64,{badge_base64}"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Entur SX sensors from a config entry."""
    coordinator: EnturSXDataUpdateCoordinator = hass.data[DOMAIN][
        entry.entry_id
    ]

    # Get the list of lines to monitor - merge data and options
    # (options takes precedence)
    config_data = {**entry.data, **entry.options}
    lines = config_data.get("lines_to_check", [])
    line_transport_modes = config_data.get(CONF_LINE_TRANSPORT_MODES, {})

    # Get language from HA's setting
    lang = normalize_language(hass.config.language)

    # Load Jinja2 template asynchronously for formatted_content
    template_content = await _async_load_template(hass, lang)

    # Clean up entities for lines that are no longer configured
    entity_registry = er.async_get(hass)

    # Get all entities for this config entry
    current_entities = er.async_entries_for_config_entry(
        entity_registry, entry.entry_id
    )

    # Build set of expected unique IDs
    expected_unique_ids = {
        f"{entry.entry_id}_{line_ref.replace(':', '_')}" for line_ref in lines
    }

    # Add summary sensor unique ID if enabled
    if config_data.get("create_summary_sensors", False):
        expected_unique_ids.add(f"{entry.entry_id}_summary")

    # Remove entities that are no longer configured
    for entity_entry in current_entities:
        if entity_entry.unique_id not in expected_unique_ids:
            _LOGGER.info(
                "Removing entity %s (unique_id: %s) - line no longer "
                "configured",
                entity_entry.entity_id,
                entity_entry.unique_id,
            )
            entity_registry.async_remove(entity_entry.entity_id)

    # Create a sensor for each line
    entities = []
    for line_ref in lines:
        # Clean the line name for entity ID (replace : with _)
        line_name = line_ref.replace(":", "_")
        transport_mode = line_transport_modes.get(line_ref)  # May be None for old configs
        entities.append(EnturSXSensor(coordinator, entry, line_ref, line_name, template_content, lang, transport_mode))

    # Create summary sensor if configured
    if config_data.get("create_summary_sensors", False):
        entities.append(EnturSXSummarySensor(coordinator, entry, lines, template_content, lang))

    _LOGGER.info("Setting up %d Entur SX sensors", len(entities))
    # Update entities immediately with coordinator's existing data
    # before adding
    async_add_entities(entities, True)


class EnturSXSensor(
    CoordinatorEntity[EnturSXDataUpdateCoordinator], SensorEntity
):
    """Sensor for a single Entur transit line deviation status."""

    _attr_has_entity_name = True
    _unrecorded_attributes = frozenset({"formatted_content", "entity_picture"})

    def __init__(
        self,
        coordinator: EnturSXDataUpdateCoordinator,
        entry: ConfigEntry,
        line_ref: str,
        line_name: str,
        template_content: str | None,
        lang: str = "no",
        transport_mode: str | None = None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.line_ref = line_ref
        self.line_name = line_name
        self.transport_mode = transport_mode  # Store API-provided transport mode (may be None for old configs)

        device_name = entry.data.get(CONF_DEVICE_NAME, "Entur Avvik")

        # Unique ID
        self._attr_unique_id = f"{entry.entry_id}_{line_name}"

        # Entity name is the line reference
        self._attr_name = line_ref

        # Device info - all lines belong to the same device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=device_name,
            manufacturer="Entur AS",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://entur.no",
        )

        # Icon
        self._attr_icon = "mdi:bus-alert"

        # Store pre-loaded template content
        self._template_content = template_content
        self._formatted_content_template = None
        self._lang = lang
        if template_content:
            self._compile_template(template_content)

        # Cache for badge SVG (generated once per line)
        self._badge_svg_cache = None

    @property
    def entity_picture(self) -> str | None:
        """Return the entity picture as a TravelTag badge."""
        if self._badge_svg_cache is None:
            # Generate badge once and cache it
            # Use stored transport mode from API if available, otherwise fall back to heuristic
            transport_mode = self.transport_mode if self.transport_mode else _detect_transport_mode(self.line_ref)
            line_name = self.line_ref.split(":")[-1]
            self._badge_svg_cache = _create_badge_svg(transport_mode, line_name)
        
        return self._badge_svg_cache

    def _compile_template(self, template_string: str) -> None:
        """Compile Jinja2 template from string."""
        try:
            from jinja2 import Template

            self._formatted_content_template = Template(template_string)
            _LOGGER.debug("Successfully compiled formatted_content template for %s", self.line_ref)
        except Exception as err:
            _LOGGER.error(
                "Failed to compile formatted_content template: %s. Formatted content will not be available.",
                err,
                exc_info=True,
            )
            self._formatted_content_template = None

    def _generate_formatted_content(self, disruptions: list[dict]) -> str:
        """Generate formatted content from template."""
        if self._formatted_content_template is None:
            return "Template not available"
        
        if not disruptions:
            disruptions = []
        
        # Use stored transport mode from API if available, otherwise fall back to heuristic
        transport_mode = self.transport_mode if self.transport_mode else _detect_transport_mode(self.line_ref)
        line_name = self.line_ref.split(":")[-1]  # Extract just the line number
        
        # Create the badge SVG
        badge_svg = _create_badge_svg(transport_mode, line_name)
        
        # Prepare disruption data with badge SVG and formatted dates
        enriched_disruptions = []
        for disruption in disruptions:
            enriched = disruption.copy()
            enriched["transport_mode"] = transport_mode
            enriched["line_name"] = line_name
            enriched["badge_svg"] = badge_svg
            
            # Sanitize description HTML to fix unclosed tags from API
            if "description" in enriched and enriched["description"]:
                enriched["description"] = _sanitize_html(enriched["description"])
            
            # Format dates
            valid_from = disruption.get("valid_from", "")
            valid_to = disruption.get("valid_to", "")
            
            if valid_from:
                try:
                    from_dt = datetime.fromisoformat(valid_from.replace("Z", "+00:00"))
                    if self._lang == "no":
                        enriched["valid_from_formatted"] = _format_datetime_norwegian(from_dt)
                    else:
                        enriched["valid_from_formatted"] = from_dt.strftime("%A, %d %B at %H:%M")
                except (ValueError, AttributeError):
                    enriched["valid_from_formatted"] = valid_from
            
            if valid_to:
                try:
                    to_dt = datetime.fromisoformat(valid_to.replace("Z", "+00:00"))
                    if self._lang == "no":
                        enriched["valid_to_formatted"] = _format_datetime_norwegian(to_dt)
                    else:
                        enriched["valid_to_formatted"] = to_dt.strftime("%A, %d %B at %H:%M")
                except (ValueError, AttributeError):
                    enriched["valid_to_formatted"] = valid_to
            
            enriched_disruptions.append(enriched)
        
        try:
            return self._formatted_content_template.render(
                disruptions=enriched_disruptions,
            )
        except Exception as err:
            _LOGGER.error("Failed to render formatted_content template: %s", err)
            return f"Error rendering template: {err}"

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor.
        
        Returns the summary of the most recent deviation.
        """
        if not self.coordinator.data:
            return None

        line_data = self.coordinator.data.get(self.line_ref, [])
        # Empty line_data means no disruptions - will return STATE_NORMAL below

        # Filter to only active (open) disruptions that are within
        # their time window
        now_timestamp = datetime.now().timestamp()
        active_disruptions = []

        for item in line_data:
            status = item.get("status")

            # Only consider open status disruptions
            if status != STATUS_OPEN:
                continue

            # Verify the disruption is within its time window
            valid_from = item.get("valid_from")
            valid_to = item.get("valid_to")

            if not valid_from:
                continue

            try:
                start_timestamp = datetime.fromisoformat(
                    valid_from
                ).timestamp()

                # Check if disruption has started
                if now_timestamp < start_timestamp:
                    continue

                # Check if disruption has ended (if end time is specified)
                if valid_to:
                    end_timestamp = datetime.fromisoformat(
                        valid_to
                    ).timestamp()
                    if now_timestamp > end_timestamp:
                        continue

                # This disruption is currently active
                active_disruptions.append(item)
            except (ValueError, AttributeError):
                # Skip items with invalid timestamps
                continue

        # If no active disruptions, return normal state
        if not active_disruptions:
            return STATE_NORMAL

        # If there's only one active disruption, return its summary
        if len(active_disruptions) == 1:
            summary = active_disruptions[0].get("summary", "Disruption")
            # Truncate if too long
            if len(summary) > 255:
                return summary[:252] + "..."
            return summary

        # Multiple active disruptions - combine their summaries
        summaries = [
            item.get("summary", "Unknown disruption")
            for item in active_disruptions
        ]

        # Join with separator for readability
        combined = " | ".join(summaries)

        # If the combined summary is too long, truncate appropriately
        if len(combined) > 255:
            # Use count format with truncated first summary
            count_prefix = f"{len(active_disruptions)} active disruptions: "
            max_summary_len = 255 - len(count_prefix) - 3  # -3 for "..."
            first_summary = summaries[0][:max_summary_len] + "..."
            return count_prefix + first_summary

        return combined

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional attributes."""
        if not self.coordinator.data:
            return None

        line_data = self.coordinator.data.get(self.line_ref, [])
        if not line_data:
            return None

        # Get the most recent deviation
        current = line_data[0]

        attrs = {
            "valid_from": current.get("valid_from"),
            "valid_to": current.get("valid_to"),
            "summary": current.get("summary"),
            "description": current.get("description"),
            "status": current.get("status"),
            "progress": current.get("progress"),
            "line_ref": self.line_ref,
        }

        # Include all deviations if there are multiple
        if len(line_data) > 1:
            attrs["all_deviations"] = line_data
            attrs["total_deviations"] = len(line_data)

            # Count by status
            status_counts = {}
            for item in line_data:
                status = item.get("status", "unknown")
                status_counts[status] = status_counts.get(status, 0) + 1
            attrs["deviations_by_status"] = status_counts

        # Add formatted_content for markdown card display
        attrs["formatted_content"] = self._generate_formatted_content(line_data)

        return attrs


class EnturSXSummarySensor(
    CoordinatorEntity[EnturSXDataUpdateCoordinator], SensorEntity
):
    """Summary sensor with markdown-ready content for all monitored lines."""

    _attr_has_entity_name = True
    _unrecorded_attributes = frozenset({"markdown_active", "markdown_planned"})

    def __init__(
        self,
        coordinator: EnturSXDataUpdateCoordinator,
        entry: ConfigEntry,
        lines: list[str],
        template_content: str | None,
        lang: str = "no",
    ) -> None:
        """Initialize the summary sensor."""
        super().__init__(coordinator)
        self.lines = lines
        self._lang = lang
        
        # Store pre-loaded template content
        self._template_content = template_content
        self._formatted_content_template = None
        if template_content:
            self._compile_template(template_content)

        device_name = entry.data.get(CONF_DEVICE_NAME, "Entur Disruption")
        config_data = {**entry.data, **entry.options}
        icon = config_data.get(CONF_SUMMARY_ICON, DEFAULT_SUMMARY_ICON)

        # Unique ID
        self._attr_unique_id = f"{entry.entry_id}_summary"

        # Entity name
        self._attr_name = "Summary"

        # Icon
        self._attr_icon = icon

        # Device info - belongs to the same device as line sensors
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=device_name,
            manufacturer="Entur AS",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://entur.no",
        )

    def _compile_template(self, template_string: str) -> None:
        """Compile Jinja2 template from string."""
        try:
            from jinja2 import Template

            self._formatted_content_template = Template(template_string)
            _LOGGER.debug("Successfully compiled formatted_content template for summary sensor")
        except Exception as err:
            _LOGGER.error(
                "Failed to compile formatted_content template: %s. Formatted content will not be available.",
                err,
                exc_info=True,
            )
            self._formatted_content_template = None

    @property
    def native_value(self) -> int:
        """Return simple state based on active (open) disruption count."""
        if not self.coordinator.data:
            return 0

        active_count = 0
        for line_ref in self.lines:
            line_data = self.coordinator.data.get(line_ref, [])
            # Empty line_data means no disruptions for this line
            if not line_data:
                continue
                
            # Check if line has active (open) disruptions
            status = line_data[0].get("status")
            if status == STATUS_OPEN:
                active_count += 1

        # Return numeric state for easy filtering/automation
        return active_count

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes.
        
        Includes markdown_active and markdown_planned with TravelTag badges for each disrupted line.
        """
        if not self.coordinator.data:
            no_planned = "Ingen planlagte avvik" if self._lang == "no" else "No planned disruptions"
            return {
                "total_lines": len(self.lines),
                "active_disruptions": 0,
                "planned_disruptions": 0,
                "normal_lines": len(self.lines),
                "markdown_active": STATE_NORMAL,
                "markdown_planned": no_planned,
            }

        active_lines = set()
        planned_lines = set()
        normal = []
        active_disruptions_list = []
        planned_disruptions_list = []

        for line_ref in self.lines:
            line_data = self.coordinator.data.get(line_ref, [])
            if not line_data or line_data[0].get("summary") == STATE_NORMAL:
                normal.append(line_ref)
                continue

            # Detect transport mode and create badge for this line
            transport_mode = _detect_transport_mode(line_ref)
            line_name = line_ref.split(":")[-1]
            badge_svg = _create_badge_svg(transport_mode, line_name)

            # Track if this line has any non-expired deviations
            has_active = False
            has_planned = False

            # Process all deviations for this line
            for deviation in line_data:
                status = deviation.get("status")

                # Skip expired deviations
                if status == STATUS_EXPIRED:
                    continue

                # Extract deviation details
                summary = deviation.get("summary", "Unknown disruption")
                description = deviation.get("description", "")
                valid_from = deviation.get("valid_from", "")
                valid_to = deviation.get("valid_to", "")
                
                # Sanitize description HTML to fix unclosed tags from API
                if description:
                    description = _sanitize_html(description)
                
                # Format dates for display
                valid_from_formatted = valid_from
                valid_to_formatted = valid_to
                
                if valid_from:
                    try:
                        from_dt = datetime.fromisoformat(valid_from.replace("Z", "+00:00"))
                        if self._lang == "no":
                            valid_from_formatted = _format_datetime_norwegian(from_dt)
                        else:
                            valid_from_formatted = from_dt.strftime("%A, %d %B at %H:%M")
                    except (ValueError, AttributeError):
                        pass
                
                if valid_to:
                    try:
                        to_dt = datetime.fromisoformat(valid_to.replace("Z", "+00:00"))
                        if self._lang == "no":
                            valid_to_formatted = _format_datetime_norwegian(to_dt)
                        else:
                            valid_to_formatted = to_dt.strftime("%A, %d %B at %H:%M")
                    except (ValueError, AttributeError):
                        pass
                
                # Build enriched disruption dict for template
                disruption_dict = {
                    'transport_mode': transport_mode,
                    'line_name': line_name,
                    'badge_svg': badge_svg,
                    'summary': summary,
                    'description': description,
                    'valid_from_formatted': valid_from_formatted,
                    'valid_to_formatted': valid_to_formatted,
                    'status': status
                }

                # Categorize by status
                if status == STATUS_OPEN:
                    has_active = True
                    active_lines.add(line_ref)
                    active_disruptions_list.append(disruption_dict)
                elif status == STATUS_PLANNED:
                    has_planned = True
                    planned_lines.add(line_ref)
                    planned_disruptions_list.append(disruption_dict)
                else:
                    # Unknown status - include in active for safety
                    has_active = True
                    active_lines.add(line_ref)
                    active_disruptions_list.append(disruption_dict)

            # If line has no non-expired deviations, mark as normal
            if not has_active and not has_planned:
                normal.append(line_ref)

        # Render markdown using template
        if not active_disruptions_list:
            markdown_active = STATE_NORMAL
        else:
            if self._formatted_content_template:
                try:
                    markdown_active = self._formatted_content_template.render(
                        disruptions=active_disruptions_list
                    )
                    # Add normal service footer
                    if normal or planned_lines:
                        normal_count = len(normal) + len(planned_lines)
                        if self._lang == "no":
                            markdown_active += (
                                f"\n*{normal_count} linje(r) med normal drift*\n"
                            )
                        else:
                            markdown_active += (
                                f"\n*{normal_count} line(s) with normal service*\n"
                            )
                except Exception as err:
                    _LOGGER.error("Failed to render active disruptions template: %s", err)
                    markdown_active = "Error rendering template"
            else:
                markdown_active = "Template not available"

        # Render planned disruptions using template
        if not planned_disruptions_list:
            markdown_planned = "Ingen planlagte avvik" if self._lang == "no" else "No planned disruptions"
        else:
            if self._formatted_content_template:
                try:
                    markdown_planned = self._formatted_content_template.render(
                        disruptions=planned_disruptions_list
                    )
                    # Add normal service footer
                    if normal or active_lines:
                        normal_count = len(normal) + len(active_lines)
                        if self._lang == "no":
                            markdown_planned += (
                                f"\n*{normal_count} linje(r) med normal drift*\n"
                            )
                        else:
                            markdown_planned += (
                                f"\n*{normal_count} line(s) with normal service*\n"
                            )
                except Exception as err:
                    _LOGGER.error("Failed to render planned disruptions template: %s", err)
                    markdown_planned = "Error rendering template"
            else:
                markdown_planned = "Template not available"

        return {
            "total_lines": len(self.lines),
            "active_disruptions": len(active_lines),
            "planned_disruptions": len(planned_lines),
            "normal_lines": len(normal),
            "active_line_refs": list(active_lines),
            "planned_line_refs": list(planned_lines),
            "normal_line_refs": normal,
            "markdown_active": markdown_active,
            "markdown_planned": markdown_planned,
        }
