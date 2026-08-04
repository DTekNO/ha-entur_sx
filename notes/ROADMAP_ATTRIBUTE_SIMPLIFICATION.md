# Roadmap — simplify the line sensor attributes

**Status:** agreed direction, not started. Nothing in 2026.8.1 depends on it.
**Decided:** 2026-08-04.

## Why

The attribute surface accumulated historically. The original plan was to build
displays with markdown cards, which cannot iterate, so the integration
pre-rendered everything: entity-level `formatted_content`, per-alert
`formatted_content`, and the summary sensor's `markdown_active` /
`markdown_planned`. On top of that, each disruption appears twice — a flat copy
of the current one at the top level, and the full list in `all_deviations` (see
"Line Sensor Attribute Structure" in `TECHNICAL_DETAILS.md`).

[ha-alert-card](https://github.com/DTekNO/ha-alert-card) iterates
`all_deviations` directly, which is both more flexible and more honest about the
data. It can show `publisher_name` and `severity` — added in 2026.8.1 — which
pre-rendered markdown cannot. So the array is the model to standardise on and
the pre-rendered markdown is the thing to retire.

The compatibility cost of doing this is low: the integration has very few users
beyond the author.

## Already true — no work needed

**The sensor state already concatenates all active summaries.** `native_value()`
joins every currently-active disruption's summary with `" | "`, which is exactly
the "concatenation of all summary texts" wanted for history. It also already
handles the 255-character state limit by falling back to
`"<n> active disruptions: <truncated first summary>…"`.

Measured against the live all-Norway feed (349 situations, 150 lines with active
disruptions):

| | value |
|---|---|
| concatenated state length | median 35, p90 107, **max 203** chars |
| lines exceeding the 255-char limit | **0** |
| max active disruptions on one line | 5 |
| individual summary length | median 34, max 163 chars |

So the truncation path is correct to keep but does not fire in practice. A line
would need roughly six or more simultaneous disruptions to trip it.

## Plan

### Stage 1 — documentation only, no behaviour change
- Rework `CARD_EXAMPLES.md` around iterating `all_deviations`. A verified
  starting template is in the appendix below; it replaces `markdown_active`
  entirely and additionally shows publisher and severity.
- Mark as deprecated in README: the summary sensor's `markdown_active` /
  `markdown_planned`, and the bulky flat fields.
- Keep everything working. This stage is reversible.

### Stage 2 — shrink the recorded surface
Target: **only `state` is recorded**; anyone wanting more builds a template
sensor from `all_deviations`.

Reaching that means adding the remaining flat attributes to
`_unrecorded_attributes` (currently `formatted_content`, `all_deviations`,
`entity_picture`, `travel_tag`).

Before doing it, confirm the debugging use case is genuinely covered — see the
caveat below.

### Stage 3 — remove pre-rendered markdown
Retire entity-level `formatted_content`, per-alert `formatted_content`, and the
summary sensor's markdown attributes, once the card examples no longer reference
them.

**Keep the summary sensor's numeric state regardless.** It is the graphable,
automatable signal and no template replaces it cheaply. Only its markdown
attributes are candidates for removal.

## Caveat worth resolving before stage 2

The stated reason for recording history is that situations are transient, and it
is useful to capture them for testing or to find out what went wrong overnight —
for example if the parser broke.

For the "what was disrupted at 03:00" question, the concatenated state is
sufficient. For "the parser broke overnight", attribute history is the wrong
tool and always was; the state would simply show `normal` or stale data with no
indication why. The right tools are:

- the per-situation `WARNING` added in 2026.8.1, which names the
  `SituationNumber` it skipped and no longer discards the whole feed on one bad
  entry
- the existing disruption tracking log (`TECHNICAL_DETAILS.md`), including its
  optional persistent log file

So stage 2 is safe for the *observability* goal, but only if the logging is
actually enabled when it matters. Worth confirming the tracking log captures
enough before dropping the attributes, since the loss is irreversible for any
period already recorded.

## Appendix — verified replacement template

Reproduces `markdown_active` from `all_deviations`, and adds publisher and
severity. Verified by rendering against real parsed feed data. Swap `'open'` for
`'planned'` to get `markdown_planned`.

```jinja
{%- set ns = namespace(rows=[]) -%}
{%- for s in states.sensor if s.attributes.line_ref is defined -%}
  {%- for d in state_attr(s.entity_id, 'all_deviations') or [] -%}
    {%- if d.status == 'open' -%}
      {%- set ns.rows = ns.rows + [(s.attributes.friendly_name, d)] -%}
    {%- endif -%}
  {%- endfor -%}
{%- endfor -%}
{%- if ns.rows -%}
{%- for name, d in ns.rows %}
### {{ name }} — {{ d.summary }}

{{ d.description }}

*{{ d.publisher_name }}{% if d.report_type %} · {{ d.report_type }}{% endif %}{% if d.severity == 'noImpact' %} · advisory{% endif %}*
{{ d.valid_from | as_timestamp | timestamp_custom('%a %d %b %H:%M') }} → {{ d.valid_to | as_timestamp | timestamp_custom('%a %d %b %H:%M') if d.valid_to else 'until further notice' }}
{% endfor %}
{%- else -%}
No active disruptions.
{%- endif -%}
```

Renders as:

```
### Jektavik - Hodnanes — Trafikkmelding
Grunna transport av utrykningskjøretøy vil avganger avvike frå rutetabell…
*GCO · general · advisory*
Tue 04 Aug 08:55 → Wed 05 Aug 08:55

### Line 1 - Bergen sentrum — Haldeplass Nonneseter stengd
…
*Skyss · incident*
Wed 18 Feb 12:00 → until further notice
```

One caveat: `s.attributes.line_ref is defined` matches any sensor carrying a
`line_ref` attribute. Tighten with an `entity_id` prefix check if another
integration ever uses the same attribute name.
