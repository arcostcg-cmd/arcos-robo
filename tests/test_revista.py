from PIL import Image

import carrossel


def test_revista_slides(tmp_path):
    cartas = [Image.new("RGB", (245, 342), c) for c in ("red", "green")]
    c = {"credito_imagem": "The Pokémon Company", "pergunta": "E aí?", "fontes": ["x"],
         "slides": [{"carta": 0, "titulo": "Título grande", "destaques": ["GRANDE"]},
                    {"carta": 1, "titulo": "Outro", "sub": "sub"}]}
    s = carrossel.carrossel_revista(c, cartas, tmp_path, "r")
    assert len(s) == 3 and Image.open(s[0]).size == (1080, 1350)
