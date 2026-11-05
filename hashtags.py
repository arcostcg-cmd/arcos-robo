"""Hashtags da Montop: no máximo 5 por post (limite do Instagram desde dez/2025).

Estratégia (recomendação do próprio Instagram: poucas e focadas, em vez de muitas genéricas):
  1. #montoptcg (marca: quem clica acha o perfil inteiro)
  2-3. duas de nicho do jogo do post (onde estão os colecionadores daquele jogo)
  4. uma do assunto (promoção, curiosidade, notícia, ranking)
  5. #tcgbrasil (público brasileiro)
"""
import re
import unicodedata

MAX = 5

JOGO = {
    "pokemon": ["#pokemontcg", "#cartaspokemon"],
    "one piece": ["#onepiececardgame", "#onepiecetcg"],
    "magic": ["#mtgbrasil", "#magicthegathering"],
    "yu-gi-oh": ["#yugiohbrasil", "#yugioh"],
    "lorcana": ["#disneylorcana", "#lorcanabrasil"],
    "digimon": ["#digimoncardgame", "#digimontcg"],
    "dragon ball": ["#dragonballsuper", "#dbscardgame"],
}
GERAL = ["#cardgame", "#colecionaveis"]

ASSUNTO = {
    "promocao": "#promocaotcg",
    "curiosidade": "#curiosidadestcg",
    "noticia": "#noticiastcg",
    "ranking": "#cartasraras",
    "rumor": "#noticiastcg",
}


def _chave(jogo):
    j = unicodedata.normalize("NFKD", (jogo or "").lower()).encode("ascii", "ignore").decode()
    for k in JOGO:
        if k.replace("-", "") in j.replace("-", "").replace("!", ""):
            return k
    return None


def escolher(jogo=None, assunto="curiosidade"):
    k = _chave(jogo)
    nicho = JOGO.get(k, GERAL)
    tags = ["#montoptcg", *nicho, ASSUNTO.get(assunto, "#curiosidadestcg"), "#tcgbrasil"]
    vistos, out = set(), []
    for t in tags:
        if t.lower() not in vistos:
            vistos.add(t.lower())
            out.append(t)
    return " ".join(out[:MAX])


_TAG = re.compile(r"(?<![\w&])#[\wÀ-ÿ]+")


def limitar(legenda, maximo=MAX):
    """Trava final: deixa só as primeiras `maximo` hashtags da legenda (sem repetir)."""
    vistos = []

    def troca(m):
        t = m.group(0)
        if t.lower() in (v.lower() for v in vistos) or len(vistos) >= maximo:
            return ""
        vistos.append(t)
        return t

    novo = _TAG.sub(troca, legenda or "")
    novo = re.sub(r"[ \t]{2,}", " ", novo)
    return re.sub(r"[ \t]+\n", "\n", novo).rstrip()
