# Translation Notes

AudioEnhancerMAX currently mixes English and Italian strings across the app UI and public landing page.

## Where Text Lives

- App shell and panels: `frontend/index.html`
- Runtime UI strings and toast messages: `frontend/js/app.js`
- Public site: `web/index.html`
- App-served landing page: `frontend/landing.html`

When updating the public site, keep `web/index.html` and `frontend/landing.html` aligned unless there is a deliberate reason to diverge.

## Suggested Workflow

1. Add or update the English source text.
2. Mirror the user-facing Italian text where it already exists.
3. Verify text length on mobile widths.
4. Avoid changing API field names when translating labels.
