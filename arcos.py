#!/usr/bin/env python3
"""Montop TCG: comando central do robô, com os dois sistemas internos.

SISTEMA DE PROMOÇÕES (só promoções; dinheiro do canal)
  python arcos.py promocoes            coleta preços, aplica cupons, monta e posta os carrosséis
  python arcos.py promocoes preparar   só coleta e monta (GitHub: 1ª etapa)
  python arcos.py promocoes publicar   só posta a fila (GitHub: 2ª etapa)
  python arcos.py cupons               caça cupons nas páginas oficiais e lê /cupom_ok do admin
  python arcos.py cupons listar        cupons ativos e candidatos
  python arcos.py radar                compara preços com os canais concorrentes
  python arcos.py radar relatorio      resumo de 7 dias dos concorrentes

SISTEMA DE NOTÍCIAS E RUMORES (informação para os fãs)
  python arcos.py noticias             notícias, furos e rumores em stories e posts
  python arcos.py noticias fontes      testa quais fontes respondem
  python arcos.py curiosidades         curiosidade verificada do horário

GERAL
  python arcos.py diagnostico          confere configuração, tokens e lojas
  python arcos.py testes               roda os testes automáticos

Em qualquer comando, acrescente --simular para ver tudo sem postar.
"""
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent

COMANDOS = {
    ("promocoes", None): ["bot.py"],
    ("promocoes", "preparar"): ["bot.py", "--etapa", "preparar"],
    ("promocoes", "publicar"): ["bot.py", "--etapa", "publicar"],
    ("cupons", None): ["cupons.py"],
    ("cupons", "listar"): ["cupons.py", "--listar"],
    ("radar", None): ["radar.py"],
    ("radar", "relatorio"): ["radar.py", "--relatorio"],
    ("noticias", None): ["noticias.py"],
    ("noticias", "preparar"): ["noticias.py", "--etapa", "preparar"],
    ("noticias", "publicar"): ["noticias.py", "--etapa", "publicar"],
    ("noticias", "fontes"): ["noticias.py", "--testar-fontes"],
    ("curiosidades", None): ["curiosidades.py"],
    ("curiosidades", "preparar"): ["curiosidades.py", "--etapa", "preparar"],
    ("curiosidades", "publicar"): ["curiosidades.py", "--etapa", "publicar"],
    ("diagnostico", None): ["bot.py", "--diagnostico", "--testar-lojas"],
}


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    extras = [a for a in argv if a.startswith("--")]
    if not args or args[0] in ("-h", "ajuda", "help"):
        print(__doc__)
        return 0
    if args[0] == "testes":
        return subprocess.call([sys.executable, "-m", "unittest", "discover", "tests"], cwd=BASE)
    chave = (args[0], args[1] if len(args) > 1 else None)
    if chave not in COMANDOS:
        print(f"Comando desconhecido: {' '.join(args)}\n{__doc__}")
        return 2
    return subprocess.call([sys.executable, *COMANDOS[chave], *extras], cwd=BASE)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
