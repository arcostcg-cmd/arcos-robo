"""Links de afiliado e cupons: as duas fontes de receita da fase 1."""
from datetime import date, timedelta
from urllib.parse import parse_qsl, quote, urlencode, urlparse, urlunparse


def link_afiliado(loja, url):
    """Transforma a URL do produto no link de afiliado da loja.

    Configuração por loja (config.yaml), campo `link_afiliado`:
      false ou ausente   -> link normal, sem comissão
      true               -> a URL cadastrada já é o link de afiliado
      {parametros: {tag: "arcos-20"}}         -> acrescenta parâmetros na URL
      {modelo: "https://ex.com/r?u={url}"}    -> monta a partir de um modelo
    Devolve (link, eh_afiliado).
    """
    conf = loja.get("link_afiliado")
    if not conf:
        return url, False
    if conf is True:
        return url, True
    if isinstance(conf, dict) and conf.get("modelo"):
        return conf["modelo"].replace("{url}", quote(url, safe="")), True
    if isinstance(conf, dict) and conf.get("parametros"):
        p = urlparse(url)
        q = dict(parse_qsl(p.query))
        q.update({k: str(v) for k, v in conf["parametros"].items()})
        return urlunparse(p._replace(query=urlencode(q))), True
    return url, False


def cupom_valido(cfg, loja_id, hoje=None):
    """Devolve o melhor cupom vigente e testado da loja, ou None.

    Um cupom só vai para o post se:
      - `valido_ate` ainda não passou;
      - `testado_em` tem no máximo `regras.cupom_teste_dias` dias (padrão 7).
    """
    hoje = hoje or date.today()
    dias = cfg.get("regras", {}).get("cupom_teste_dias", 7)
    vigentes = []
    for c in cfg.get("cupons", []) or []:
        if c.get("loja") != loja_id or not c.get("codigo"):
            continue
        try:
            validade = date.fromisoformat(str(c["valido_ate"]))
            testado = date.fromisoformat(str(c["testado_em"]))
        except (KeyError, ValueError):
            continue
        if validade < hoje or testado < hoje - timedelta(days=dias):
            continue
        vigentes.append(c)
    if not vigentes:
        return None
    return max(vigentes, key=lambda c: float(c.get("percentual", 0) or 0))


def preco_com_cupom(preco, cupom):
    """Preço final estimado com o cupom (percentual e pedido mínimo). Sem cupom, o próprio preço."""
    if not cupom or not cupom.get("percentual"):
        return preco
    minimo = cupom.get("minimo") or 0
    if preco < float(minimo):
        return preco
    return round(preco * (1 - float(cupom["percentual"]) / 100), 2)


def cupons_vencendo(cfg, hoje=None, dias=3):
    """Cupons que vencem em breve ou precisam de novo teste (para avisar o admin)."""
    hoje = hoje or date.today()
    limite_teste = cfg.get("regras", {}).get("cupom_teste_dias", 7)
    avisos = []
    for c in cfg.get("cupons", []) or []:
        try:
            validade = date.fromisoformat(str(c["valido_ate"]))
            testado = date.fromisoformat(str(c["testado_em"]))
        except (KeyError, ValueError):
            avisos.append(f"Cupom {c.get('codigo', '?')}: datas inválidas no config")
            continue
        if hoje <= validade <= hoje + timedelta(days=dias):
            avisos.append(f"Cupom {c['codigo']} ({c['loja']}) vence em {validade:%d/%m}")
        if testado < hoje - timedelta(days=limite_teste) and validade >= hoje:
            avisos.append(f"Cupom {c['codigo']} ({c['loja']}) precisa ser testado de novo")
    return avisos
