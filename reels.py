#!/usr/bin/env python3
"""Publica os Reels da agenda (tipo: reel) no horário marcado, pela API oficial do Instagram.

Roda de hora em hora junto com as curiosidades. Conta dentro do limite de 3 posts por dia no feed.
Sem INSTAGRAM_TOKEN/conta_id, não faz nada (e avisa no log).
"""
import logging
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

import publicar
import seguranca  # noqa: F401 (logs sem token)

BASE = Path(__file__).resolve().parent
BR = timezone(timedelta(hours=-3))
log = logging.getLogger("reels")


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = yaml.safe_load(open(BASE / "config.yaml", encoding="utf-8"))
    if not os.environ.get("INSTAGRAM_TOKEN") or not cfg["instagram"].get("conta_id"):
        log.info("Instagram ainda não conectado (INSTAGRAM_TOKEN / instagram.conta_id): Reels ficam na fila")
        return
    con = sqlite3.connect(BASE / "curiosidades.db")
    con.execute("CREATE TABLE IF NOT EXISTS curiosidades_postadas (id TEXT PRIMARY KEY, quando TEXT)")
    feitos = {r[0] for r in con.execute("SELECT id FROM curiosidades_postadas")}
    agora = datetime.now(BR)
    for it in yaml.safe_load((BASE / "agenda.yaml").read_text(encoding="utf-8")) or []:
        if it.get("tipo") != "reel" or it["id"] in feitos:
            continue
        quando = datetime.fromisoformat(it["quando"]).replace(tzinfo=BR)
        if not (quando <= agora < quando + timedelta(hours=1)):
            continue
        if publicar.feed_cheio(cfg):
            log.info("Feed já tem os posts do dia: Reels %s fica para amanhã", it["id"])
            return
        if not (BASE / it["video"]).exists():
            log.error("Vídeo %s não está no repositório", it["video"])
            continue
        mid = publicar.instagram_reel(cfg, it["video"], it["legenda_instagram"], it.get("capa"))
        con.execute("INSERT OR IGNORE INTO curiosidades_postadas VALUES (?, ?)", (it["id"], agora.isoformat()))
        con.commit()
        log.info("Reels publicado: %s (mídia %s)", it["id"], mid)
        (BASE / ".reel_agora").write_text(it["id"])
        publicar.avisar_admin(cfg, f"🎬 Reels publicado no Instagram: {it['id']}")
        return


if __name__ == "__main__":
    main()
