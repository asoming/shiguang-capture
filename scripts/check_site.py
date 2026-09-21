"""Check static pages, metadata, local assets/anchors and README file links."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
import re

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / 'docs'


class Page(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.refs, self.ids, self.meta = [], set(), {}
        self.lang = None
        self.feed(source)
        self.close()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'html':
            self.lang = attrs.get('lang')
        if 'id' in attrs:
            self.ids.add(attrs['id'])
        if tag == 'meta':
            self.meta[attrs.get('name', attrs.get('property'))] = attrs.get('content')
        for name in ('href', 'src', 'data-still', 'data-animation'):
            if attrs.get(name):
                self.refs.append(attrs[name])


def main():
    errors = []
    pages = {path: Page(path.read_text(encoding='utf-8')) for path in SITE.rglob('*.html')}
    for path, page in pages.items():
        relative = path.relative_to(ROOT)
        if not page.lang:
            errors.append(f'{relative}: missing language')
        for ref in page.refs:
            parsed = urlsplit(ref)
            if parsed.scheme or parsed.netloc:
                continue
            target = (path.parent / unquote(parsed.path)).resolve() if parsed.path else path
            if target.is_dir():
                target /= 'index.html'
            if not target.is_file():
                errors.append(f'{relative}: missing {ref}')
            elif parsed.fragment and target in pages and unquote(parsed.fragment) not in pages[target].ids:
                errors.append(f'{relative}: missing anchor {ref}')
        if path.name == 'index.html':
            for field in ('viewport', 'description', 'og:title', 'og:image', 'twitter:card'):
                if not page.meta.get(field):
                    errors.append(f'{relative}: missing {field}')
            for asset in ('site.css', 'site.js'):
                if not any(ref.endswith('assets/' + asset) for ref in page.refs):
                    errors.append(f'{relative}: missing shared {asset}')
    for path in [ROOT/'README.md', ROOT/'README.en.md', *(ROOT/'guides').glob('*.md')]:
        source = path.read_text(encoding='utf-8')
        refs = re.findall(r'\]\(([^)]+)\)|(?:src|href)="([^"]+)"', source)
        for match in refs:
            ref = next(value for value in match if value)
            parsed = urlsplit(ref)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            if not (path.parent / unquote(parsed.path)).exists():
                errors.append(f'{path.relative_to(ROOT)}: missing {ref}')
    for error in errors:
        print('FAIL', error)
    if errors:
        return 1
    print(f'site-check OK ({len(pages)} HTML pages, metadata, local links, anchors and README assets)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
