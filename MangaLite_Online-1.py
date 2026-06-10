"""
MangaLite Online — Fuentes en español tipo Aniyomi
Fuentes: MangaDex · LeerCapitulo · InManga · LectorTMOo · LectorTMO.vip · LectorMangass
pip install requests cloudscraper beautifulsoup4 Pillow
"""
import tkinter as tk
from tkinter import messagebox, filedialog
import threading, requests, json, os, io, zipfile, re, configparser
from pathlib import Path

try:
    import cloudscraper; CS_OK = True
except ImportError:
    CS_OK = False

try:
    from bs4 import BeautifulSoup; BS_OK = True
except ImportError:
    BS_OK = False

try:
    from PIL import Image, ImageTk; PIL_OK = True
except ImportError:
    PIL_OK = False

# ── Config ────────────────────────────────────────────────
CFG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mangalite_online.cfg")
DL_DIR   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Descargas")

FUENTE_DEFAULTS = {
    "mangadex":      {"activa":"1","cloudflare":"0","nombre":"MangaDex",      "color":"#00d4ff"},
    "leercapitulo":  {"activa":"1","cloudflare":"1","nombre":"LeerCapitulo",   "color":"#ff9800"},
    "inmanga":       {"activa":"1","cloudflare":"0","nombre":"InManga",        "color":"#4caf50"},
    "lectortmoo":    {"activa":"1","cloudflare":"1","nombre":"LectorTMOo",     "color":"#e91e63"},
    "lectortmovip":  {"activa":"1","cloudflare":"1","nombre":"LectorTMO.vip",  "color":"#9c27b0"},
    "lectormangass": {"activa":"1","cloudflare":"1","nombre":"LectorMangass",  "color":"#ff5722"},
}

GLOBAL_DEFAULTS = {
    "timeout":        "20",
    "proxy":          "",
    "zoom":           "fit_width",
    "modo":           "vertical",
    "idioma":         "es",
    "descarga_dir":   DL_DIR,
    "busqueda_todas": "1",
    "precarga":       "3",
    "filtro_adultos": "0",
}

def load_cfg():
    cfg = configparser.ConfigParser()
    cfg.read(CFG_FILE, encoding="utf-8")
    if "global" not in cfg: cfg["global"] = {}
    for k,v in GLOBAL_DEFAULTS.items():
        if k not in cfg["global"]: cfg["global"][k] = v
    for fid, fd in FUENTE_DEFAULTS.items():
        sec = f"fuente_{fid}"
        if sec not in cfg: cfg[sec] = {}
        for k,v in fd.items():
            if k not in cfg[sec]: cfg[sec][k] = v
    return cfg

def save_cfg(cfg):
    with open(CFG_FILE,"w",encoding="utf-8") as f: cfg.write(f)

def gg(cfg,k):
    try: return cfg["global"].get(k, GLOBAL_DEFAULTS.get(k,""))
    except: return GLOBAL_DEFAULTS.get(k,"")

def gf(cfg,fid,k):
    sec = f"fuente_{fid}"
    try:
        if cfg.has_section(sec):
            return cfg.get(sec, k)
    except: pass
    return FUENTE_DEFAULTS.get(fid,{}).get(k,"")

# ── Paleta ────────────────────────────────────────────────
BG    = "#0b0d12"; BG2 = "#13161e"; BG3 = "#1a1e2a"
TEXT  = "#e8eaf0"; MUTED = "#4a5068"; BORDER = "#1e2230"
HOVER = "#1c2030"; SEL = "#18203c"
CYAN  = "#00d4ff"; RED = "#ff4060"; GREEN = "#00e676"; AMBER = "#ffb300"
FTB   = ("Segoe UI",9,"bold"); FTS = ("Segoe UI",8)
FTT   = ("Segoe UI",13,"bold"); FT = ("Segoe UI",9); FTM = ("Consolas",8)
SPINNER = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]

def lighten(c,a=18):
    try:
        return "#{:02x}{:02x}{:02x}".format(
            min(255,int(c[1:3],16)+a),
            min(255,int(c[3:5],16)+a),
            min(255,int(c[5:7],16)+a))
    except: return c

HDRS = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept-Language":"es-ES,es;q=0.9"}

def make_session(use_cf=False):
    if use_cf and CS_OK:
        s = cloudscraper.create_scraper(browser={"browser":"chrome","platform":"windows"})
    else:
        s = requests.Session()
    s.headers.update(HDRS)
    return s

def safe_get(session, url, timeout=20):
    try:
        r = session.get(url, timeout=timeout)
        return r if r.status_code == 200 else None
    except Exception as ex:
        print(f"GET error {url}: {ex}"); return None

# ══════════════════════════════════════════════════════════
#  FUENTES
# ══════════════════════════════════════════════════════════

# ── MangaDex ──────────────────────────────────────────────
class MangaDex:
    ID   = "mangadex"
    BASE = "https://api.mangadex.org"
    CDN  = "https://uploads.mangadex.org"

    @staticmethod
    def buscar(query, cfg):
        lang = gg(cfg,"idioma")
        try:
            r = requests.get(f"{MangaDex.BASE}/manga", params={
                "title":query,"limit":20,
                "availableTranslatedLanguage[]":[lang,"es-la"],
                "contentRating[]":["safe","suggestive"],
                "includes[]":["cover_art","author"],
                "order[relevance]":"desc",
            }, headers=HDRS, timeout=int(gg(cfg,"timeout")))
            if r.status_code!=200: return []
            return [MangaDex._parse(m) for m in r.json().get("data",[])]
        except Exception as ex:
            print(f"MangaDex buscar: {ex}"); return []

    @staticmethod
    def _parse(m):
        a   = m.get("attributes",{})
        rel = m.get("relationships",[])
        t   = (a.get("title",{}).get("es") or a.get("title",{}).get("es-la")
               or a.get("title",{}).get("en") or next(iter(a.get("title",{}).values()),"?"))
        cov = ""
        for r in rel:
            if r.get("type")=="cover_art":
                fn=r.get("attributes",{}).get("fileName","")
                if fn: cov=f"{MangaDex.CDN}/covers/{m['id']}/{fn}.256.jpg"
                break
        aut = next((r.get("attributes",{}).get("name","") for r in rel if r.get("type")=="author"),"")
        tags= [t2.get("attributes",{}).get("name",{}).get("en","") for t2 in a.get("tags",[])]
        return {"id":m["id"],"title":t,"cover_url":cov,"autor":aut,
                "desc":(a.get("description",{}).get("es") or a.get("description",{}).get("en",""))[:250],
                "tags":tags[:5],"estado":a.get("status",""),"fuente":"MangaDex",
                "fuente_id":"mangadex","tipo":a.get("originalLanguage","")}

    @staticmethod
    def capitulos(manga, cfg):
        lang = gg(cfg,"idioma")
        try:
            caps=[]; offset=0
            while True:
                r = requests.get(f"{MangaDex.BASE}/manga/{manga['id']}/feed",
                    params={"translatedLanguage[]":[lang,"es-la"],
                            "order[chapter]":"desc","limit":100,"offset":offset,
                            "contentRating[]":["safe","suggestive"]},
                    headers=HDRS, timeout=int(gg(cfg,"timeout")))
                if r.status_code!=200: break
                d=r.json(); data=d.get("data",[])
                if not data: break
                for c in data:
                    a=c.get("attributes",{}); num=a.get("chapter","?")
                    caps.append({"id":c["id"],"num":num,
                        "title":a.get("title","") or f"Capítulo {num}",
                        "fecha":(a.get("publishAt","") or "")[:10],
                        "pages":a.get("pages",0),"fuente":"MangaDex","fuente_id":"mangadex"})
                offset+=100
                if offset>=d.get("total",0): break
            return caps
        except Exception as ex:
            print(f"MangaDex caps: {ex}"); return []

    @staticmethod
    def paginas(cap, cfg):
        try:
            r = requests.get(f"{MangaDex.BASE}/at-home/server/{cap['id']}",
                             headers=HDRS, timeout=int(gg(cfg,"timeout")))
            if r.status_code!=200: return []
            d=r.json(); b=d["baseUrl"]; ch=d["chapter"]
            return [f"{b}/data/{ch['hash']}/{p}" for p in ch.get("data",[])]
        except Exception as ex:
            print(f"MangaDex pags: {ex}"); return []

# ── Base para scrapers ────────────────────────────────────
class BaseScraper:
    ID   = ""
    BASE = ""

    @classmethod
    def _ses(cls, cfg):
        use_cf = gf(cfg, cls.ID, "cloudflare") == "1"
        return make_session(use_cf)

    @classmethod
    def _soup(cls, cfg, url):
        s = cls._ses(cfg)
        r = safe_get(s, url, int(gg(cfg,"timeout")))
        if not r: return None
        return BeautifulSoup(r.text,"html.parser")

    @classmethod
    def _nombre(cls, cfg):
        return gf(cfg, cls.ID, "nombre") or cls.ID

# ── LeerCapitulo ──────────────────────────────────────────
class LeerCapitulo(BaseScraper):
    ID   = "leercapitulo"
    BASE = "https://www.leercapitulo.co"

    # Estructura real de leercapitulo.co:
    # Búsqueda:  /search_ajax/  POST  o  /?s=query
    # Manga:     /manga/{id}/{slug}/
    # Capítulo:  /leer/{id}/{slug}/{num}/
    # Las imágenes usan lazy load con JS — se extraen de scripts inline

    @classmethod
    def _req(cls, cfg, url, method="GET", data=None):
        """Petición con headers completos que simulan navegador real"""
        use_cf = gf(cfg, cls.ID, "cloudflare") == "1"
        s = make_session(use_cf)
        s.headers.update({
            "Referer": cls.BASE + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "es-ES,es;q=0.9",
        })
        try:
            if method == "POST":
                r = s.post(url, data=data, timeout=int(gg(cfg,"timeout")))
            else:
                r = s.get(url, timeout=int(gg(cfg,"timeout")))
            return r if r and r.status_code == 200 else None
        except Exception as ex:
            print(f"LeerCapitulo req error: {ex}"); return None

    @classmethod
    def buscar(cls, query, cfg):
        if not BS_OK: return []
        res = []

        # Método 1: búsqueda directa con parámetro s=
        r = cls._req(cfg, f"{cls.BASE}/?s={requests.utils.quote(query)}")
        if r:
            soup = BeautifulSoup(r.text, "html.parser")
            res = cls._parse_lista(soup, cfg)

        # Método 2: si no hay resultados, intentar /search/
        if not res:
            r2 = cls._req(cfg, f"{cls.BASE}/search/?query={requests.utils.quote(query)}")
            if r2:
                soup2 = BeautifulSoup(r2.text, "html.parser")
                res = cls._parse_lista(soup2, cfg)

        # Método 3: buscar en tendencias/home si sigue vacío
        if not res:
            print(f"LeerCapitulo: sin resultados para '{query}' — probando home")
            r3 = cls._req(cfg, cls.BASE)
            if r3:
                soup3 = BeautifulSoup(r3.text, "html.parser")
                # Extraer todos los manga del home que coincidan
                for a in soup3.select("a[href*='/manga/']"):
                    titulo = a.get("title","") or a.get_text(strip=True)
                    if query.lower() in titulo.lower():
                        href = a.get("href","")
                        if not href.startswith("http"): href = cls.BASE + href
                        if not any(x["url"]==href for x in res):
                            res.append({"id":href,"url":href,
                                "title":titulo[:80],"cover_url":"",
                                "desc":"","autor":"","tags":[],"estado":"",
                                "fuente":cls._nombre(cfg),"fuente_id":cls.ID,"tipo":""})
        return res

    @classmethod
    def _parse_lista(cls, soup, cfg):
        """Parsea resultados de búsqueda — soporta múltiples estructuras"""
        res = []
        # Estructura 1: divs con clase c-tabs-item o similar
        selectors = [
            "div.c-tabs-item", "div.manga-item", "div.page-item-detail",
            "article.manga", "div.bs", "div.bsx",
            # Estructura home/tendencias de leercapitulo
            "div.aniframe", "div.animefull",
        ]
        cards = []
        for sel in selectors:
            found = soup.select(sel)
            if found: cards = found; break

        # Fallback: buscar todos los h3 con enlace a manga
        if not cards:
            for h in soup.select("h3"):
                a = h.select_one("a[href*='/manga/']")
                if a:
                    href = a.get("href","")
                    if not href.startswith("http"): href = cls.BASE + href
                    titulo = a.get_text(strip=True) or a.get("title","")
                    if titulo and not any(x["url"]==href for x in res):
                        res.append({"id":href,"url":href,
                            "title":titulo[:80],"cover_url":"",
                            "desc":"","autor":"","tags":[],"estado":"",
                            "fuente":cls._nombre(cfg),"fuente_id":cls.ID,"tipo":""})
            return res

        for card in cards:
            a   = card.select_one("a[href*='/manga/']") or card.select_one("a")
            img = card.select_one("img")
            ttl = card.select_one("h3, h2, .series-title, .manga-name, .title")
            if not a: continue
            href = a.get("href","")
            if not href.startswith("http"): href = cls.BASE + href
            if "/manga/" not in href: continue
            titulo = (ttl.get_text(strip=True) if ttl
                      else a.get("title","") or a.get_text(strip=True))
            cover = ""
            if img:
                cover = (img.get("src") or img.get("data-src") or
                         img.get("data-lazy-src") or img.get("data-cfsrc",""))
            if not any(x["url"]==href for x in res):
                res.append({"id":href,"url":href,
                    "title":titulo[:80],"cover_url":cover,
                    "desc":"","autor":"","tags":[],"estado":"",
                    "fuente":cls._nombre(cfg),"fuente_id":cls.ID,"tipo":""})
        return res

    @classmethod
    def capitulos(cls, manga, cfg):
        if not BS_OK: return []
        url = manga.get("url", manga.get("id",""))
        r   = cls._req(cfg, url)
        if not r: return []
        soup = BeautifulSoup(r.text, "html.parser")
        caps = []

        # Selectores de capítulos en orden de prioridad
        cap_selectors = [
            "ul.version-chap li",
            "ul.clstyle li",
            "ul#chapterlist li",
            "div.eplister ul li",
            ".chapter-list li",
            ".chapters li",
            "li.wp-manga-chapter",
        ]
        items = []
        for sel in cap_selectors:
            items = soup.select(sel)
            if items: break

        if not items:
            # Fallback: todos los enlaces que parezcan capítulos
            for a in soup.select("a[href*='/leer/']"):
                href = a.get("href","")
                if not href.startswith("http"): href = cls.BASE + href
                txt = a.get_text(strip=True)
                if txt:
                    caps.append({"id":href,"url":href,"num":txt,
                        "title":txt,"fecha":"","pages":0,
                        "fuente":cls._nombre(cfg),"fuente_id":cls.ID})
            return caps

        for li in items:
            a = li.select_one("a")
            if not a: continue
            href = a.get("href","")
            if not href.startswith("http"): href = cls.BASE + href
            num  = a.get_text(strip=True)
            fecha_el = li.select_one(".chapter-release-date, i, .date, span")
            fecha = fecha_el.get_text(strip=True) if fecha_el else ""
            caps.append({"id":href,"url":href,"num":num,
                "title":num,"fecha":fecha,"pages":0,
                "fuente":cls._nombre(cfg),"fuente_id":cls.ID})
        return caps

    @classmethod
    def paginas(cls, cap, cfg):
        url = cap.get("url", cap.get("id",""))
        r   = cls._req(cfg, url)
        if not r: return []

        # Método 1: extraer URLs de imágenes de scripts JS inline
        imgs = []
        for pat in [
            r'["\'](https?://[^\s\'"]+\.(?:jpg|jpeg|png|webp))["\']',
            r'src\s*=\s*["\']([^"\']+\.(?:jpg|jpeg|png|webp))["\']',
        ]:
            found = re.findall(pat, r.text)
            if found:
                # Filtrar solo las imágenes de capítulo (descartar logos, iconos)
                filtered = [u for u in found
                            if any(x in u for x in ["/leer/","chapter","page",
                                                     "upload","image","img",
                                                     "cdn","scan"])]
                if filtered:
                    imgs = list(dict.fromkeys(filtered)); break

        # Método 2: BS4 sobre el HTML
        if not imgs and BS_OK:
            soup = BeautifulSoup(r.text, "html.parser")
            for img in soup.select(
                    ".page-break img, .wp-manga-chapter-img, "
                    ".reading-content img, #readerarea img, "
                    ".chapter-img img, img.alignnone"):
                src = (img.get("src") or img.get("data-src") or
                       img.get("data-lazy-src",""))
                if src and src.startswith("http"):
                    imgs.append(src)
            imgs = list(dict.fromkeys(imgs))

        return imgs

# ── InManga ───────────────────────────────────────────────
class InManga(BaseScraper):
    ID   = "inmanga"
    BASE = "https://inmanga.com"

    @classmethod
    def buscar(cls, query, cfg):
        try:
            s=cls._ses(cfg)
            r=safe_get(s,
                f"{cls.BASE}/manga/GetConsultedMangas?suggestion={requests.utils.quote(query)}"
                f"&genres=&orderby=4&status=false&OnlyFavorites=false"
                f"&dateFilterType=false&startDate&endDate&Take=20",
                int(gg(cfg,"timeout")))
            if not r: return []
            data=r.json()
            res=[]
            for m in (data if isinstance(data,list) else data.get("data",[])):
                slug=m.get("Identification","") or m.get("slug","")
                res.append({
                    "id":slug,"url":f"{cls.BASE}/ver-manga/{slug}",
                    "title":(m.get("Name","") or m.get("name",""))[:80],
                    "cover_url":f"https://pack-yak.intomanga.com/images/manga/{slug}/cover/",
                    "desc":""," autor":m.get("Author",""),
                    "tags":[],"estado":m.get("StatusName",""),
                    "fuente":cls._nombre(cfg),"fuente_id":cls.ID,"tipo":""})
            return res
        except Exception as ex:
            print(f"InManga buscar: {ex}")
            # Fallback HTML
            return cls._buscar_html(query, cfg)

    @classmethod
    def _buscar_html(cls, query, cfg):
        if not BS_OK: return []
        soup = cls._soup(cfg, f"{cls.BASE}/manga/consult?suggestion={requests.utils.quote(query)}")
        if not soup: return []
        res=[]
        for card in soup.select(".manga-title,.manga-info-panel,.manga-card"):
            a = card.select_one("a")
            if not a: continue
            href=a.get("href","")
            if not href.startswith("http"): href=cls.BASE+href
            img=card.select_one("img")
            res.append({"id":href,"url":href,
                "title":a.get_text(strip=True)[:80],
                "cover_url":img.get("src","") if img else "",
                "desc":"","autor":"","tags":[],"estado":"",
                "fuente":cls._nombre(cfg),"fuente_id":cls.ID,"tipo":""})
        return res

    @classmethod
    def capitulos(cls, manga, cfg):
        if not BS_OK: return []
        soup = cls._soup(cfg, manga.get("url",""))
        if not soup: return []
        caps=[]
        for a in soup.select("a[href*='/ver-manga/']"):
            href=a.get("href","")
            if not href.startswith("http"): href=cls.BASE+href
            num=a.get_text(strip=True)
            if num:
                caps.append({"id":href,"url":href,"num":num,"title":f"Cap. {num}",
                    "fecha":"","pages":0,"fuente":cls._nombre(cfg),"fuente_id":cls.ID})
        return caps

    @classmethod
    def paginas(cls, cap, cfg):
        if not BS_OK: return []
        soup = cls._soup(cfg, cap.get("url",""))
        if not soup: return []
        imgs=[]
        for sc in soup.find_all("script"):
            t=sc.string or ""
            found=re.findall(r'https?://[^\s\'"\\]+\.(?:jpg|jpeg|png|webp)',t)
            if found: imgs=list(dict.fromkeys(found)); break
        if not imgs:
            for img in soup.select("img.ImageContainer,img.PagesContainer,img[id^='page']"):
                src=img.get("src") or img.get("data-src","")
                if src and src.startswith("http"): imgs.append(src)
        return imgs

# ── LectorTMOo ────────────────────────────────────────────
class LectorTMOo(BaseScraper):
    ID   = "lectortmoo"
    BASE = "https://lectortmoo.com"

    @classmethod
    def buscar(cls, query, cfg):
        if not BS_OK: return []
        soup = cls._soup(cfg, f"{cls.BASE}/?s={requests.utils.quote(query)}")
        if not soup: return []
        return cls._parse_cards(soup, cfg)

    @classmethod
    def _parse_cards(cls, soup, cfg):
        res=[]
        for card in soup.select("article.wp-manga,.manga-item,.c-tabs-item"):
            a   = card.select_one("a[href*='/manga/']") or card.select_one("a")
            img = card.select_one("img")
            ttl = card.select_one(".post-title,.manga-name,h3,h2")
            if not a: continue
            href=a.get("href","")
            if not href.startswith("http"): href=cls.BASE+href
            src=img.get("src") or img.get("data-src","") if img else ""
            res.append({"id":href,"url":href,
                "title":(ttl.get_text(strip=True) if ttl else a.get_text(strip=True))[:80],
                "cover_url":src,"desc":"","autor":"","tags":[],"estado":"",
                "fuente":cls._nombre(cfg),"fuente_id":cls.ID,"tipo":""})
        return res

    @classmethod
    def capitulos(cls, manga, cfg):
        if not BS_OK: return []
        soup = cls._soup(cfg, manga.get("url",""))
        if not soup: return []
        caps=[]
        for li in soup.select(".wp-manga-chapter,li.chapter,.chapter-item"):
            a=li.select_one("a")
            if not a: continue
            href=a.get("href","")
            if not href.startswith("http"): href=cls.BASE+href
            fecha=li.select_one(".chapter-release-date,i,.date")
            caps.append({"id":href,"url":href,"num":a.get_text(strip=True),
                "title":a.get_text(strip=True),
                "fecha":fecha.get_text(strip=True) if fecha else "",
                "pages":0,"fuente":cls._nombre(cfg),"fuente_id":cls.ID})
        return caps

    @classmethod
    def paginas(cls, cap, cfg):
        if not BS_OK: return []
        soup = cls._soup(cfg, cap.get("url",""))
        if not soup: return []
        imgs=[]
        for sc in soup.find_all("script"):
            t=sc.string or ""
            found=re.findall(r'https?://[^\s\'"\\]+\.(?:jpg|jpeg|png|webp)',t)
            if found: imgs=list(dict.fromkeys(found)); break
        if not imgs:
            for img in soup.select(".page-break img,.wp-manga-chapter-img img,img.wp-manga-chapter-img"):
                src=img.get("src") or img.get("data-src","")
                if src and src.startswith("http"): imgs.append(src)
        return imgs

# ── LectorTMO.vip ─────────────────────────────────────────
class LectorTMOvip(BaseScraper):
    ID   = "lectortmovip"
    BASE = "https://lectortmo.vip"

    @classmethod
    def buscar(cls, query, cfg):
        if not BS_OK: return []
        soup = cls._soup(cfg, f"{cls.BASE}/?s={requests.utils.quote(query)}")
        if not soup: return []
        return LectorTMOo._parse_cards(soup, cfg)  # misma estructura WordPress

    @classmethod
    def capitulos(cls, manga, cfg):
        return LectorTMOo.capitulos(manga, cfg)

    @classmethod
    def paginas(cls, cap, cfg):
        return LectorTMOo.paginas(cap, cfg)

# ── LectorMangass ─────────────────────────────────────────
class LectorMangass(BaseScraper):
    ID   = "lectormangass"
    BASE = "https://lectormangass.net"

    @classmethod
    def buscar(cls, query, cfg):
        if not BS_OK: return []
        soup = cls._soup(cfg, f"{cls.BASE}/?s={requests.utils.quote(query)}")
        if not soup: return []
        return LectorTMOo._parse_cards(soup, cfg)

    @classmethod
    def capitulos(cls, manga, cfg):
        return LectorTMOo.capitulos(manga, cfg)

    @classmethod
    def paginas(cls, cap, cfg):
        return LectorTMOo.paginas(cap, cfg)

# ── Mapa de fuentes (LeerCapitulo primero = mayor prioridad) ─
FUENTES = {
    "leercapitulo":  LeerCapitulo,
    "mangadex":      MangaDex,
    "inmanga":       InManga,
    "lectortmoo":    LectorTMOo,
    "lectortmovip":  LectorTMOvip,
    "lectormangass": LectorMangass,
}

def fuentes_activas(cfg):
    return [fid for fid,cls in FUENTES.items()
            if gf(cfg,fid,"activa")=="1"]

# ══════════════════════════════════════════════════════════
#  WIDGETS COMUNES
# ══════════════════════════════════════════════════════════
class Btn(tk.Label):
    def __init__(self,p,text,bg,fg,cmd,font=FTB,px=10,py=5,**kw):
        super().__init__(p,text=text,bg=bg,fg=fg,font=font,
                         padx=px,pady=py,cursor="hand2",relief="flat",**kw)
        self._bg=bg
        self.bind("<Button-1>",lambda e:cmd())
        self.bind("<Enter>",   lambda e:self.configure(bg=lighten(self._bg)))
        self.bind("<Leave>",   lambda e:self.configure(bg=self._bg))

def scrollable(parent):
    c=tk.Canvas(parent,bg=BG,highlightthickness=0)
    vsb=tk.Scrollbar(parent,orient="vertical",command=c.yview)
    c.configure(yscrollcommand=vsb.set)
    vsb.pack(side="right",fill="y"); c.pack(side="left",fill="both",expand=True)
    lf=tk.Frame(c,bg=BG)
    wid=c.create_window((0,0),window=lf,anchor="nw")
    lf.bind("<Configure>",lambda e:c.configure(scrollregion=c.bbox("all")))
    c.bind("<Configure>", lambda e:c.itemconfig(wid,width=e.width))
    c.bind_all("<MouseWheel>",lambda e:c.yview_scroll(int(-1*(e.delta/120)),"units"))
    return lf

def fuente_badge(parent, fuente_id, cfg):
    color = gf(cfg, fuente_id, "color") or CYAN
    nombre= gf(cfg, fuente_id, "nombre") or fuente_id
    lbl = tk.Label(parent, text=nombre[:12], bg=color, fg="#000",
                   font=("Segoe UI",7,"bold"), padx=4, pady=1, relief="flat")
    lbl.pack(side="left", padx=(0,4))
    return lbl

# ══════════════════════════════════════════════════════════
#  LECTOR ONLINE
# ══════════════════════════════════════════════════════════
class OnlineReader(tk.Toplevel):
    def __init__(self, parent, titulo, cap, get_pags_fn, dl_fn=None, cfg=None):
        super().__init__(parent)
        self.title(f"📖 {titulo[:50]} — {cap.get('num','')}")
        self.geometry("920x700"); self.configure(bg="#000")
        self.titulo=titulo; self.cap=cap; self.get_pags=get_pags_fn
        self.dl_fn=dl_fn; self.cfg=cfg or {}
        self.urls=[]; self._imgs={}; self._page=0
        self._modo=gg(cfg,"modo") if cfg else "vertical"
        self._zoom=gg(cfg,"zoom") if cfg else "fit_width"
        self._loading=False; self._keep=[]
        self._build()
        self.bind("<Left>",   lambda e:self._prev())
        self.bind("<Right>",  lambda e:self._next())
        self.bind("<Escape>", lambda e:self.destroy())
        self.bind("<v>",      lambda e:self._set_modo("vertical"))
        self.bind("<h>",      lambda e:self._set_modo("horizontal"))
        self.bind("<f>",      lambda e:self.attributes("-fullscreen",not self.attributes("-fullscreen")))
        self.bind("<plus>",   lambda e:self._zoom_in())
        self.bind("<minus>",  lambda e:self._zoom_out())
        self.focus_set()
        self.after(80, self._cargar)

    def _build(self):
        tb=tk.Frame(self,bg=BG2,pady=3); tb.pack(fill="x")
        self._b(tb,"◀",self._prev)
        self._b(tb,"▶",self._next)
        self.pg_lbl=tk.Label(tb,text="Cargando...",bg=BG2,fg=TEXT,font=FTB)
        self.pg_lbl.pack(side="left",padx=8)
        self._b(tb,"↕V",lambda:self._set_modo("vertical"),  side="left",bg=BG3 if self._modo!="vertical"  else CYAN,fg="#000" if self._modo=="vertical"  else TEXT)
        self._b(tb,"↔H",lambda:self._set_modo("horizontal"),side="left",bg=BG3 if self._modo!="horizontal" else CYAN,fg="#000" if self._modo=="horizontal" else TEXT)
        ZOOMS=["fit_width","fit_page","75","100","150","200"]
        self.zoom_v=tk.StringVar(value=self._zoom)
        zm=tk.OptionMenu(tb,self.zoom_v,*ZOOMS,command=self._on_zoom)
        zm.configure(bg=BG3,fg=TEXT,activebackground=HOVER,activeforeground=TEXT,
                     relief="flat",highlightthickness=0,font=FTS)
        zm["menu"].configure(bg=BG3,fg=TEXT,activebackground=SEL)
        zm.pack(side="left",padx=4)
        if self.dl_fn:
            self._b(tb,"⬇ CBZ",self._descargar,side="right",bg=GREEN,fg="#000")
        self._b(tb,"✕",self.destroy,side="right",bg=RED,fg="#fff")

        wrap=tk.Frame(self,bg="#000"); wrap.pack(fill="both",expand=True)
        self.canvas=tk.Canvas(wrap,bg="#000",highlightthickness=0)
        vsb=tk.Scrollbar(wrap,orient="vertical",command=self.canvas.yview)
        hsb=tk.Scrollbar(wrap,orient="horizontal",command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=vsb.set,xscrollcommand=hsb.set)
        hsb.pack(side="bottom",fill="x"); vsb.pack(side="right",fill="y")
        self.canvas.pack(fill="both",expand=True)
        self.canvas.bind("<MouseWheel>",self._wheel)
        self.canvas.bind("<Configure>", lambda e:self._render())
        self.canvas.bind("<Button-1>",  lambda e:self.focus_set())
        self.st=tk.Label(self,text="",bg=BG,fg=MUTED,font=FTS); self.st.pack()

    def _b(self,p,text,cmd,side="left",bg=BG3,fg=TEXT):
        b=tk.Label(p,text=text,bg=bg,fg=fg,font=FTB,padx=9,pady=4,cursor="hand2",relief="flat")
        b.pack(side=side,padx=2)
        b.bind("<Button-1>",lambda e:cmd())
        b.bind("<Enter>",   lambda e:b.configure(bg=lighten(bg)))
        b.bind("<Leave>",   lambda e:b.configure(bg=bg))

    def _cargar(self):
        self.st.config(text="Cargando páginas...",fg=CYAN)
        def _bg():
            try:
                urls=self.get_pags(self.cap)
                self.after(0,self._on_urls,urls)
            except Exception as ex:
                self.after(0,lambda:self.st.config(text=f"Error: {ex}",fg=RED))
        threading.Thread(target=_bg,daemon=True).start()

    def _on_urls(self,urls):
        if not urls:
            self.st.config(text="No se encontraron páginas.",fg=RED); return
        self.urls=urls; self._page=0
        self.st.config(text=""); self._render()

    def _render(self):
        if not self.urls or self._loading: return
        self._loading=True; page=self._page; modo=self._modo
        total=len(self.urls); self.pg_lbl.config(text=f"{page+1} / {total}")
        def _bg():
            try:
                if modo=="vertical":
                    pre=int(gg(self.cfg,"precarga")) if self.cfg else 3
                    idxs=list(range(max(0,page-1),min(total,page+pre+1)))
                    photos=[(i,self._get_photo(i)) for i in idxs]
                    photos=[(i,ph) for i,ph in photos if ph]
                    self.after(0,self._draw_v,photos,page)
                else:
                    ph=self._get_photo(page)
                    self.after(0,self._draw_h,ph)
            finally: self._loading=False
        threading.Thread(target=_bg,daemon=True).start()

    def _get_photo(self,idx):
        if idx in self._imgs: return self._imgs[idx]
        if idx>=len(self.urls): return None
        url=self.urls[idx]
        try:
            fid=self.cap.get("fuente_id","")
            use_cf = gf(self.cfg,fid,"cloudflare")=="1" if self.cfg else False
            s=make_session(use_cf); s.headers.update({"Referer":url})
            r=s.get(url,timeout=20)
            if r.status_code!=200: return None
            img=Image.open(io.BytesIO(r.content)).convert("RGB")
            cw=max(self.canvas.winfo_width(),400)
            z=self._zoom
            if z=="fit_width":
                rat=cw/img.width; img=img.resize((cw,int(img.height*rat)),Image.LANCZOS)
            elif z=="fit_page":
                ch=max(self.canvas.winfo_height(),400)
                rat=min(cw/img.width,ch/img.height)
                img=img.resize((int(img.width*rat),int(img.height*rat)),Image.LANCZOS)
            elif z.isdigit():
                rat=int(z)/100
                img=img.resize((int(img.width*rat),int(img.height*rat)),Image.LANCZOS)
            ph=ImageTk.PhotoImage(img); self._imgs[idx]=ph; return ph
        except Exception as ex:
            print(f"img {idx}: {ex}"); return None

    def _draw_h(self,ph):
        self.canvas.delete("all"); self._keep=[]
        if not ph:
            self.canvas.create_text(200,200,text="Error",fill=MUTED,font=FT); return
        cw,ch=max(self.canvas.winfo_width(),400),max(self.canvas.winfo_height(),400)
        self.canvas.create_image(cw//2,ch//2,anchor="center",image=ph)
        self.canvas.config(scrollregion=(0,0,max(cw,ph.width()),max(ch,ph.height())))
        self._keep.append(ph)

    def _draw_v(self,photos,cur):
        self.canvas.delete("all"); self._keep=[]; cw=max(self.canvas.winfo_width(),400)
        y=8; fy=None
        for i,ph in photos:
            if i==cur and fy is None: fy=y
            self.canvas.create_image(max(cw//2,ph.width()//2),y,anchor="n",image=ph)
            y+=ph.height()+6; self._keep.append(ph)
        tw=max(cw,max((ph.width() for _,ph in photos),default=cw))
        self.canvas.config(scrollregion=(0,0,tw,y+10))
        if fy: self.canvas.yview_moveto(fy/max(y,1))

    def _prev(self):
        if self._modo=="horizontal": self._go(self._page-1)
        else: self.canvas.yview_scroll(-3,"units")
    def _next(self):
        if self._modo=="horizontal": self._go(self._page+1)
        else: self.canvas.yview_scroll(3,"units")
    def _go(self,p):
        p=max(0,min(p,len(self.urls)-1)); self._page=p; self._imgs.clear(); self._render()
    def _wheel(self,e):
        d=-1 if e.delta>0 else 1
        if self._modo=="vertical": self.canvas.yview_scroll(d*3,"units")
        else: self._go(self._page+d)
    def _set_modo(self,m):
        self._modo=m; self._imgs.clear(); self._render()
    def _on_zoom(self,v):
        self._zoom=v; self._imgs.clear(); self._render()
    def _zoom_in(self):
        Z=["fit_width","fit_page","75","100","150","200"]
        try: i=Z.index(self._zoom); self._on_zoom(Z[min(i+1,len(Z)-1)])
        except: self._on_zoom("150")
    def _zoom_out(self):
        Z=["fit_width","fit_page","75","100","150","200"]
        try: i=Z.index(self._zoom); self._on_zoom(Z[max(i-1,0)])
        except: self._on_zoom("75")
    def _descargar(self):
        if not self.urls: return
        self.st.config(text="Descargando CBZ...",fg=CYAN)
        def _bg():
            try:
                path=self.dl_fn(self.titulo,self.cap,self.urls)
                self.after(0,lambda:self.st.config(text=f"✓ {Path(path).name}",fg=GREEN))
            except Exception as ex:
                self.after(0,lambda:self.st.config(text=f"Error: {ex}",fg=RED))
        threading.Thread(target=_bg,daemon=True).start()

# ══════════════════════════════════════════════════════════
#  PANEL CAPÍTULOS
# ══════════════════════════════════════════════════════════
class CapitulosPanel(tk.Toplevel):
    def __init__(self,parent,manga,cfg):
        super().__init__(parent)
        self.title(f"Capítulos — {manga.get('title','')[:50]}")
        self.geometry("620x580"); self.configure(bg=BG)
        self.manga=manga; self.cfg=cfg; self.caps=[]
        self._build(); self.after(80,self._cargar)

    def _build(self):
        hdr=tk.Frame(self,bg=BG2,pady=8,padx=14); hdr.pack(fill="x")
        # Badge fuente
        br=tk.Frame(hdr,bg=BG2); br.pack(anchor="w")
        fuente_badge(br, self.manga.get("fuente_id",""), self.cfg)
        tk.Label(hdr,text=self.manga.get("title","")[:65],
                 bg=BG2,fg=TEXT,font=FTB,wraplength=560).pack(anchor="w")
        if self.manga.get("autor"):
            tk.Label(hdr,text=f"✍ {self.manga['autor']}",
                     bg=BG2,fg=MUTED,font=FTS).pack(anchor="w")
        if self.manga.get("desc"):
            tk.Label(hdr,text=self.manga["desc"][:180],
                     bg=BG2,fg=MUTED,font=FTS,wraplength=560,justify="left").pack(anchor="w",pady=(2,0))

        sf=tk.Frame(self,bg=BG,pady=3,padx=12); sf.pack(fill="x")
        self.st=tk.Label(sf,text="Cargando...",bg=BG,fg=MUTED,font=FTS); self.st.pack(side="left")
        self.sp=tk.Label(sf,text="",bg=BG,fg=CYAN,font=FTS); self.sp.pack(side="left",padx=4)
        # Búsqueda de capítulo
        tk.Label(sf,text="Cap:",bg=BG,fg=MUTED,font=FTS).pack(side="right",padx=(8,3))
        self.fq=tk.StringVar()
        self.fq.trace_add("write",lambda *a:self._filtrar())
        tk.Entry(sf,textvariable=self.fq,bg=BG3,fg=TEXT,insertbackground=TEXT,
                 font=FTM,relief="flat",highlightthickness=1,
                 highlightcolor=CYAN,highlightbackground=BORDER,width=12
                 ).pack(side="right",ipady=3)

        tk.Frame(self,bg=BORDER,height=1).pack(fill="x")
        wrap=tk.Frame(self,bg=BG); wrap.pack(fill="both",expand=True)
        self.lf=scrollable(wrap)

        ft=tk.Frame(self,bg=BG2,pady=6,padx=12); ft.pack(fill="x")
        Btn(ft,"⬇ Descargar todos",self._dl_todos,bg=AMBER,fg="#000",font=FTS,py=4).pack(side="right")

    def _cargar(self):
        self._spin_go()
        fid=self.manga.get("fuente_id","")
        src=FUENTES.get(fid)
        def _bg():
            caps=src.capitulos(self.manga,self.cfg) if src else []
            self.after(0,self._on_caps,caps)
        threading.Thread(target=_bg,daemon=True).start()

    def _on_caps(self, caps):
        self._spin_stop()
        self.caps = caps
        if caps:
            self.st.config(text=f"{len(caps)} capítulos", fg=MUTED)
        else:
            fid = self.manga.get("fuente_id","")
            self.st.config(
                text=f"Sin capítulos — intenta activar bypass Cloudflare en ⚙ Config",
                fg=AMBER)
        self._filtrar()

    def _filtrar(self):
        q = self.fq.get().strip().lower()
        data = [c for c in self.caps
                if not q or q in c.get("num","").lower()
                or q in c.get("title","").lower()]
        self._render(data)

    def _render(self, data):
        for w in self.lf.winfo_children(): w.destroy()
        if not data:
            fr = tk.Frame(self.lf, bg=BG); fr.pack(expand=True, fill="both", pady=30)
            tk.Label(fr, text="Sin capítulos encontrados.", bg=BG, fg=MUTED,
                     font=FTB).pack()
            tk.Label(fr,
                text="Posibles causas:\n"
                     "• El sitio usa Cloudflare → activa bypass en ⚙ Config\n"
                     "• La URL del manga no cargó correctamente\n"
                     "• El manga no tiene capítulos en español en esta fuente",
                bg=BG, fg=MUTED, font=FTS, justify="left").pack(pady=(6,0))
            # Botón reintentar
            Btn(fr, "↺ Reintentar", BG3, CYAN, self._cargar,
                font=FTS, py=4).pack(pady=(10,0))
            return

        for cap in data:
            row = tk.Frame(self.lf, bg=BG2, pady=7, cursor="hand2")
            row.pack(fill="x", padx=10, pady=(2,0))
            sb  = tk.Frame(row, bg=BG2, width=3); sb.pack(side="left", fill="y")
            inn = tk.Frame(row, bg=BG2, padx=10); inn.pack(side="left", fill="both", expand=True)

            num   = cap.get("num","") or cap.get("title","?")
            fecha = cap.get("fecha","")
            pages = cap.get("pages",0)

            tk.Label(inn, text=num[:70], bg=BG2, fg=TEXT,
                     font=FTB, anchor="w").pack(fill="x")
            meta = "   ".join(filter(None,[fecha,
                f"{pages} págs." if pages else ""]))
            if meta:
                tk.Label(inn, text=meta, bg=BG2, fg=MUTED,
                         font=FTS, anchor="w").pack(fill="x")

            br = tk.Frame(inn, bg=BG2); br.pack(anchor="w", pady=(4,0))
            Btn(br,"▶ Leer", BG3,CYAN,  lambda c=cap:self._leer(c),  font=FTS,py=3,px=8).pack(side="left",padx=(0,5))
            Btn(br,"⬇ CBZ",  BG3,AMBER, lambda c=cap:self._dl_uno(c),font=FTS,py=3,px=8).pack(side="left")

            # Clic en fila = leer
            for w in [row, inn, sb]:
                w.bind("<Button-1>", lambda e,c=cap: self._leer(c))
                w.bind("<Enter>",    lambda e,r=row,i=inn,s=sb: (
                    r.configure(bg=HOVER), i.configure(bg=HOVER), s.configure(bg=CYAN)))
                w.bind("<Leave>",    lambda e,r=row,i=inn,s=sb: (
                    r.configure(bg=BG2),   i.configure(bg=BG2),   s.configure(bg=BG2)))

    def _paginas(self,cap):
        fid=self.manga.get("fuente_id","")
        src=FUENTES.get(fid)
        return src.paginas(cap,self.cfg) if src else []

    def _leer(self,cap):
        OnlineReader(self,self.manga.get("title",""),cap,
                     get_pags_fn=self._paginas,
                     dl_fn=self._guardar_cbz,cfg=self.cfg)

    def _dl_uno(self,cap):
        self.st.config(text=f"Descargando {cap.get('num','')}...",fg=AMBER)
        def _bg():
            try:
                urls=self._paginas(cap)
                if not urls: raise RuntimeError("Sin páginas")
                p=self._guardar_cbz(self.manga.get("title",""),cap,urls)
                self.after(0,lambda:self.st.config(text=f"✓ {Path(p).name}",fg=GREEN))
            except Exception as ex:
                self.after(0,lambda:self.st.config(text=f"Error: {ex}",fg=RED))
        threading.Thread(target=_bg,daemon=True).start()

    def _dl_todos(self):
        if not self.caps: return
        if not messagebox.askyesno("Descargar todo",
            f"¿Descargar {len(self.caps)} capítulos?\nPuede tardar varios minutos."): return
        self.st.config(text="Descargando...",fg=AMBER)
        def _bg():
            ok=fail=0
            for cap in self.caps:
                try:
                    urls=self._paginas(cap)
                    if urls: self._guardar_cbz(self.manga.get("title",""),cap,urls); ok+=1
                    else: fail+=1
                except: fail+=1
            msg=f"✓ {ok} descargados"+(f", {fail} fallidos" if fail else "")
            self.after(0,lambda:self.st.config(text=msg,fg=GREEN if not fail else AMBER))
        threading.Thread(target=_bg,daemon=True).start()

    def _guardar_cbz(self,titulo,cap,urls):
        safe="".join(c for c in titulo if c.isalnum() or c in " _-")[:40].strip()
        num=str(cap.get("num","?")).replace("/","-")
        out=Path(gg(self.cfg,"descarga_dir"))/safe; out.mkdir(parents=True,exist_ok=True)
        cbz=out/f"Cap_{num}.cbz"
        fid=cap.get("fuente_id","")
        use_cf=gf(self.cfg,fid,"cloudflare")=="1"
        s=make_session(use_cf); s.headers.update({"Referer":urls[0] if urls else ""})
        with zipfile.ZipFile(cbz,"w",zipfile.ZIP_DEFLATED) as zf:
            for i,url in enumerate(urls):
                try:
                    r=s.get(url,timeout=20)
                    if r.status_code==200:
                        ext=url.split("?")[0].split(".")[-1] or "jpg"
                        zf.writestr(f"{i+1:03d}.{ext}",r.content)
                except: pass
        return str(cbz)

    def _spin_go(self):
        self._sa=True; self._si=0; self._tick()
    def _tick(self):
        if self._sa:
            self.sp.config(text=SPINNER[self._si%len(SPINNER)]); self._si+=1
            self.after(80,self._tick)
    def _spin_stop(self): self._sa=False; self.sp.config(text="")

# ══════════════════════════════════════════════════════════
#  PANEL CONFIGURACIÓN TIPO ANIYOMI
# ══════════════════════════════════════════════════════════
class ConfigPanel(tk.Toplevel):
    def __init__(self,parent,cfg,on_save):
        super().__init__(parent)
        self.title("⚙ Configuración — MangaLite Online")
        self.geometry("700x620"); self.configure(bg=BG)
        self.cfg=cfg; self.on_save=on_save; self._v={}
        self._build()

    def _build(self):
        # Tabs
        tb=tk.Frame(self,bg=BG2,pady=6,padx=12); tb.pack(fill="x")
        tk.Label(tb,text="⚙  Configuración",bg=BG2,fg=TEXT,font=FTT).pack(side="left")
        Btn(tb,"💾 Guardar",GREEN,"#000",self._save,font=FTB,py=4).pack(side="right")

        tabs=tk.Frame(self,bg=BG); tabs.pack(fill="x",padx=0)
        self._tab_frames={}; self._tab_btns={}
        for name in ["Fuentes","Lector","Red","Descargas","Filtros"]:
            fr=tk.Frame(self,bg=BG); self._tab_frames[name]=fr
            b=tk.Label(tabs,text=name,bg=BG3,fg=MUTED,font=FTB,
                       padx=14,pady=6,cursor="hand2",relief="flat")
            b.pack(side="left")
            b.bind("<Button-1>",lambda e,n=name:self._show_tab(n))
            self._tab_btns[name]=b
        tk.Frame(self,bg=BORDER,height=1).pack(fill="x")

        self._build_fuentes()
        self._build_lector()
        self._build_red()
        self._build_descargas()
        self._build_filtros()
        self._show_tab("Fuentes")

    def _show_tab(self,name):
        for n,fr in self._tab_frames.items():
            fr.pack_forget()
            self._tab_btns[n].configure(bg=BG3,fg=MUTED)
        self._tab_frames[name].pack(fill="both",expand=True)
        self._tab_btns[name].configure(bg=CYAN,fg="#000")

    def _row(self,pad,label,key,kind="entry",opts=None,section="global",fid=None):
        fr=tk.Frame(pad,bg=BG,pady=4); fr.pack(fill="x")
        tk.Label(fr,text=label,bg=BG,fg=TEXT,font=FT,width=26,anchor="w").pack(side="left")
        val=(gg(self.cfg,key) if section=="global" else gf(self.cfg,fid,key))
        vkey=f"{section}_{fid}_{key}" if fid else f"global_{key}"
        if kind=="entry":
            v=tk.StringVar(value=val)
            tk.Entry(fr,textvariable=v,bg=BG3,fg=TEXT,insertbackground=TEXT,
                     font=FTM,relief="flat",highlightthickness=1,
                     highlightcolor=CYAN,highlightbackground=BORDER,width=32
                     ).pack(side="left",ipady=4)
            self._v[vkey]=(section,key,fid,v)
        elif kind=="check":
            v=tk.IntVar(value=int(val or 0))
            tk.Checkbutton(fr,variable=v,bg=BG,activebackground=BG,
                           selectcolor=BG3,fg=CYAN,activeforeground=CYAN).pack(side="left")
            self._v[vkey]=(section,key,fid,v)
        elif kind=="combo":
            v=tk.StringVar(value=val)
            om=tk.OptionMenu(fr,v,*opts)
            om.configure(bg=BG3,fg=TEXT,activebackground=HOVER,
                         activeforeground=TEXT,relief="flat",highlightthickness=0,font=FTS)
            om["menu"].configure(bg=BG3,fg=TEXT,activebackground=SEL)
            om.pack(side="left")
            self._v[vkey]=(section,key,fid,v)

    def _sec(self,pad,txt):
        tk.Frame(pad,bg=BORDER,height=1).pack(fill="x",pady=(12,4))
        tk.Label(pad,text=txt,bg=BG,fg=CYAN,font=("Segoe UI",9,"bold")).pack(anchor="w")

    def _build_fuentes(self):
        pad=tk.Frame(self._tab_frames["Fuentes"],bg=BG,padx=20,pady=10)
        pad.pack(fill="both",expand=True)
        tk.Label(pad,text="Activa o desactiva fuentes y configura el bypass de Cloudflare.",
                 bg=BG,fg=MUTED,font=FTS).pack(anchor="w",pady=(0,8))
        for fid, fd in FUENTE_DEFAULTS.items():
            self._sec(pad, fd["nombre"])
            fr2=tk.Frame(pad,bg=BG); fr2.pack(fill="x")
            color=gf(self.cfg,fid,"color")
            tk.Frame(fr2,bg=color,width=8,height=30).pack(side="left",padx=(0,8))
            col=tk.Frame(fr2,bg=BG); col.pack(side="left",fill="both",expand=True)
            # Activa
            f1=tk.Frame(col,bg=BG); f1.pack(fill="x",pady=2)
            tk.Label(f1,text="Fuente activa",bg=BG,fg=TEXT,font=FT,width=20,anchor="w").pack(side="left")
            va=tk.IntVar(value=int(gf(self.cfg,fid,"activa") or 0))
            tk.Checkbutton(f1,variable=va,bg=BG,activebackground=BG,
                           selectcolor=BG3,fg=CYAN,activeforeground=CYAN).pack(side="left")
            self._v[f"fuente_{fid}_activa"]=(f"fuente_{fid}","activa",fid,va)
            # Cloudflare bypass
            f2=tk.Frame(col,bg=BG); f2.pack(fill="x",pady=2)
            tk.Label(f2,text="Usar bypass Cloudflare",bg=BG,fg=TEXT,font=FT,width=20,anchor="w").pack(side="left")
            vc=tk.IntVar(value=int(gf(self.cfg,fid,"cloudflare") or 0))
            tk.Checkbutton(f2,variable=vc,bg=BG,activebackground=BG,
                           selectcolor=BG3,fg=AMBER,activeforeground=AMBER).pack(side="left")
            tk.Label(f2,text="(requiere cloudscraper)" if not CS_OK else "✓ disponible",
                     bg=BG,fg=MUTED if not CS_OK else GREEN,font=FTS).pack(side="left",padx=6)
            self._v[f"fuente_{fid}_cloudflare"]=(f"fuente_{fid}","cloudflare",fid,vc)

        tk.Frame(pad,bg=BORDER,height=1).pack(fill="x",pady=(14,4))
        tk.Label(pad,
            text="Si Cloudflare bloquea una fuente, activa el bypass para esa fuente.\n"
                 "Instala cloudscraper si no está: pip install cloudscraper",
            bg=BG,fg=MUTED,font=FTS,justify="left").pack(anchor="w")

    def _build_lector(self):
        pad=tk.Frame(self._tab_frames["Lector"],bg=BG,padx=20,pady=10)
        pad.pack(fill="both",expand=True)
        self._sec(pad,"Modo de lectura")
        self._row(pad,"Modo predeterminado","modo","combo",["vertical","horizontal"])
        self._row(pad,"Zoom predeterminado","zoom","combo",
                  ["fit_width","fit_page","75","100","150","200"])
        self._row(pad,"Páginas a precargar","precarga")
        self._sec(pad,"Idioma")
        self._row(pad,"Idioma de capítulos","idioma","combo",["es","es-la","en"])

    def _build_red(self):
        pad=tk.Frame(self._tab_frames["Red"],bg=BG,padx=20,pady=10)
        pad.pack(fill="both",expand=True)
        self._sec(pad,"Conexión")
        self._row(pad,"Timeout (segundos)","timeout")
        self._row(pad,"Proxy (ej: socks5://127.0.0.1:1080)","proxy")
        self._sec(pad,"Búsqueda global")
        self._row(pad,"Buscar en todas las fuentes","busqueda_todas","check")
        tk.Label(pad,
            text="Al activar 'Buscar en todas', la búsqueda lanza peticiones\n"
                 "a todas las fuentes activas simultáneamente.",
            bg=BG,fg=MUTED,font=FTS,justify="left").pack(anchor="w",pady=(8,0))

    def _build_descargas(self):
        pad=tk.Frame(self._tab_frames["Descargas"],bg=BG,padx=20,pady=10)
        pad.pack(fill="both",expand=True)
        self._sec(pad,"Carpeta de descargas")
        fr=tk.Frame(pad,bg=BG,pady=4); fr.pack(fill="x")
        tk.Label(fr,text="Carpeta",bg=BG,fg=TEXT,font=FT,width=26,anchor="w").pack(side="left")
        v=tk.StringVar(value=gg(self.cfg,"descarga_dir"))
        tk.Entry(fr,textvariable=v,bg=BG3,fg=TEXT,insertbackground=TEXT,
                 font=FTM,relief="flat",highlightthickness=1,
                 highlightcolor=CYAN,highlightbackground=BORDER,width=32
                 ).pack(side="left",ipady=4)
        Btn(fr,"...",BG3,TEXT,lambda:v.set(filedialog.askdirectory() or v.get()),
            font=FTS,py=3,px=7).pack(side="left",padx=(4,0))
        self._v["global_descarga_dir"]=("global","descarga_dir",None,v)
        tk.Label(pad,
            text="Los capítulos se descargan como archivos .cbz\n"
                 "organizados en subcarpetas por título.",
            bg=BG,fg=MUTED,font=FTS,justify="left").pack(anchor="w",pady=(10,0))

    def _build_filtros(self):
        pad=tk.Frame(self._tab_frames["Filtros"],bg=BG,padx=20,pady=10)
        pad.pack(fill="both",expand=True)
        self._sec(pad,"Contenido")
        self._row(pad,"Filtrar contenido adulto (+18)","filtro_adultos","check")
        tk.Label(pad,
            text="Al activar el filtro, se excluyen resultados marcados como +18\n"
                 "de las fuentes que soporten esta opción (MangaDex).",
            bg=BG,fg=MUTED,font=FTS,justify="left").pack(anchor="w",pady=(8,0))

    def _save(self):
        for vkey,(section,key,fid,v) in self._v.items():
            val=str(v.get())
            if section=="global":
                self.cfg["global"][key]=val
            else:
                sec=f"fuente_{fid}"
                if sec not in self.cfg: self.cfg[sec]={}
                self.cfg[sec][key]=val
        save_cfg(self.cfg)
        messagebox.showinfo("Guardado","Configuración guardada. ✓",parent=self)
        self.on_save()
        self.destroy()

# ══════════════════════════════════════════════════════════
#  PANEL PRINCIPAL
# ══════════════════════════════════════════════════════════
class OnlinePanel(tk.Frame):
    def __init__(self,parent,cfg=None,descarga_dir=None,**kw):
        super().__init__(parent,bg=BG,**kw)
        self.cfg=cfg or load_cfg()
        if descarga_dir: self.cfg["global"]["descarga_dir"]=descarga_dir
        self._sa=False; self._si=0; self._resultados=[]
        self._build()

    def _build(self):
        # Header
        hdr=tk.Frame(self,bg=BG2,pady=7,padx=12); hdr.pack(fill="x")
        badge=tk.Frame(hdr,bg=CYAN,width=34,height=34)
        badge.pack(side="left"); badge.pack_propagate(False)
        tk.Label(badge,text="🌐",bg=CYAN,font=("Segoe UI",14)
                 ).place(relx=.5,rely=.5,anchor="center")
        tf=tk.Frame(hdr,bg=BG2); tf.pack(side="left",padx=10)
        tk.Label(tf,text="MangaLite Online",bg=BG2,fg=TEXT,font=FTT).pack(anchor="w")
        tk.Label(tf,text="MangaDex · LeerCapitulo · InManga · LectorTMOo · LectorTMO.vip · LectorMangass",
                 bg=BG2,fg=MUTED,font=FTS).pack(anchor="w")
        Btn(hdr,"⚙",BG3,MUTED,self._config,font=FTS,px=9,py=5).pack(side="right")

        # Barra búsqueda
        sf=tk.Frame(self,bg=BG,pady=6,padx=14); sf.pack(fill="x")
        self.q_v=tk.StringVar()
        qe=tk.Entry(sf,textvariable=self.q_v,bg=BG3,fg=TEXT,
                    insertbackground=TEXT,font=FT,relief="flat",
                    highlightthickness=1,highlightcolor=CYAN,highlightbackground=BORDER)
        qe.pack(side="left",fill="x",expand=True,ipady=6)
        qe.bind("<Return>",lambda e:self._buscar())
        qe.focus_set()
        Btn(sf,"Buscar",CYAN,"#000",self._buscar,px=14).pack(side="left",padx=(7,0))

        # Selector de fuente — LeerCapitulo primero
        sf2=tk.Frame(self,bg=BG,pady=2,padx=14); sf2.pack(fill="x")
        tk.Label(sf2,text="Fuente:",bg=BG,fg=MUTED,font=FTS).pack(side="left",padx=(0,4))
        self.fuente_v=tk.StringVar(value="LeerCapitulo")  # prioridad LeerCapitulo
        # Orden: LeerCapitulo primero, luego el resto
        fids_ordenados = ["leercapitulo"] + [f for f in FUENTES if f != "leercapitulo"]
        opts=["Todas"]+[gf(self.cfg,fid,"nombre") for fid in fids_ordenados
                        if gf(self.cfg,fid,"activa")=="1"]
        om=tk.OptionMenu(sf2,self.fuente_v,*opts)
        om.configure(bg=BG3,fg=TEXT,activebackground=HOVER,activeforeground=TEXT,
                     relief="flat",highlightthickness=0,font=FTS)
        om["menu"].configure(bg=BG3,fg=TEXT,activebackground=SEL)
        om.pack(side="left")

        # Status
        self.st=tk.Label(sf2,text="Busca manga o manhwa en español",
                         bg=BG,fg=MUTED,font=FTS); self.st.pack(side="left",padx=12)
        self.sp=tk.Label(sf2,text="",bg=BG,fg=CYAN,font=FTS); self.sp.pack(side="left",padx=4)

        # Badges de fuentes activas
        bf=tk.Frame(self,bg=BG,padx=14,pady=3); bf.pack(fill="x")
        for fid in FUENTES:
            if gf(self.cfg,fid,"activa")=="1":
                fuente_badge(bf, fid, self.cfg)

        tk.Frame(self,bg=BORDER,height=1).pack(fill="x")

        # Lista
        wrap=tk.Frame(self,bg=BG); wrap.pack(fill="both",expand=True)
        self.lf=scrollable(wrap)

    def _buscar(self):
        q=self.q_v.get().strip()
        if not q: return
        for w in self.lf.winfo_children(): w.destroy()
        self._resultados=[]; self._lc_done=False
        fuente_sel=self.fuente_v.get()

        # Determinar qué fuentes buscar — LeerCapitulo siempre primero
        if fuente_sel=="Todas":
            fids=(["leercapitulo"] if gf(self.cfg,"leercapitulo","activa")=="1" else []) + \
                 [fid for fid in FUENTES if fid!="leercapitulo" and gf(self.cfg,fid,"activa")=="1"]
        else:
            fids=[fid for fid in FUENTES
                  if gf(self.cfg,fid,"nombre")==fuente_sel and gf(self.cfg,fid,"activa")=="1"]

        if not fids:
            self.st.config(text="No hay fuentes activas.",fg=RED); return

        self.st.config(text=f"Buscando '{q}'...",fg=MUTED)
        self._spin_go()
        self._pending=len(fids)

        for fid in fids:
            def _bg(fid=fid):
                try:
                    results=FUENTES[fid].buscar(q,self.cfg)
                    self.after(0,self._on_results,results,fid)
                except Exception as ex:
                    print(f"{fid} error: {ex}")
                    self.after(0,self._on_results,[],fid)
            threading.Thread(target=_bg,daemon=True).start()

    def _on_results(self,results,fid):
        self._pending-=1
        # LeerCapitulo: insertar al principio de la lista
        if fid=="leercapitulo":
            for m in results:
                self._card(m, prepend=True)
            self._resultados = results + self._resultados
        else:
            for m in results:
                self._card(m)
            self._resultados.extend(results)

        if self._pending<=0:
            self._spin_stop()
            total=len(self._resultados)
            if total:
                self.st.config(text=f"{total} resultado(s)",fg=GREEN)
            else:
                self.st.config(
                    text="Sin resultados — activa bypass Cloudflare en ⚙ o prueba otra fuente",
                    fg=AMBER)

    def _card(self, m, prepend=False):
        row=tk.Frame(self.lf,bg=BG2,pady=8,cursor="hand2")
        if prepend:
            row.pack(fill="x",padx=10,pady=(3,0),before=self.lf.winfo_children()[0]
                     if self.lf.winfo_children() else None)
        else:
            row.pack(fill="x",padx=10,pady=(3,0))
        sb=tk.Frame(row,bg=BG2,width=4); sb.pack(side="left",fill="y")

        # Portada
        cv=tk.Canvas(row,bg=BG3,width=68,height=96,highlightthickness=0)
        cv.pack(side="left",padx=(10,10),pady=2)
        cv.create_text(34,48,text="📖",fill=MUTED,font=("Segoe UI",16))

        inn=tk.Frame(row,bg=BG2); inn.pack(side="left",fill="both",expand=True,padx=(0,8))

        # Badge fuente
        br=tk.Frame(inn,bg=BG2); br.pack(anchor="w",pady=(0,2))
        fuente_badge(br, m.get("fuente_id",""), self.cfg)
        if m.get("tipo"):
            tk.Label(br,text=m["tipo"].upper(),bg=BG3,fg=MUTED,
                     font=("Segoe UI",7),padx=4,pady=1).pack(side="left",padx=(0,4))
        if m.get("estado"):
            tk.Label(br,text=m["estado"],bg=BG3,fg=MUTED,
                     font=("Segoe UI",7),padx=4,pady=1).pack(side="left")

        tk.Label(inn,text=m.get("title","")[:70],bg=BG2,fg=TEXT,
                 font=FTB,anchor="w",wraplength=440,justify="left").pack(fill="x")
        if m.get("autor"):
            tk.Label(inn,text=f"✍ {m['autor']}",bg=BG2,fg=MUTED,font=FTS,anchor="w").pack(fill="x")
        if m.get("tags"):
            tk.Label(inn,text=", ".join(m["tags"][:5]),
                     bg=BG2,fg=MUTED,font=FTS,anchor="w").pack(fill="x")
        if m.get("desc"):
            tk.Label(inn,text=m["desc"][:150],bg=BG2,fg=MUTED,font=FTS,
                     anchor="w",wraplength=440,justify="left").pack(fill="x")

        Btn(inn,"📋 Ver capítulos",BG3,CYAN,
            lambda m_=m:CapitulosPanel(self.winfo_toplevel(),m_,self.cfg),
            font=FTS,py=3,px=10).pack(anchor="w",pady=(5,0))

        # Color borde izq según fuente
        color=gf(self.cfg,m.get("fuente_id",""),"color") or CYAN
        ws=[row,inn,sb,cv]
        def hover(on,c=color,ws_=ws,s=sb):
            col=HOVER if on else BG2
            for w in ws_:
                try: w.configure(bg=col)
                except: pass
            s.configure(bg=c if on else BG2)
        for w in ws:
            w.bind("<Enter>",lambda e,h=hover:h(True))
            w.bind("<Leave>",lambda e,h=hover:h(False))

        # Portada async
        if m.get("cover_url") and PIL_OK:
            threading.Thread(target=self._load_cover,
                             args=(m["cover_url"],cv,m.get("fuente_id","")),daemon=True).start()

    def _load_cover(self,url,cv,fid):
        try:
            use_cf=gf(self.cfg,fid,"cloudflare")=="1"
            s=make_session(use_cf)
            r=s.get(url,timeout=10)
            if r.status_code!=200: return
            img=Image.open(io.BytesIO(r.content)).convert("RGB").resize((68,96),Image.LANCZOS)
            ph=ImageTk.PhotoImage(img); cv._img=ph
            cv.delete("all"); cv.create_image(0,0,anchor="nw",image=ph)
        except: pass

    def _config(self):
        ConfigPanel(self.winfo_toplevel(),self.cfg,on_save=lambda:None)

    def _spin_go(self):
        self._sa=True; self._si=0; self._tick()
    def _tick(self):
        if self._sa:
            self.sp.config(text=SPINNER[self._si%len(SPINNER)]); self._si+=1
            self.after(80,self._tick)
    def _spin_stop(self): self._sa=False; self.sp.config(text="")

# ══════════════════════════════════════════════════════════
if __name__ == "__main__":
    root=tk.Tk()
    root.title("MangaLite Online"); root.geometry("920x660"); root.configure(bg=BG)
    OnlinePanel(root).pack(fill="both",expand=True)
    root.mainloop()
