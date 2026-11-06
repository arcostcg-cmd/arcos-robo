"""Postagem de carrosséis: álbum no Telegram e carrossel no Instagram."""
import hashtags
import json
import os
import time
from contextlib import ExitStack
from pathlib import Path

import requests


class ErroTelegram(RuntimeError):
    """Erro do Telegram SEM o token (a URL da API leva o token; nunca vai para o log)."""


def _tg(metodo, data, files=None, timeout=60, tentativas=3):
    """Chama a API do Telegram respeitando o limite (429 + retry_after) e sem vazar o token em erro."""
    token = os.environ["TELEGRAM_TOKEN"]
    url = f"https://api.telegram.org/bot{token}/{metodo}"
    for n in range(tentativas):
        try:
            r = requests.post(url, data=data, files=files, timeout=timeout)
        except requests.RequestException as e:
            raise ErroTelegram(f"{metodo}: falha de rede ({type(e).__name__})") from None
        if r.status_code == 429 and n < tentativas - 1:
            try:
                espera = int(r.json().get("parameters", {}).get("retry_after", 5))
            except Exception:
                espera = 5
            time.sleep(min(espera, 60) + 1)
            if files:
                for f in files.values():
                    f.seek(0)
            continue
        if r.status_code >= 400:
            try:
                desc = r.json().get("description", "")
            except Exception:
                desc = ""
            raise ErroTelegram(f"{metodo}: HTTP {r.status_code} {desc}".strip())
        return r
    raise ErroTelegram(f"{metodo}: limite do Telegram, tentei {tentativas} vezes")


def telegram_album(cfg, caminhos, legenda, html=False):
    """Envia até 10 imagens como um álbum, com a legenda na primeira."""
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
        _tg("sendMediaGroup", {"chat_id": cfg["telegram"]["canal"], "media": json.dumps(media)},
            files=arquivos, timeout=120)


def telegram_texto(cfg, texto, chat=None, html=False):
    _tg("sendMessage", {"chat_id": chat or cfg["telegram"]["canal"], "text": texto[:4096],
                        "disable_web_page_preview": False, **({"parse_mode": "HTML"} if html else {})},
        timeout=30)


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


def feed_cheio(cfg):
    """True se o feed do Instagram já recebeu instagram.max_feed_dia posts hoje (horário de Brasília).

    Conta direto na API (fonte única de verdade, vale para todos os módulos do robô).
    """
    from datetime import datetime, timedelta, timezone
    limite = cfg["instagram"].get("max_feed_dia", 3)
    try:
        r = requests.get(f"{_ig(cfg)}/{cfg['instagram']['conta_id']}/media", timeout=30, params={
            "fields": "timestamp,media_product_type", "limit": 25,
            "access_token": os.environ["INSTAGRAM_TOKEN"]})
        br = timezone(timedelta(hours=-3))
        hoje = datetime.now(br).date()
        n = 0
        for m in r.json().get("data", []):
            if m.get("media_product_type", "FEED") != "FEED":
                continue
            t = datetime.strptime(m["timestamp"], "%Y-%m-%dT%H:%M:%S%z").astimezone(br)
            n += t.date() == hoje
        return n >= limite
    except Exception:
        return False


def instagram_carrossel(cfg, caminhos, legenda, furo=False):
    """Publica 2 a 10 imagens como um único carrossel (respeita o limite diário do feed)."""
    if feed_cheio(cfg):
        raise CotaInstagram(f"feed já tem {cfg['instagram'].get('max_feed_dia', 3)} posts hoje")
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
        "caption": hashtags.limitar(legenda)[:2200], "access_token": token})
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
    with open(caminho, "rb") as f:
        _tg("sendPhoto", {"chat_id": cfg["telegram"]["canal"], "caption": legenda[:1024]},
            files={"photo": f}, timeout=60)


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
