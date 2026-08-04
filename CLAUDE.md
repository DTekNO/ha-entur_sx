# Guidance for AI coding agents

Full project conventions live in
[.github/copilot-instructions.md](.github/copilot-instructions.md) — read that
first. It applies to any agent, not just Copilot. This file adds the bits worth
having in front of you before you touch anything.

## Entur documentation is machine-readable — use it

Do not scrape the HTML site or guess at API behaviour.

| URL | What it is |
|---|---|
| `https://developer.entur.no/llms.txt` | Index of every doc page, ~7 KB — **start here as an agent** |
| `https://developer.entur.no/llms-full.txt` | All documentation in one file, ~200 KB |
| `https://developer.entur.no/<path>.md` | Any page as Markdown, e.g. `/docs/authentication.md` |
| `https://developer.entur.no/docs/getting-started.md` | Human onboarding: service tiers, `ET-Client-Name`, first call |

Entur's own guidance calls `/llms.txt` "the best starting point for any LLM", and
that holds up — `getting-started.md` is written for a person arriving new, and
its Markdown rendering leaks raw MDX components (`<Card className=…>`, `zudoku/ui`
imports), so it is mostly noise to an agent. Read it for orientation and
conventions; use `llms.txt` to find things.

These live at the **site root**, not under `/docs`: `/llms.txt` works,
`/docs/llms.txt` is a 404.

For anything SIRI-related start at `/open-data/realtime.md` — it holds the
"Available data streams" table, the authoritative list of codespace owners.

**`ET-Client-Name` is mandatory on every Entur API, open or partner**, and must
be `<company>-<application>`, lowercase and without spaces. Requests lacking it
may be rate limited or blocked. This integration sends `homeassistant-entur-sx`;
keep any new call site consistent with that.

## Assume the Entur API is correct

It is well implemented. When our data looks wrong, the bug is almost always in
this repo — usually querying the wrong thing rather than the API answering
badly. Two real examples:

- `operators` vs `authorities`: a codespace's *owner* is an authority. Reading a
  name out of `operators` returns whichever company happens to run a service in
  that codespace, which is a different question, not a wrong answer.
- `ParticipantRef` vs `SituationNumber`: the publisher is the codespace prefix
  of `SituationNumber`. `ParticipantRef` just echoes the dataset you asked for.

Content *can* be imperfect — publisher-authored HTML in descriptions has broken
things before (see `HTMLSanitizer` in `sensor.py`, and re-escape anything you
re-emit). Distinguish "the feed content is messy" from "the API is wrong".

Also expect real-world churn: Norwegian transport authorities rebrand and merge
regularly (NSB→Vy, Troms fylkestrafikk→Svipper) while their codespace tag stays
stable for continuity. A name mismatch usually means `CODESPACE_NAMES` has gone
stale, not that Entur made a mistake.

## Duplicate-looking alerts are usually genuine

Two publishers often report the same real-world event. Line 1033 has carried a
Skyss `incident` and a Fjord1-via-GCO `general` message for one emergency-vehicle
transport. Check `situation_number` before concluding there is a parsing bug;
`Severity: noImpact` tends to mark the redundant one.

## Verify against the live feed

Claims about feed shape should be checked, not assumed — the JSON rendering is
inconsistent (`{"value": x}` vs bare scalars, singletons as object or array):

```bash
curl -H "ET-Client-Name: <you>-<app>" -H "Accept: application/json" \
  "https://api.entur.io/realtime/v1/rest/sx?datasetId=SKY"
```

Omit `datasetId` for all of Norway. `_parse_response()` can be driven directly
against a saved response to check parsing end to end.

## Releases

Version strings in `manifest.json` are owned by release automation — do not bump
them as part of a change.
