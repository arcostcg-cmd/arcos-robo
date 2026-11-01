"""Postagem de carrosséis: álbum no Telegram e carrossel no Instagram."""
import json
import os
import time
from contextlib import ExitStack
from pathlib import Path

import requests


def telegram_album(cfg, caminhos, legenda, html=False):
    """Envia até 10 imagens como um álbum, com a legenda na primeira."""
    token = os.environ["TELEGRAM_TOKEN"]
    media, arquivos = [], {}
    with ExitStack() as pilha:
        for i, c in enumerate(caminhos[:10]):
            chave = f"f{i}"
            arquivos[chave] = pilha.enter_context(open(c, "rb"))
            item = {"type": "photo", "media": f"attach://{chave}"}
            if i == 0:
                item["caption"] = legenda[:1024]
                if html:
                    item["parse_mode"] = "HTML"
            media.append(item)
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMediaGroup", timeout=120,
            data={"chat_id": cfg["telegram"]["canal"], "media": json.dumps(media)},
            files=arquivos)
    r.raise_for_status()


def telegram_texto(cfg, texto, chat=None, html=False):
    token = os.environ["TELEGRAM_TOKEN"]
    r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", timeout=30,
                      data={"chat_id": chat or cfg["telegram"]["canal"], "text": texto,
                            "disable_web_page_preview": False,
                            **({"parse_mode": "HTML"} if html else {})})
    r.raise_for_status()


def url_publica(cfg, caminho):
    base = (cfg.get("curiosidades", {}) or {}).get("url_publica_imagens")
    if not base:
        raise RuntimeError("defina curiosidades.url_publica_imagens (o Instagram exige link público)")
    return f"{base.rstrip('/')}/{Path(caminho).name}"


def _ig(cfg):
    """Host da API: graph.instagram.com (login do Instagram, sem página do Facebook)
    ou graph.facebook.com (conta ligada a uma página). Definido em instagram.api_host."""
    ic = cfg["instagram"]
    host = ic.get("api_host", "graph.facebook.com")
    return f"https://{host}/{ic.get('versao_api', 'v23.0')}"


class CotaInstagram(Exception):
    """A cota diária de publicações da API do Instagram acabou."""


def conferir_cota(cfg):
    """Pergunta à API quantas publicações ainda cabem nas últimas 24 h.

    Se a consulta falhar, segue (a própria publicação devolve erro se não couber).
    """
    token = os.environ["INSTAGRAM_TOKEN"]
    ig = cfg["instagram"]["conta_id"]
    try:
        r = requests.get(f"{_ig(cfg)}/{ig}/content_publishing_limit",
                         params={"fields": "quota_usage,config", "access_token": token}, timeout=30)
        dados = (r.json().get("data") or [{}])[0]
        uso = dados.get("quota_usage")
        total = (dados.get("config") or {}).get("quota_total")
    except Exception:
        return
    reserva = cfg["instagram"].get("reserva_cota", 3)  # guarda espaço para os furos
    if uso is not None and total and uso >= total - reserva:
        raise CotaInstagram(f"cota do Instagram quase no fim ({uso}/{total})")


def instagram_carrossel(cfg, caminhos, legenda, furo=False):
    """Publica 2 a 10 imagens como um único carrossel."""
    if not furo:
        conferir_cota(cfg)
    token = os.environ["INSTAGRAM_TOKEN"]
    ig = cfg["instagram"]["conta_id"]
    base = f"{_ig(cfg)}/{ig}"
    filhos = []
    for c in caminhos[:10]:
        r = requests.post(f"{base}/media", timeout=60, data={
            "image_url": url_publica(cfg, c), "is_carousel_item": "true",
            "access_token": token})
        r.raise_for_status()
        filhos.append(r.json()["id"])
    r = requests.post(f"{base}/media", timeout=60, data={
        "media_type": "CAROUSEL", "children": ",".join(filhos),
        "caption": legenda[:2200], "access_token": token})
    r.raise_for_status()
    pai = r.json()["id"]
    for _ in range(12):  # espera o Instagram processar as imagens
        time.sleep(10)
        st = requests.get(f"{_ig(cfg)}/{pai}", timeout=30, params={
            "fields": "status_code", "access_token": token}).json()
        if st.get("status_code") == "FINISHED":
            break
        if st.get("status_code") == "ERROR":
            raise RuntimeError(f"Instagram recusou o carrossel: {st}")
    r = requests.post(f"{base}/media_publish", timeout=60, data={
        "creation_id": pai, "access_token": token})
    r.raise_for_status()


def avisar_admin(cfg, texto):
    """Mensagem privada para o administrador (telegram.admin_chat). Nunca derruba o robô."""
    chat = cfg.get("telegram", {}).get("admin_chat")
    if not chat or not os.environ.get("TELEGRAM_TOKEN"):
        return
    try:
        telegram_texto(cfg, texto, chat)
    except Exception:
        pass


def telegram_foto(cfg, caminho, legenda):
    token = os.environ["TELEGRAM_TOKEN"]
    with open(caminho, "rb") as f:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendPhoto", timeout=60,
                          data={"chat_id": cfg["telegram"]["canal"], "caption": legenda[:1024]},
                          files={"photo": f})
    r.raise_for_status()


def instagram_story(cfg, caminho, furo=False):
    """Publica uma imagem 1080×1920 como story (conta profissional, API oficial)."""
    if not furo:
        conferir_cota(cfg)
    token = os.environ["INSTAGRAM_TOKEN"]
    ig = cfg["instagram"]["conta_id"]
    base = f"{_ig(cfg)}/{ig}"
    r = requests.post(f"{base}/media", timeout=60, data={
        "image_url": url_publica(cfg, caminho), "media_type": "STORIES",
        "access_token": token})
    r.raise_for_status()
    criacao = r.json()["id"]
    time.sleep(10)
    r = requests.post(f"{base}/media_publish", timeout=60, data={
        "creation_id": criacao, "access_token": token})
    r.raise_for_status()
