"""Lectura de páginas web (para la base de conocimiento y el motor de investigación).
Solo descarga lo que pides; el contenido se trata como DATOS, nunca como instrucciones."""

import re
from html.parser import HTMLParser
from urllib.parse import urlparse

import httpx

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15 VISTAN/4.0"
MAX_BYTES = 2_500_000


class _Text(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "nav", "footer", "header", "form", "aside", "iframe"}
    BLOCK = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "tr", "section", "article", "pre", "blockquote"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip = 0
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag, attrs):  # noqa: ANN001
        if tag in self.SKIP:
            self.skip += 1
        if tag == "title":
            self._in_title = True
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):  # noqa: ANN001
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        if tag == "title":
            self._in_title = False
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):  # noqa: ANN001
        if self._in_title:
            self.title += data
        elif not self.skip:
            self.parts.append(data)


def html_to_text(html: str) -> tuple[str, str]:
    p = _Text()
    try:
        p.feed(html)
    except Exception:  # noqa: BLE001 - HTML roto: devolvemos lo que se haya podido leer
        pass
    text = re.sub(r"[ \t\r\f\v]+", " ", "".join(p.parts))
    text = re.sub(r"\n\s*\n+", "\n\n", text).strip()
    return p.title.strip(), text


def check_url(url: str) -> str:
    u = urlparse(url.strip())
    if u.scheme not in ("http", "https") or not u.netloc:
        raise ValueError("Solo enlaces http(s)")
    host = (u.hostname or "").lower()
    if host in ("localhost", "127.0.0.1", "0.0.0.0", "::1") or host.endswith(".local") or host.startswith("192.168.") \
            or host.startswith("10.") or host.endswith(".ts.net"):
        raise ValueError("Por seguridad no leo direcciones de tu red local")
    return url.strip()


def fetch(url: str, client: httpx.Client | None = None, timeout: float = 15.0) -> dict:
    """{'url','title','text','content_type'}. Lanza ValueError con un mensaje claro si falla."""
    url = check_url(url)
    c = client or httpx.Client(follow_redirects=True, timeout=timeout, headers={"User-Agent": UA, "Accept-Language": "es,en;q=0.8"})
    try:
        with c.stream("GET", url) as r:
            if r.status_code >= 400:
                raise ValueError(f"La web respondió {r.status_code}")
            ctype = r.headers.get("content-type", "")
            data = b""
            for chunk in r.iter_bytes():
                data += chunk
                if len(data) > MAX_BYTES:
                    break
            final = str(r.url)
    except httpx.HTTPError as exc:
        raise ValueError(f"No se pudo descargar ({type(exc).__name__})") from exc
    if "pdf" in ctype or final.lower().endswith(".pdf"):
        from atlas.knowledge.extract import extract
        return {"url": final, "title": final.rsplit("/", 1)[-1], "text": extract("pdf", data), "content_type": "pdf"}
    html = data.decode(r.encoding or "utf-8", errors="replace")
    if "html" not in ctype and "<html" not in html[:2000].lower():
        return {"url": final, "title": final, "text": html[:200_000], "content_type": ctype}
    title, text = html_to_text(html)
    return {"url": final, "title": title or final, "text": text, "content_type": "html"}
