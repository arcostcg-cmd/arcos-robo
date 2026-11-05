#!/usr/bin/env python3
"""Posta uma curiosidade verificada sobre TCG em carrossel, no Telegram e no Instagram.

Roda pelo cron 3 vezes por dia. Cada execução escolhe UMA curiosidade inédita
(alternando o jogo), procura uma foto de licença livre no Wikimedia Commons,
monta o carrossel com a identidade do Montop e posta com os créditos.

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


DESTAQUES = ["Pokémon", "One Piece"]  # mais espaço no feed, sem abandonar os outros jogos


def escolher(con, itens, destaques=None):
    """Rodízio: Pokémon, One Piece, outro jogo, Pokémon, One Piece, outro jogo...

    No "outro jogo" entra o que está há mais tempo sem aparecer (Magic, Yu-Gi-Oh!,
    Lorcana, Digimon...), então nenhum jogo fica de fora.
    """
    destaques = destaques or DESTAQUES
    feitos = {r[0] for r in con.execute("SELECT id FROM curiosidades_postadas")}
    pendentes = [c for c in itens if c["id"] not in feitos]
    if not pendentes:
        return None, 0
    hist = [r[0] for r in con.execute(
        "SELECT jogo FROM curiosidades_postadas ORDER BY postado_em DESC")]
    ciclo = destaques + ["outro"]
    vez = ciclo[len(hist) % len(ciclo)]
    if vez == "outro":
        outros = [c for c in pendentes if c["jogo"] not in destaques]
        if outros:
            def ultima_vez(jogo):
                return hist.index(jogo) if jogo in hist else 10 ** 6
            return max(outros, key=lambda c: ultima_vez(c["jogo"])), len(pendentes)
    else:
        da_vez = [c for c in pendentes if c["jogo"] == vez]
        if da_vez:
            return da_vez[0], len(pendentes)
    ultimo = hist[0] if hist else None  # sem item do jogo da vez: evita repetir o último jogo
    outros = [c for c in pendentes if c["jogo"] != ultimo]
    return (outros or pendentes)[0], len(pendentes)


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


# Buscas extras por jogo: fotos de pessoas jogando, eventos e coleções (Wikimedia Commons, licença livre)
BUSCAS_JOGO = {
    "Pokémon": ["Pokémon Trading Card Game players", "Pokémon World Championships", "Pokémon cards collection"],
    "Magic": ["Magic: The Gathering players", "Magic The Gathering tournament", "Magic The Gathering cards"],
    "Yu-Gi-Oh!": ["Yu-Gi-Oh! tournament", "Yu-Gi-Oh! players", "Yu-Gi-Oh! cards"],
    "One Piece": ["One Piece Card Game", "One Piece cosplay", "trading card game tournament"],
    "Lorcana": ["Disney Lorcana", "Lorcana cards", "trading card game players"],
    "Digimon": ["Digimon card game", "Digimon cosplay", "trading card game players"],
}
GERAIS = ["trading card game players", "collectible card game tournament", "trading cards collection"]


def preparar(cfg, con, itens):
    c, restantes = escolher(con, itens)
    if not c:
        return None, 0
    n = len(carrossel._frases(c["texto"], limite=110)) + 2
    termos = ([c["busca_imagem"]] if c.get("busca_imagem") else []) + c.get("buscas_imagem", []) \
        + BUSCAS_JOGO.get(c["jogo"], []) + GERAIS
    fotos = imagens.buscar_commons_varias(termos, n)
    cartas = []
    for k in c.get("cartas_oficiais", []):  # só imagens de fonte OFICIAL, com crédito
        img = imagens.baixar(k["url"])
        if img is not None:
            cartas.append({"imagem": img, "credito": f"Imagem: {k['credito']}"})
    slides, creditos = carrossel.carrossel_curiosidade(c, fotos, BASE / "imagens", cartas)
    dados = {"item": c, "slides": [str(s) for s in slides], "creditos": creditos}
    PREPARADA.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    return dados, restantes


AGENDA = BASE / "agenda.yaml"


def post_da_agenda(con, janela_horas=1):
    """Post planejado (ex.: Top 10) cujo horário chegou. Fica em agenda.yaml e as imagens em imagens/.

    Formato de cada item: quando ("2026-11-02T09:00", horário de Brasília), id, jogo, slides (nomes em
    imagens/), legenda_telegram, legenda_instagram. Se nada estiver na hora, segue a curiosidade normal.
    """
    from datetime import datetime, timedelta, timezone
    if not AGENDA.exists():
        return None
    br = timezone(timedelta(hours=-3))
    agora_br = datetime.now(br)
    feitos = {r[0] for r in con.execute("SELECT id FROM curiosidades_postadas")}
    for it in yaml.safe_load(AGENDA.read_text(encoding="utf-8")) or []:
        quando = datetime.fromisoformat(it["quando"]).replace(tzinfo=br)
        if it["id"] in feitos or not (quando <= agora_br < quando + timedelta(hours=janela_horas)):
            continue
        slides = [str(BASE / "imagens" / n) for n in it["slides"]]
        if all((BASE / "imagens" / n).exists() for n in it["slides"]):
            return {"item": {"id": it["id"], "jogo": it.get("jogo", "TCG")}, "slides": slides,
                    "creditos": [], "legendas": {"telegram": it["legenda_telegram"],
                                                  "instagram": it["legenda_instagram"]}}
    return None


DIAS = ["seg", "ter", "qua", "qui", "sex", "sab", "dom"]
PADRAO_HORARIOS = {"seg": [18, 19, 20], "ter": [15, 17, 19], "qua": [8, 12, 18], "qui": [9, 18, 20],
                   "sex": [6, 20, 22], "sab": [20, 21, 22], "dom": [20, 21, 22]}


def horario_do_dia(cfg, agora=None):
    """Horário (hora cheia, Brasília) do slot atual, ou None se agora não é um dos 3 melhores horários."""
    from datetime import datetime, timedelta, timezone
    agora = agora or datetime.now(timezone(timedelta(hours=-3)))
    tab = (cfg.get("instagram", {}) or {}).get("horarios_feed") or PADRAO_HORARIOS
    return agora.hour if agora.hour in tab.get(DIAS[agora.weekday()], []) else None


def texto_post(dados, cfg, rede):
    if dados.get("legendas"):
        return dados["legendas"][rede]
    return legenda(dados["item"], dados["creditos"], cfg, rede)


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
    ap.add_argument("--forcar", action="store_true", help="roda fora dos melhores horários (teste manual)")
    a = ap.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(),
                  logging.FileHandler(BASE / "bot.log", encoding="utf-8")])

    with open(a.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if not (a.forcar or a.simular or a.etapa == "publicar") and horario_do_dia(cfg) is None:
        log.info("Fora dos 3 melhores horários de hoje: nada a fazer")
        return
    arq = BASE / cfg.get("curiosidades", {}).get("arquivo", "curiosidades.yaml")
    with open(arq, encoding="utf-8") as f:
        itens = [c for c in (yaml.safe_load(f) or [])
                 if c.get("fonte_url") and c.get("verificado_em")]

    con = abrir_banco(BASE / cfg.get("banco_curiosidades", "curiosidades.db"))
    preparar_banco(con)

    planejado = post_da_agenda(con) if a.etapa in ("tudo", "preparar") else None
    if planejado:
        PREPARADA.write_text(json.dumps(planejado, ensure_ascii=False, indent=1), encoding="utf-8")
        log.info("Post planejado da agenda: %s", planejado["item"]["id"])
        if a.etapa == "preparar" or a.simular:
            return
    elif a.etapa in ("tudo", "preparar"):
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
    if cfg["telegram"].get("ativo") and not cfg["telegram"].get("so_promocoes"):  # Telegram = só promoções
        try:
            publicar.telegram_album(cfg, dados["slides"], texto_post(dados, cfg, "telegram"))
            ok = True
        except Exception as e:
            log.error("Telegram falhou: %s", e)
    if cfg["instagram"].get("ativo"):
        try:
            publicar.instagram_carrossel(cfg, dados["slides"], texto_post(dados, cfg, "instagram"))
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
