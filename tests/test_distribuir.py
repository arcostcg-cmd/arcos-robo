from datetime import datetime

import distribuir

IT = {"id": "r1", "tipo": "reel", "quando": "2026-11-07T20:30",
      "legenda_instagram": "Gancho muito forte aqui 😱\n\n📌 fato\n\n#montoptcg #pokemontcg"}


def test_titulo_youtube_tem_shorts_e_limite():
    t = distribuir.titulo_youtube({**IT, "legenda_instagram": "x" * 300})
    assert t.endswith("#shorts") and len(t) <= 100


def test_tiktok_publica_direto():
    assert distribuir.ajustes("tiktok", IT)["content_posting_method"] == "DIRECT_POST"
    assert distribuir.ajustes("youtube", IT)["type"] == "public"


def test_so_videos_vao_para_youtube_e_tiktok():
    carrossel = {**IT, "id": "c1", "tipo": None}
    agora = datetime(2026, 11, 7, 21, 0, tzinfo=distribuir.BR)
    ids = [it["id"] for it, _ in distribuir.vencidos([IT, carrossel], {}, agora, ["youtube", "tiktok"])]
    assert ids == ["r1"]


def test_nao_repete_rede_ja_enviada():
    agora = datetime(2026, 11, 7, 21, 0, tzinfo=distribuir.BR)
    r = list(distribuir.vencidos([IT], {"r1": {"youtube": "x"}}, agora, ["youtube", "tiktok"]))
    assert r[0][1] == ["tiktok"]
