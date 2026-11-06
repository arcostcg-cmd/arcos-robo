#!/usr/bin/env python3
"""Caça promoções no AliExpress pela API OFICIAL de afiliados (AliExpress Open Platform / Portals).

Precisa dos Secrets ALI_APP_KEY, ALI_APP_SECRET e ALI_TRACKING_ID (painel de afiliado).
Travas (o AliExpress tem muita falsificação):
  - termos suspeitos no título descartam o produto (réplica, proxy, custom, "orica", etc.);
  - avaliação da loja/produto >= aliexpress.min_avaliacao e vendas >= aliexpress.min_vendas;
  - desconto entre regras.desconto_minimo e regras.alerta_suspeito;
  - todo post leva o alerta de falsificação da loja "aliexpress" do config.
Uso: python aliexpress.py [--simular]
"""
import hashlib
import seguranca  # noqa: F401 (protege os logs)
import hmac
import json
import logging
import os
import sys
import time

import requests
import yaml

from bot import BASE, abrir_banco, agora, iso, termo_suspeito

log = logging.getLogger("aliexpress")
API = "https://api-sg.aliexpress.com/sync"


def assinatura(params, segredo):
    """Assinatura HMAC-SHA256 da API de afiliados (parâmetros ordenados, chave+valor concatenados)."""
    base = "".join(f"{k}{params[k]}" for k in sorted(params))
    return hmac.new(segredo.encode(), base.encode(), hashlib.sha256).hexdigest().upper()


def buscar(termo, pagina=1):
    chave, seg = os.environ.get("ALI_APP_KEY"), os.environ.get("ALI_APP_SECRET")
    if not chave or not seg:
        raise RuntimeError("cadastre ALI_APP_KEY, ALI_APP_SECRET e ALI_TRACKING_ID nos Secrets")
    p = {"app_key": chave, "method": "aliexpress.affiliate.product.query", "sign_method": "sha256",
         "timestamp": str(int(time.time() * 1000)), "keywords": termo, "page_no": str(pagina),
         "page_size": "30", "target_currency": "BRL", "target_language": "PT", "ship_to_country": "BR",
         "sort": "LAST_VOLUME_DESC", "tracking_id": os.environ.get("ALI_TRACKING_ID", "")}
    p["sign"] = assinatura(p, seg)
    r = requests.post(API, data=p, timeout=30)
    r.raise_for_status()
    res = r.json().get("aliexpress_affiliate_product_query_response", {}).get("resp_result", {})
    return ((res.get("result") or {}).get("products") or {}).get("product") or []


def _num(v):
    try:
        return float(str(v).replace("%", "").replace(",", "."))
    except (TypeError, ValueError):
        return 0.0


def avaliar(cfg, p):
    """Devolve (oferta, None) ou (None, motivo)."""
    a, r = cfg.get("aliexpress", {}), cfg["regras"]
    titulo = p.get("product_title", "")
    termo = termo_suspeito(cfg, titulo)
    if termo:
        return None, f"termo suspeito: {termo}"
    preco, de = _num(p.get("target_sale_price")), _num(p.get("target_original_price"))
    if not preco or not de or de <= preco:
        return None, "sem preço 'de'"
    desc = 1 - preco / de
    if desc < r["desconto_minimo"] or desc > r["alerta_suspeito"]:
        return None, f"desconto fora da faixa ({desc:.0%})"
    if _num(p.get("evaluate_rate")) < a.get("min_avaliacao", 95):
        return None, "avaliação baixa"
    if _num(p.get("lastest_volume")) < a.get("min_vendas", 50):
        return None, "poucas vendas"
    if not p.get("product_main_image_url") or not p.get("promotion_link"):
        return None, "sem foto ou link"
    loja = next((l for l in cfg["lojas"] if l["id"] == "aliexpress"), {})
    return {
        "produto": titulo[:90], "jogo": p.get("_jogo", ""), "descricao": p.get("_categoria", "Colecionável"),
        "loja": "aliexpress", "loja_nome": "AliExpress", "preco": preco, "ref": de, "ref_fonte": "loja",
        "url": p.get("product_detail_url", p["promotion_link"]), "link": p["promotion_link"],
        "imagem": p["product_main_image_url"], "visto": iso(agora()), "afiliado": True,
        "cupom": None, "preco_final": preco, "confianca": loja.get("confianca", 3),
        "bandeira": "🇨🇳", "reputacao": f"avaliação {p.get('evaluate_rate')} · {int(_num(p.get('lastest_volume')))} vendidos",
        "alerta_loja": loja.get("alerta", ""), "frete_gratis": False,
    }, None


def main(simular=False):
    import bot
    import carrossel
    import imagens
    import publicar
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = yaml.safe_load(open(BASE / "config.yaml", encoding="utf-8"))
    a = cfg.get("aliexpress", {})
    if not a.get("ativo") or not os.environ.get("ALI_APP_KEY"):
        log.info("AliExpress desligado ou sem chaves: nada a fazer")
        return
    con = abrir_banco(BASE / cfg["banco"])
    achadas = []
    for t in a.get("termos", []):
        try:
            for p in buscar(t["q"]):
                p["_jogo"], p["_categoria"] = t.get("jogo", ""), t.get("categoria", "Colecionável")
                of, motivo = avaliar(cfg, p)
                if of and not bot.ja_postado(con, of["produto"], "aliexpress", of["preco"], "telegram",
                                             cfg["regras"]["nao_repetir_horas"]):
                    achadas.append(of)
        except Exception as e:
            log.warning("AliExpress '%s': %s", t["q"], e)
    achadas.sort(key=lambda o: o["preco"] / o["ref"])
    log.info("AliExpress: %d ofertas aprovadas", len(achadas))
    for o in achadas[: a.get("max_por_execucao", 1)]:
        foto = imagens.baixar(o["imagem"])
        if foto is None:
            continue
        slides, _ = carrossel.carrossel_promocao(o, foto, bot.PASTA_IMG)
        texto = bot.texto_telegram(o)
        if simular:
            print(texto)
            continue
        publicar.telegram_album(cfg, [str(s) for s in slides], texto, html=True)
        con.execute("INSERT INTO postados VALUES (?,?,?,?,?)", (o["produto"], "aliexpress", o["preco"],
                                                                 "telegram", iso(agora())))
        con.commit()


if __name__ == "__main__":
    main("--simular" in sys.argv)
