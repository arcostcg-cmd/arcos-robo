#!/usr/bin/env python3
"""Radar de concorrentes: lê canais PÚBLICOS do Telegram e compara preços.

O que faz:
  - abre a página pública https://t.me/s/<canal> (sem login, sem entrar em grupo);
  - abre páginas PÚBLICAS de promoção em sites (`radar.sites`), como uma página
    de ofertas aberta, e lê os trechos com preço em R$;
  - extrai de cada post o preço em R$ e tenta casar com os produtos do Arcos;
  - se um concorrente anunciou um preço menor que o melhor preço confirmado do
    Arcos, avisa o admin para o Caçador de Ofertas checar a loja;
  - gera um relatório semanal: quem postou o quê, quando e por quanto.

O que NÃO faz (de propósito):
  - não copia texto, imagem nem link de concorrente;
  - não posta nada sozinho: o Arcos só posta depois de conferir na loja,
    com o próprio link;
  - não lê grupos de WhatsApp nem Instagram (os termos de uso proíbem robôs).

Uso:
  python radar.py              # varre os canais e alerta
  python radar.py --relatorio  # resumo dos últimos 7 dias
"""
import argparse
import html as html_lib
import logging
import re
import unicodedata
from datetime import timedelta

import requests
import yaml

from bot import BASE, UA, abrir_banco, agora, dominio, iso, na_lista_negra, para_float, reais

log = logging.getLogger("radar")
TEXTO_RE = re.compile(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', re.S)
DATA_RE = re.compile(r'<time[^>]*datetime="([^"]+)"')
PRECO_RE = re.compile(r"R\$\s?(\d{1,3}(?:\.\d{3})*(?:,\d{2})?|\d+(?:,\d{2})?)")


def normalizar(texto):
    t = unicodedata.normalize("NFKD", texto.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]+", " ", t)


def limpar_html(trecho):
    trecho = re.sub(r"<br\s*/?>", "\n", trecho)
    return html_lib.unescape(re.sub(r"<[^>]+>", "", trecho)).strip()


def ler_canal(canal):
    """Devolve [(id_post, texto, data_iso)] dos posts recentes do canal público."""
    url = f"https://t.me/s/{canal.lstrip('@')}"
    try:
        r = requests.get(url, headers=UA, timeout=30)
        r.raise_for_status()
    except requests.RequestException as e:
        log.warning("Radar: não consegui ler %s: %s", canal, e)
        return []
    return extrair_posts(r.text)


def ler_site(url):
    """Página pública de promoções: cada preço em R$ vira um "post" com o texto em volta."""
    try:
        r = requests.get(url, headers=UA, timeout=30)
        r.raise_for_status()
    except requests.RequestException as e:
        log.warning("Radar: não consegui ler o site %s: %s", url, e)
        return []
    return trechos_site(url, r.text)


def trechos_site(url, pagina):
    import hashlib
    pagina = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", pagina, flags=re.S | re.I)
    texto = re.sub(r"\s+", " ", html_lib.unescape(re.sub(r"<[^>]+>", " ", pagina)))
    posts, vistos, fim_anterior = [], set(), 0
    for m in PRECO_RE.finditer(texto):  # cada trecho vai do preço anterior até este preço
        trecho = texto[max(fim_anterior, m.start() - 200): m.end()].strip()
        fim_anterior = m.end()
        chave = hashlib.sha1(normalizar(trecho).encode()).hexdigest()[:16]
        if chave not in vistos:
            vistos.add(chave)
            posts.append((f"site:{dominio(url)}:{chave}", trecho, ""))
    return posts


def extrair_posts(pagina):
    """Separa a página em posts (um bloco por data-post) para não misturar posts."""
    posts = []
    for bloco in pagina.split('data-post="')[1:]:
        pid = bloco.split('"', 1)[0]
        texto = TEXTO_RE.search(bloco)
        data = DATA_RE.search(bloco)
        if texto:
            posts.append((pid, limpar_html(texto.group(1)), data.group(1) if data else ""))
    return posts


def casar_produto(texto, produtos):
    """Acha o produto do Arcos citado no post pelas palavras-chave (`palavras` no config)."""
    t = normalizar(texto)
    melhor, pontos = None, 0
    for p in produtos:
        chaves = p.get("palavras") or normalizar(p["nome"]).split()
        chaves = [normalizar(k).strip() for k in chaves if len(k) > 2]
        acertos = sum(1 for k in chaves if k and k in t)
        exigido = max(2, int(len(chaves) * 0.6))
        if acertos >= exigido and acertos > pontos:
            melhor, pontos = p, acertos
    return melhor


def preparar_banco(con):
    con.execute(
        "CREATE TABLE IF NOT EXISTS radar(id_post TEXT PRIMARY KEY, canal TEXT, "
        "produto TEXT, preco REAL, resumo TEXT, postado_em TEXT, lido_em TEXT)")
    con.commit()


def melhor_preco_arcos(con, produto):
    """Menor preço em estoque lido pelo robô nas últimas 24 horas."""
    desde = iso(agora() - timedelta(hours=24))
    linha = con.execute(
        "SELECT MIN(preco), loja FROM precos WHERE produto=? AND em_estoque=1 "
        "AND visto_em>=?", (produto, desde)).fetchone()
    return linha if linha and linha[0] is not None else (None, None)


def varrer(cfg, con, simular=False):
    import publicar
    preparar_banco(con)
    canais = cfg.get("radar", {}).get("canais", [])
    produtos = cfg.get("produtos", [])
    alertas, novos = [], 0
    fontes = [(c, ler_canal) for c in canais] + \
             [(u, ler_site) for u in cfg.get("radar", {}).get("sites", []) or []]
    for fonte, ler in fontes:
        canal = dominio(fonte) if ler is ler_site else fonte
        for pid, texto, data in ler(fonte):
            if con.execute("SELECT 1 FROM radar WHERE id_post=?", (pid,)).fetchone():
                continue
            precos = []
            for bruto in PRECO_RE.findall(texto):
                try:
                    precos.append(para_float(bruto))
                except ValueError:
                    pass
            prod = casar_produto(texto, produtos)
            preco = min(precos) if precos else None
            con.execute("INSERT INTO radar VALUES (?,?,?,?,?,?,?)", (
                pid, canal, prod["nome"] if prod else None, preco,
                texto.replace("\n", " ")[:140], data, iso(agora())))
            novos += 1
            for link in set(re.findall(r"https?://[^\s\"'<>]+", texto)):
                golpe = na_lista_negra(cfg, link)
                if golpe:
                    alertas.append(f"• ⚠️ {canal} divulgou link da lista negra: {dominio(link)} "
                                   f"({golpe}). Possível alerta de golpe para os seguidores.")
            if prod and preco:
                nosso, loja = melhor_preco_arcos(con, prod["nome"])
                if nosso is None or preco < nosso * 0.99:
                    alertas.append(
                        f"• {canal}: {prod['nome']} por {reais(preco)}"
                        + (f" (nosso melhor: {reais(nosso)} na {loja})" if nosso else
                           " (não temos preço recente)"))
    con.commit()
    log.info("Radar: %d posts novos, %d alertas", novos, len(alertas))
    if alertas:
        msg = ("🛰️ Radar Arcos: preço menor ou link suspeito nos concorrentes. Confira se a loja é "
               "aprovada e o preço é real antes de postar com o NOSSO link:\n" + "\n".join(alertas[:15]))
        if simular:
            print(msg)
        else:
            publicar.avisar_admin(cfg, msg)
    return alertas


def relatorio(con, dias=7):
    preparar_banco(con)
    desde = iso(agora() - timedelta(days=dias))
    print(f"Radar: últimos {dias} dias")
    for canal, total, com_produto in con.execute(
            "SELECT canal, COUNT(*), SUM(produto IS NOT NULL) FROM radar "
            "WHERE lido_em>=? GROUP BY canal ORDER BY 2 DESC", (desde,)):
        print(f"• {canal}: {total} posts, {com_produto or 0} de produtos que o Arcos acompanha")
    print("\nMenores preços vistos nos concorrentes:")
    for prod, preco, canal in con.execute(
            "SELECT produto, MIN(preco), canal FROM radar WHERE produto IS NOT NULL "
            "AND preco IS NOT NULL AND lido_em>=? GROUP BY produto", (desde,)):
        nosso, _ = melhor_preco_arcos(con, prod)
        comp = f" | Arcos: {reais(nosso)}" if nosso else ""
        print(f"• {prod}: {reais(preco)} ({canal}){comp}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(BASE / "config.yaml"))
    ap.add_argument("--relatorio", action="store_true")
    ap.add_argument("--simular", action="store_true")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.StreamHandler(),
                                  logging.FileHandler(BASE / "bot.log", encoding="utf-8")])
    with open(a.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    con = abrir_banco(BASE / cfg.get("banco", "precos.db"))
    if a.relatorio:
        relatorio(con)
    elif cfg.get("radar", {}).get("ativo"):
        varrer(cfg, con, a.simular)
    else:
        log.info("Radar desligado (radar.ativo: false)")


if __name__ == "__main__":
    main()
