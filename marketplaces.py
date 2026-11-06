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
import seguranca  # noqa: F401 (protege os logs)
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
    if ml_catalogo_id(url):
        return ml_oferta_catalogo(url, loja)
    iid = ml_id(url)
    if not iid:
        return None, "link do Mercado Livre sem código MLB"
    try:
        item = _ml_get(f"/items/{iid}")
        vendedor = _ml_get(f"/users/{item['seller_id']}") if not item.get("official_store_id") else {}
        exigir = tuple(loja.get("ml_exigir") or ("oficial", "platinum", "gold"))
        return interpretar_item_ml(item, vendedor, exigir) + (url,), None
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


def ml_catalogo_id(url):
    """'https://www.mercadolivre.com.br/.../p/MLB74773271' -> 'MLB74773271'."""
    m = re.search(r"/p/(MLB\d+)", url or "", re.I)
    return m.group(1).upper() if m else None


def escolher_oferta_catalogo(ofertas, vendedores, loja):
    """Entre as ofertas do catálogo, a mais barata de vendedor confiável.

    loja.ml_lojas_oficiais: lista de IDs de lojas oficiais aceitas (ex.: [236642] = Pokémon).
    loja.ml_exigir: "oficial" (qualquer loja oficial), "platinum", "gold".
    Devolve (oferta, selo) ou (None, motivo).
    """
    exigir = tuple(loja.get("ml_exigir") or ("oficial", "platinum", "gold"))
    oficiais = set(loja.get("ml_lojas_oficiais") or [])
    boas = []
    for o in ofertas:
        if o.get("currency_id", "BRL") != "BRL" or (o.get("condition") or "new") != "new":
            continue
        loja_of = o.get("official_store_id")
        if oficiais:
            if loja_of in oficiais:
                boas.append((o, "Loja Oficial"))
            continue
        ok, selo = vendedor_confiavel(o, vendedores.get(o.get("seller_id")), exigir)
        if ok:
            boas.append((o, selo))
    if not boas:
        return None, "nenhuma oferta de vendedor confiável no catálogo"
    return min(boas, key=lambda x: float(x[0]["price"]))


# Preço "de" (riscado) que a própria loja informa no anúncio, por URL lida. Usado só como
# referência extra: o robô ainda exige vendedor confiável, 2 leituras iguais e preço que não
# esteja acima do normal registrado.
PRECO_DE = {}


def ml_oferta_catalogo(url, loja):
    """Lê um produto do CATÁLOGO do Mercado Livre (/p/MLB...) pela API oficial.

    Devolve ((preco, estoque, imagem, titulo, selo, url_do_anuncio), None) ou (None, erro).
    """
    cid = ml_catalogo_id(url)
    try:
        prod = _ml_get(f"/products/{cid}")
        ofertas = _ml_get(f"/products/{cid}/items").get("results") or []
        vendedores = {}
        if not loja.get("ml_lojas_oficiais"):
            for o in ofertas[:15]:
                sid = o.get("seller_id")
                if sid and sid not in vendedores and not o.get("official_store_id"):
                    try:
                        vendedores[sid] = _ml_get(f"/users/{sid}")
                    except Exception:
                        vendedores[sid] = {}
        oferta, selo = escolher_oferta_catalogo(ofertas, vendedores, loja)
        if not oferta:
            return None, f"barrado: {selo}"
        fotos = prod.get("pictures") or []
        img = fotos[0].get("url") if fotos else None
        iid = oferta["item_id"]
        link = f"https://produto.mercadolivre.com.br/MLB-{iid[3:]}" if iid.upper().startswith("MLB") else url
        orig = oferta.get("original_price")
        if orig and float(orig) > float(oferta["price"]):
            PRECO_DE[url] = float(orig)
        else:
            PRECO_DE.pop(url, None)
        return (float(oferta["price"]), True, img, prod.get("name", ""), selo, link), None
    except requests.HTTPError as e:
        cod = e.response.status_code if e.response is not None else "?"
        return None, f"API do Mercado Livre (catálogo) respondeu {cod}"
    except Exception as e:
        return None, f"API do Mercado Livre (catálogo): {type(e).__name__}"


# ------------------------------------------------------------ Shopee (API oficial de afiliados)
SHOPEE_API = "https://open-api.affiliate.shopee.com.br/graphql"
SHOPEE_QUERY = """query($keyword:String,$itemId:Int64,$shopId:Int64,$page:Int,$limit:Int){
  productOfferV2(keyword:$keyword,itemId:$itemId,shopId:$shopId,page:$page,limit:$limit){
    nodes{ itemId shopId productName priceMin priceMax shopName shopType ratingStar sales imageUrl offerLink productLink }
  }
}"""


def shopee_assinatura(app_id, segredo, payload, ts):
    """Assinatura exigida pela API de afiliados: SHA256(AppId + Timestamp + Payload + Secret)."""
    import hashlib
    return hashlib.sha256(f"{app_id}{ts}{payload}{segredo}".encode("utf-8")).hexdigest()


def shopee_chamar(variaveis):
    import json as _json
    app_id, seg = os.environ.get("SHOPEE_APP_ID"), os.environ.get("SHOPEE_SECRET")
    if not app_id or not seg:
        raise RuntimeError("cadastre SHOPEE_APP_ID e SHOPEE_SECRET (Shopee Afiliados > Open API)")
    payload = _json.dumps({"query": SHOPEE_QUERY, "variables": variaveis}, separators=(",", ":"))
    ts = int(time.time())
    h = {"Content-Type": "application/json",
         "Authorization": f"SHA256 Credential={app_id}, Timestamp={ts}, Signature={shopee_assinatura(app_id, seg, payload, ts)}"}
    r = requests.post(SHOPEE_API, data=payload, headers=h, timeout=25)
    r.raise_for_status()
    j = r.json()
    if j.get("errors"):
        raise RuntimeError(str(j["errors"])[:200])
    return (j.get("data") or {}).get("productOfferV2", {}).get("nodes") or []


def shopee_ids(url):
    """'https://shopee.com.br/produto-i.123.456' ou '.../product/123/456' -> (shop_id, item_id)."""
    m = re.search(r"-i\.(\d+)\.(\d+)", url or "") or re.search(r"/product/(\d+)/(\d+)", url or "")
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def shopee_confiavel(n, loja):
    """Só Shopee Mall / Loja Oficial (shopType 1) ou lojas da lista branca do config."""
    tipos = n.get("shopType") or []
    tipos = tipos if isinstance(tipos, list) else [tipos]
    if n.get("shopId") in set(loja.get("shopee_lojas") or []):
        return True, "Loja aprovada pelo Montop"
    if 1 in tipos:
        return True, "Shopee Mall (loja oficial)"
    return False, "vendedor sem selo Shopee Mall"


def shopee_oferta(url, loja):
    """Lê uma oferta da Shopee pela API de afiliados. Devolve ((preco, estoque, img, titulo, selo, link), erro)."""
    shop_id, item_id = shopee_ids(url)
    if not item_id:
        return None, "link da Shopee sem código do produto"
    try:
        nodes = shopee_chamar({"itemId": item_id, "shopId": shop_id, "page": 1, "limit": 1})
    except Exception as e:
        return None, f"Shopee: {str(e)[:150]}"
    if not nodes:
        return None, "Shopee: produto não encontrado (ou sem estoque)"
    n = nodes[0]
    ok, selo = shopee_confiavel(n, loja)
    if not ok:
        return None, f"barrado: {selo}"
    preco = float(n.get("priceMin") or n.get("priceMax"))
    link = n.get("offerLink") or n.get("productLink") or url  # offerLink já é o link de afiliado
    return (preco, True, n.get("imageUrl"), n.get("productName", ""), selo, link), None
