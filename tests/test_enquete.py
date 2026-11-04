from PIL import Image

import carrossel


def test_enquete_6_slides(tmp_path):
    cartas = [Image.new("RGB", (245, 342), c) for c in ("red", "green", "blue", "yellow")]
    e = {"pergunta": "Qual você escolhe?", "jogo": "Pokémon", "credito_imagem": "The Pokémon Company",
         "opcoes": [{"nome": f"Carta {k}", "detalhe": "x"} for k in range(4)]}
    slides = carrossel.carrossel_enquete(e, cartas, tmp_path, "t")
    assert len(slides) == 6
    assert Image.open(slides[0]).size == (1080, 1350)
