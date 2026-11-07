#!/usr/bin/env python3
"""Distribui cada vídeo da agenda (tipo: reel) para YouTube Shorts e TikTok, além do Instagram.

Regra do Marcos (07/11/2026):
- YouTube e TikTok recebem SÓ vídeos, sempre os mesmos que vão para o Instagram.
- Instagram recebe carrosséis e vídeos (os vídeos saem por reels.py ou, sem token da Meta, por aqui).

Caminho: Postiz (agendador com aprovação oficial nas três redes). O YouTube trava como privado
todo vídeo enviado por app próprio sem auditoria, então a API direta não serve agora.
Precisa do segredo POSTIZ_API_KEY no GitHub e dos canais conectados dentro do Postiz.
Sem a chave, não faz nada e avisa no log.
"""
import json
import logging
import os
import re
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

import seguranca  # noqa: F401 (logs sem token)

BASE = Path(__file__).resolve().parent
BR = timezone(timedelta(hours=-3))
ESTADO = BASE / "distribuidos.json"
log = logging.getLogger("distribuir")

# identificadores do Postiz para cada rede
REDES = {"youtube": ("youtube",), "tiktok": ("tiktok",), "instagram": ("instagram", "instagram-standalone")}


def _postiz(*args):
    r = subprocess.run(["postiz", *args], capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        raise RuntimeError(f"postiz {args[0]} falhou: {r.stderr.strip()[:300]}")
    saida = r.stdout.strip()
    i = min([p for p in (saida.find("{"), saida.find("[")) if p >= 0], default=0)
    return json.loads(saida[i:]) if saida else {}


def titulo_youtube(it):
    """Título do Short: o gancho da legenda, até 100 caracteres, com #shorts."""
    t = it.get("titulo_youtube") or it["legenda_instagram"].split("\n")[0]
    t = re.sub(r"\s+", " ", t).strip()
    return (t[:90].rstrip() + " #shorts")[:100]


def legenda_tiktok(it):
    """Legenda do TikTok: a mesma do Instagram (já tem até 5 hashtags) + #fyp."""
    leg = it.get("legenda_tiktok") or it["legenda_instagram"]
    return leg if "#fyp" in leg else leg + " #fyp"


def ajustes(rede, it):
    if rede == "youtube":
        return {"title": titulo_youtube(it), "type": "public"}
    if rede == "tiktok":
        return {"privacy_level": "PUBLIC_TO_EVERYONE", "duet": True, "stitch": True, "comment": True,
                "content_posting_method": "DIRECT_POST"}
    return {"post_type": "post"}


def texto(rede, it):
    if rede == "tiktok":
        return legenda_tiktok(it)
    return it["legenda_instagram"]


def vencidos(agenda, estado, agora, redes):
    """Vídeos cujo horário já chegou (até 6 h de atraso) e que ainda faltam em alguma rede."""
    for it in agenda:
        if it.get("tipo") != "reel":
            continue
        quando = datetime.fromisoformat(str(it["quando"])).replace(tzinfo=BR)
        if not (quando <= agora < quando + timedelta(hours=6)):
            continue
        faltam = [r for r in redes if r not in estado.get(it["id"], {})]
        if faltam:
            yield it, faltam


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = yaml.safe_load(open(BASE / "config.yaml", encoding="utf-8"))
    redes = list(cfg.get("videos", {}).get("redes", ["youtube", "tiktok"]))
    # Instagram só por aqui quando a API da Meta não está ligada (senão reels.py cuida)
    if os.environ.get("INSTAGRAM_TOKEN") and cfg["instagram"].get("conta_id"):
        redes = [r for r in redes if r != "instagram"]
    if not os.environ.get("POSTIZ_API_KEY"):
        log.info("POSTIZ_API_KEY ausente: vídeos para %s ficam na fila", ", ".join(redes))
        return
    if not shutil.which("postiz"):
        log.error("CLI do Postiz não instalada (npm install -g postiz)")
        return
    agenda = yaml.safe_load((BASE / "agenda.yaml").read_text(encoding="utf-8")) or []
    estado = json.loads(ESTADO.read_text()) if ESTADO.exists() else {}
    agora = datetime.now(BR)
    pendentes = list(vencidos(agenda, estado, agora, redes))
    if not pendentes:
        log.info("Nenhum vídeo no horário")
        return
    canais = {}
    for c in _postiz("integrations:list"):
        for rede, ids in REDES.items():
            if c.get("identifier") in ids and not c.get("disabled"):
                canais.setdefault(rede, c["id"])
    for it, faltam in pendentes:
        video = BASE / it["video"]
        if not video.exists():
            log.error("Vídeo %s não está no repositório", it["video"])
            continue
        url = _postiz("upload", str(video))["path"]
        for rede in faltam:
            if rede not in canais:
                log.warning("%s não está conectado no Postiz", rede)
                continue
            regras = _postiz("integrations:settings", canais[rede]).get("output", {}).get("rules")
            if regras:
                log.info("Regras do Postiz para %s: %s", rede, str(regras)[:400])
            daqui = (agora + timedelta(minutes=2)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            try:
                _postiz("posts:create", "-c", texto(rede, it), "-s", daqui, "-m", url,
                        "--settings", json.dumps(ajustes(rede, it), ensure_ascii=False), "-i", canais[rede])
            except RuntimeError as e:
                log.error("%s: %s", rede, e)
                continue
            estado.setdefault(it["id"], {})[rede] = agora.isoformat()
            ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=1))
            log.info("Vídeo %s enviado para %s", it["id"], rede)


if __name__ == "__main__":
    main()
