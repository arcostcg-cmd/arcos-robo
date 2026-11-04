#!/usr/bin/env python3
"""Monta uma enquete "Escolha 1" a partir de enquetes/<arquivo>.yaml e coloca na agenda do feed.

Uso: python enquete.py enquetes/me01-qual-mega.yaml
Imagens só de URL OFICIAL (pokemon.com, onepiece-cardgame.com). Sem imagem, não monta.
"""
import sys
from pathlib import Path

import yaml

import carrossel
import imagens

BASE = Path(__file__).resolve().parent


def legenda(e):
    ops = "\n".join(f"{k}️⃣ {o['nome']}" for k, o in enumerate(e["opcoes"], 1))
    return (f"🗳️ {e['pergunta']}\n\n{ops}\n\n💬 Comenta o número da sua escolha e marca um amigo pra votar também\n"
            f"🔖 Salva e volta pra ver quem ganhou\n\n📷 Imagens das cartas: {e['credito_imagem']}\n\n"
            f"🔔 Promoções verificadas no nosso Telegram (link na bio).\n\n{e['hashtags']}")


def main(arq):
    e = yaml.safe_load(open(arq, encoding="utf-8"))
    cartas = []
    for o in e["opcoes"]:
        img = imagens.baixar(o.get("imagem") or e["imagem_base"].format(n=o["n"]))
        if img is None:
            raise SystemExit(f"sem imagem oficial para {o['nome']}: não monto o post")
        cartas.append(img)
    slides = carrossel.carrossel_enquete(e, cartas, BASE / "imagens", e["id"])
    ig = legenda(e)
    agenda = BASE / "agenda.yaml"
    itens = yaml.safe_load(agenda.read_text(encoding="utf-8")) if agenda.exists() else []
    itens = [x for x in (itens or []) if x["id"] != e["id"]]
    itens.append({"quando": e["quando"], "id": e["id"], "jogo": e["jogo"],
                  "slides": [Path(s).name for s in slides],
                  "legenda_telegram": ig, "legenda_instagram": ig})
    agenda.write_text(yaml.safe_dump(sorted(itens, key=lambda x: x["quando"]), allow_unicode=True,
                                     sort_keys=False), encoding="utf-8")
    print("Agendado:", e["id"], "para", e["quando"], "|", len(slides), "slides")


if __name__ == "__main__":
    main(sys.argv[1])
