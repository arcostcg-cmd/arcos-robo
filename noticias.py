#!/usr/bin/env python3
"""Notícias de TCG do mundo todo em stories e posts, automaticamente.

Fluxo:
  1. Lê os feeds (RSS/Atom) das fontes cadastradas: oficiais, imprensa
     especializada e fóruns públicos (Reddit etc.).
  2. Separa o que é relevante (coleção nova, lançamento, banimento, torneio...).
  3. Escreve título e resumo em português com uma IA, SÓ com fatos do texto
     original, e confere por código que todo número do resumo está na fonte.
     Se a conferência falhar, a notícia é descartada.
  4. Marca com selo RUMOR tudo que vier de fórum ou falar em vazamento.
  5. Gera story (1080×1920) e, para o destaque do dia, um carrossel.
  6. Posta: stories no Instagram, fotos no canal do Telegram.

Nunca copia o texto da notícia nem usa imagem da fonte: o design é do Montop,
o texto é resumo próprio e a fonte vai com link em todo post.

Uso:
  python noticias.py --simular              # lê, resume e gera imagens sem postar
  python noticias.py --etapa preparar       # GitHub Actions: gera e salva a fila
  python noticias.py --etapa publicar       # posta a fila
  python noticias.py --testar-fontes        # mostra quais feeds respondem
"""
import argparse
import email.utils
import html as html_lib
import json
import logging
import os
import re
from pathlib import Path
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

import requests
import yaml

from bot import BASE, UA, abrir_banco, agora, iso

log = logging.getLogger("noticias")
FILA = BASE / "noticias_fila.json"
RUMOR_RE = re.compile(r"\b(leak|leaked|rumou?r|spoiler|datamin\w*|vazamento|vazad[oa]|boato|"
                      r"unconfirmed|n[aã]o confirmad[oa])\b", re.I)
PESO_TIPO = {"oficial": 3, "imprensa": 2, "forum": 1}


# ------------------------------------------------------------ leitura dos feeds

def _texto(el, *nomes):
    for n in nomes:
        achado = el.find(n)
        if achado is not None and (achado.text or achado.get("href")):
            return (achado.text or achado.get("href") or "").strip()
    return ""


def _data(valor):
    if not valor:
        return None
    try:
        return email.utils.parsedate_to_datetime(valor)
    except (TypeError, ValueError):
        pass
    try:
        return datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except ValueError:
        return None


def limpar(texto):
    texto = re.sub(r"<[^>]+>", " ", html_lib.unescape(texto or ""))
    return re.sub(r"\s+", " ", texto).strip()


def ler_feed(xml_texto):
    """Lê RSS 2.0 ou Atom. Devolve [{titulo, link, data, resumo}]."""
    raiz = ET.fromstring(xml_texto)
    ns = {"a": "http://www.w3.org/2005/Atom"}
    itens = []
    for it in raiz.iter("item"):  # RSS
        img = None
        for tag in ("{http://search.yahoo.com/mrss/}content", "{http://search.yahoo.com/mrss/}thumbnail", "enclosure"):
            el = it.find(tag)
            if el is not None and el.get("url") and (tag != "enclosure" or "image" in (el.get("type") or "")):
                img = el.get("url")
                break
        itens.append({"titulo": limpar(_texto(it, "title")), "link": _texto(it, "link"),
                      "data": _data(_texto(it, "pubDate")),
                      "resumo": limpar(_texto(it, "description"))[:1500], "imagem": img})
    for it in raiz.iter("{http://www.w3.org/2005/Atom}entry"):  # Atom (Reddit usa Atom)
        link = it.find("a:link", ns)
        itens.append({"titulo": limpar(_texto(it, "{http://www.w3.org/2005/Atom}title")),
                      "link": link.get("href") if link is not None else "",
                      "data": _data(_texto(it, "{http://www.w3.org/2005/Atom}updated",
                                           "{http://www.w3.org/2005/Atom}published")),
                      "resumo": limpar(_texto(it, "{http://www.w3.org/2005/Atom}content",
                                              "{http://www.w3.org/2005/Atom}summary"))[:1500]})
    return [i for i in itens if i["titulo"] and i["link"]]


class FonteBloqueou(Exception):
    """A fonte pediu calma (HTTP 429/403): pausa a fonte por um tempo."""


def baixar_feed(fonte):
    try:
        r = requests.get(fonte["url"], headers=UA, timeout=30)
        if r.status_code in (429, 403):
            raise FonteBloqueou(f"HTTP {r.status_code}")
        r.raise_for_status()
        return ler_feed(r.content)
    except FonteBloqueou:
        raise
    except Exception as e:
        log.warning("Fonte %s indisponível: %s", fonte["nome"], e)
        return None


def ler_fonte_com_calma(con, fonte):
    """Respeita o intervalo da fonte e pausa 1 hora quem bloquear (Reddit faz isso)."""
    linha = con.execute("SELECT ultima_leitura, pausada_ate FROM fontes_estado WHERE nome=?",
                        (fonte["nome"],)).fetchone()
    agora_iso = iso(agora())
    if linha:
        ultima, pausada = linha
        if pausada and pausada > agora_iso:
            return []
        intervalo = fonte.get("intervalo_minutos", 10)
        if ultima and ultima > iso(agora() - timedelta(minutes=intervalo - 1)):
            return []
    try:
        itens = baixar_feed(fonte)
    except FonteBloqueou as e:
        log.warning("Fonte %s bloqueou (%s): pausada por 1 hora", fonte["nome"], e)
        con.execute("INSERT INTO fontes_estado VALUES (?,?,?) ON CONFLICT(nome) DO UPDATE "
                    "SET pausada_ate=excluded.pausada_ate",
                    (fonte["nome"], agora_iso, iso(agora() + timedelta(hours=1))))
        con.commit()
        return []
    con.execute("INSERT INTO fontes_estado VALUES (?,?,NULL) ON CONFLICT(nome) DO UPDATE "
                "SET ultima_leitura=excluded.ultima_leitura, pausada_ate=NULL",
                (fonte["nome"], agora_iso))
    con.commit()
    return itens or []


# ------------------------------------------------------------ relevância e selo

def relevante(item, palavras):
    alvo = f"{item['titulo']} {item['resumo']}".lower()
    return any(p.lower() in alvo for p in palavras)


def eh_rumor(item, fonte):
    """Fórum e blog de fãs são sempre rumor; qualquer fonte que fale em vazamento também."""
    return fonte.get("tipo") in ("forum", "blog") or \
        bool(RUMOR_RE.search(f"{item['titulo']} {item['resumo']}"))


def eh_furo(item, fonte, cfg):
    """Furo = notícia confirmada e importante, publicada na fonte há pouco tempo.

    Sai em story E no feed, fora do limite diário, sem nenhum destaque de "furo"
    na arte ou no texto. Nunca é rumor.
    """
    f = cfg.get("noticias", {}).get("furo", {})
    if not f.get("ativo", True) or not item["data"] or eh_rumor(item, fonte):
        return False
    if fonte.get("tipo") not in f.get("tipos", ["oficial", "imprensa"]):
        return False
    idade_min = (agora() - item["data"]).total_seconds() / 60
    if idade_min > f.get("janela_minutos", 90):
        return False
    return relevante(item, f.get("palavras", []))


def eh_furo_rumor(item, fonte, cfg):
    """Furo de rumor = vazamento ou boato quente de fórum, fã ou blog, de até 90 minutos.

    Sai em story fora do limite diário (e no feed, se `tambem_no_feed`), SEMPRE
    com "Rumor:" no título, selo na arte e aviso na legenda.
    """
    f = cfg.get("noticias", {}).get("furo_rumor", {})
    if not f.get("ativo", True) or not item["data"] or not eh_rumor(item, fonte):
        return False
    idade_min = (agora() - item["data"]).total_seconds() / 60
    if idade_min > f.get("janela_minutos", 90):
        return False
    return relevante(item, f.get("palavras", []))


def pontuar(item, fonte):
    """Oficial pesa mais; dentro do mesmo tipo, vence a mais recente."""
    idade_h = (agora() - item["data"]).total_seconds() / 3600 if item["data"] else 24
    return PESO_TIPO.get(fonte.get("tipo"), 1) * 100 - idade_h


# ------------------------------------------------------------ resumo com IA + checagem

NUM_RE = re.compile(r"\d+(?:[.,]\d+)*")


def numeros(texto):
    return {re.sub(r"[.,]", "", n) for n in NUM_RE.findall(texto or "")}


def numeros_conferem(resumo_pt, original):
    """Todo número escrito pela IA precisa existir no texto original."""
    return numeros(resumo_pt) <= numeros(original)


PROMPT = """Você é o editor de notícias do Montop TCG, canal brasileiro de informação para fãs de cartas colecionáveis.
Escreva em português do Brasil correto, com acentos, com suas palavras, a partir APENAS do texto abaixo.
Tom: jornalístico, claro e neutro, como uma agência de notícias. Sem exclamação, sem caixa alta,
sem emoji e sem palavras como urgente, bomba, furo, exclusivo, imperdível, chocante.
Regras: não acrescente nenhum fato, número, data ou nome que não esteja no texto; não especule;
se o texto for especulação ou vazamento, diga isso com clareza ("segundo ...", "ainda sem confirmação oficial");
mantenha nomes de coleções e cartas como no original; não copie frases inteiras;
se o texto não tiver informação suficiente, responda {{"pular": true}}.
Responda só um JSON: {{"titulo": "até 8 palavras, frase informativa", "resumo": "até 2 frases completas, terminadas em ponto", "jogo": "{jogo}"}}

FONTE: {fonte}
TÍTULO ORIGINAL: {titulo}
TEXTO: {resumo}"""


PROIBIDAS = re.compile(r"\b(urgente|bomba|furo|exclusiv[oa]|imperd[ií]vel|chocante|inacredit[aá]vel|"
                       r"corre+|surreal|absurd[oa])\b", re.I)


def texto_ok(titulo, resumo):
    """Confere a qualidade do texto antes de publicar. Devolve (titulo, resumo) ou None."""
    titulo = re.sub(r"\s+", " ", titulo).strip().rstrip(".").replace("!", "")
    resumo = re.sub(r"\s+", " ", resumo).strip().replace("!", ".")
    if PROIBIDAS.search(f"{titulo} {resumo}"):
        return None
    letras = [c for c in titulo if c.isalpha()]
    if letras and sum(c.isupper() for c in letras) / len(letras) > 0.5:
        return None  # título gritado em caixa alta
    if not (3 <= len(titulo.split()) <= 12) or len(resumo) < 25:
        return None
    if not resumo.endswith((".", "?", '"', "”")):
        resumo += "."
    return titulo, resumo


class LimiteIA(Exception):
    """A IA recusou por limite de uso (HTTP 429): para agora e tenta na próxima rodada."""


_MODELO_GEMINI = None


def escolher_modelo_gemini(modelos):
    """Escolhe o modelo 'flash' estável mais novo que gera texto."""
    bons = []
    for m in modelos:
        nome = m.get("name", "").split("/")[-1]
        metodos = m.get("supportedGenerationMethods", [])
        if "generateContent" not in metodos or "flash" not in nome:
            continue
        if any(x in nome for x in ("preview", "exp", "image", "tts", "live", "audio", "thinking")):
            continue
        versao = [int(n) for n in re.findall(r"\d+", nome)[:2]] or [0]
        bons.append((versao, "lite" not in nome, nome))
    return max(bons)[2] if bons else None


def modelo_gemini(ia):
    global _MODELO_GEMINI
    if ia.get("modelo"):
        return ia["modelo"]
    if not _MODELO_GEMINI:
        r = requests.get("https://generativelanguage.googleapis.com/v1beta/models",
                         params={"key": os.environ["GEMINI_API_KEY"], "pageSize": 200}, timeout=30)
        r.raise_for_status()
        _MODELO_GEMINI = escolher_modelo_gemini(r.json().get("models", []))
        log.info("Gemini: usando o modelo %s", _MODELO_GEMINI)
    if not _MODELO_GEMINI:
        raise RuntimeError("nenhum modelo Gemini 'flash' disponível; defina noticias.ia.modelo")
    return _MODELO_GEMINI


def regras_equipe():
    """Instruções fixas da equipe Montop (resumo da skill), enviadas como instrução de sistema."""
    arq = Path(__file__).resolve().parent / "equipe" / "regras-ia.md"
    return arq.read_text(encoding="utf-8") if arq.exists() else ""


def chamar_ia(cfg, prompt):
    ia = cfg.get("noticias", {}).get("ia", {})
    sistema = regras_equipe()
    prov = ia.get("provedor", "nenhum")
    if prov == "anthropic":
        r = requests.post("https://api.anthropic.com/v1/messages", timeout=60, headers={
            "x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01",
            "content-type": "application/json"}, json={
            "model": ia.get("modelo", "claude-haiku-5-5"), "max_tokens": 400,
            **({"system": sistema} if sistema else {}),
            "messages": [{"role": "user", "content": prompt}]})
        if r.status_code == 429:
            raise LimiteIA("limite da API atingido")
        r.raise_for_status()
        return r.json()["content"][0]["text"]
    if prov == "gemini":
        modelo = modelo_gemini(ia)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
        corpo = {"contents": [{"parts": [{"text": prompt}]}],
                 **({"systemInstruction": {"parts": [{"text": sistema}]}} if sistema else {}),
                 "generationConfig": {"temperature": 0.2}}
        r = requests.post(url, params={"key": os.environ["GEMINI_API_KEY"]}, timeout=120, json=corpo)
        if r.status_code == 429:
            raise LimiteIA("limite do Gemini atingido")
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]
    return None


def resumir(cfg, item, fonte):
    """Devolve {titulo, resumo} em PT conferido, ou None (descartar)."""
    original = f"{item['titulo']} {item['resumo']}"
    if fonte.get("idioma", "en") == "pt" and cfg.get("noticias", {}).get("ia", {}).get("provedor", "nenhum") == "nenhum":
        frase = re.split(r"(?<=[.!?])\s", item["resumo"])[0][:220] if item["resumo"] else ""
        bom = texto_ok(item["titulo"][:90], frase)
        return {"titulo": bom[0], "resumo": bom[1]} if bom else None
    try:
        bruto = chamar_ia(cfg, PROMPT.format(jogo=fonte.get("jogo", "TCG"), fonte=fonte["nome"],
                                             titulo=item["titulo"], resumo=item["resumo"][:1200]))
    except LimiteIA:
        raise
    except Exception as e:
        log.warning("IA falhou para %s: %s", item["link"], e)
        return None
    if not bruto:
        log.info("Sem IA configurada: notícia em outro idioma pulada (%s)", item["titulo"][:60])
        return None
    try:
        dados = json.loads(re.search(r"\{.*\}", bruto, re.S).group(0))
    except (AttributeError, json.JSONDecodeError):
        return None
    if dados.get("pular") or not dados.get("titulo") or not dados.get("resumo"):
        return None
    if not numeros_conferem(f"{dados['titulo']} {dados['resumo']}", original):
        log.warning("Resumo com número que não está na fonte; descartado: %s", item["link"])
        return None
    bom = texto_ok(dados["titulo"][:90], dados["resumo"][:300])
    if not bom:
        log.warning("Texto fora do padrão de qualidade; descartado: %s", item["link"])
        return None
    return {"titulo": bom[0], "resumo": bom[1]}


# ------------------------------------------------------------ banco

def preparar_banco(con):
    con.execute("CREATE TABLE IF NOT EXISTS noticias(link TEXT PRIMARY KEY, fonte TEXT, "
                "titulo TEXT, rumor INTEGER, formato TEXT, postado_em TEXT)")
    con.execute("CREATE TABLE IF NOT EXISTS fontes_estado(nome TEXT PRIMARY KEY, "
                "ultima_leitura TEXT, pausada_ate TEXT)")
    con.commit()


def postadas_hoje(con, formato):
    desde = iso(agora() - timedelta(hours=24))
    return con.execute("SELECT COUNT(*) FROM noticias WHERE formato=? AND postado_em>=?",
                       (formato, desde)).fetchone()[0]


# ------------------------------------------------------------ etapas

def preparar(cfg, con):
    import carrossel
    n = cfg.get("noticias", {})
    palavras = n.get("palavras_relevantes", [])
    max_story, max_post = n.get("max_stories_dia", 5), n.get("max_posts_dia", 1)
    janela = agora() - timedelta(hours=n.get("janela_horas", 24))
    candidatas = []
    for fonte in n.get("fontes", []):
        lidos = ler_fonte_com_calma(con, fonte)
        log.info("Fonte %s: %d itens lidos", fonte["nome"], len(lidos or []))
        for item in lidos or []:
            if item["data"] and item["data"].astimezone(timezone.utc) < janela.astimezone(timezone.utc):
                continue
            if con.execute("SELECT 1 FROM noticias WHERE link=?", (item["link"],)).fetchone():
                continue
            if fonte.get("tipo") != "oficial" and palavras and not relevante(item, palavras):
                continue
            candidatas.append((pontuar(item, fonte), item, fonte))
    candidatas.sort(key=lambda x: -x[0])
    log.info("Candidatas novas (24 h, relevantes, inéditas): %d", len(candidatas))

    vagas_story = max(0, max_story - postadas_hoje(con, "story"))
    vagas_post = max(0, max_post - postadas_hoje(con, "post"))
    vagas_furo = max(0, n.get("furo", {}).get("max_por_dia", 10) - postadas_hoje(con, "furo"))
    # furos primeiro: são os que não podem esperar
    fr = n.get("furo_rumor", {})
    vagas_furo_rumor = max(0, fr.get("max_por_dia", 10) - postadas_hoje(con, "furo_rumor"))

    bonus = cfg.get("destaque_jogos", {"Pokémon": 6, "One Piece": 6})  # vale como "X horas mais nova"

    def prioridade(c):  # furo confirmado, depois furo de rumor, depois o resto
        extra = bonus.get(c[2].get("jogo"), 0)
        return (0 if eh_furo(c[1], c[2], cfg) else 1 if eh_furo_rumor(c[1], c[2], cfg) else 2,
                -(c[0] + extra))
    candidatas.sort(key=prioridade)
    fila, vistos = [], set()
    chamadas, max_ia = 0, n.get("ia", {}).get("max_por_execucao", 10)

    def contar(fmt):
        return sum(1 for f in fila if f["formato"] == fmt)

    for _, item, fonte in candidatas:
        if chamadas >= max_ia:
            break
        furo = eh_furo(item, fonte, cfg) and contar("furo") < vagas_furo
        furo_rumor = not furo and eh_furo_rumor(item, fonte, cfg) and \
            contar("furo_rumor") < vagas_furo_rumor
        if not (furo or furo_rumor) and contar("story") >= vagas_story and contar("post") >= vagas_post:
            continue
        chave = re.sub(r"\W+", "", item["titulo"].lower())[:40]
        if chave in vistos:  # mesma notícia em duas fontes
            continue
        chamadas += 1
        try:
            texto = resumir(cfg, item, fonte)
        except LimiteIA as e:
            log.warning("%s: o resto fica para a próxima rodada", e)
            break
        if not texto:
            continue
        vistos.add(chave)
        nome_fonte = fonte["nome"]
        if nome_fonte.startswith("Google Notícias") and " - " in item["titulo"]:
            nome_fonte = item["titulo"].rsplit(" - ", 1)[1].strip()  # o veículo original, não o agregador
        noticia = {**texto, "jogo": fonte.get("jogo", "TCG"), "fonte": nome_fonte,
                   "link": item["link"], "rumor": eh_rumor(item, fonte),
                   "data": item["data"].isoformat() if item["data"] else iso(agora())}
        if noticia["rumor"] and not noticia["titulo"].lower().startswith("rumor"):
            noticia["titulo"] = f"Rumor: {noticia['titulo']}"  # sempre dito com todas as letras
        if furo:
            formato = "furo"  # story + post no feed, fora do limite
        elif furo_rumor:
            formato = "furo_rumor"  # story fora do limite, sempre marcado como rumor
        elif not noticia["rumor"] and contar("post") < vagas_post:
            formato = "post"
        elif contar("story") < vagas_story:
            formato = "story"
        else:
            continue
        no_feed = formato in ("post", "furo") or (formato == "furo_rumor" and fr.get("tambem_no_feed"))
        carta = imagem_oficial(item, fonte) if not noticia["rumor"] else None
        if carta is not None:
            credito = fonte.get("credito_imagem") or fonte["nome"]
            noticia["credito_imagem"] = credito
            story = [] if formato == "post" else [str(salvar_arte(carrossel.arte_carta_story(
                carta, noticia["titulo"], noticia["jogo"], credito, semente=chave), "story", chave))]
            feed = []
            if no_feed:
                capa = salvar_arte(carrossel.arte_carta_post(
                    carta, noticia["titulo"], noticia["jogo"], credito, semente=chave), "capa", chave)
                feed = [str(capa)] + [str(x) for x in carrossel.carrossel_noticia(noticia, BASE / "imagens")][1:]
        else:
            # imagem, imagem, imagem: fotos livres do Commons (pessoas, eventos, cartas do jogo)
            import curiosidades
            import imagens
            termos = curiosidades.BUSCAS_JOGO.get(noticia["jogo"], []) + curiosidades.GERAIS
            fotos = imagens.buscar_commons_varias(termos, 2) if n.get("fotos_commons") else []
            if fotos:
                noticia["credito_imagem"] = "foto ilustrativa, " + fotos[0]["credito"].replace("Foto: ", "")
            story = [] if formato == "post" else [str(carrossel.story_noticia(
                noticia, BASE / "imagens", fotos[0] if fotos else None))]
            feed = [str(x) for x in carrossel.carrossel_noticia(noticia, BASE / "imagens", fotos)] if no_feed else []
        fila.append({**noticia, "formato": formato, "story": story, "slides": feed or story})
    FILA.write_text(json.dumps(fila, ensure_ascii=False, indent=1), encoding="utf-8")
    log.info("Notícias na fila: %d", len(fila))
    return fila


OG_IMG_RE = re.compile(r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\'][^>]+content=["\']([^"\']+)', re.I)


def imagem_oficial(item, fonte):
    """Imagem REAL da carta/produto, só de fonte OFICIAL (ou com imagem: true no config).

    Rumor e vazamento nunca levam imagem: imagem vazada pode ser de material
    confidencial e as editoras derrubam posts com ela. Devolve PIL.Image ou None.
    """
    from io import BytesIO

    from PIL import Image
    if not (fonte.get("tipo") == "oficial" or fonte.get("imagem") is True):
        return None
    try:
        url = item.get("imagem")
        if not url:
            r = requests.get(item["link"], headers=UA, timeout=20)
            r.raise_for_status()
            m = OG_IMG_RE.search(r.text)
            url = m.group(1) if m else None
        if not url:
            return None
        if url.startswith("//"):
            url = "https:" + url
        r = requests.get(url, headers=UA, timeout=20)
        r.raise_for_status()
        img = Image.open(BytesIO(r.content))
        img.load()
        if min(img.size) < 300:  # pequena demais: melhor o design sem foto
            return None
        return img.convert("RGB")
    except Exception as e:
        log.info("Sem imagem oficial para %s: %s", item.get("link"), type(e).__name__)
        return None


def salvar_arte(img, tipo, chave):
    pasta = BASE / "imagens"
    pasta.mkdir(parents=True, exist_ok=True)
    caminho = pasta / f"carta-{tipo}-{chave[:30]}.jpg"
    img.save(caminho, "JPEG", quality=88)
    return caminho


def legenda(n, cfg, rede):
    selo = "🟠 RUMOR — não confirmado oficialmente\n\n" if n["rumor"] else ""
    tags = " ".join(cfg.get("noticias", {}).get("hashtags", []))
    if rede == "telegram":
        cred = f"\n📷 Imagem: {n['credito_imagem']}" if n.get("credito_imagem") else ""
        return (f"📰 {n['jogo'].upper()} | {selo}{n['titulo']}\n\n{n['resumo']}\n\n"
                f"Fonte: {n['fonte']}\n{n['link']}{cred}")
    return f"📰 {n['jogo']} | {selo}{n['titulo']}\n\n{n['resumo']}\n\nFonte: {n['fonte']}\n\n{tags}".strip()


def publicar_fila(cfg, con, simular):
    import publicar
    if not FILA.exists():
        return
    for n in json.loads(FILA.read_text(encoding="utf-8")):
        if simular:
            arquivos = n.get("story", []) + [s for s in n["slides"] if s not in n.get("story", [])]
            print(f"\n--- [{n['formato'].upper()} | SIMULAÇÃO] {', '.join(os.path.basename(s) for s in arquivos)}")
            print(legenda(n, cfg, "telegram"))
            continue
        ok = False
        if cfg["telegram"].get("ativo") and not cfg["telegram"].get("so_promocoes"):  # Telegram = só promoções
            try:
                if len(n["slides"]) > 1:
                    publicar.telegram_album(cfg, n["slides"], legenda(n, cfg, "telegram"))
                else:
                    publicar.telegram_foto(cfg, n["slides"][0], legenda(n, cfg, "telegram"))
                ok = True
            except Exception as e:
                log.error("Telegram falhou: %s", e)
        if cfg["instagram"].get("ativo"):
            try:
                urgente = n["formato"] in ("furo", "furo_rumor")  # furo usa a reserva da cota
                if n.get("story"):
                    publicar.instagram_story(cfg, n["story"][0], furo=urgente)
                # feed do Instagram: só os 3 posts planejados por dia; notícia vai para story
                if len(n["slides"]) > 1 and cfg.get("noticias", {}).get("instagram_feed", False):
                    publicar.instagram_carrossel(cfg, n["slides"], legenda(n, cfg, "instagram"), furo=urgente)
                ok = True
            except Exception as e:
                log.error("Instagram falhou: %s", e)
        if ok:
            con.execute("INSERT OR IGNORE INTO noticias VALUES (?,?,?,?,?,?)",
                        (n["link"], n["fonte"], n["titulo"], int(n["rumor"]), n["formato"], iso(agora())))
            con.commit()
    if not simular:
        FILA.unlink()


def testar_fontes(cfg):
    for f in cfg.get("noticias", {}).get("fontes", []):
        try:
            itens = baixar_feed(f)
        except FonteBloqueou as e:
            print(f"• {f['nome']} [{f.get('tipo')}]: BLOQUEOU ({e}); aumente intervalo_minutos")
            continue
        estado = f"OK, {len(itens)} itens" if itens else "NÃO RESPONDE (desligue ou troque a URL)"
        print(f"• {f['nome']} [{f.get('tipo')}]: {estado}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(BASE / "config.yaml"))
    ap.add_argument("--simular", action="store_true")
    ap.add_argument("--testar-fontes", action="store_true")
    ap.add_argument("--etapa", choices=["tudo", "preparar", "publicar"], default="tudo")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.StreamHandler(),
                                  logging.FileHandler(BASE / "bot.log", encoding="utf-8")])
    with open(a.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if a.testar_fontes:
        testar_fontes(cfg)
        return
    if not cfg.get("noticias", {}).get("ativo"):
        log.info("Notícias desligadas (noticias.ativo: false)")
        return
    con = abrir_banco(BASE / cfg.get("banco_noticias", "noticias.db"))
    preparar_banco(con)
    if a.etapa in ("tudo", "preparar"):
        preparar(cfg, con)
    if a.etapa in ("tudo", "publicar") or a.simular:
        publicar_fila(cfg, con, a.simular)


if __name__ == "__main__":
    main()
