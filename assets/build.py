"""Builds the profile README artwork: a personnel technical record printed on
greenbar continuous-feed stock, the same document as the portfolio
(https://piozac002.github.io/PortfolioPage/).

Every card is written twice, `*-light.svg` (top copy, daylight) and
`*-dark.svg` (archive microfilm), and the README picks one with <picture>.
The fonts (Archivo, Martian Mono, both SIL OFL) are subset to the glyphs each
card uses and embedded as WOFF2, because an SVG shown as an image cannot load
anything from the network.

    pip install fonttools brotli
    python assets/build.py [path/to/fonts]

The default font path is the portfolio checkout next to this repository.
"""

import base64
import io
import sys
from pathlib import Path
from xml.sax.saxutils import escape

from fontTools.subset import Options, Subsetter
from fontTools.ttLib import TTFont

HERE = Path(__file__).resolve().parent
FONTS = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parents[1] / 'PortfolioPage/src/assets/fonts'

W = 880          # every card shares one width
PERF = 26        # tractor-feed margin with the sprocket holes
X0, X1 = PERF + 22, W - PERF - 22   # inner text margins

PALETTES = {
    'light': dict(paper='#f6f7f1', band='#e3ecdc', sunk='#eceee4', ink='#191c14', ink2='#4a5044',
                  ink3='#636a5b', rule='#c2c9b7', rule2='#6e7664', hole='#dcdfd2', hole_edge='#cfd4c4',
                  green='#1e6b3c', amber='#7e5608', blue='#1b4f80', mark='#a82a1c'),
    'dark': dict(paper='#121510', band='#1b1f17', sunk='#0d0f0a', ink='#e8ecdf', ink2='#9ca591',
                 ink3='#818a77', rule='#363c2e', rule2='#6b7361', hole='#1e2219', hole_edge='#2a2f23',
                 green='#5cc184', amber='#dca92f', blue='#77aee0', mark='#ea6853'),
}

FACES = {
    'plate': ['archivo-normal-latin.woff2', 'archivo-normal-latin-ext.woff2'],
    'data': ['martian-mono-normal-latin.woff2', 'martian-mono-normal-latin-ext.woff2'],
}
FAMILY = {'plate': 'Plate', 'data': 'Data'}

_fonts = {key: [TTFont(FONTS / f) for f in files] for key, files in FACES.items()}
_paths = {id(font): FONTS / f for key, files in FACES.items() for font, f in zip(_fonts[key], files)}


def advance(face, text, size):
    """Text width at the font's default instance (wdth 100, wght 400)."""
    total = 0
    for ch in text:
        for font in _fonts[face]:
            name = font.getBestCmap().get(ord(ch))
            if name:
                total += font['hmtx'][name][0] / font['head'].unitsPerEm
                break
        else:
            total += 0.6
    return total * size


def embed_fonts(texts):
    """@font-face rules with each face subset to the characters in use."""
    rules = []
    for face, fonts in _fonts.items():
        chars = set(''.join(texts[face]))
        for font in fonts:
            cmap = font.getBestCmap()
            have = sorted(c for c in {ord(ch) for ch in chars} if c in cmap)
            if not have:
                continue
            sub = TTFont(_paths[id(font)])
            opts = Options()
            opts.flavor = 'woff2'
            opts.layout_features = ['*']
            subsetter = Subsetter(opts)
            subsetter.populate(unicodes=have)
            subsetter.subset(sub)
            buf = io.BytesIO()
            sub.flavor = 'woff2'
            sub.save(buf)
            data = base64.b64encode(buf.getvalue()).decode()
            ranges = ','.join(f'U+{c:04X}' for c in have)
            rules.append(f"@font-face{{font-family:{FAMILY[face]};src:url(data:font/woff2;base64,{data}) format('woff2');"
                         f"font-weight:100 900;font-stretch:62% 125%;unicode-range:{ranges}}}")
    return '\n'.join(rules)




class Card:
    """Collects SVG nodes and the text each font face has to cover."""

    def __init__(self, height, theme, title, w=W, perf=('l', 'r')):
        self.h, self.theme, self.title, self.w, self.perf = height, theme, title, w, perf
        self.p = PALETTES[theme]
        self.nodes = []
        self.texts = {'plate': [], 'data': []}

    def text(self, x, y, s, face='plate', size=14, fill='ink', weight=400, wdth=100, anchor='start',
             spacing=0, cls='', upper=False):
        s = s.upper() if upper else s
        self.texts[face].append(s)
        attrs = (f'x="{x:.1f}" y="{y:.1f}" font-family="{FAMILY[face]}" font-size="{size}" '
                 f'fill="{self.p[fill]}" style="font-variation-settings:\'wght\' {weight},\'wdth\' {wdth}"')
        if anchor != 'start':
            attrs += f' text-anchor="{anchor}"'
        if spacing:
            attrs += f' letter-spacing="{spacing}"'
        if cls:
            attrs += f' class="{cls}"'
        self.nodes.append(f'<text {attrs}>{escape(s)}</text>')

    def raw(self, node):
        self.nodes.append(node)

    def line(self, x1, y1, x2, y2, stroke='rule', width=1, cls=''):
        c = f' class="{cls}"' if cls else ''
        self.raw(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{self.p[stroke]}" stroke-width="{width}"{c}/>')

    def rect(self, x, y, w, h, fill='none', stroke=None, width=1, cls='', rx=0):
        s = f' stroke="{self.p[stroke]}" stroke-width="{width}"' if stroke else ''
        f = self.p[fill] if fill != 'none' else 'none'
        c = f' class="{cls}"' if cls else ''
        r = f' rx="{rx}"' if rx else ''
        self.raw(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{f}"{s}{r}{c}/>')

    def stamp(self, cx, cy, label, sub=None, kind='green', rotate=-6, cls='stamp', size=15):
        """A rubber stamp: double rule, wide caps, slightly off-square."""
        pad_x, pad_y = 14, 9
        w = max(advance('plate', label.upper(), size) * 1.12 + size * 0.12 * len(label),
                advance('data', sub.upper(), 8) + 4 if sub else 0) + pad_x * 2
        h = size + pad_y * 2 + (13 if sub else 0)
        col = self.p[kind]
        parts = [f'<g class="{cls}" transform="translate({cx:.1f} {cy:.1f}) rotate({rotate})">',
                 f'<rect x="{-w/2:.1f}" y="{-h/2:.1f}" width="{w:.1f}" height="{h:.1f}" fill="none" stroke="{col}" stroke-width="2.2" rx="2"/>',
                 f'<rect x="{-w/2+4:.1f}" y="{-h/2+4:.1f}" width="{w-8:.1f}" height="{h-8:.1f}" fill="none" stroke="{col}" stroke-width="0.9" rx="1"/>']
        ty = -h / 2 + pad_y + size * 0.82
        self.texts['plate'].append(label.upper())
        parts.append(f'<text x="0" y="{ty:.1f}" text-anchor="middle" font-family="Plate" font-size="{size}" fill="{col}" '
                     f'letter-spacing="{size*0.12:.1f}" style="font-variation-settings:\'wght\' 800,\'wdth\' 112">{escape(label.upper())}</text>')
        if sub:
            self.texts['data'].append(sub.upper())
            parts.append(f'<text x="0" y="{ty + 15:.1f}" text-anchor="middle" font-family="Data" font-size="8" fill="{col}" '
                         f'letter-spacing="0.8" style="font-variation-settings:\'wght\' 600,\'wdth\' 87.5">{escape(sub.upper())}</text>')
        parts.append('</g>')
        self.raw(''.join(parts))

    def chip(self, x, y, label, qualifier=None):
        """A register entry; a qualifier the subject wrote travels with it in amber."""
        size = 11
        w = advance('data', label, size) + 16
        q = 0
        if qualifier:
            q = advance('data', qualifier.upper(), 7.5) + 20
        total = w + q
        stroke = 'amber' if qualifier else 'rule2'
        self.rect(x, y, total, 24, fill='paper', stroke=stroke)
        self.text(x + 8, y + 16, label, face='data', size=size, fill='ink', weight=500)
        if qualifier:
            self.raw(f'<circle cx="{x + w + 2:.1f}" cy="{y + 12}" r="2.2" fill="{self.p["amber"]}"/>')
            self.text(x + w + 8, y + 15, qualifier, face='data', size=7.5, fill='amber', weight=700, upper=True, spacing=0.6)
        return total

    def sheet(self):
        """Paper, greenbar bands, the tractor-feed margins and the fold.

        Cards stack into one continuous sheet; GitHub leaves a few pixels between
        images, so every card starts on a perforated fold and the gap reads as
        the tear between two pages of continuous stock."""
        p, w, h = self.p, self.w, self.h
        left = PERF if 'l' in self.perf else 0
        right = w - PERF if 'r' in self.perf else w
        out = [f'<rect width="{w}" height="{h}" fill="{p["paper"]}"/>']
        for i, y in enumerate(range(0, h, 24)):
            if i % 2:
                out.append(f'<rect x="{left}" y="{y}" width="{right - left}" height="24" fill="{p["band"]}" opacity="0.55"/>')
        if 'l' in self.perf:
            out.append(f'<rect x="0" y="0" width="{PERF}" height="{h}" fill="{p["sunk"]}"/>')
            out.append(f'<line x1="{PERF}" y1="0" x2="{PERF}" y2="{h}" stroke="{p["rule"]}" stroke-dasharray="2 3"/>')
        if 'r' in self.perf:
            out.append(f'<rect x="{w - PERF}" y="0" width="{PERF}" height="{h}" fill="{p["sunk"]}"/>')
            out.append(f'<line x1="{w - PERF}" y1="0" x2="{w - PERF}" y2="{h}" stroke="{p["rule"]}" stroke-dasharray="2 3"/>')
        for y in range(13, h, 26):
            for x, side in ((13, 'l'), (w - 13, 'r')):
                if side in self.perf:
                    out.append(f'<circle cx="{x}" cy="{y}" r="4.6" fill="{p["hole"]}" stroke="{p["hole_edge"]}"/>')
        out.append(f'<line x1="0" y1="0.5" x2="{w}" y2="0.5" stroke="{p["rule2"]}" stroke-dasharray="1 3" opacity=".8"/>')
        return ''.join(out)

    def render(self):
        style = f"""
{embed_fonts(self.texts)}
text{{font-kerning:normal}}
.feed{{animation:feed .6s cubic-bezier(.2,.7,.2,1) backwards}}
@keyframes feed{{from{{transform:translateY(5px)}}to{{transform:none}}}}
.stamp{{transform-box:fill-box;animation:thump .45s cubic-bezier(.3,1.6,.5,1) backwards;animation-delay:.9s}}
@keyframes thump{{from{{opacity:.8}}to{{opacity:1}}}}
.blink{{animation:blink 1.05s steps(1) infinite}}
@keyframes blink{{50%{{opacity:.15}}}}
.head{{animation:head 2.6s cubic-bezier(.45,0,.2,1) 1 both}}
@keyframes head{{from{{transform:translateY(0);opacity:.9}}90%{{opacity:.9}}to{{transform:translateY(var(--travel));opacity:0}}}}
.d1{{animation-delay:.08s}}.d2{{animation-delay:.18s}}.d3{{animation-delay:.3s}}.d4{{animation-delay:.42s}}
.d5{{animation-delay:.54s}}.d6{{animation-delay:.66s}}.d7{{animation-delay:.78s}}.d8{{animation-delay:.9s}}
@media (prefers-reduced-motion:reduce){{*{{animation:none!important}}}}
"""
        body = ''.join(self.nodes)
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" width="{self.w}" height="{self.h}" '
                f'role="img" aria-label="{escape(self.title)}"><title>{escape(self.title)}</title>'
                f'<style>{style}</style>{self.sheet()}{body}</svg>')


def mark(c, x, y):
    """The red reader mark from the portfolio: an open corner."""
    col = c.p['mark']
    c.raw(f'<path d="M{x} {y+17} V{y} H{x+24}" fill="none" stroke="{col}" stroke-width="2.4"/>')


def section_head(c, y, no, title, aside=''):
    c.text(X0, y, no, face='data', size=11, fill='ink3', weight=700)
    c.text(X0 + 34, y + 1, title, face='plate', size=22, fill='ink', weight=800, wdth=112, upper=True, spacing=0.4)
    if aside:
        c.text(X1, y, aside, face='data', size=9.5, fill='ink3', weight=500, anchor='end', upper=True, spacing=0.8)
    c.line(X0, y + 12, X1, y + 12, stroke='ink', width=2)


# ── Cards ────────────────────────────────────────────────────────────────────

def header(theme):
    c = Card(388, theme, 'Personnel technical record REC-2025-PZ-001: Piotr Zaćmiński, Junior Full-stack Developer, '
                         'Operations Analyst (L2/L3) at Quad Graphics since 09.2022, Bydgoszcz, Poland. Status: open.')
    # form strip
    c.rect(PERF, 0, W - 2 * PERF, 34, fill='sunk')
    c.text(X0, 21, 'REC-2025-PZ-001', face='data', size=9.5, fill='ink2', weight=700, spacing=0.8)
    c.text(W / 2, 21, 'Personnel technical record', face='data', size=9.5, fill='ink2', weight=500, anchor='middle',
           upper=True, spacing=1.6)
    c.text(X1, 21, 'Form 3A-INC · Rev. 10.2026', face='data', size=9.5, fill='ink2', weight=500, anchor='end',
           upper=True, spacing=0.8)
    c.line(PERF, 34, W - PERF, 34, stroke='ink', width=2)

    mark(c, X0 - 8, 52)
    c.raw('<g class="feed d1">')
    c.text(X0, 112, 'PIOTR', face='plate', size=58, fill='ink', weight=850, wdth=118, spacing=-0.5)
    c.raw('</g><g class="feed d2">')
    c.text(X0, 168, 'ZAĆMIŃSKI', face='plate', size=58, fill='ink', weight=850, wdth=118, spacing=-0.5)
    c.raw('</g><g class="feed d3">')
    role = 'Junior full-stack developer · Operations analyst (L2/L3)'
    c.text(X0, 198, role, face='data', size=11.5, fill='ink2', weight=500, upper=True, spacing=0.9)
    cx = X0 + advance('data', role.upper(), 11.5) + len(role) * 0.9 - 2
    c.rect(cx, 188, 8, 13, fill='mark', cls='blink')
    c.raw('</g>')

    c.stamp(X1 - 86, 120, 'Open', sub='to junior roles', kind='green', rotate=-7, size=22)

    # record fields
    top = 222
    cols = [X0, X0 + 290, X0 + 520]
    widths = [290, 230, X1 - (X0 + 520)]
    rows = [
        [('Current post', 'Operations Analyst · Quad Graphics'), ('On record since', '09.2022'),
         ('Location', 'Bydgoszcz, Poland')],
        [('Education', 'B.Eng. Applied Computer Science'), ('Institution', 'Politechnika Bydgoska'),
         ('Classification', 'Junior Full-stack Developer')],
    ]
    for r, row in enumerate(rows):
        y = top + r * 66
        c.raw(f'<g class="feed d{4 + r}">')
        for i, (label, value) in enumerate(row):
            c.rect(cols[i], y, widths[i], 66, fill='paper', stroke='rule2')
            c.text(cols[i] + 12, y + 22, label, face='data', size=8.5, fill='ink3', weight=600, upper=True, spacing=1)
            c.text(cols[i] + 12, y + 46, value, face='plate', size=15, fill='ink', weight=600)
        c.raw('</g>')
    c.line(PERF, c.h - 1, W - PERF, c.h - 1, stroke='rule', width=1)
    c.raw(f'<g class="head" style="--travel:{c.h - 40}px"><rect x="{PERF}" y="36" width="{W - 2*PERF}" height="2" '
          f'fill="{c.p["mark"]}" opacity=".55"/></g>')
    return c


def parity(theme):
    c = Card(300, theme, 'Two sides of one record. Side A, Diagnosis: finds out why production software misbehaves, '
                         'using .NET debugging, SQL and log analysis, and Cherwell and Halo tickets. Side B, Construction: '
                         'designs, builds and ships full-stack web apps with React, Java and Spring Boot, Docker and Google Cloud.')
    section_head(c, 40, '§1', 'Two sides of one record')
    sides = [
        ('Side A', 'Diagnosis', ['Finds out why production software misbehaves,',
                                 'and whether the cause is code, data,',
                                 'infrastructure or the business logic itself.'],
         ['.NET solutions · Visual Studio · ReSharper', 'SQL queries · application log analysis',
          'Cherwell & Halo · retracing user steps'], 'At work since 09.2022'),
        ('Side B', 'Construction', ['Designs, builds and ships full-stack web',
                                    'applications, from the database schema',
                                    'to the interface, and deploys them himself.'],
         ['React · TypeScript · Node.js', 'Java · Spring Boot · PostgreSQL', 'Docker · Google Cloud Run · Render'],
         '4 systems in the register'),
    ]
    mid = W / 2
    c.line(mid, 70, mid, 272, stroke='rule2')
    for i, (label, title, lead, items, foot) in enumerate(sides):
        x = X0 if i == 0 else mid + 22
        c.raw(f'<g class="feed d{1 + i * 2}">')
        c.text(x, 84, label, face='data', size=9, fill='ink3', weight=700, upper=True, spacing=1.2)
        c.text(x, 114, title, face='plate', size=28, fill='ink', weight=800, wdth=110)
        for n, ln in enumerate(lead):
            c.text(x, 140 + n * 18, ln, face='plate', size=13.5, fill='ink2', weight=420)
        c.raw('</g>')
        c.raw(f'<g class="feed d{2 + i * 2}">')
        for n, item in enumerate(items):
            y = 210 + n * 20
            c.rect(x, y - 8, 6, 6, fill='mark' if i == 0 else 'blue')
            c.text(x + 14, y, item, face='data', size=10.5, fill='ink', weight=500)
        c.text(x, 284, foot, face='data', size=8.5, fill='ink3', weight=600, upper=True, spacing=1)
        c.raw('</g>')
    return c


PROJECTS = [
    ('E-01', 'TaskSystem', 'Jira-inspired issue tracker: 8 workflow states, Kanban board, teams and comments.',
     ['React', 'Spring Boot', 'PostgreSQL', 'Google Cloud'], 'Cloud Run'),
    ('E-02', 'BarberApp', 'Barbershop booking with separate views for clients, barbers and admins.',
     ['TypeScript', 'React', 'Express', 'PostgreSQL'], 'Render'),
    ('E-03', 'Hala 4', 'Scroll-driven WebGL walk-around of a car and an AI front desk on its own server.',
     ['React Three Fiber', 'GLSL', 'Node.js', 'Gemini API'], 'Render'),
    ('E-04', 'Portfolio', 'This record as a bilingual web form, with live links and screenshot galleries.',
     ['React', 'Vite', 'CSS', 'GitHub Actions'], 'GitHub Pages'),
]


def register_head(theme):
    c = Card(100, theme, '§2 Construction: four deployed systems. Each row links to its live demo. '
                         'The demos run on free tiers, so the first visit can take up to a minute to wake up.')
    section_head(c, 40, '§2', 'Construction', aside='4 entries · click a row to open')
    c.text(X0, 72, 'Free-tier hosting: the first visit after a quiet spell can take up to a minute to wake up.',
           face='plate', size=12.5, fill='ink3', weight=420)
    c.text(X0, 94, 'Entry', face='data', size=8.5, fill='ink3', weight=600, upper=True, spacing=1)
    c.text(X1, 94, 'Deployment', face='data', size=8.5, fill='ink3', weight=600, upper=True, spacing=1, anchor='end')
    return c


def project(theme, entry):
    eid, name, desc, stack, host = entry
    c = Card(104, theme, f'{eid} {name}: {desc} Stack: {", ".join(stack)}. Deployed on {host}. Opens the live demo.')
    c.line(PERF, 0, W - PERF, 0, stroke='rule2')
    c.raw('<g class="feed d1">')
    c.text(X0, 34, eid, face='data', size=10, fill='ink3', weight=700, spacing=0.6)
    c.text(X0 + 48, 36, name, face='plate', size=24, fill='ink', weight=800, wdth=108)
    nx = X0 + 48 + advance('plate', name, 24) * 1.12 + 12
    c.raw(f'<path d="M{nx:.1f} 34 l9 -9 M{nx+2:.1f} 25 h7 v7" fill="none" stroke="{c.p["mark"]}" stroke-width="2"/>')
    c.text(X0 + 48, 62, desc, face='plate', size=13, fill='ink2', weight=420)
    c.raw('</g><g class="feed d2">')
    x = X0 + 48
    for item in stack:
        x += c.chip(x, 74, item) + 6
    c.raw('</g>')
    c.stamp(X1 - 64, 52, 'Deployed', sub=host, kind='green', rotate=-5, size=12)
    return c


def arrow(c, x, y, kind='link'):
    col = c.p['mark']
    if kind == 'mail':
        c.raw(f'<path d="M{x} {y-9} h12 v9 h-12 z M{x} {y-9} l6 5 l6 -5" fill="none" stroke="{col}" stroke-width="1.6"/>')
    else:
        c.raw(f'<path d="M{x:.1f} {y} l9 -9 M{x+2:.1f} {y-9} h7 v7" fill="none" stroke="{col}" stroke-width="2"/>')


def cell(theme, w, index, count, label, value, sub, kind, title):
    """One field of a strip of linked cells; the strip shares a single sheet."""
    perf = tuple(side for side, on in (('l', index == 0), ('r', index == count - 1)) if on)
    c = Card(76, theme, title, w=w, perf=perf)
    x0 = PERF + 22 if 'l' in perf else 20
    if index < count - 1:
        c.line(w - 0.5, 12, w - 0.5, 64, stroke='rule2')
    c.text(x0, 25, label, face='data', size=8.5, fill='ink3', weight=600, upper=True, spacing=1)
    c.text(x0, 49, value, face='plate', size=17, fill='ink', weight=780, wdth=108)
    arrow(c, x0 + advance('plate', value, 17) * 1.1 + 10, 47, kind)
    c.text(x0, 66, sub, face='data', size=8.5, fill='ink2', weight=500)
    return c


CHANNELS = [
    ('Channel 01', 'Portfolio', 'piozac002.github.io/PortfolioPage', 'link'),
    ('Channel 02', 'LinkedIn', 'in/piotr-zaćmiński', 'link'),
    ('Channel 03', 'Email', 'piotrek.zacminski2002@gmail.com', 'mail'),
]

SOURCES = [('Source · E-01', 'TaskSystem', 'PioZac002/TaskSystemm'),
           ('Source · E-02', 'BarberApp', 'PioZac002/BarberAppv2'),
           ('Source · E-03', 'Hala 4', 'PioZac002/hala-4'),
           ('Source · E-04', 'Portfolio', 'PioZac002/PortfolioPage')]

COURSES = [('Agile Project Management - AgilePM® Foundation', 'Centrum Szkoleniowe ProcessTeam'),
           ('Complete React, Next.js & TypeScript Projects Course 2025', 'Udemy · Jānis Smilga'),
           ('MERN 2025 Edition - MongoDB, Express, React and NodeJS', 'Udemy · Jānis Smilga'),
           ('NodeJS Tutorial and Projects Course', 'Udemy · Jānis Smilga'),
           ('JavaScript Tutorial and Projects Course', 'Udemy · Jānis Smilga'),
           ('HTML/CSS Tutorial and Projects Course', 'Udemy · Jānis Smilga')]


def qualifications(theme):
    h = 150 + len(COURSES) * 28 + 46
    c = Card(h, theme, '§4 Qualifications: B.Eng. in Applied Computer Science, Politechnika Bydgoska, 09.2021 - 03.2025. '
                       'Courses: ' + '; '.join(f'{n} ({p})' for n, p in COURSES)
                       + '. Languages: Polish (native), English (B2+/C1), German (A2).')
    section_head(c, 40, '§4', 'Qualifications', aside='degree · 6 courses · 3 languages')
    c.raw('<g class="feed d1">')
    c.rect(X0, 66, X1 - X0, 62, fill='paper', stroke='rule2')
    c.text(X0 + 14, 88, 'Degree', face='data', size=8.5, fill='ink3', weight=600, upper=True, spacing=1)
    c.text(X0 + 14, 112, 'B.Eng. in Applied Computer Science', face='plate', size=17, fill='ink', weight=760, wdth=105)
    c.text(X1 - 14, 88, '09.2021 - 03.2025', face='data', size=9.5, fill='ink2', weight=600, anchor='end', spacing=0.4)
    c.text(X1 - 14, 112, 'Politechnika Bydgoska', face='plate', size=14, fill='ink', weight=560, anchor='end')
    c.raw('</g>')
    y = 156
    c.text(X0, y, 'Certifications & courses', face='data', size=8.5, fill='ink3', weight=600, upper=True, spacing=1)
    for n, (name, provider) in enumerate(COURSES):
        ry = y + 14 + n * 28
        c.raw(f'<g class="feed d{min(n + 2, 8)}">')
        c.line(X0, ry, X1, ry, stroke='rule')
        c.raw(f'<path d="M{X0 + 2} {ry + 15} l3.5 3.5 l7 -8" fill="none" stroke="{c.p["green"]}" stroke-width="1.8"/>')
        c.text(X0 + 22, ry + 19, name, face='plate', size=13.5, fill='ink', weight=480)
        c.text(X1, ry + 19, provider, face='data', size=9, fill='ink2', weight=500, anchor='end')
        c.raw('</g>')
    ly = y + 14 + len(COURSES) * 28
    c.line(X0, ly, X1, ly, stroke='rule')
    c.text(X0, ly + 28, 'Languages', face='data', size=8.5, fill='ink3', weight=600, upper=True, spacing=1)
    c.text(X0 + 104, ly + 28, 'Polish · native     English · B2+/C1     German · A2', face='plate', size=13.5,
           fill='ink', weight=520)
    return c


STACK = [
    ('Frontend', [('JavaScript', None), ('React', None), ('TypeScript', 'basics'), ('Next.js', 'basics'),
                  ('Tailwind CSS', None), ('MUI / shadcn/ui', None), ('HTML · CSS', None), ('PWA', None)]),
    ('Backend', [('Node.js', 'basics'), ('Java · Spring Boot', None), ('SQL (PostgreSQL) / NoSQL (MongoDB)', None),
                 ('C# / Java', 'solid OOP foundations'), ('C / C++', 'basics')]),
    ('AI & automation', [('Claude Code / GitHub Copilot / OpenAI Codex', None), ('Prompt engineering', None),
                         ('n8n', 'basics')]),
    ('Cloud & tooling', [('Docker', None), ('Git', None), ('Postman', None), ('Figma', None), ('Vite', None),
                         ('AWS / Azure DevOps / Google Cloud', 'basics')]),
    ('Testing & process', [('Vitest / Testing Library', None), ('Agile / Scrum', None)]),
]


def stack(theme):
    # lay out first to know the height
    col_x, max_x = X0 + 170, X1
    rows, y = [], 84
    for group, entries in STACK:
        x, line_y, placed = col_x, y, []
        for label, q in entries:
            w = advance('data', label, 11) + 16 + (advance('data', q.upper(), 7.5) + 20 if q else 0)
            if x + w > max_x:
                x, line_y = col_x, line_y + 32
            placed.append((x, line_y, label, q))
            x += w + 6
        rows.append((group, y, line_y, placed))
        y = line_y + 46
    c = Card(y + 6, theme, '§3 Competence: ' + '; '.join(
        f'{g}: ' + ', '.join(f'{l} ({q})' if q else l for l, q in e) for g, e in STACK)
        + '. Amber entries carry the level the subject declared.')
    section_head(c, 40, '§3', 'Competence', aside='amber = declared level')
    for n, (group, gy, last_y, placed) in enumerate(rows):
        c.raw(f'<g class="feed d{min(n + 1, 8)}">')
        c.text(X0, gy + 16, group, face='data', size=9, fill='ink3', weight=700, upper=True, spacing=1)
        c.text(X0, gy + 32, f'{len(placed):02d} entries', face='data', size=8, fill='ink3', weight=400, spacing=0.4)
        for x, ly, label, q in placed:
            c.chip(x, ly, label, q)
        c.raw('</g>')
        if n < len(rows) - 1:
            c.line(X0, last_y + 38, X1, last_y + 38, stroke='rule')
    return c


def footer(theme):
    c = Card(56, theme, 'Record maintained by Piotr Zaćmiński. REC-2025-PZ-001, form 3A-INC, revision 10.2026.')
    c.rect(PERF, 0, W - 2 * PERF, 56, fill='sunk')
    c.line(PERF, 0, W - PERF, 0, stroke='ink', width=2)
    c.text(X0, 24, 'Record maintained by', face='data', size=8.5, fill='ink3', weight=600, upper=True, spacing=1)
    c.text(X0, 43, 'Piotr Zaćmiński', face='plate', size=15, fill='ink', weight=750)
    c.text(X1, 34, 'REC-2025-PZ-001 · Form 3A-INC · Rev. 10.2026 · Page 1 of 1', face='data', size=8.5,
           fill='ink3', weight=500, anchor='end', upper=True, spacing=0.9)
    return c


def main():
    out = HERE
    builders = {'header': header, 'parity': parity, 'register': register_head, 'stack': stack,
                'qualifications': qualifications, 'footer': footer}
    for theme in PALETTES:
        for name, build in builders.items():
            (out / f'{name}-{theme}.svg').write_text(build(theme).render())
        for entry in PROJECTS:
            slug = entry[1].lower().replace(' ', '')
            (out / f'project-{slug}-{theme}.svg').write_text(project(theme, entry).render())
        for i, (label, value, sub, kind) in enumerate(CHANNELS):
            card = cell(theme, W / len(CHANNELS), i, len(CHANNELS), label, value, sub, kind,
                        f'{label}: {value}, {sub}')
            (out / f'channel-{value.lower()}-{theme}.svg').write_text(card.render())
        for i, (label, value, sub) in enumerate(SOURCES):
            card = cell(theme, W / len(SOURCES), i, len(SOURCES), label, value, sub, 'link',
                        f'{label}: source code of {value} on GitHub, {sub}')
            slug = value.lower().replace(' ', '')
            (out / f'source-{slug}-{theme}.svg').write_text(card.render())
    for f in sorted(out.glob('*.svg')):
        print(f'{f.name:34} {f.stat().st_size / 1024:6.1f} KB')


if __name__ == '__main__':
    main()
