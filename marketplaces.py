"""Sistema de Promoções: leitura dos grandes marketplaces pelos canais OFICIAIS.

- Mercado Livre: API oficial (api.mercadolibre.com). Com o app do Marcos
  (ML_CLIENT_ID e ML_CLIENT_SECRET nos Secrets), o robô pega um token oficial.
  Só aceita Loja Oficial ou vendedor MercadoLíder Platinum/Gold (lojas.md).
- Amazon, Shopee e AliExpress: só pelas APIs dos programas de afiliados,
  depois que o Marcos for aprovado em cada um. Até lá, ficam desligadas e as
  ofertas desses lugares entram pela varredura manual, com o link de afiliado.

Nunca raspa página de marketplace (os termos de uso proíbem e eles bloqueiam).
"""
import logging
import os
import re
import time

import requests

log = logging.getLogger("marketplaces")
ML_API = "https://api.mercadolibre.com"
_token = {"valor": None, "expira": 0}
ULTIMO_ERRO_TOKEN = {"msg": ""}

# Integrações que dependem de aprovação em programa de afiliados
AGUARDANDO_CHAVE = {
    "amazon": "API de afiliados da Amazon (liberada após as primeiras vendas no Amazon Associados)",
    "shopee": "API do Shopee Afiliados (após aprovação no programa)",
    "aliexpress": "API do AliExpress Portals (após aprovação no programa)",
}


def ml_id(url):
    """'https://produto.mercadolivre.com.br/MLB-1234567890-...' -> 'MLB1234567890'."""
    m = re.search(r"\b(MLB)-?(\d{6,})", url or "", re.I)
    return f"MLB{m.group(2)}" if m else None


def ml_token():
    cid, seg = os.environ.get("ML_CLIENT_ID"), os.environ.get("ML_CLIENT_SECRET")
    if not cid or not seg:
        return None
    if _token["valor"] and time.time() < _token["expira"]:
        return _token["valor"]
    try:
        r = requests.post(f"{ML_API}/oauth/token", timeout=20, data={
            "grant_type": "client_credentials", "client_id": cid, "client_secret": seg})
        r.raise_for_status()
        j = r.json()
        _token.update(valor=j["access_token"], expira=time.time() + int(j.get("expires_in", 3600)) - 60)
        return _token["valor"]
    except Exception as e:
        detalhe = ""
        if isinstance(e, requests.HTTPError) and e.response is not None:
            try:
                j = e.response.json()
                detalhe = f" [{j.get('error')}: {str(j.get('message'))[:120]}]"
            except Exception:
                pass
        log.warning("Mercado Livre: não consegui o token oficial: %s%s", type(e).__name__, detalhe)
        ULTIMO_ERRO_TOKEN["msg"] = f"{type(e).__name__}{detalhe}"
        return None


def _ml_get(caminho):
    tok = ml_token()
    h = {"Authorization": f"Bearer {tok}"} if tok else {}
    r = requests.get(f"{ML_API}{caminho}", headers=h, timeout=20)
    r.raise_for_status()
    return r.json()


def vendedor_confiavel(item, vendedor, exigir=("oficial", "platinum", "gold")):
    """Loja Oficial, ou MercadoLíder Platinum/Gold com reputação verde."""
    if "oficial" in exigir and item.get("official_store_id"):
        return True, "Loja Oficial"
    rep = (vendedor or {}).get("seller_reputation") or {}
    nivel = (rep.get("power_seller_status") or "").lower()
    cor = (rep.get("level_id") or "")
    if nivel in exigir and cor.startswith("5_"):  # 5_green = melhor reputação
        return True, f"MercadoLíder {nivel.capitalize()}"
    return False, f"vendedor sem selo exigido ({nivel or 'sem MercadoLíder'}, {cor or 'sem cor'})"


def interpretar_item_ml(item, vendedor, exigir=("oficial", "platinum", "gold")):
    """Devolve (preco, estoque, imagem, titulo, selo) ou levanta ValueError com o motivo."""
    if item.get("currency_id", "BRL") != "BRL":
        raise ValueError("preço fora de reais")
    ok, selo = vendedor_confiavel(item, vendedor, exigir)
    if not ok:
        raise ValueError(selo)
    if (item.get("condition") or "new") != "new":
        raise ValueError("produto não é novo")
    preco = float(item["price"])
    estoque = item.get("status") == "active" and int(item.get("available_quantity") or 0) > 0
    fotos = item.get("pictures") or []
    img = (fotos[0].get("secure_url") or fotos[0].get("url")) if fotos else item.get("thumbnail")
    return preco, estoque, img, item.get("title", ""), selo


def ml_oferta(url, loja):
    """Lê uma oferta do Mercado Livre pela API oficial. Devolve (res, erro)."""
    iid = ml_id(url)
    if not iid:
        return None, "link do Mercado Livre sem código MLB"
    try:
        item = _ml_get(f"/items/{iid}")
        vendedor = _ml_get(f"/users/{item['seller_id']}") if not item.get("official_store_id") else {}
        exigir = tuple(loja.get("ml_exigir") or ("oficial", "platinum", "gold"))
        return interpretar_item_ml(item, vendedor, exigir), None
    except ValueError as e:
        return None, f"barrado: {e}"
    except requests.HTTPError as e:
        cod = e.response.status_code if e.response is not None else "?"
        try:
            j = e.response.json()
            motivo = f" [{j.get('code') or j.get('error') or ''}: {str(j.get('message') or '')[:120]}]"
        except Exception:
            motivo = ""
        token = "com token" if _token["valor"] else "SEM token"
        return None, f"API do Mercado Livre respondeu {cod} ({token}){motivo}"
    except Exception as e:
        return None, f"API do Mercado Livre: {e}"
