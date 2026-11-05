#!/usr/bin/env python3
"""Curiosidade sobre cartas no estilo "revista" (linha dos posts salvos) e coloca na agenda.

Uso: python revista.py revista/mega-ex-3-premios.yaml
Imagens só de URL OFICIAL. Cada fato precisa de fonte em `fontes`.
"""
import hashtags
import sys
import time
from pathlib import Path

import yaml
from PIL import Image

import carrossel
import imagens

BASE = Path(__file__).resolve().parent


def legenda(c):
    corpo = "\n".join(f"▪️ {s['titulo']}" for s in c["slides"][1:])
    fontes = "\n".join(c["fontes"])
    return (f"🃏 {c['slides'][0]['titulo']}\n\n{corpo}\n\n💬 {c['pergunta']}\n🔖 Salva e manda pro amigo do TCG\n\n"
            f"📚 Fontes:\n{fontes}\n📷 Imagens das cartas: {c['credito_imagem']}\n\n"
            f"🔔 Promoções verificadas no nosso Telegram (link na bio).\n\n"
            + hashtags.escolher(c.get("jogo"), "curiosidade"))


def main(arq):
    c = yaml.safe_load(open(arq, encoding="utf-8"))
    if not c.get("fontes"):
        raise SystemExit("curiosidade sem fonte: não monto")
    cartas = []
    def pegar(n):
        url = n if str(n).startswith("http") else c["imagem_base"].format(n=n)
        local = BASE / "cache_cartas" / url.rsplit("/", 1)[-1]
        if local.exists():  # cópia da mesma imagem oficial, baixada antes
            return Image.open(local).convert("RGB")
        for _ in range(6):  # o CDN oficial às vezes recusa na primeira
            img = imagens.baixar(url)
            if img is not None:
                local.parent.mkdir(exist_ok=True)
                img.save(local)
                return img
            time.sleep(2)
        raise SystemExit(f"sem imagem oficial ({url}): não monto")

    for n in c["cartas"]:
        if isinstance(n, dict) and n.get("junta"):  # duas metades lado a lado (ex.: Estádio Lendário)
            partes = [pegar(x).convert("RGB") for x in n["junta"]]
            h = min(p.height for p in partes)
            partes = [p.resize((int(p.width * h / p.height), h)) for p in partes]
            junto = Image.new("RGB", (sum(p.width for p in partes), h))
            x = 0
            for p in partes:
                junto.paste(p, (x, 0))
                x += p.width
            cartas.append(junto)
        else:
            cartas.append(pegar(n))
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
