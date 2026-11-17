"""Design tokens -> one stylesheet. The component rules below use ONLY var(--...) values: no colour,
font, radius or shadow is written here directly, so a new design is a new theme.json, never new CSS.
Light mode only. Separation comes from spacing, soft shadows and background tone, never border lines."""
import json
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
_lock = threading.Lock()
_cache = {}


def load(path="theme.json"):
    """The project's theme, or the kit's default theme."""
    p = Path(path)
    key = str(p.resolve()) if p.exists() else "default"
    with _lock:
        if key not in _cache:
            src = p if p.exists() else HERE / "default_theme.json"
            _cache[key] = json.loads(src.read_text())
        return _cache[key]


def reset():
    with _lock:
        _cache.clear()


def _sizes(ratio, base=17):
    r = float(ratio)
    px = lambda n: round(base * r ** n, 1)
    return {"xs": max(13, px(-2)), "sm": max(14.5, px(-1)), "md": base, "lg": px(1), "xl": px(2), "2xl": px(3),
            "3xl": px(4), "4xl": px(5), "display": px(6.2)}


def css(theme):
    t = theme["tokens"]
    fonts = "".join(
        f"@font-face{{font-family:'{FAMILY[f]}';src:url('/static/fonts/{f}.woff2') format('woff2');"
        f"font-weight:{'400' if f == 'instrument-serif' else '200 900'};font-style:normal;font-display:swap}}"
        for f in theme.get("fonts", []) if f in FAMILY)
    s = _sizes(t.get("ratio", 1.25))
    root = ";".join(f"--{k}:{v}" for k, v in t.items() if k != "ratio")
    sizes = ";".join(f"--fs-{k}:{v / 16:.4f}rem" for k, v in s.items())
    return fonts + f":root{{{root};{sizes}}}" + COMPONENTS


FAMILY = {"inter": "Inter", "manrope": "Manrope", "plus-jakarta-sans": "Plus Jakarta Sans", "dm-sans": "DM Sans", "outfit": "Outfit",
          "figtree": "Figtree", "nunito": "Nunito", "fraunces": "Fraunces", "playfair-display": "Playfair Display",
          "source-serif-4": "Source Serif 4", "lora": "Lora", "bricolage-grotesque": "Bricolage Grotesque",
          "cormorant-garamond": "Cormorant Garamond", "sora": "Sora", "libre-franklin": "Libre Franklin",
          "instrument-serif": "Instrument Serif"}

COMPONENTS = """
*,*::before,*::after{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;scroll-behavior:smooth}
body{margin:0;background:var(--color-bg);color:var(--color-ink);font-family:var(--font-body);font-size:var(--body-size);line-height:1.6;
 -webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility;overflow-wrap:break-word}
h1,h2,h3,h4{font-family:var(--font-heading);font-weight:var(--heading-weight);letter-spacing:var(--heading-tracking);color:var(--color-heading);
 line-height:1.12;margin:0 0 calc(var(--space)*2);text-wrap:balance}
h1{font-size:var(--fs-3xl)}h2{font-size:var(--fs-2xl)}h3{font-size:var(--fs-lg);line-height:1.3}
p{margin:0 0 calc(var(--space)*2);max-width:62ch;text-wrap:pretty}
a{color:var(--color-link);text-decoration-thickness:1px;text-underline-offset:3px}
:focus-visible{outline:3px solid var(--color-focus);outline-offset:3px;border-radius:4px}
.icon{display:block;flex:none}
.wrap{width:100%;max-width:1160px;margin:0 auto;padding-inline:clamp(20px,5vw,40px)}
.narrow-wrap{max-width:460px}
.lead{font-size:var(--fs-lg);color:var(--color-ink-muted);line-height:1.55}
.muted{color:var(--color-ink-muted)}
.eyebrow{display:inline-flex;align-items:center;gap:8px;font-family:var(--font-body);font-size:var(--fs-xs);font-weight:650;
 text-transform:var(--label-case);letter-spacing:var(--label-tracking);color:var(--color-accent-ink);margin:0 0 calc(var(--space)*2)}
.on-strong .eyebrow{color:var(--color-on-strong-muted)}
.skip{position:absolute;left:-9999px}.skip:focus{left:16px;top:16px;z-index:50;background:var(--color-surface);padding:8px 14px;border-radius:var(--radius-sm)}

/* buttons: one primary action per screen, everything else quieter */
.btn{display:inline-flex;align-items:center;justify-content:center;gap:10px;min-height:48px;padding:0 26px;border:0;cursor:pointer;
 font:inherit;font-weight:650;font-size:var(--fs-md);text-decoration:none;border-radius:var(--radius-button);
 background:var(--color-surface-2);color:var(--color-ink);transition:background-color .15s ease,transform .15s ease,box-shadow .15s ease;justify-self:start}
.btn:hover{background:var(--color-surface-3)}
.btn-primary{background:var(--color-action);color:var(--color-on-action);box-shadow:var(--shadow-sm)}
.btn-primary:hover{background:var(--color-action-hover);box-shadow:var(--shadow);transform:translateY(-1px)}
.btn-ghost{background:transparent;color:var(--color-ink-muted);padding:0 12px;min-height:44px}
.btn-ghost:hover{background:var(--color-surface-2);color:var(--color-ink)}
.btn .icon{width:18px;height:18px}
.on-strong .btn-secondary{background:transparent;color:var(--color-on-strong)}
.on-strong>.wrap>div>.hero-actions .btn-primary,.hero-banner .btn-primary{background:var(--color-on-strong);color:var(--color-strong)}
.hero-banner .btn-primary:hover{background:var(--color-on-strong);opacity:.92}

/* top bar */
.topbar{position:sticky;top:0;z-index:20}
.bar{display:flex;align-items:center;gap:12px;min-height:72px;flex-wrap:wrap}
.nav-bar .topbar-inner{background:var(--color-surface);box-shadow:var(--shadow-sm)}
.nav-minimal .topbar-inner{background:var(--color-bg)}
.nav-floating{padding-top:12px}.nav-floating .bar{background:var(--color-surface);box-shadow:var(--shadow);border-radius:calc(var(--radius-lg) + 8px);padding:0 10px 0 22px;min-height:64px}
.brand{display:inline-flex;align-items:center;gap:10px;font-family:var(--font-heading);font-weight:var(--heading-weight);font-size:var(--fs-lg);
 letter-spacing:var(--heading-tracking);color:var(--color-heading);text-decoration:none;margin-right:auto;line-height:1.1}
.brand-mark{display:grid;place-items:center;width:34px;height:34px;border-radius:var(--radius-sm);background:var(--color-strong);color:var(--color-on-strong);
 font-size:var(--fs-md);font-family:var(--font-heading)}
.menu{display:none;flex-basis:100%;flex-direction:column;gap:2px;padding:4px 0 12px;order:3}
.menu a{padding:12px 14px;color:var(--color-ink-muted);text-decoration:none;border-radius:var(--radius-sm);font-weight:550}
.menu a:hover{color:var(--color-ink);background:var(--color-surface-2)}.menu a.active{color:var(--color-ink);background:var(--color-surface-2)}
.nav-toggle{display:grid;place-items:center;width:44px;height:44px;border-radius:var(--radius-sm);cursor:pointer;order:2;color:var(--color-ink);user-select:none}
.nav-toggle:hover{background:var(--color-surface-2)}#nav-toggle:checked~.menu{display:flex}
.account{display:flex;align-items:center;gap:6px;order:1}.who{display:none;color:var(--color-ink-muted);font-size:var(--fs-sm)}
@media(min-width:760px){.who{display:inline}}
@media(min-width:760px){.menu{display:flex;flex-basis:auto;flex-direction:row;padding:0;order:0;margin-left:auto}
 .menu a{padding:10px 14px}.nav-toggle{display:none}.brand{margin-right:24px}.account{order:1;margin-left:8px}}

/* page shells */
main{display:block}
.page-head{padding:calc(var(--space)*6) 0 calc(var(--space)*3)}
.page-head h1{font-size:var(--fs-2xl);margin:0}
.app-main{padding-bottom:calc(var(--space)*10)}
.section{padding-block:calc(var(--section-space)*0.62)}
@media(min-width:900px){.section{padding-block:var(--section-space)}}
.tone-1{background:var(--color-bg)}.tone-2{background:var(--color-surface-2)}
.tone-strong{background:var(--color-strong);color:var(--color-on-strong)}
.tone-strong h1,.tone-strong h2,.tone-strong h3{color:var(--color-on-strong)}.tone-strong p,.tone-strong .lead{color:var(--color-on-strong-muted)}
.section-head{max-width:720px;margin-bottom:calc(var(--space)*6)}
.section-head.center{margin-inline:auto;text-align:center}.section-head.center p{margin-inline:auto}
.section-head h2{margin-bottom:calc(var(--space)*1.5)}

/* hero */
.hero{padding-block:calc(var(--space)*8) calc(var(--space)*9)}
.hero h1{font-size:clamp(var(--fs-2xl),3.2vw + 1rem,var(--fs-display));line-height:1.04;margin-bottom:calc(var(--space)*3)}
.hero .lead{margin-bottom:calc(var(--space)*4)}
.hero-actions{display:flex;flex-wrap:wrap;gap:12px;align-items:center}
@media(min-width:900px){.hero{padding-block:calc(var(--space)*13) calc(var(--space)*14)}}
.hero-split .hero-grid{display:grid;gap:calc(var(--space)*6);align-items:center}
@media(min-width:900px){.hero-split .hero-grid{grid-template-columns:1.15fr 0.85fr;gap:calc(var(--space)*10)}}
.hero-visual{background:var(--color-surface);border-radius:var(--radius-lg);box-shadow:var(--shadow-lg);padding:calc(var(--space)*3.5)}
.hero-visual .hv-head{font-size:var(--fs-xs);font-weight:650;text-transform:var(--label-case);letter-spacing:var(--label-tracking);color:var(--color-ink-muted);margin:4px 6px calc(var(--space)*2)}
.hv-item{display:flex;align-items:center;gap:14px;padding:14px;border-radius:var(--radius);}
.hv-item+.hv-item{margin-top:6px}.hv-item:nth-child(even){background:var(--color-surface-2)}
.hv-item strong{display:block;font-weight:650;line-height:1.3}.hv-item span:not(.icon-wrap){color:var(--color-ink-muted);font-size:var(--fs-sm);line-height:1.4;display:block}
.monogram{display:grid;place-items:center;aspect-ratio:1/1;border-radius:var(--radius-lg);background:var(--color-support-soft);color:var(--color-support-ink);
 font-family:var(--font-heading);font-size:clamp(4rem,12vw,9rem);font-weight:var(--heading-weight);box-shadow:var(--shadow)}
.hero-centered{text-align:center}.hero-centered h1,.hero-centered .lead{margin-inline:auto;max-width:18ch}.hero-centered .lead{max-width:46ch}
.hero-centered .hero-actions{justify-content:center}
.chips{display:flex;flex-wrap:wrap;gap:10px;justify-content:center;margin-top:calc(var(--space)*7)}
.chip{display:inline-flex;align-items:center;gap:10px;padding:10px 18px 10px 12px;background:var(--color-surface);border-radius:999px;box-shadow:var(--shadow-sm);font-weight:600;font-size:var(--fs-sm)}
.chip .icon-wrap{width:30px;height:30px}
.hero-editorial h1{font-size:clamp(var(--fs-3xl),5vw + 1rem,calc(var(--fs-display)*1.15));max-width:16ch}
.hero-editorial .ed-grid{display:grid;gap:calc(var(--space)*3)}
@media(min-width:900px){.hero-editorial .ed-grid{grid-template-columns:1fr 1fr;align-items:end;gap:calc(var(--space)*10)}.hero-editorial .ed-grid .lead{margin-bottom:calc(var(--space)*3)}}
.highlights{display:grid;gap:calc(var(--space)*3);margin-top:calc(var(--space)*9)}
@media(min-width:760px){.highlights{grid-template-columns:repeat(auto-fit,minmax(200px,1fr))}}
.highlight{display:flex;gap:14px;align-items:flex-start}.highlight strong{display:block;line-height:1.3}.highlight span:not(.icon-wrap){display:block;color:var(--color-ink-muted);font-size:var(--fs-sm)}
.hero-banner{background:var(--color-strong);color:var(--color-on-strong)}
.hero-banner h1{color:var(--color-on-strong);max-width:15ch}.hero-banner .lead{color:var(--color-on-strong-muted)}
.hero-banner .hero-grid{display:grid;gap:calc(var(--space)*6);align-items:center}
@media(min-width:900px){.hero-banner .hero-grid{grid-template-columns:1.2fr .8fr;gap:calc(var(--space)*10)}}
.banner-list{display:grid;gap:12px}
.banner-list .bl-item{display:flex;align-items:center;gap:14px;padding:16px 18px;border-radius:var(--radius);background:color-mix(in oklab,var(--color-on-strong) 9%,transparent)}
.banner-list strong{display:block;line-height:1.3}.banner-list span:not(.icon-wrap){display:block;font-size:var(--fs-sm);color:var(--color-on-strong-muted)}
.banner-list .icon{color:var(--color-on-strong)}
.hero-card{background:var(--color-surface-2)}
.hero-card .hc-grid{display:grid;gap:calc(var(--space)*4);align-items:center}
@media(min-width:900px){.hero-card .hc-grid{grid-template-columns:1.3fr .7fr;gap:calc(var(--space)*6)}}
.hero-card .hc-card{background:var(--color-surface);border-radius:calc(var(--radius-lg) + 6px);box-shadow:var(--shadow-lg);padding:clamp(28px,5vw,64px)}
.hero-card .hc-card h1{font-size:clamp(var(--fs-2xl),3vw + 1rem,var(--fs-4xl))}
.side-list{display:grid;gap:10px}
.side-list .sl-item{display:flex;align-items:center;gap:12px;background:var(--color-surface);border-radius:var(--radius);padding:14px 16px;box-shadow:var(--shadow-sm);font-weight:600}

/* icon tiles */
.icon-wrap{display:inline-flex;align-items:center;justify-content:center;width:48px;height:48px;border-radius:var(--radius);background:var(--color-accent-soft);color:var(--color-accent-ink);flex:none}
.icon-wrap .icon{width:22px;height:22px}
.icon-wrap.quiet{background:var(--color-support-soft);color:var(--color-support-ink)}
.icon-wrap.num{font-family:var(--font-heading);font-weight:var(--heading-weight);font-size:var(--fs-md)}
.tone-strong .icon-wrap{background:color-mix(in oklab,var(--color-on-strong) 12%,transparent);color:var(--color-on-strong)}

/* features */
.f-cards{display:grid;gap:calc(var(--space)*3);grid-template-columns:repeat(auto-fit,minmax(min(100%,250px),1fr))}
.f-card{background:var(--color-surface);border-radius:var(--radius-lg);box-shadow:var(--shadow);padding:calc(var(--space)*4)}
.f-card h3{margin:calc(var(--space)*2.5) 0 var(--space)}.f-card p{color:var(--color-ink-muted);margin:0}
.f-list{display:grid;gap:calc(var(--space)*4) calc(var(--space)*6)}
@media(min-width:760px){.f-list{grid-template-columns:repeat(2,1fr)}}
.f-list .fl-item{display:flex;gap:18px;align-items:flex-start}.f-list h3{margin:6px 0 6px}.f-list p{color:var(--color-ink-muted);margin:0}
.f-rows{display:grid;gap:calc(var(--space)*2)}
.f-rows .fr-item{display:grid;grid-template-columns:auto 1fr;grid-template-areas:"num title" "num text";column-gap:calc(var(--space)*3);row-gap:4px;align-items:start;padding:calc(var(--space)*3.5);border-radius:var(--radius-lg);background:var(--color-surface);box-shadow:var(--shadow-sm)}
.tone-2 .f-rows .fr-item{background:var(--color-surface)}
.f-rows .fr-num{grid-area:num;font-family:var(--font-heading);font-size:var(--fs-2xl);line-height:1;color:var(--color-accent-ink);min-width:2.2ch;font-weight:var(--heading-weight)}
.f-rows h3{grid-area:title;margin:4px 0 0}.f-rows p{grid-area:text;margin:0;color:var(--color-ink-muted)}
@media(min-width:900px){.f-rows .fr-item{grid-template-columns:96px minmax(0,1fr) minmax(0,1.3fr);grid-template-areas:"num title text";align-items:center;column-gap:calc(var(--space)*4)}.f-rows h3{margin:0}}
.f-tiles{display:grid;gap:calc(var(--space)*2);grid-template-columns:repeat(auto-fit,minmax(min(100%,230px),1fr))}
.f-tile{background:var(--color-support-soft);border-radius:var(--radius-lg);padding:calc(var(--space)*4)}
.tone-2 .f-tile{background:var(--color-surface)}
.f-tile h3{margin:calc(var(--space)*3) 0 var(--space)}.f-tile p{margin:0;color:var(--color-ink-muted)}
.f-tile .icon-wrap{background:var(--color-surface);color:var(--color-support-ink)}
.f-steps{display:grid;gap:calc(var(--space)*4);grid-template-columns:repeat(auto-fit,minmax(min(100%,220px),1fr));counter-reset:step}
.f-steps .fs-item h3{margin:calc(var(--space)*2.5) 0 var(--space)}.f-steps p{margin:0;color:var(--color-ink-muted)}
.step-num{display:grid;place-items:center;width:44px;height:44px;border-radius:999px;background:var(--color-strong);color:var(--color-on-strong);font-weight:700}

/* single facts */
.fact-callout{text-align:center}
.fact-callout .fact-text{font-family:var(--font-heading);font-size:clamp(var(--fs-xl),2.4vw + 1rem,var(--fs-3xl));line-height:1.2;color:var(--color-heading);
 max-width:24ch;margin:0 auto;font-weight:var(--heading-weight);letter-spacing:var(--heading-tracking)}
.tone-strong .fact-callout .fact-text{color:var(--color-on-strong)}
.fact-callout .icon-wrap{display:flex;margin:0 auto calc(var(--space)*3)}.fact-callout .eyebrow{display:flex;justify-content:center}
.fact-inline .fi-grid{display:grid;gap:calc(var(--space)*2)}
@media(min-width:900px){.fact-inline .fi-grid{grid-template-columns:.8fr 1.2fr;gap:calc(var(--space)*10);align-items:center}}
.fact-inline h2{margin:0}.fact-inline .fact-text{font-size:var(--fs-xl);line-height:1.45;margin:0;color:var(--color-ink)}
.tone-strong .fact-inline .fact-text{color:var(--color-on-strong)}
.fact-panel .fp-card{display:flex;gap:calc(var(--space)*3);align-items:center;background:var(--color-surface);border-radius:var(--radius-lg);box-shadow:var(--shadow);
 padding:calc(var(--space)*5);max-width:760px;margin:0 auto}
.fact-panel h2{font-size:var(--fs-xl);margin:0 0 6px}.fact-panel .fact-text{margin:0;font-size:var(--fs-lg);color:var(--color-ink-muted)}
.fact-panel .icon-wrap{width:64px;height:64px}.fact-panel .icon-wrap .icon{width:28px;height:28px}
@media(max-width:560px){.fact-panel .fp-card{flex-direction:column;align-items:flex-start}}

/* cards keep their own colours when they sit on a strong band */
.tone-strong .fp-card h2,.tone-strong .form-card h2{color:var(--color-heading)}
.tone-strong .fp-card .fact-text{color:var(--color-ink-muted)}
.tone-strong .fp-card .icon-wrap{background:var(--color-accent-soft);color:var(--color-accent-ink)}
.tone-strong .form-card{color:var(--color-ink)}
.contact-facts{display:grid;gap:14px;margin-top:calc(var(--space)*3)}
.contact-facts .cf-item{display:flex;gap:14px;align-items:center}.contact-facts strong{display:block;line-height:1.3}
.contact-facts span:not(.icon-wrap){display:block;color:var(--color-ink-muted)}.tone-strong .contact-facts span:not(.icon-wrap){color:var(--color-on-strong-muted)}
.tone-strong .contact-facts .icon-wrap{background:color-mix(in oklab,var(--color-on-strong) 12%,transparent);color:var(--color-on-strong)}

/* forms */
.form{display:grid;gap:calc(var(--space)*2.25)}
.field{display:grid;gap:8px;font-size:var(--fs-sm);font-weight:600;color:var(--color-ink)}
input,select,textarea{font:inherit;font-size:var(--fs-md);font-weight:400;color:var(--color-ink);background:var(--color-surface-2);border:0;border-radius:var(--radius-sm);
 padding:14px 16px;width:100%;min-width:0;min-height:50px;transition:background-color .15s ease,box-shadow .15s ease}
input::placeholder,textarea::placeholder{color:var(--color-ink-soft)}
input:hover,select:hover,textarea:hover{background:var(--color-surface-3)}
input:focus,select:focus,textarea:focus{outline:none;background:var(--color-surface);box-shadow:0 0 0 3px var(--color-focus)}
.form .btn{margin-top:var(--space)}
.form-card{background:var(--color-surface);border-radius:var(--radius-lg);box-shadow:var(--shadow-lg);padding:clamp(24px,4vw,44px)}
.tone-2 .form-card input,.form-card input{background:var(--color-surface-2)}
.form-split .fs-grid{display:grid;gap:calc(var(--space)*5);align-items:center}
@media(min-width:900px){.form-split .fs-grid{grid-template-columns:1fr 1fr;gap:calc(var(--space)*10)}}
.form-panel .form-card{max-width:600px;margin:0 auto}.form-panel .form-card h2{font-size:var(--fs-xl)}
.form-band .fb-grid{display:grid;gap:calc(var(--space)*5);align-items:center}
@media(min-width:900px){.form-band .fb-grid{grid-template-columns:1fr 1fr;gap:calc(var(--space)*10)}}
.form-band .form-card{color:var(--color-ink)}

/* app pieces */
.card{background:var(--color-surface);border-radius:var(--radius-lg);box-shadow:var(--shadow);padding:clamp(20px,3vw,32px);margin-bottom:calc(var(--space)*3)}
.card h3{font-size:var(--fs-lg);margin-bottom:calc(var(--space)*2)}.grid>.card{margin-bottom:0}
.grid{display:grid;gap:calc(var(--space)*3);grid-template-columns:repeat(auto-fit,minmax(min(100%,250px),1fr))}
.stats{display:grid;gap:calc(var(--space)*2);grid-template-columns:repeat(auto-fit,minmax(min(100%,150px),1fr));margin-bottom:calc(var(--space)*4)}
.stat{background:var(--color-surface);border-radius:var(--radius-lg);box-shadow:var(--shadow);padding:calc(var(--space)*3)}
.stat:first-child{background:var(--color-strong);color:var(--color-on-strong)}
.stat:first-child .stat-label,.stat:first-child .stat-hint{color:var(--color-on-strong-muted)}.stat:first-child .stat-value{color:var(--color-on-strong)}
.stat-label{color:var(--color-ink-muted);font-size:var(--fs-sm);font-weight:600}
.stat-value{font-family:var(--font-heading);font-size:var(--fs-3xl);font-weight:var(--heading-weight);line-height:1.1;margin-top:6px;font-variant-numeric:tabular-nums;color:var(--color-heading)}
.stat-hint{color:var(--color-ink-muted);font-size:var(--fs-xs);min-height:1em}
.table-wrap{overflow-x:auto;background:var(--color-surface);border-radius:var(--radius-lg);box-shadow:var(--shadow-sm);margin-bottom:calc(var(--space)*3);padding:6px}
table{border-collapse:separate;border-spacing:0;width:100%;font-variant-numeric:tabular-nums}
th,td{text-align:left;padding:13px 16px;white-space:nowrap;border:0}
th{font-size:var(--fs-xs);font-weight:650;text-transform:uppercase;letter-spacing:.06em;color:var(--color-ink-muted)}
tbody tr:nth-child(odd) td{background:var(--color-surface-2)}
tbody td:first-child{border-radius:var(--radius-sm) 0 0 var(--radius-sm)}tbody td:last-child{border-radius:0 var(--radius-sm) var(--radius-sm) 0}
.empty{color:var(--color-ink-muted);padding:22px;background:var(--color-surface-2);border-radius:var(--radius-lg)}
.search{display:flex;gap:10px;margin-bottom:calc(var(--space)*3);max-width:560px}.search input{flex:1;background:var(--color-surface);box-shadow:var(--shadow-sm)}
.alert{border-radius:var(--radius);padding:16px 18px;margin-bottom:calc(var(--space)*3);background:var(--color-support-soft);color:var(--color-support-ink);font-weight:550}
.alert-success{background:var(--color-success-bg);color:var(--color-success-ink)}.alert-error{background:var(--color-error-bg);color:var(--color-error-ink)}
.alert-warning{background:var(--color-accent-soft);color:var(--color-accent-ink)}
.badge{display:inline-block;border-radius:999px;padding:3px 12px;font-size:var(--fs-xs);font-weight:650;background:var(--color-accent-soft);color:var(--color-accent-ink)}
.badge-success{background:var(--color-success-bg);color:var(--color-success-ink)}.badge-error{background:var(--color-error-bg);color:var(--color-error-ink)}
.login-wrap{min-height:calc(100vh - 140px);display:grid;place-items:center;padding:calc(var(--space)*6) 0}
.login-wrap .card{width:100%;max-width:440px;box-shadow:var(--shadow-lg);padding:clamp(28px,5vw,44px)}
.login-wrap h1{font-size:var(--fs-2xl);margin-bottom:calc(var(--space)*3)}
.thanks{padding:calc(var(--space)*12) 0;text-align:center}.thanks .alert{display:inline-block;font-size:var(--fs-lg);padding:20px 26px}.thanks .btn{margin-top:var(--space)}

.app-grid{display:grid;gap:calc(var(--space)*3)}
@media(min-width:1024px){.app-grid{grid-template-columns:minmax(0,1.7fr) minmax(300px,1fr);align-items:start}.app-side{position:sticky;top:96px}}

/* footer */
.footer{background:var(--color-surface-2);color:var(--color-ink-muted);padding:calc(var(--space)*7) 0 calc(var(--space)*5);font-size:var(--fs-sm)}
.footer .ft-grid{display:flex;flex-wrap:wrap;gap:calc(var(--space)*3);justify-content:space-between;align-items:center}
.footer .brand{font-size:var(--fs-md)}.footer nav{display:flex;flex-wrap:wrap;gap:4px 18px}.footer nav a{color:var(--color-ink-muted);text-decoration:none}
.footer nav a:hover{color:var(--color-ink)}.footer .copy{flex-basis:100%;width:100%;max-width:none;margin:calc(var(--space)*2) 0 0;order:9}
.tone-2+.footer,.app-main+.footer{background:var(--color-surface-3)}
@media(prefers-reduced-motion:reduce){*{transition:none!important;scroll-behavior:auto!important}}
"""
