# Submission Checklist for Entur SX Brand Assets

Use this checklist when submitting to Home Assistant brands repository.

## Pre-Submission

- [ ] All SVG files converted to PNG
- [ ] PNG files optimized (under 10KB each preferred)
- [ ] Transparent backgrounds verified
- [ ] Correct dimensions verified:
  - icon.png: 256x256px
  - dark_icon.png: 256x256px
  - logo.png: 256x128px (if included)
  - dark_logo.png: 256x128px (if included)

## Repository Setup

- [ ] Forked https://github.com/home-assistant/brands
- [ ] Created `brands/custom_integrations/entur_sx/` folder
- [ ] Copied PNG files to folder
- [ ] No SVG files included in submission (PNG only)

## Pull Request

Use this template for your PR:

### Title
```
Add Entur SX integration logos
```

### Description
```
This PR adds brand assets for the Entur Situation Exchange (entur_sx) custom integration.

**Integration**: Entur Situation Exchange
**Domain**: entur_sx
**Type**: Custom Integration

**Files included:**
- icon.png (256x256px, X KB)
- dark_icon.png (256x256px, X KB)
- logo.png (256x128px, X KB) [if included]
- dark_logo.png (256x128px, X KB) [if included]

**Design attribution:**
Based on Entur AS official app icon design. Entur branding used with respect to their brand guidelines.

**Links:**
- Entur official branding: https://linje.entur.no/identitet/verktoykassen/logo
- Integration repository: https://github.com/DTekNO/ha-entur_sx
```

## Verification

- [ ] PR created
- [ ] CI/CD checks passing
- [ ] Images displayed correctly in preview
- [ ] No linting errors

## Post-Submission

- [ ] Responded to reviewer feedback (if any)
- [ ] PR merged
- [ ] Brand assets visible in Home Assistant brands repository
- [ ] Integration manifest.json domain matches folder name (entur_sx)

## Notes

Remember that brand assets may take time to propagate to Home Assistant after merge. The assets will become available in future Home Assistant releases.
