#!/usr/bin/env python3
"""Posta uma curiosidade verificada sobre TCG em carrossel, no Telegram e no Instagram.

Roda pelo cron 3 vezes por dia. Cada execução escolhe UMA curiosidade inédita
(alternando o jogo), procura uma foto de licença livre no Wikimedia Commons,
monta o carrossel com a identidade do Arcos e posta com os créditos.

Uso:
  python curiosidades.py --simular              # gera os slides sem postar
  python curiosidades.py --etapa preparar       # só gera os slides (GitHub Actions)
  python curiosidades.py --etapa publicar       # posta os slides já gerados
  python curiosidades.py                        # tudo de uma vez (servidor próprio)
"""
import argparse
import json
import logging

import yaml

import carrossel
import imagens
import publicar
from bot import BASE, abrir_banco, agora, iso

log = logging.getLogger("curiosidades")
PREPARADA = BASE / "curiosidade_preparada.json"


def preparar_banco(con):
    con.execute(
        "CREATE TABLE IF NOT EXISTS curiosidades_postadas("
        "id TEXT PRIMARY KEY, jogo TEXT, postado_em TEXT)")
    con.commit()


def escolher(con, itens):
    feitos = {r[0] for r in con.execute("SELECT id FROM curiosidades_postadas")}
    pendentes = [c for c in itens if c["id"] not in feitos]
    ultimo = con.execute(
        "SELECT jogo FROM curiosidades_postadas ORDER BY postado_em DESC LIMIT 1"
    ).fetchone()
    if ultimo:  # evita dois posts seguidos do mesmo jogo
        outros = [c for c in pendentes if c["jogo"] != ultimo[0]]
        if outros:
            return outros[0], len(pendentes)
    return (pendentes[0] if pendentes else None), len(pendentes)


def legenda(c, creditos, cfg, rede):
    tags = " ".join(cfg.get("curiosidades", {}).get("hashtags", []))
    cred = "\n".join(creditos)
    if rede == "telegram":
        perg = f"💬 {c['pergunta']}\n\n" if c.get("pergunta") else ""
        return (f"🧠 VOCÊ SABIA? • {c['jogo']}\n\n{c['titulo']}\n\n{c['texto']}\n\n{perg}"
                f"📚 Fonte: {c['fonte_nome']}\n{c['fonte_url']}\n\n{cred}")
    abertura = c.get("gancho") or c["titulo"]
    perg = f"💬 {c['pergunta']}\n\n" if c.get("pergunta") else ""
    return (f"🧠 {abertura}\n\n{c['titulo']} • {c['jogo']}\n\n{c['texto']}\n\n{perg}"
            f"🔖 {carrossel.chamada_final(c)}\n\n"
            f"📚 Fonte: {c['fonte_nome']}\n{cred}\n\n"
            f"🔔 Promoções verificadas no nosso Telegram (link na bio).\n\n{tags}").strip()


def preparar(cfg, con, itens):
    c, restantes = escolher(con, itens)
    if not c:
        return None, 0
    foto = imagens.buscar_commons(c["busca_imagem"]) if c.get("busca_imagem") else None
    slides, creditos = carrossel.carrossel_curiosidade(c, foto, BASE / "imagens")
    dados = {"item": c, "slides": [str(s) for s in slides], "creditos": creditos}
    PREPARADA.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    return dados, restantes


def avisar_admin(cfg, texto):
    chat = cfg["telegram"].get("admin_chat")
    if chat:
        try:
            publicar.telegram_texto(cfg, texto, chat)
        except Exception as e:
            log.warning("Aviso ao administrador falhou: %s", e)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(BASE / "config.yaml"))
    ap.add_argument("--simular", action="store_true")
    ap.add_argument("--etapa", choices=["tudo", "preparar", "publicar"], default="tudo")
    a = ap.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(),
                  logging.FileHandler(BASE / "bot.log", encoding="utf-8")])

    with open(a.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    arq = BASE / cfg.get("curiosidades", {}).get("arquivo", "curiosidades.yaml")
    with open(arq, encoding="utf-8") as f:
        itens = [c for c in (yaml.safe_load(f) or [])
                 if c.get("fonte_url") and c.get("verificado_em")]

    con = abrir_banco(BASE / cfg.get("banco_curiosidades", "curiosidades.db"))
    preparar_banco(con)

    if a.etapa in ("tudo", "preparar"):
        dados, restantes = preparar(cfg, con, itens)
        if not dados:
            log.warning("Sem curiosidades inéditas")
            if not a.simular:
                avisar_admin(cfg, "⚠️ Acabaram as curiosidades verificadas. Peça um novo lote.")
            return
        log.info("Carrossel pronto: %s (%d slides)", dados["item"]["id"], len(dados["slides"]))
        if a.simular:
            print(legenda(dados["item"], dados["creditos"], cfg, "telegram"))
            print("\nSlides:", *dados["slides"], sep="\n")
            print(f"\nRestam {restantes - 1} curiosidades inéditas.")
            return
        if restantes - 1 <= 3:
            avisar_admin(cfg, f"⚠️ Restam só {restantes - 1} curiosidades inéditas. "
                              "Peça ao Claude um novo lote verificado.")
        if a.etapa == "preparar":
            return

    if not PREPARADA.exists():
        log.warning("Nada preparado para postar")
        return
    dados = json.loads(PREPARADA.read_text(encoding="utf-8"))
    c = dados["item"]
    ok = False
    if cfg["telegram"].get("ativo"):
        try:
            publicar.telegram_album(cfg, dados["slides"], legenda(c, dados["creditos"], cfg, "telegram"))
            ok = True
        except Exception as e:
            log.error("Telegram falhou: %s", e)
    if cfg["instagram"].get("ativo"):
        try:
            publicar.instagram_carrossel(cfg, dados["slides"], legenda(c, dados["creditos"], cfg, "instagram"))
            ok = True
        except Exception as e:
            log.error("Instagram falhou: %s", e)
    if ok:
        con.execute("INSERT INTO curiosidades_postadas VALUES (?,?,?)",
                    (c["id"], c["jogo"], iso(agora())))
        con.commit()
        PREPARADA.unlink()
        log.info("Curiosidade postada: %s", c["id"])


if __name__ == "__main__":
    main()
