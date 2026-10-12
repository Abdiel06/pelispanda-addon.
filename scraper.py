import os, re, logging, urllib.request, html, json

logging.basicConfig(level=logging.DEBUG, format="[%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

def fetch_rendered_html(url: str, is_search: bool = False) -> str:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError("playwright no instalado")

    log.info("Abriendo browser headless ultrarrápido...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        def intercept_route(route):
            if route.request.resource_type in ["image", "stylesheet", "font", "media"]:
                route.abort()
            else:
                route.continue_()

        page.route("**/*", intercept_route)
        
        log.info("Navegando a %s ...", url)
        
        # Si es búsqueda, esperamos a que la red se calme (networkidle)
        wait_state = "networkidle" if is_search else "domcontentloaded"
        page.goto(url, wait_until=wait_state, timeout=30000)
        
        if is_search:
            # Damos 2 segundos extras para que React dibuje los resultados
            page.wait_for_timeout(2000)
        else:
            try:
                page.wait_for_selector(".accordion__card", timeout=8000)
            except Exception:
                pass
                
        content = page.content()
        browser.close()
        
    log.info("HTML renderizado obtenido (%d bytes)", len(content))
    return content

def fetch_raw_html(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode("utf-8", errors="replace")

def parse_magnets(raw: str) -> list:
    results = []
    season_blocks = re.split(r'id="collapse-(\d+)"', raw)
    if len(season_blocks) < 3:
        return results
    i = 1
    while i < len(season_blocks) - 1:
        season = int(season_blocks[i])
        block  = season_blocks[i + 1]
        for row in re.findall(r"<tr>(.*?)</tr>", block, re.DOTALL):
            ep_m = re.search(r"<td>(\d+)</td>", row)
            if not ep_m:
                continue
            ep = int(ep_m.group(1))
            mag_m = re.search(r'href="(magnet:[^"]+)"', row)
            if not mag_m:
                continue
            uri = html.unescape(mag_m.group(1))
            results.append((season, ep, uri))
        i += 2
    return results