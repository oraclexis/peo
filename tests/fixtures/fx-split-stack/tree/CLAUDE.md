# Project instructions
Front-end in Nuxt with server rendering at the root; back office in Laravel under `backend/`.
## Commands
```bash
npm run dev
npm run build
npm run typecheck
```
## Rules
- Keep every page server-rendered; browser-only code runs in `onMounted`.
- Import client-only libraries dynamically.
- No `border-radius` anywhere: corners stay square.
- Use color tokens only; never a raw color value.
- Spacing comes from the spacing token scale.
- One font family, loaded from the design tokens.
- Respect `prefers-reduced-motion` for every animation.
- Keep the main bundle small: lazy-load heavy 3D scenes.
- Keep components small; split files above 300 lines.
## Structure
Pages live in `app/pages/`, components in `app/components/`.
Shared logic lives in `app/composables/`.
Styles live in `app/assets/css/`.
The back office runs in Docker: see the `Makefile`.
## Testing
Unit tests use Vitest; end-to-end tests use Playwright.
## Priorities
TODO (priority): write `ContentBlock.vue` to render content blocks.
