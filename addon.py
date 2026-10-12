from flask import Flask, jsonify
from flask_cors import CORS
import urllib.request
import urllib.error
import urllib.parse
import json
import re
import unicodedata
import html

import scraper

app = Flask(__name__)
CORS(app)

MANIFEST = {
    "id": "com.nayelhis.pelispanda",
    "version": "1.1.8",
    "name": "Pelispanda Anime Pro",
    "description": "Soporte total para Películas, Series y Anime (TMDB/Kitsu)",
    "idPrefixes": ["tt", "tmdb", "kitsu"],
    "resources": ["stream"],
    "types": ["series", "movie", "anime"],
    "catalogs": []
}

CACHE_URLS = {}   
CACHE_MAGNETS = {}   

TMDB_TOKEN = "eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiIwYzI1YmVkZjI5YmU2NGQ3MWMwOGIxNDU0YWQ2MGUyYyIsIm5iZiI6MTc5MTY3NjQ3OC4xMDksInN1YiI6IjZhY2FkMDNlYzc2ZGVhMTdkNzJkZWMxZCIsInNjb3BlcyI6WyJhcGlfcmVhZCJdLCJ2ZXJzaW9uIjoxfQ.OsMsdKy3bQqUXuHD_-jAug0VvJ6qjg0qWzG7DHqazFU"

@app.route('/manifest.json')
def manifest():
    return jsonify(MANIFEST)

def obtener_nombres_posibles(video_id, tipo):
    nombres = []
    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {TMDB_TOKEN}"
    }
    
    # 1. Búsqueda en TMDB API
    try:
        if str(video_id).startswith("tmdb:"):
            id_puro = str(video_id).replace("tmdb:", "")
            endpoint = "tv" if tipo in ["series", "anime"] else "movie"
            url_tmdb = f"https://api.themoviedb.org/3/{endpoint}/{id_puro}?language=es-MX"
            
            req = urllib.request.Request(url_tmdb, headers=headers)
            with urllib.request.urlopen(req, timeout=5) as r:
                data = json.loads(r.read().decode())
                nombre_es = data.get("name") if tipo in ["series", "anime"] else data.get("title")
                if nombre_es: nombres.append(nombre_es)
                
        elif str(video_id).startswith("tt"):
            url_tmdb = f"https://api.themoviedb.org/3/find/{video_id}?external_source=imdb_id&language=es-MX"
            req = urllib.request.Request(url_tmdb, headers=headers)
            with urllib.request.urlopen(req, timeout=5) as r:
                data = json.loads(r.read().decode())
                if tipo in ["series", "anime"] and data.get("tv_results"):
                    nombres.append(data["tv_results"][0].get("name"))
                elif tipo == "movie" and data.get("movie_results"):
                    nombres.append(data["movie_results"][0].get("title"))
    except Exception as e:
        print(f"Error TMDB Oficial: {e}")

    # 2. Respaldo en Inglés (Soporta IDs de Kitsu y Cinemeta)
    if str(video_id).startswith("tt") or str(video_id).startswith("kitsu"):
        try:
            url_cinemeta = f"https://v3-cinemeta.strem.io/meta/{tipo}/{video_id}.json"
            req = urllib.request.Request(url_cinemeta, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as r:
                data = json.loads(r.read().decode())
                nombre_en = data.get("meta", {}).get("name", "")
                if nombre_en: nombres.append(nombre_en)
        except Exception:
            pass

    return list(dict.fromkeys([n for n in nombres if n]))

def generar_slug(nombre):
    nombre_limpio = ''.join(c for c in unicodedata.normalize('NFD', nombre) if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9]+', '-', nombre_limpio.lower()).strip('-')

def verificar_url(url):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as r:
            return True 
    except urllib.error.HTTPError as e:
        if e.code == 404: 
            return False
    except Exception:
        return False
    return False

def extraer_enlaces(html_busqueda, tipo):
    # ¡LA CLAVE ESTÁ AQUÍ! Ahora el buscador interno rastrea la carpeta /anime/
    if tipo in ["series", "anime"]:
        pattern = r'href="((?:https://pelispanda\.org)?/(?:serie|anime)/[^"]+)"'
    else:
        pattern = r'href="((?:https://pelispanda\.org)?/(?:pelicula|anime)/[^"]+)"'
        
    matches = re.findall(pattern, html_busqueda)
    return [f"https://pelispanda.org{m}" if m.startswith("/") else m for m in matches]

def enlace_es_valido(enlace, nombres):
    slug = enlace.strip('/').split('/')[-1].replace('-', ' ')
    
    palabras_clave = set()
    for n in nombres:
        n_limpio = ''.join(c for c in unicodedata.normalize('NFD', n.lower()) if unicodedata.category(c) != 'Mn')
        for p in re.sub(r'[^a-z0-9]+', ' ', n_limpio).split():
            if len(p) > 2: 
                palabras_clave.add(p)
                
    for p in palabras_clave:
        if p in slug:
            return True
    return False

def buscar_url_real(video_id, tipo):
    if video_id in CACHE_URLS:
        return CACHE_URLS[video_id]

    nombres = obtener_nombres_posibles(video_id, tipo)
    
    if not nombres:
        print("❌ No se encontró el título en las bases de datos.")
        return None
        
    print(f"\n🔍 Procesando: '{nombres[0]}'")
    
    # Probamos generar los enlaces directos
    for nombre in nombres:
        slug = generar_slug(nombre)
        
        # Si es serie, probamos primero en /serie/ y luego en /anime/
        prefijos = ["serie", "anime"] if tipo in ["series", "anime"] else ["pelicula", "anime"]
        
        for prefijo in prefijos:
            url_candidata = f"https://pelispanda.org/{prefijo}/{slug}/"
            print(f"   Probando enlace directo: {url_candidata}")
            if verificar_url(url_candidata):
                print(f"✅ ¡Enlace correcto encontrado!: {url_candidata}")
                CACHE_URLS[video_id] = url_candidata
                return url_candidata
            
    print("⚠️ Enlaces directos fallaron. Usando buscador inteligente de Pelispanda...")
    try:
        nombre_busqueda = nombres[0] 
        url_busqueda = f"https://pelispanda.org/?s={urllib.parse.quote(nombre_busqueda)}"
        
        html_busqueda = scraper.fetch_raw_html(url_busqueda)
        enlaces_brutos = extraer_enlaces(html_busqueda, tipo)
        
        for enlace in enlaces_brutos:
            if enlace_es_valido(enlace, nombres):
                print(f"✅ ¡Encontrado por búsqueda!: {enlace}")
                CACHE_URLS[video_id] = enlace
                return enlace
                
    except Exception as e:
        print(f"   Error en búsqueda: {e}")
            
    print(f"❌ Definitivamente no se encontró en Pelispanda.")
    return None

@app.route('/stream/<tipo>/<id_stremio>.json')
def get_stream(tipo, id_stremio):
    streams = []
    partes = id_stremio.split(":")
    
    # Procesamiento inteligente de IDs (TMDB, Kitsu y Cinemeta)
    if id_stremio.startswith("tmdb:"):
        video_id = f"{partes[0]}:{partes[1]}"
        es_serie = (len(partes) == 4)
        if es_serie:
            temporada_solicitada = int(partes[2])
            episodio_solicitado = int(partes[3])
    elif id_stremio.startswith("kitsu:"):
        video_id = f"{partes[0]}:{partes[1]}"
        es_serie = (len(partes) >= 3)
        if es_serie:
            temporada_solicitada = 1 # Kitsu casi siempre usa formato de temporada 1 absoluta
            episodio_solicitado = int(partes[2])
    else:
        video_id = partes[0]
        es_serie = (len(partes) == 3)
        if es_serie:
            temporada_solicitada = int(partes[1])
            episodio_solicitado = int(partes[2])
            
    url_pelispanda = buscar_url_real(video_id, tipo)
    if not url_pelispanda:
        return jsonify({"streams": streams})
        
    try:
        if url_pelispanda not in CACHE_MAGNETS:
            print("⏳ Escaneando torrent con tu scraper rápido...")
            raw_html = scraper.fetch_rendered_html(url_pelispanda)
            
            if tipo in ["series", "anime"]:
                CACHE_MAGNETS[url_pelispanda] = scraper.parse_magnets(raw_html)
            else:
                magnets = re.findall(r'href="(magnet:\?xt=urn:btih:[^"]+)"', raw_html)
                if magnets:
                    CACHE_MAGNETS[url_pelispanda] = [html.unescape(magnets[0])] 
                else:
                    CACHE_MAGNETS[url_pelispanda] = []
        else:
            print("⚡ ¡Extraído de la memoria caché! (Velocidad instantánea)")
                    
        resultados = CACHE_MAGNETS.get(url_pelispanda, [])
        
        if tipo in ["series", "anime"] and es_serie:
            for temp, ep, magnet in resultados:
                if temp == temporada_solicitada and ep == episodio_solicitado:
                    streams.append({
                        "title": f"Pelispanda 🐼\nS{temp}E{ep}",
                        "url": magnet
                    })
                    break 
                    
        else:
            if resultados:
                streams.append({
                    "title": "Pelispanda 🐼\nReproducir",
                    "url": resultados[0] 
                })
                    
    except Exception as e:
        print(f"Error al extraer: {e}")

    return jsonify({"streams": streams})

if __name__ == '__main__':
    print("Servidor corriendo... Pega esto en Stremio: http://127.0.0.1:5000/manifest.json")
    app.run(port=5000, debug=True)