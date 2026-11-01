#!/usr/bin/env python3
"""Descobre produtos de TCG no catálogo do Mercado Livre que têm oferta de vendedor confiável
(loja oficial, MercadoLíder Platinum ou Gold) e gera os itens prontos para o config.yaml.

Mais produtos vigiados = mais chances de promoção de verdade no Telegram.
Uso: python descobrir.py termos.json saida.yaml
"""
import json
import re
import sys

import yaml

import marketplaces as m

JOGOS = [("pokémon", "Pokémon"), ("pokemon", "Pokémon"), ("one piece", "One Piece"), ("magic", "Magic"),
         ("yu-gi-oh", "Yu-Gi-Oh!"), ("yugioh", "Yu-Gi-Oh!"), ("lorcana", "Lorcana"), ("digimon", "Digimon"),
         ("dragon ball", "Dragon Ball Super")]
TIPOS = re.compile(r"booster|box|deck|treinador avan|elite trainer|etb|blister|lata|tin|cole[cç][aã]o|bundle|starter|kit", re.I)
FORA = re.compile(r"tatuagem|adesivo|estojo|boneco|pel[uú]cia|camis|caneca|chaveiro|capinha|fich[aá]rio|sleeve|shield|playmat|"
                  r"mochila|lote|avuls|proxy|r[eé]plica|custom|repack|misterios", re.I)


def jogo_de(nome):
    n = nome.lower()
    return next((j for k, j in JOGOS if k in n), None)


def main(entrada, saida):
    termos = json.load(open(entrada, encoding="utf-8"))["termos"]
    loja = {"api": "mercadolivre", "ml_exigir": ["oficial", "platinum", "gold"]}
    vistos, novos = set(), []
    for t in termos:
        try:
            r = m._ml_get(f"/products/search?status=active&site_id=MLB&q={m.requests.utils.quote(t)}&limit=15")
        except Exception as e:
            print("erro na busca", t, e)
            continue
        for p in r.get("results") or []:
            pid, nome = p.get("id"), p.get("name", "")
            if pid in vistos or FORA.search(nome) or not TIPOS.search(nome) or not jogo_de(nome):
                continue
            vistos.add(pid)
            url = f"https://www.mercadolivre.com.br/p/{pid}"
            res, erro = m.ml_oferta_catalogo(url, loja)
            if not res:
                continue
            preco, estoque, img, titulo, selo, _ = res
            if not estoque or not img:
                continue
            novos.append({"nome": nome[:90], "jogo": jogo_de(nome), "descricao": "Lacrado",
                          "palavras": [], "ofertas": [{"loja": "mercadolivre", "url": url}],
                          "_preco_hoje": preco, "_selo": selo})
            print(f"OK {pid} | {nome[:70]} | R$ {preco} | {selo}")
    open(saida, "w", encoding="utf-8").write(yaml.safe_dump(novos, allow_unicode=True, sort_keys=False))
    print(len(novos), "produtos com vendedor confiável")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
