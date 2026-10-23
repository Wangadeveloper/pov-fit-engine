# Implementation Plan — Qloo-First POV Confidence & Gender Expression

## What changes

1. **Style Expression field** — add inclusive `style_expression` to FitProfile (Masculine / Feminine / Fluid / Non-binary / Prefer not to say). Used as a Qloo signal, never shown publicly.
2. **Conditional catalogue** — new accounts see a clean, unscored catalogue. Once taste is saved (aesthetic + cultural interests), catalogue re-sorts by Qloo POV% descending with badges.
3. **Qloo as primary engine** — Qloo resonance now drives 70% of the composite score (vs 50%). Style expression feeds Qloo aesthetic matching.
4. **Onboarding UX** — new Step 0 (style expression) before the fit steps, zero pressure, easy to skip.
5. **DB migration** — adds `style_expression` column to `fit_profiles`.
