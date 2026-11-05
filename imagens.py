"""Busca de imagens com licença conhecida e crédito automático.

Fontes permitidas:
- foto oficial do produto publicada pela própria loja (promoções);
- Wikimedia Commons, apenas CC0, domínio público, CC BY e CC BY-SA.
Imagens soltas da internet nunca são usadas: crédito não substitui licença.
"""
import io
import logging
import re

import requests

import seguranca
from PIL import Image

log = logging.getLogger("imagens")
Image.MAX_IMAGE_PIXELS = 60_000_000  # trava contra "bomba" de descompressão
UA = {"User-Agent": "ArcosTCGBot/1.0 (robo de promocoes TCG; contato no canal)"}
LICENCAS_OK = re.compile(
    r"^(cc0|public domain|domínio público|pd|cc[ -]by([ -]sa)?[ -][0-9.]+)", re.I)


def _get(url, **kw):
    """GET educado: pausa curta entre chamadas e nova tentativa se o site pedir calma (429)."""
    import time
    for espera in (1.5, 8, 20):
        time.sleep(espera if "wikimedia" in url else 0)
        r = requests.get(url, headers=UA, timeout=30, **kw)
        if r.status_code != 429:
            return r
    return r


NAO_FOTO = re.compile(r"diagram|scheme|schema|template|anatomy|logo|icon|map|chart|layout|"
                      r"[\u0400-\u04FF\u3040-\u30FF\u4E00-\u9FFF]", re.I)


def baixar(url):
    """Baixa uma imagem e devolve um PIL.Image em RGB, ou None."""
    try:
        if not url.startswith("https://"):
            raise ValueError("só imagem por HTTPS")
        r = _get(url.split("?utm_")[0])
        r.raise_for_status()
        if not seguranca.imagem_segura(r):
            raise ValueError("arquivo não é imagem ou é grande demais")
        img = Image.open(io.BytesIO(r.content))
        img.verify()  # confere que é imagem de verdade antes de usar
        img = Image.open(io.BytesIO(r.content))
        return img.convert("RGB")
    except Exception as e:
        log.warning("Não consegui baixar a imagem %s: %s", url, e)
        return None


def _limpar_html(texto):
    texto = re.sub(r"<[^>]+>", "", texto or "")
    return re.sub(r"\s+", " ", texto).strip()


def buscar_commons(termo, largura=1080):
    """Procura no Wikimedia Commons uma foto de licença livre.

    Devolve {"imagem": PIL.Image, "credito": str, "pagina": str} ou None.
    """
    fotos = buscar_commons_varias([termo], 1, largura)
    return fotos[0] if fotos else None


def buscar_commons_varias(termos, quantas=4, largura=1080, minimo_lado=500):
    """Várias fotos livres e diferentes (uma por slide), percorrendo os termos em ordem.

    Só CC0, domínio público, CC BY e CC BY-SA, cada uma com seu crédito.
    """
    achadas, vistas = [], set()
    for termo in termos:
        if len(achadas) >= quantas:
            break
        for f in _commons_termo(termo, largura, minimo_lado):
            if f["pagina"] in vistas:
                continue
            vistas.add(f["pagina"])
            achadas.append(f)
            if len(achadas) >= quantas:
                break
    return achadas


def _commons_termo(termo, largura, minimo_lado):
    params = {
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": f"{termo} filetype:bitmap", "gsrnamespace": 6,
        "gsrlimit": 20, "prop": "imageinfo",
        "iiprop": "url|extmetadata|mime", "iiurlwidth": largura,
    }
    try:
        r = _get("https://commons.wikimedia.org/w/api.php", params=params)
        r.raise_for_status()
        paginas = r.json().get("query", {}).get("pages", {})
    except Exception as e:
        log.warning("Busca no Commons falhou (%s): %s", termo, e)
        return
    for p in sorted(paginas.values(), key=lambda x: x.get("index", 99)):
        if NAO_FOTO.search(p.get("title", "")):  # esquemas, logos, mapas: não servem de foto
            continue
        info = (p.get("imageinfo") or [{}])[0]
        if info.get("mime") not in ("image/jpeg", "image/png"):
            continue
        meta = info.get("extmetadata", {})
        licenca = _limpar_html(meta.get("LicenseShortName", {}).get("value"))
        if not LICENCAS_OK.match(licenca) or "nonfree" in licenca.lower():
            continue
        autor = _limpar_html(meta.get("Artist", {}).get("value")) or "autor desconhecido"
        img = baixar(info.get("thumburl") or info.get("url"))
        if img is None or min(img.size) < minimo_lado:
            continue
        yield {
            "imagem": img,
            "credito": f"Foto: {autor[:60]} · {licenca} · Wikimedia Commons",
            "pagina": info.get("descriptionurl", ""),
        }
