#!/usr/bin/env python3
"""Monta um post da série Top 10 a partir de tops/<arquivo>.yaml e coloca na agenda do feed.

Uso: python top10.py tops/me01-mais-valiosas.yaml
Imagens das cartas: só URL OFICIAL (pokemon.com). Preços: fonte e data escritas no post.
"""
import hashtags
import seguranca  # noqa: F401 (protege os logs)
import sys
from pathlib import Path

import yaml

import carrossel
import imagens

BASE = Path(__file__).resolve().parent


def legendas(t):
    linhas = [f"{i['pos']}º {i['nome']}" + (f" ({i['numero']})" if i.get("numero") else "") + f": {i['preco']}"
              for i in sorted(t["itens"], key=lambda x: -x["pos"])]
    corpo = "\n".join(linhas)
    comum = t.get("nota_legenda") or (f"Preços de referência de cartas sem nota (versão em inglês), segundo {t['fonte_preco'].split(' (')[0]}, "
             f"consultados em {t['data']}. Não são preços oficiais nem garantia de venda; mudam todo dia.")
    ig = (f"🏆 {t['titulo']}\n\nArrasta até o fim e descobre qual é o nº 1 👀\n\n{corpo}\n\n"
          f"📊 {comum}\n📷 Imagens das cartas: {t.get('credito_imagem', 'The Pokémon Company (pokemon.com/br)')}\n\n"
          f"💬 {t.get('pergunta', 'Qual dessas você tem ou queria ter?')}\n🔖 Salva pra consultar depois\n\n"
          f"🔔 Promoções verificadas no nosso Telegram (link na bio).\n\n"
          + hashtags.escolher(t.get("jogo", "Pokémon"), "ranking"))
    tg = (f"🏆 {t['titulo'].upper()}\n\n{corpo}\n\n📊 {comum}\nFonte: {t['fonte_url']}\n"
          f"📷 Imagens: {t.get('credito_imagem', 'The Pokémon Company (pokemon.com/br)')}\n\n💬 {t.get('pergunta', 'Qual dessas você tem?')}")
    return tg, ig


def main(arq):
    t = yaml.safe_load(open(arq, encoding="utf-8"))
    cartas = {}
    for i in t["itens"]:
        img = imagens.baixar(i.get("imagem") or t["imagem_base"].format(n=i["n"]))
        if img is None:
            raise SystemExit(f"sem imagem oficial para {i['nome']}: não monto o post")
        cartas[i["pos"]] = img
    slides = carrossel.carrossel_top10(t, cartas, BASE / "imagens", t["id"])
    tg, ig = legendas(t)
    agenda = BASE / "agenda.yaml"
    itens = yaml.safe_load(agenda.read_text(encoding="utf-8")) if agenda.exists() else []
    itens = [x for x in (itens or []) if x["id"] != t["id"]]
    itens.append({"quando": t["quando"], "id": t["id"], "jogo": t["jogo"],
                  "slides": [Path(s).name for s in slides],
                  "legenda_telegram": tg, "legenda_instagram": ig})
    agenda.write_text(yaml.safe_dump(sorted(itens, key=lambda x: x["quando"]), allow_unicode=True,
                                     sort_keys=False), encoding="utf-8")
    print("Agendado:", t["id"], "para", t["quando"], "|", len(slides), "slides")


if __name__ == "__main__":
    main(sys.argv[1])
