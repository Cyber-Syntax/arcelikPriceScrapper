from __future__ import annotations

import fnmatch
import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urljoin, urlparse

from selectolax.lexbor import LexborHTMLParser as HTMLParser

from .http import BASE, Http

log = logging.getLogger("scrapper.categories")

CACHE_VERSION = 1
CACHE_TTL_HOURS = 24

# Blog bir fiyat/kategori kaynagi degildir; config'den bagimsiz olarak asla alinmaz.
ALWAYS_EXCLUDED_SLUGS = frozenset({"blog"})


def _is_blog_slug(slug: str) -> bool:
    first = slug.strip("/").split("/")[0].casefold()
    return first in ALWAYS_EXCLUDED_SLUGS


def is_blog_url(url: str) -> bool:
    return _is_blog_slug(urlparse(url).path)


def is_always_excluded(node: CategoryNode) -> bool:
    return any(_is_blog_slug(part.slug) for part in node.path())

# Turkce karakterleri eslestirme icin sadelestirir.
_TR_MAP = str.maketrans(
    {
        "ı": "i",
        "İ": "i",
        "ş": "s",
        "Ş": "s",
        "ğ": "g",
        "Ğ": "g",
        "ü": "u",
        "Ü": "u",
        "ö": "o",
        "Ö": "o",
        "ç": "c",
        "Ç": "c",
        "â": "a",
        "Â": "a",
        "î": "i",
        "Î": "i",
    }
)


def clean(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def norm_key(text: str | None) -> str:
    """Karsilastirma anahtari: Turkce sadelestirme + kucuk harf + bosluk."""
    text = clean(text).translate(_TR_MAP).casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def norm_pattern(text: str | None) -> str:
    """Glob (*, ?) koruyan karsilastirma anahtari."""
    text = clean(text).translate(_TR_MAP).casefold()
    text = re.sub(r"[^a-z0-9*?]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def slug_of(href: str | None) -> str:
    if not href:
        return ""
    return urlparse(urljoin(BASE, href)).path.strip("/")


@dataclass
class CategoryNode:
    level: int
    name: str
    slug: str
    parent: CategoryNode | None = None
    children: list[CategoryNode] = field(default_factory=list)

    @property
    def url(self) -> str:
        return f"{BASE}/{self.slug}" if self.slug else BASE

    def path(self) -> list[CategoryNode]:
        node: CategoryNode | None = self
        out: list[CategoryNode] = []
        while node is not None:
            out.append(node)
            node = node.parent
        return list(reversed(out))

    def path_names(self) -> str:
        return " > ".join(n.name for n in self.path())

    def path_slugs(self) -> str:
        return "/".join(n.slug for n in self.path())

    def lv1(self) -> CategoryNode:
        root = self
        while root.parent is not None:
            root = root.parent
        return root

    def lv2(self) -> CategoryNode | None:
        """Uygulama kategorisi icin varsayilan dugum: 2. seviye atasi.

        2. seviye ise kendisi; 3. seviye ise ebeveyni; 1. seviye ise None.
        """
        if self.level == 2:
            return self
        if self.level == 3:
            return self.parent
        return None

    def to_dict(self) -> dict[str, object]:
        return {
            "level": self.level,
            "name": self.name,
            "slug": self.slug,
            "parent": self.parent.slug if self.parent is not None else None,
            "children": [c.slug for c in self.children],
        }


class CategoryTree:
    def __init__(self, roots: list[CategoryNode]) -> None:
        self.roots = roots
        self.nodes: list[CategoryNode] = []
        self.by_slug: dict[str, list[CategoryNode]] = {}
        self.by_name: dict[str, list[CategoryNode]] = {}
        self.by_path: dict[str, CategoryNode] = {}
        self._index()

    def _index(self) -> None:
        def walk(node: CategoryNode) -> None:
            if is_always_excluded(node):
                return
            self.nodes.append(node)
            if node.slug:
                self.by_slug.setdefault(node.slug, []).append(node)
            self.by_name.setdefault(norm_key(node.name), []).append(node)
            path_key = "/".join(norm_key(n.name) for n in node.path())
            self.by_path[path_key] = node
            for child in node.children:
                walk(child)

        for root in self.roots:
            walk(root)
        log.info(
            "kategori agaci: %d dugum, %d kok, %d slug",
            len(self.nodes),
            len(self.roots),
            len(self.by_slug),
        )

    def find(self, token: str, *, warn: bool = True) -> CategoryNode | None:
        """Slug, ad veya tam yol ile tek dugum bulur."""
        token = clean(token)
        if not token:
            return None
        direct = self.by_slug.get(token)
        if direct:
            if len(direct) > 1 and warn:
                log.warning("belirsiz slug %s: %d dugum, ilki kullanildi", token, len(direct))
            return direct[0]
        key = norm_key(token)
        named = self.by_name.get(key)
        if named:
            if len(named) > 1 and warn:
                log.warning("belirsiz ad %s: %d dugum, ilki kullanildi", token, len(named))
            return named[0]
        path_key = "/".join(norm_key(p) for p in re.split(r"\s*(?:>|/)\s*", token) if p)
        return self.by_path.get(path_key)

    def resolve_hierarchy(self, hierarchy: str | None) -> CategoryNode | None:
        """Karttaki Top/Mid/Leaf metnini agacta en derin bilinen dugume cevirir."""
        parts = [p for p in (clean(x) for x in (hierarchy or "").split("/")) if p]
        if not parts:
            return None
        keys = [norm_key(p) for p in parts]
        for size in range(len(keys), 1, -1):
            for start in range(0, len(keys) - size + 1):
                window = keys[start : start + size]
                path_key = "/".join(window)
                if path_key in self.by_path:
                    return self.by_path[path_key]
        for key in reversed(keys):
            named = self.by_name.get(key)
            if named:
                return named[0]
        return None

    def descendants(self, node: CategoryNode) -> list[CategoryNode]:
        out: list[CategoryNode] = []

        def walk(n: CategoryNode) -> None:
            for child in n.children:
                if is_always_excluded(child):
                    continue
                out.append(child)
                walk(child)

        walk(node)
        return out

    def is_excluded(self, node: CategoryNode | None, patterns: list[str]) -> bool:
        if node is None:
            return False
        if is_always_excluded(node):
            return True
        normalized = [norm_pattern(p) for p in patterns if clean(p)]
        if not normalized:
            return False
        for candidate in node.path():
            keys = {
                norm_key(candidate.slug),
                norm_key(candidate.name),
                "/".join(norm_key(n.name) for n in candidate.path()),
                "/".join(norm_key(n.slug) for n in candidate.path()),
            }
            for pattern in normalized:
                for key in keys:
                    if key and fnmatch.fnmatch(key, pattern):
                        return True
        return False

    def to_rows(self) -> list[list[object]]:
        return [
            [
                n.level,
                n.path_names(),
                n.name,
                n.slug,
                n.url,
                "",
                "",
                "",
            ]
            for n in self.nodes
            if not is_always_excluded(n)
        ]

    def to_dict(self) -> dict[str, object]:
        flat: list[dict[str, object]] = []
        for node in self.nodes:
            flat.append(
                {
                    "level": node.level,
                    "name": node.name,
                    "slug": node.slug,
                    "parent_path": "/".join(n.slug for n in node.path()[:-1]),
                }
            )
        return {"version": CACHE_VERSION, "fetched_at": time.time(), "nodes": flat}

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> CategoryTree:
        nodes_data = data.get("nodes")
        if not isinstance(nodes_data, list):
            raise ValueError("gecersiz kategori cache")
        by_slug_path: dict[str, CategoryNode] = {}
        roots: list[CategoryNode] = []
        for item in nodes_data:
            if not isinstance(item, dict):
                continue
            slug = str(item.get("slug") or "")
            if not slug:
                continue
            node = CategoryNode(
                level=int(item.get("level") or 1),
                name=str(item.get("name") or slug),
                slug=slug,
            )
            parent_path = str(item.get("parent_path") or "")
            if parent_path:
                parent = by_slug_path.get(parent_path + "/" + slug)
                if parent is None:
                    parent = by_slug_path.get(parent_path)
                if parent is not None:
                    node.parent = parent
                    parent.children.append(node)
                else:
                    roots.append(node)
            else:
                roots.append(node)
            by_slug_path["/".join(n.slug for n in node.path())] = node
        return cls(roots)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: Path, ttl_hours: int = CACHE_TTL_HOURS) -> CategoryTree | None:
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        fetched = float(data.get("fetched_at") or 0)
        if time.time() - fetched > ttl_hours * 3600:
            return None
        try:
            return cls.from_dict(data)
        except (TypeError, ValueError):
            return None


def _first_link(node) -> tuple[str, str] | None:
    for child in node.iter():
        if child.tag == "a":
            return clean(child.text(strip=True)), child.attributes.get("href") or ""
    return None


def parse_nav(html: str) -> CategoryTree:
    """Sayfadaki nav#nav-menu-category agacini ayristirir."""
    tree = HTMLParser(html)
    nav = tree.css_first("nav#nav-menu-category")
    if nav is None:
        raise ValueError("nav#nav-menu-category bulunamadi")
    roots: list[CategoryNode] = []
    for lv1 in nav.css("li.lv1-li"):
        link1 = _first_link(lv1)
        if link1 is None:
            continue
        name1, href1 = link1
        slug1 = slug_of(href1)
        if not name1 or not slug1:
            continue
        node1 = CategoryNode(level=1, name=name1, slug=slug1)
        roots.append(node1)
        for lv2 in lv1.css("li.lv2-li"):
            link2 = _first_link(lv2)
            if link2 is None:
                continue
            name2, href2 = link2
            slug2 = slug_of(href2)
            if not name2 or not slug2:
                continue
            node2 = CategoryNode(level=2, name=name2, slug=slug2, parent=node1)
            node1.children.append(node2)
            for lv3 in lv2.css("ul.lv-3 li"):
                link3 = _first_link(lv3)
                if link3 is None:
                    continue
                name3, href3 = link3
                slug3 = slug_of(href3)
                if not name3 or not slug3:
                    continue
                node3 = CategoryNode(level=3, name=name3, slug=slug3, parent=node2)
                node2.children.append(node3)
    if not roots:
        raise ValueError("kategori agaci bos")
    return CategoryTree(roots)


async def fetch_category_tree(
    http: Http,
    cache_path: Path | None = None,
    ttl_hours: int = CACHE_TTL_HOURS,
) -> CategoryTree:
    if cache_path is not None:
        cached = CategoryTree.load(cache_path, ttl_hours)
        if cached is not None:
            log.info("kategori agaci cache'ten okundu: %s", cache_path)
            return cached
    html = await http.get(f"{BASE}/")
    if not html:
        raise ValueError("kategori agaci icin ana sayfa alinamadi")
    tree = parse_nav(html)
    if cache_path is not None:
        try:
            tree.save(cache_path)
        except OSError as exc:
            log.warning("kategori cache yazilamadi: %s", exc)
    return tree


def write_category_files(
    tree: CategoryTree,
    out_dir: Path,
    include_slugs: set[str],
    app_categories: dict[str, str | None],
    exclude_patterns: list[str],
    rows: list[list[object]],
    stamp: str,
) -> list[Path]:
    """Kategorileri txt + kopyalanabilir toml olarak out/ altina yazar."""
    out_dir.mkdir(parents=True, exist_ok=True)
    txt_path = out_dir / "categories.txt"
    toml_path = out_dir / "categories.toml"

    def cell(value: object) -> str:
        return "" if value is None else str(value)

    txt_lines = [
        f"# Arcelik kategori listesi {stamp}",
        "# level\tpath\tname\tslug\turl\tin_config\texcluded\tproduct_count",
    ]
    txt_lines += ["\t".join(cell(v) for v in row) for row in rows]
    txt_path.write_text("\n".join(txt_lines) + "\n", encoding="utf-8")

    toml_lines = [
        f"## Arcelik kategori listesi {stamp}",
        "## Istediginiz blogu secip nvim'de gc ile yorumlari acin.",
        "## ## ile baslayan satirlar yorum kalir; tek # ile baslayan TOML satirlari aktif olur.",
        "## [config] = su an config.toml'da; [excluded] = kara listede.",
        "## app_category varsayilani 2. seviye; LV1 icin include_children = true onerilir.",
        "",
    ]
    seen_slugs: set[str] = set()
    for node in tree.nodes:
        if is_always_excluded(node):
            continue
        if norm_key(node.name) == "tum urunler":
            continue
        flags = ""
        if node.slug in include_slugs:
            flags += " [config]"
        if tree.is_excluded(node, exclude_patterns):
            flags += " [excluded]"
        if node.slug in seen_slugs:
            toml_lines.append(
                f"## [L{node.level}] {node.path_names()} [duplicate slug]"
            )
            toml_lines.append("")
            continue
        seen_slugs.add(node.slug)
        app = app_categories.get(node.slug)
        if not app and node.lv2() is not None:
            app = node.lv2().name
        toml_lines.append(f"## [L{node.level}] {node.path_names()}{flags}")
        toml_lines.append("# [[categories.include]]")
        toml_lines.append(
            "# slug = " + json.dumps(node.slug, ensure_ascii=False)
        )
        if app:
            toml_lines.append(
                "# app_category = " + json.dumps(app, ensure_ascii=False)
            )
        if node.level == 1:
            toml_lines.append(
                "# include_children = true   # tum alt kategoriler icin"
            )
        toml_lines.append("")
    toml_path.write_text("\n".join(toml_lines), encoding="utf-8")
    return [txt_path, toml_path]


async def sitemap_category_urls(http: Http) -> set[str]:
    """CATEGORY sitemap'indeki URL'ler (denetim icin)."""
    index = await http.get(f"{BASE}/sitemap.xml") or ""
    urls: set[str] = set()
    for loc in re.findall(r"<loc>\s*(.*?)\s*</loc>", index):
        if "CATEGORY" not in loc.upper() or "CATEGORYLANDING" in loc.upper():
            continue
        xml = await http.get(loc.replace("&amp;", "&")) or ""
        urls |= {
            u.rstrip("/")
            for u in re.findall(r"<loc>\s*(https://[^<\s]+?)\s*</loc>", xml)
        }
    return {url for url in urls if not is_blog_url(url)}
