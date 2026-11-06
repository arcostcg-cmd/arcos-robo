#!/usr/bin/env python3
"""Segurança do robô Montop TCG: travas que rodam em todo post e uma varredura do repositório.

Travas em tempo de execução (usadas pelo bot, notícias e imagens):
- link_seguro(): promoção só sai com link HTTPS de domínio aprovado (lojas do config + encurtadores
  oficiais de afiliado). Evita postar link de golpe se uma API, feed ou loja for invadida.
- limpar_texto_ia(): tira qualquer link e comando que a IA (Gemini) tente colocar no texto
  (proteção contra "prompt injection" vinda de notícia maliciosa).
- imagem_segura(): limita tamanho e tipo do arquivo baixado (contra arquivo-bomba e vírus disfarçado).

Varredura (python seguranca.py): procura token/senha vazados nos arquivos do repositório,
gatilhos perigosos nos workflows, ações não fixadas e arquivos que nunca deviam estar aqui.
Sai com erro (e o workflow avisa o admin no Telegram) se achar algo grave.
"""
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

BASE = Path(__file__).resolve().parent

# domínios oficiais (e encurtadores oficiais de afiliado) aceitos em links de promoção
DOMINIOS_BASE = {
    "mercadolivre.com.br", "mercadolivre.com", "mercadolibre.com", "mlstatic.com",
    "amazon.com.br", "amzn.to",
    "shopee.com.br", "shope.ee",
    "aliexpress.com", "aliexpress.us", "a.aliexpress.com", "s.click.aliexpress.com",
    "t.me",
}
EXTENSOES_PROIBIDAS = (".exe", ".apk", ".scr", ".bat", ".cmd", ".msi", ".js", ".vbs", ".zip", ".rar", ".jar")
MAX_IMAGEM = 15 * 1024 * 1024  # 15 MB

PADROES_SEGREDO = {
    "token de bot do Telegram": r"\b\d{8,10}:AA[A-Za-z0-9_-]{30,}\b",
    "token da Meta/Instagram": r"\b(EAA[A-Za-z0-9]{60,}|IGAA[A-Za-z0-9_-]{60,}|IGQV[A-Za-z0-9_-]{60,})\b",
    "chave Google/Gemini": r"\bAIza[0-9A-Za-z_-]{35}\b",
    "token do GitHub": r"\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}\b|\bgithub_pat_[A-Za-z0-9_]{60,}\b",
    "chave privada": r"-----BEGIN (RSA |EC |OPENSSH |)PRIVATE KEY-----",
    "segredo do Mercado Livre": r"\bAPP_USR-\d{6,}-\d{6}-[a-f0-9]{32}-\d+\b",
    "senha escrita": r"(?i)\b(senha|password|passwd)\s*[:=]\s*['\"][^'\"\s]{6,}['\"]",
}
ARQUIVOS_PROIBIDOS = (".env", "config.local.yaml", "*.pem", "*.key", "id_rsa*", "*.p12")


def _dominio_ok(host, permitidos):
    host = (host or "").lower().rstrip(".")
    return any(host == d or host.endswith("." + d) for d in permitidos)


def dominios_permitidos(cfg=None):
    ds = set(DOMINIOS_BASE)
    for loja in (cfg or {}).get("lojas", []) or []:
        for chave in ("url", "busca", "site", "link_afiliado"):
            v = loja.get(chave) if isinstance(loja, dict) else None
            if isinstance(v, str) and v.startswith("https://"):
                h = urlparse(v).hostname or ""
                ds.add(h[4:] if h.startswith("www.") else h)
        for d in (loja.get("dominios") or []) if isinstance(loja, dict) else []:
            ds.add(d.lower())
    return ds


def link_seguro(url, cfg=None, permitidos=None):
    """True só para https, sem usuário/senha embutidos, sem arquivo executável, em domínio aprovado."""
    try:
        u = urlparse(str(url).strip())
    except Exception:
        return False
    if u.scheme != "https" or not u.hostname or u.username or u.password:
        return False
    if "xn--" in u.hostname:  # domínio com letras disfarçadas (ataque homográfico)
        return False
    if u.path.lower().endswith(EXTENSOES_PROIBIDAS):
        return False
    return _dominio_ok(u.hostname, permitidos or dominios_permitidos(cfg))


def link_noticia_seguro(url):
    """Notícia aponta para a fonte original: exige https, sem executável e sem domínio disfarçado."""
    try:
        u = urlparse(str(url).strip())
    except Exception:
        return False
    return (u.scheme == "https" and bool(u.hostname) and "xn--" not in u.hostname and not u.username
            and not u.path.lower().endswith(EXTENSOES_PROIBIDAS))


_URL = re.compile(r"(https?://\S+|www\.\S+|\b[\w-]+\.(?:ly|gl|gg|io|xyz|top|click|link|ru|cn)/\S*)", re.I)


def limpar_texto_ia(texto, limite=900):
    """Tira links, menções em massa e comandos do texto gerado pela IA. O link certo é posto pelo robô."""
    t = _URL.sub("", texto or "")
    t = re.sub(r"(?i)@(everyone|here|all|todos)\b", "", t)
    t = re.sub(r"(?im)^\s*/\w+.*$", "", t)  # linhas que parecem comando de bot
    t = re.sub(r"<[^>]+>", "", t)  # nada de HTML vindo da IA
    t = re.sub(r"[ \t]+\n", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t).strip()
    return t[:limite]


def imagem_segura(resposta):
    """Confere a resposta HTTP antes de abrir como imagem: tipo de imagem e tamanho máximo."""
    tipo = (resposta.headers.get("Content-Type") or "").lower()
    if tipo and not tipo.startswith("image/") and "octet-stream" not in tipo:
        return False
    tam = resposta.headers.get("Content-Length")
    if tam and tam.isdigit() and int(tam) > MAX_IMAGEM:
        return False
    return len(resposta.content) <= MAX_IMAGEM


# ------------------------------------------------------------------ logs sem segredo

_SEGREDOS_ENV = ("TELEGRAM_TOKEN", "INSTAGRAM_TOKEN", "GEMINI_API_KEY", "ANTHROPIC_API_KEY", "ML_CLIENT_SECRET",
                 "ML_REFRESH_TOKEN", "ALI_APP_SECRET", "SHOPEE_SECRET", "AMAZON_SECRET_KEY")


def ocultar(texto):
    """Troca por *** qualquer token conhecido (variáveis de ambiente e padrões de chave)."""
    import os
    t = str(texto)
    for nome in _SEGREDOS_ENV:
        v = os.environ.get(nome)
        if v and len(v) >= 8:
            t = t.replace(v, "***")
    for padrao in list(PADROES_SEGREDO.values())[:4]:
        t = re.sub(padrao, "***", t)
    t = re.sub(r"(?i)((?:access_token|key|token|secret|sign)=)[^&\s]+", r"\1***", t)
    return t


def proteger_logs():
    """Todo log do robô passa por ocultar() antes de ser escrito (vale para qualquer módulo)."""
    import logging
    if getattr(logging, "_montop_protegido", False):
        return
    antiga = logging.getLogRecordFactory()

    def fabrica(*a, **k):
        rec = antiga(*a, **k)
        try:
            rec.msg = ocultar(rec.getMessage())
            rec.args = ()
        except Exception:
            pass
        return rec

    logging.setLogRecordFactory(fabrica)
    logging._montop_protegido = True


proteger_logs()


# ------------------------------------------------------------------ varredura do repositório

def _arquivos_rastreados():
    r = subprocess.run(["git", "ls-files"], cwd=BASE, capture_output=True, text=True)
    return [BASE / p for p in r.stdout.splitlines() if p]


def varrer():
    graves, avisos = [], []
    arquivos = _arquivos_rastreados()
    for p in arquivos:
        rel = p.relative_to(BASE).as_posix()
        if any(Path(rel).match(g) for g in ARQUIVOS_PROIBIDOS):
            graves.append(f"arquivo que não pode estar no repositório: {rel}")
            continue
        if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".mp4", ".wav", ".ttf", ".onnx", ".db", ".gif"}:
            continue
        if p.name == "seguranca.py" or rel.startswith("tests/"):
            continue  # os próprios padrões e exemplos de teste
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for nome, padrao in PADROES_SEGREDO.items():
            if re.search(padrao, txt):
                graves.append(f"possível {nome} exposto em {rel}")
    for wf in (BASE / ".github" / "workflows").glob("*.yml"):
        s = wf.read_text(encoding="utf-8")
        if "pull_request_target" in s:
            graves.append(f"{wf.name}: gatilho pull_request_target (deixa estranhos rodarem código com os segredos)")
        if re.search(r"\$\{\{\s*github\.event\.(issue|comment|pull_request|head_commit)\.[^}]*\}\}", s) and "run:" in s:
            avisos.append(f"{wf.name}: usa texto de evento do GitHub direto em comando (risco de injeção)")
        for uso in re.findall(r"uses:\s*([\w./-]+)@([\w.-]+)", s):
            if not re.fullmatch(r"[0-9a-f]{40}", uso[1]):
                avisos.append(f"{wf.name}: ação {uso[0]}@{uso[1]} não está fixada por SHA")
        if "permissions:" not in s:
            avisos.append(f"{wf.name}: sem bloco permissions (usa o padrão do repositório)")
        if re.search(r"pip install (?!-r )(?!--)", s):
            avisos.append(f"{wf.name}: instala pacotes sem versão fixa (use requirements.txt)")
    gi = (BASE / ".gitignore").read_text(encoding="utf-8") if (BASE / ".gitignore").exists() else ""
    for item in (".env", "config.local.yaml"):
        if item not in gi:
            avisos.append(f".gitignore não protege {item}")
    return graves, avisos


def main():
    graves, avisos = varrer()
    for g in graves:
        print("🚨 GRAVE:", g)
    for a in avisos:
        print("⚠️ aviso:", a)
    if not graves and not avisos:
        print("✅ Nenhum problema encontrado.")
    sys.exit(1 if graves else 0)


if __name__ == "__main__":
    main()
