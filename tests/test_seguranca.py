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


def test_comando_cupom_validado(tmp_path):
    import sqlite3
    import cupons
    con = sqlite3.connect(tmp_path / "c.db")
    cupons.preparar_banco(con)
    assert "inválido" in cupons.aplicar_comando(con, "/cupom_ok <script> 10 30/12")
    assert "fora do normal" in cupons.aplicar_comando(con, "/cupom_ok PROMO10 95 30/12")


def test_erro_telegram_sem_token(monkeypatch):
    import publicar

    class R:
        status_code = 400
        def json(self):
            return {"description": "Bad Request: chat not found"}

    monkeypatch.setenv("TELEGRAM_TOKEN", "123456789:AAsegredo")
    monkeypatch.setattr(publicar.requests, "post", lambda *a, **k: R())
    try:
        publicar._tg("sendMessage", {"chat_id": 1, "text": "x"})
    except publicar.ErroTelegram as e:
        assert "segredo" not in str(e) and "chat not found" in str(e)


def test_log_sem_token(monkeypatch, caplog):
    import logging
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaFAKEKEYFAKEKEYFAKEKEYFAKEKEY12345")
    with caplog.at_level(logging.WARNING):
        logging.getLogger("x").warning("IA falhou: %s", "https://api/x?key=AIzaFAKEKEYFAKEKEYFAKEKEYFAKEKEY12345&a=1")
    assert "FAKEKEY" not in caplog.text and "***" in caplog.text
