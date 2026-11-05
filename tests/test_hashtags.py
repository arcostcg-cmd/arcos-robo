import re

import hashtags as h


def test_no_maximo_5():
    for jogo in ["Pokémon", "One Piece", "Magic", "Yu-Gi-Oh!", "Lorcana", "Digimon", None]:
        for assunto in ["promocao", "curiosidade", "noticia", "ranking", "rumor"]:
            tags = h.escolher(jogo, assunto).split()
            assert len(tags) <= 5 and "#montoptcg" in tags


def test_trava_corta_excesso():
    leg = h.limitar("texto #a #b #c #d #e #f #g")
    assert len(re.findall(r"#\w+", leg)) == 5
