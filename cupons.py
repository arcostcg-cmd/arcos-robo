#!/usr/bin/env python3
"""Sistema de Promoções: caçador de cupons.

1. Lê as páginas OFICIAIS de cupom e promoção das lojas aprovadas
   (`paginas_cupom` em cada loja do config) e procura códigos de cupom.
2. Todo código novo vira "candidato" e o admin recebe um aviso no Telegram.
   Cupom candidato NUNCA vai para post: um cupom só é confiável depois de testado.
3. O admin testa no carrinho da loja e responde ao bot:
     /cupom_ok CODIGO 10 30/11      -> testado, 10% off, válido até 30/11
     /cupom_ok CODIGO 10 30/11 199  -> idem, com pedido mínimo de R$ 199
     /cupom_ruim CODIGO             -> não funcionou, descartado
     /cupons                        -> lista os cupons ativos e os candidatos
4. Cupom aprovado entra sozinho nos posts das promoções daquela loja até vencer
   ou até precisar de novo teste (`regras.cupom_teste_dias`).

Nunca copia cupom de site agregador: só páginas da própria loja.

Uso:
  python cupons.py              # procura cupons novos e lê os comandos do admin
  python cupons.py --listar     # mostra cupons ativos e candidatos
"""
import argparse
import logging
import os
import re
from datetime import date

import requests
import yaml

from bot import BASE, UA, abrir_banco, agora, iso

log = logging.getLogger("cupons")

# "cupom ARCOS10", "use o código: BOOSTER15", "coupon code TCG20"
CODIGO_RE = re.compile(
    r"(?i:cupom|cupon|c[oó]digo|coupon|code|use)\s*(?i:de desconto)?\s*[:\-–]?\s*"
    r"[\"'“”«]?([A-Z][A-Z0-9]{3,19})\b")
PCT_RE = re.compile(r"(\d{1,2})\s?%")
NAO_CODIGO = {"OFF", "FRETE", "GRATIS", "GRÁTIS", "DESCONTO", "AQUI", "PROMO", "HTTPS",
              "PARA", "COMPRA", "PRIMEIRA", "CLIQUE", "COPIAR", "APLICAR"}


def preparar_banco(con):
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS cupons(
            loja TEXT, codigo TEXT, percentual REAL, minimo REAL, valido_ate TEXT,
            status TEXT, testado_em TEXT, origem TEXT, trecho TEXT, visto_em TEXT,
            PRIMARY KEY (loja, codigo));
        CREATE TABLE IF NOT EXISTS telegram_offset(id INTEGER PRIMARY KEY, valor INTEGER);
        """)
    con.commit()


def limpar_html(pagina):
    pagina = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", pagina, flags=re.S | re.I)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", pagina))


def achar_cupons(texto):
    """Devolve [(codigo, percentual_ou_None, trecho)] encontrados no texto."""
    achados, vistos = [], set()
    for m in CODIGO_RE.finditer(texto):
        codigo = m.group(1).upper()
        if codigo in vistos or codigo in NAO_CODIGO or codigo.isdigit():
            continue
        if not re.search(r"\d", codigo) and len(codigo) < 6:
            continue  # palavra comum em caixa alta, não parece código
        vistos.add(codigo)
        trecho = texto[max(0, m.start() - 80): m.end() + 80].strip()
        pct = PCT_RE.search(trecho)
        achados.append((codigo, float(pct.group(1)) if pct else None, trecho[:200]))
    return achados


def descobrir(cfg, con, avisar=True):
    import publicar
    novos = []
    for loja in cfg.get("lojas", []):
        if not loja.get("aprovada"):
            continue
        for url in loja.get("paginas_cupom", []) or []:
            try:
                r = requests.get(url, headers=UA, timeout=30)
                r.raise_for_status()
            except requests.RequestException as e:
                log.warning("Cupons: não consegui ler %s: %s", url, e)
                continue
            for codigo, pct, trecho in achar_cupons(limpar_html(r.text)):
                existe = con.execute("SELECT 1 FROM cupons WHERE loja=? AND codigo=?",
                                     (loja["id"], codigo)).fetchone()
                if existe:
                    continue
                con.execute("INSERT INTO cupons VALUES (?,?,?,?,?,?,?,?,?,?)",
                            (loja["id"], codigo, pct, None, None, "candidato", None, url,
                             trecho, iso(agora())))
                novos.append((loja, codigo, pct, url))
    con.commit()
    if novos and avisar:
        linhas = [f"• {c} na {l['nome']}" + (f" (~{p:.0f}%)" if p else "") + f"\n  {u}"
                  for l, c, p, u in novos[:10]]
        publicar.avisar_admin(cfg, "🎟️ Cupons novos para TESTAR (não vão para post antes disso):\n"
                              + "\n".join(linhas)
                              + "\n\nFuncionou? Responda: /cupom_ok CODIGO % dd/mm [mínimo]"
                              + "\nNão funcionou? /cupom_ruim CODIGO")
    log.info("Cupons: %d candidatos novos", len(novos))
    return novos


def _data_br(texto):
    """'30/11' ou '30/11/2026' -> date. Sem ano: o próximo 30/11."""
    partes = [int(p) for p in texto.split("/")]
    hoje = agora().date()
    if len(partes) == 3:
        ano = partes[2] + (2000 if partes[2] < 100 else 0)
        return date(ano, partes[1], partes[0])
    d = date(hoje.year, partes[1], partes[0])
    return d if d >= hoje else date(hoje.year + 1, partes[1], partes[0])


def aplicar_comando(con, texto):
    """Executa um comando do admin. Devolve a resposta (ou None se não for comando)."""
    partes = texto.strip().split()
    if not partes:
        return None
    cmd = partes[0].split("@")[0].lower()
    if cmd == "/cupom_ok" and len(partes) >= 4:
        codigo = partes[1].upper()
        try:
            pct = float(partes[2].replace("%", "").replace(",", "."))
            validade = _data_br(partes[3])
            minimo = float(partes[4].replace(",", ".")) if len(partes) > 4 else None
        except ValueError:
            return "Formato: /cupom_ok CODIGO 10 30/11 [mínimo]"
        n = con.execute("UPDATE cupons SET status='ok', percentual=?, valido_ate=?, minimo=?, "
                        "testado_em=? WHERE codigo=?",
                        (pct, validade.isoformat(), minimo, agora().date().isoformat(), codigo)).rowcount
        con.commit()
        return (f"✅ Cupom {codigo} aprovado: {pct:.0f}% até {validade:%d/%m}"
                + (f", mínimo R$ {minimo:.2f}" if minimo else "") if n else
                f"Não achei o cupom {codigo} entre os candidatos.")
    if cmd == "/cupom_ruim" and len(partes) >= 2:
        codigo = partes[1].upper()
        n = con.execute("UPDATE cupons SET status='ruim', testado_em=? WHERE codigo=?",
                        (agora().date().isoformat(), codigo)).rowcount
        con.commit()
        return f"🗑️ Cupom {codigo} descartado." if n else f"Não achei o cupom {codigo}."
    if cmd == "/cupons":
        linhas = [f"{s.upper()}: {c} ({l})" + (f" {p:.0f}% até {v}" if p and v else "")
                  for l, c, p, v, s in con.execute(
                      "SELECT loja, codigo, percentual, valido_ate, status FROM cupons "
                      "WHERE status IN ('ok','candidato') ORDER BY status, loja")]
        return "\n".join(linhas) or "Nenhum cupom ativo ou candidato."
    return None


def ler_comandos(cfg, con):
    """Lê as mensagens novas do admin para o bot e responde."""
    import publicar
    token, admin = os.environ.get("TELEGRAM_TOKEN"), str(cfg["telegram"].get("admin_chat", ""))
    if not token or not admin:
        return
    linha = con.execute("SELECT valor FROM telegram_offset WHERE id=1").fetchone()
    offset = linha[0] if linha else 0
    try:
        r = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=30,
                         params={"offset": offset, "timeout": 0, "allowed_updates": '["message"]'})
        updates = r.json().get("result", [])
    except Exception as e:
        log.warning("Cupons: não consegui ler comandos: %s", e)
        return
    for u in updates:
        offset = max(offset, u["update_id"] + 1)
        msg = u.get("message") or {}
        if str(msg.get("chat", {}).get("id")) != admin:
            continue  # só o admin manda no robô
        resposta = aplicar_comando(con, msg.get("text", ""))
        if resposta:
            publicar.avisar_admin(cfg, resposta)
    con.execute("INSERT INTO telegram_offset VALUES (1, ?) ON CONFLICT(id) DO UPDATE "
                "SET valor=excluded.valor", (offset,))
    con.commit()


def cupons_aprovados(con):
    """Cupons testados pelo admin, no formato que afiliados.cupom_valido entende."""
    preparar_banco(con)
    return [{"loja": l, "codigo": c, "percentual": p, "minimo": m, "valido_ate": v,
             "testado_em": t, "descricao": f"{p:.0f}% de desconto" if p else "desconto extra"}
            for l, c, p, m, v, t in con.execute(
                "SELECT loja, codigo, percentual, minimo, valido_ate, testado_em "
                "FROM cupons WHERE status='ok'")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(BASE / "config.yaml"))
    ap.add_argument("--listar", action="store_true")
    ap.add_argument("--simular", action="store_true", help="procura cupons sem avisar nem ler comandos")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.StreamHandler(),
                                  logging.FileHandler(BASE / "bot.log", encoding="utf-8")])
    with open(a.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    con = abrir_banco(BASE / cfg.get("banco", "precos.db"))
    preparar_banco(con)
    if a.listar:
        print(aplicar_comando(con, "/cupons"))
        return
    if not a.simular:
        ler_comandos(cfg, con)
    for loja, codigo, pct, url in descobrir(cfg, con, avisar=not a.simular):
        if a.simular:
            print(f"Candidato: {codigo} na {loja['nome']} ({pct or '?'}%) — {url}")


if __name__ == "__main__":
    main()
