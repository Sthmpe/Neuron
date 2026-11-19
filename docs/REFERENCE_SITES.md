# Reference sites (step 7): waiting for the owner's approval

Three sites built by NEURON itself from an owner's request, with the 8 GB model (gemma-4-E4B), on 2026-11-18.
The requests are in `benchmark/reference_sites/requests.json` (fictional businesses; every price, time, day and
address on the pages comes from the request; no phone numbers were given, so none appear). Measured results:
`benchmark/results/reference_sites.json`. Rebuild: `python3 -m benchmark.reference_sites.run --tier 8gb`.

| Site | Build time | Model calls | Words checked on the finished page | Owner facts on the page | Sideways scrolling (phone, tablet, desktop) | Photos |
|---|---|---|---|---|---|---|
| Law firm (Okafor & Bello) | 501 s | 6 | no problems | all | 0, 0, 0 px | 1 of 3 licensed (hero: law library shelves), 2 placeholders |
| Bakery (Iya Bisi's) | 342 s | 4 | no problems | all | 0, 0, 0 px | 2 of 3 licensed (hero: artisan loaves; bakery counter; both CC0), 1 placeholder |
| Salon (Glow Hair Studio) | 327 s | 4 | no problems | all | 0, 0, 0 px | **3 of 3 licensed**; the job is fully VERIFIED |

Screenshots (phone 390 px, tablet 820 px, desktop 1440 px wide, full page):
`docs/screens/reference/<law_firm|bakery|salon>-<phone|tablet|desktop>.png`

## What the checks guarantee

- Nothing invented: no testimonials, reviews, statistics, years of experience, awards, qualifications, opening
  hours or contact details beyond what the owner wrote (rules in `neuron/design/content.py`, checked on the plan
  and again on the finished page).
- Every owner fact is on the page: each price, duration, time, day range and address in the request.
- No leftover template text, stock phrases, repeated sentences, duplicated sections, empty cards, or a line under
  the headline that names nothing of the business.
- Design checks in a real browser at three widths: 0 failures on all three sites.

## What the first builds found (all fixed before these)

- The planner left out the address, hours and fee; cards had no words; the kit repeated a section beside the form.
- Five priced products filled five phone screens as tall cards (now a compact price list); the line under the
  headline was generic ("Baking delicious treats for you"); information rows were numbered like steps; a one-item
  section showed as a lonely "01"; the photo row's spacing made the design review inflate every page.
- The first licensed photo chosen for the law firm was a baroque ceiling painting: artworks are now refused, and a
  rejected photo is never picked again.

## Honest limits

- **Photos.** Wikimedia Commons rate-limits this shared cloud machine's address as a whole ("too many requests"),
  so photos arrive slowly: 6 of 9 so far, found by NEURON's own retries (sources in each site's `IMAGE_CREDITS.md`). NEURON backs off and retries by itself (a polite retry runs every 15 minutes
  and retakes the screenshots when photos arrive); it never tries to get around the limit. Until then the pages show
  on-brand placeholders that say "Image needed". On a home connection this step is expected to work but is not yet
  verified. The owner's own photos always come first (attach them to the job).
- One page per site (hero, sections, photos, form). No multi-page sites, maps, menus with photos or online payment.
- The words are correct and specific but plain; they are the 8 GB model's words, checked by rules, not a copywriter's.

## Waiting for you

This track stops here until you approve. After approval: the same standard for documents and slides, then the
20-request design rerun.
