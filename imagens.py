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
from PIL import Image

log = logging.getLogger("imagens")
UA = {"User-Agent": "ArcosTCGBot/1.0 (robo de promocoes TCG; contato no canal)"}
LICENCAS_OK = re.compile(
    r"^(cc0|public domain|domínio público|pd|cc[ -]by([ -]sa)?[ -][0-9.]+)", re.I)


def baixar(url):
    """Baixa uma imagem e devolve um PIL.Image em RGB, ou None."""
    try:
        r = requests.get(url, headers=UA, timeout=30)
        r.raise_for_status()
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
    params = {
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": f"{termo} filetype:bitmap", "gsrnamespace": 6,
        "gsrlimit": 10, "prop": "imageinfo",
        "iiprop": "url|extmetadata|mime", "iiurlwidth": largura,
    }
    try:
        r = requests.get("https://commons.wikimedia.org/w/api.php",
                         params=params, headers=UA, timeout=30)
        r.raise_for_status()
        paginas = r.json().get("query", {}).get("pages", {})
    except Exception as e:
        log.warning("Busca no Commons falhou (%s): %s", termo, e)
        return None
    for p in sorted(paginas.values(), key=lambda x: x.get("index", 99)):
        info = (p.get("imageinfo") or [{}])[0]
        if info.get("mime") not in ("image/jpeg", "image/png"):
            continue
        meta = info.get("extmetadata", {})
        licenca = _limpar_html(meta.get("LicenseShortName", {}).get("value"))
        if not LICENCAS_OK.match(licenca) or "nonfree" in licenca.lower():
            continue
        autor = _limpar_html(meta.get("Artist", {}).get("value")) or "autor desconhecido"
        img = baixar(info.get("thumburl") or info.get("url"))
        if img is None:
            continue
        return {
            "imagem": img,
            "credito": f"Foto: {autor[:60]} · {licenca} · Wikimedia Commons",
            "pagina": info.get("descriptionurl", ""),
        }
    log.info("Nenhuma imagem livre no Commons para: %s", termo)
    return None
