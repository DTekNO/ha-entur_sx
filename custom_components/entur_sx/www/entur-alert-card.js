/**
 * Entur Alert Timeline Card
 * 
 * A custom Lovelace card that displays transport alerts in a collapsible timeline format.
 * Shows current and future disruptions sorted by start time.
 */

class EnturAlertCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._expanded = {};
  }

  setConfig(config) {
    if (!config.entity) {
      throw new Error('Please define an entity');
    }
    this.config = config;
    this.render();
  }

  set hass(hass) {
    this._hass = hass;
    this.render();
  }

  _toggleExpand(eventId) {
    this._expanded[eventId] = !this._expanded[eventId];
    this.render();
  }

  _formatDate(dateStr) {
    if (!dateStr) return '';
    try {
      const date = new Date(dateStr);
      const now = new Date();
      const tomorrow = new Date(now);
      tomorrow.setDate(tomorrow.getDate() + 1);
      
      const isToday = date.toDateString() === now.toDateString();
      const isTomorrow = date.toDateString() === tomorrow.toDateString();
      
      const time = date.toLocaleTimeString(this._hass.language, { 
        hour: '2-digit', 
        minute: '2-digit' 
      });
      
      if (isToday) return `Today at ${time}`;
      if (isTomorrow) return `Tomorrow at ${time}`;
      
      return date.toLocaleDateString(this._hass.language, {
        weekday: 'short',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch (e) {
      return dateStr;
    }
  }

  _getTimelinePosition(startDate) {
    // Returns a percentage for positioning on timeline (0 = now, 100 = far future)
    const now = new Date();
    const start = new Date(startDate);
    const diffHours = (start - now) / (1000 * 60 * 60);
    
    if (diffHours < 0) return 0; // Past/current
    if (diffHours > 168) return 100; // More than a week
    return Math.min((diffHours / 168) * 100, 100);
  }

  render() {
    if (!this._hass || !this.config) return;

    const stateObj = this._hass.states[this.config.entity];
    if (!stateObj) {
      this.shadowRoot.innerHTML = `
        <ha-card>
          <div class="card-content">
            Entity ${this.config.entity} not found
          </div>
        </ha-card>
      `;
      return;
    }

    const allDisruptions = stateObj.attributes.new_disruptions || [];
    const showPlanned = this.config.show_planned !== false;
    const showOnlyNew = this.config.show_only_new === true;
    const maxItems = this.config.max_items || 10;

    // Get all disruptions from active and planned lists
    let disruptions = [];
    if (showOnlyNew) {
      disruptions = allDisruptions;
    } else {
      // Combine active and planned disruptions from markdown attributes
      // For now, use new_disruptions as the source
      // TODO: Could parse markdown_active/markdown_planned for full list
      disruptions = allDisruptions;
    }

    // Sort by start time
    disruptions.sort((a, b) => {
      const aTime = new Date(a.valid_from || 0);
      const bTime = new Date(b.valid_from || 0);
      return aTime - bTime;
    });

    disruptions = disruptions.slice(0, maxItems);

    const title = this.config.title || 'Transport Alerts';
    const showTimeline = this.config.show_timeline !== false;

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
        }
        ha-card {
          padding: 16px;
        }
        .card-header {
          font-size: 24px;
          font-weight: 500;
          margin-bottom: 16px;
          display: flex;
          justify-content: space-between;
          align-items: center;
        }
        .count-badge {
          background: var(--primary-color);
          color: var(--text-primary-color);
          border-radius: 12px;
          padding: 4px 12px;
          font-size: 14px;
          font-weight: 600;
        }
        .timeline {
          position: relative;
          margin: 20px 0;
        }
        .timeline-line {
          position: absolute;
          left: 12px;
          top: 0;
          bottom: 0;
          width: 2px;
          background: var(--divider-color);
        }
        .alert-item {
          position: relative;
          margin: 0 0 16px 0;
          padding-left: ${showTimeline ? '40px' : '0'};
        }
        .timeline-dot {
          position: absolute;
          left: 0;
          top: 8px;
          width: 24px;
          height: 24px;
          border-radius: 50%;
          background: var(--card-background-color);
          border: 3px solid var(--primary-color);
          z-index: 1;
        }
        .timeline-dot.planned {
          border-color: var(--warning-color);
        }
        .alert-card {
          background: var(--secondary-background-color);
          border-radius: 8px;
          padding: 12px 16px;
          border-left: 3px solid var(--primary-color);
          cursor: pointer;
          transition: all 0.2s;
        }
        .alert-card.planned {
          border-left-color: var(--warning-color);
        }
        .alert-card:hover {
          background: var(--divider-color);
        }
        .alert-header {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          gap: 12px;
        }
        .alert-main {
          flex: 1;
        }
        .alert-line {
          font-weight: 600;
          margin-bottom: 4px;
          display: inline-flex;
          align-items: center;
          gap: 8px;
        }
        .line-badge {
          display: inline-block;
          padding: 2px 8px;
          border-radius: 4px;
          background: var(--primary-color);
          color: var(--text-primary-color);
          font-size: 12px;
          font-weight: 600;
        }
        .alert-summary {
          font-size: 14px;
          color: var(--primary-text-color);
          margin-bottom: 4px;
        }
        .alert-time {
          font-size: 12px;
          color: var(--secondary-text-color);
        }
        .expand-icon {
          color: var(--secondary-text-color);
          transition: transform 0.2s;
          font-size: 20px;
        }
        .expand-icon.expanded {
          transform: rotate(180deg);
        }
        .alert-details {
          margin-top: 12px;
          padding-top: 12px;
          border-top: 1px solid var(--divider-color);
          font-size: 13px;
          line-height: 1.5;
          color: var(--secondary-text-color);
        }
        .alert-details p {
          margin: 8px 0;
        }
        .empty-state {
          text-align: center;
          padding: 32px 16px;
          color: var(--secondary-text-color);
        }
        .empty-icon {
          font-size: 48px;
          opacity: 0.3;
          margin-bottom: 16px;
        }
      </style>
      <ha-card>
        <div class="card-header">
          <span>${title}</span>
          ${disruptions.length > 0 ? `<span class="count-badge">${disruptions.length}</span>` : ''}
        </div>
        ${disruptions.length === 0 ? `
          <div class="empty-state">
            <div class="empty-icon">✓</div>
            <div>No disruptions</div>
          </div>
        ` : `
          <div class="timeline">
            ${showTimeline ? '<div class="timeline-line"></div>' : ''}
            ${disruptions.map(alert => {
              const isExpanded = this._expanded[alert.disruption_id];
              const isPlanned = alert.status === 'planned';
              return `
                <div class="alert-item">
                  ${showTimeline ? `<div class="timeline-dot ${isPlanned ? 'planned' : ''}"></div>` : ''}
                  <div class="alert-card ${isPlanned ? 'planned' : ''}" 
                       data-id="${alert.disruption_id}">
                    <div class="alert-header">
                      <div class="alert-main">
                        <div class="alert-line">
                          <span class="line-badge">${alert.line_name || ''}</span>
                          ${isPlanned ? '<span style="color: var(--warning-color);">⏰ Planned</span>' : ''}
                        </div>
                        <div class="alert-summary">${alert.summary || 'No summary'}</div>
                        <div class="alert-time">
                          ${this._formatDate(alert.valid_from)}
                          ${alert.valid_to ? ' → ' + this._formatDate(alert.valid_to) : ''}
                        </div>
                      </div>
                      <span class="expand-icon ${isExpanded ? 'expanded' : ''}">▼</span>
                    </div>
                    ${isExpanded && alert.description ? `
                      <div class="alert-details">
                        ${alert.description}
                      </div>
                    ` : ''}
                  </div>
                </div>
              `;
            }).join('')}
          </div>
        `}
      </ha-card>
    `;

    // Add click handlers
    this.shadowRoot.querySelectorAll('.alert-card').forEach(card => {
      card.addEventListener('click', () => {
        const id = card.dataset.id;
        this._toggleExpand(id);
      });
    });
  }

  getCardSize() {
    return 3;
  }
}

customElements.define('entur-alert-card', EnturAlertCard);

// Register the card with Home Assistant
window.customCards = window.customCards || [];
window.customCards.push({
  type: 'entur-alert-card',
  name: 'Entur Alert Card',
  description: 'Display Entur transport disruptions in a timeline format',
  preview: false,
});

console.info(
  '%c  ENTUR-ALERT-CARD  \n%c  Version 1.0.0     ',
  'color: orange; font-weight: bold; background: black',
  'color: white; font-weight: bold; background: dimgray',
);
