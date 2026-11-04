#!/usr/bin/env python3
"""Curiosidade sobre cartas no estilo "revista" (linha dos posts salvos) e coloca na agenda.

Uso: python revista.py revista/mega-ex-3-premios.yaml
Imagens só de URL OFICIAL. Cada fato precisa de fonte em `fontes`.
"""
import sys
from pathlib import Path

import yaml

import carrossel
import imagens

BASE = Path(__file__).resolve().parent


def legenda(c):
    corpo = "\n".join(f"▪️ {s['titulo']}" for s in c["slides"])
    fontes = "\n".join(c["fontes"])
    return (f"🃏 {c['slides'][0]['titulo']}\n\n{corpo}\n\n💬 {c['pergunta']}\n🔖 Salva e manda pro amigo do TCG\n\n"
            f"📚 Fontes:\n{fontes}\n📷 Imagens das cartas: {c['credito_imagem']}\n\n"
            f"🔔 Promoções verificadas no nosso Telegram (link na bio).\n\n"
            + c.get("hashtags", "#pokemontcg #pokemon #cartaspokemon #curiosidades #tcgbrasil #montoptcg"))


def main(arq):
    c = yaml.safe_load(open(arq, encoding="utf-8"))
    if not c.get("fontes"):
        raise SystemExit("curiosidade sem fonte: não monto")
    cartas = []
    for n in c["cartas"]:
        url = n if str(n).startswith("http") else c["imagem_base"].format(n=n)
        img = imagens.baixar(url)
        if img is None:
            raise SystemExit(f"sem imagem oficial ({url}): não monto")
        cartas.append(img)
    slides = carrossel.carrossel_revista(c, cartas, BASE / "imagens", c["id"])
    ig = legenda(c)
    agenda = BASE / "agenda.yaml"
    itens = yaml.safe_load(agenda.read_text(encoding="utf-8")) if agenda.exists() else []
    itens = [x for x in (itens or []) if x["id"] != c["id"] and x["quando"] != c["quando"]]
    itens.append({"quando": c["quando"], "id": c["id"], "jogo": c["jogo"],
                  "slides": [Path(s).name for s in slides], "legenda_telegram": ig, "legenda_instagram": ig})
    agenda.write_text(yaml.safe_dump(sorted(itens, key=lambda x: x["quando"]), allow_unicode=True,
                                     sort_keys=False), encoding="utf-8")
    print("Agendado:", c["id"], "para", c["quando"], "|", len(slides), "slides")


if __name__ == "__main__":
    main(sys.argv[1])
