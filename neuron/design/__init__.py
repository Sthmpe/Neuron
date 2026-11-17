"""NEURON design engine (build time). Taste lives here as rules and data, not in the model.

  color   - perceptual colour maths (OKLCH), contrast, tonal scales, lightness-only contrast fixes
  names   - colour words people use ("navy", "terracotta", "#1f6feb") -> colours
  mood    - who the site is for -> the feeling it should give -> every later choice
  engine  - mood + optional user colours + seed -> a complete, explained design (tokens + variants)
  check   - renders a page in a real browser and finds what a designer would notice
  fix     - turns findings into token changes, then the page is checked again
"""
