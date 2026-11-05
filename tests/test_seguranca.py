import seguranca as s


def test_link_promocao():
    cfg = {"lojas": [{"url": "https://www.freitastcg.com.br/"}]}
    assert s.link_seguro("https://www.mercadolivre.com.br/p/MLB123", cfg)
    assert s.link_seguro("https://produto.mercadolivre.com.br/MLB-1", cfg)
    assert s.link_seguro("https://www.freitastcg.com.br/box", cfg)
    assert not s.link_seguro("http://www.mercadolivre.com.br/p/MLB123", cfg)        # sem https
    assert not s.link_seguro("https://mercadolivre.com.br.golpe.ru/p", cfg)          # domínio falso
    assert not s.link_seguro("https://xn--mercadolivr-u9a.com.br/p", cfg)            # letras disfarçadas
    assert not s.link_seguro("https://user:pass@www.mercadolivre.com.br/", cfg)      # credencial embutida
    assert not s.link_seguro("https://www.mercadolivre.com.br/app.apk", cfg)         # executável


def test_texto_ia_sem_links():
    t = s.limpar_texto_ia("Nova coleção! Veja em https://golpe.xyz/premio e bit.ly/abc @everyone <b>x</b>")
    assert "http" not in t and "bit.ly" not in t and "@everyone" not in t and "<b>" not in t


def test_varredura_acha_token(tmp_path, monkeypatch):
    f = tmp_path / "vaza.txt"
    f.write_text("token = 1234567890:AA" + "x" * 33)
    monkeypatch.setattr(s, "BASE", tmp_path)
    monkeypatch.setattr(s, "_arquivos_rastreados", lambda: [f])
    graves, _ = s.varrer()
    assert any("Telegram" in g for g in graves)
