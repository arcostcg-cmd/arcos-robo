"""Testes do robô Arcos TCG. Rode da pasta bot/:  python -m unittest discover tests"""
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import afiliados  # noqa: E402
import marketplaces  # noqa: E402
import bot  # noqa: E402
import radar  # noqa: E402


def pagina(preco, estoque="InStock", moeda="BRL"):
    return ('<script type="application/ld+json">{"@type":"Product","image":["http://x/i.jpg"],'
            f'"offers":{{"price":"{preco}","priceCurrency":"{moeda}",'
            f'"availability":"https://schema.org/{estoque}"}}}}</script>')


class TestLeitura(unittest.TestCase):
    def test_para_float(self):
        self.assertEqual(bot.para_float("1.299,90"), 1299.9)
        self.assertEqual(bot.para_float("1299.90"), 1299.9)
        self.assertEqual(bot.para_float("R$ 49,90"), 49.9)
        self.assertEqual(bot.para_float(899), 899.0)

    def test_extrair_oferta(self):
        self.assertEqual(bot.extrair_oferta(pagina("799.90")), (799.9, True, "http://x/i.jpg"))
        self.assertEqual(bot.extrair_oferta(pagina("100", "OutOfStock"))[1], False)
        self.assertIsNone(bot.extrair_oferta(pagina("100", moeda="USD")))
        self.assertIsNone(bot.extrair_oferta("<html>sem dados</html>"))


class TestAfiliadosCupons(unittest.TestCase):
    def test_link_afiliado(self):
        url = "https://loja.com/p?id=1"
        self.assertEqual(afiliados.link_afiliado({}, url), (url, False))
        self.assertEqual(afiliados.link_afiliado({"link_afiliado": True}, url), (url, True))
        link, ok = afiliados.link_afiliado({"link_afiliado": {"parametros": {"tag": "arcos-20"}}}, url)
        self.assertTrue(ok)
        self.assertIn("tag=arcos-20", link)
        self.assertIn("id=1", link)
        link, ok = afiliados.link_afiliado({"link_afiliado": {"modelo": "https://r.com/?u={url}"}}, url)
        self.assertTrue(link.startswith("https://r.com/?u=https%3A%2F%2Floja.com"))

    def test_cupom_valido(self):
        hoje = date(2026, 11, 10)
        cfg = {"regras": {"cupom_teste_dias": 7}, "cupons": [
            {"loja": "a", "codigo": "VELHO", "valido_ate": "2026-11-09", "testado_em": "2026-11-08"},
            {"loja": "a", "codigo": "SEMTESTE", "valido_ate": "2026-12-01", "testado_em": "2026-10-01"},
            {"loja": "a", "codigo": "BOM", "percentual": 10, "valido_ate": "2026-12-01", "testado_em": "2026-11-09"},
            {"loja": "b", "codigo": "OUTRA", "valido_ate": "2026-12-01", "testado_em": "2026-11-09"},
        ]}
        self.assertEqual(afiliados.cupom_valido(cfg, "a", hoje)["codigo"], "BOM")
        self.assertIsNone(afiliados.cupom_valido(cfg, "c", hoje))
        avisos = afiliados.cupons_vencendo(cfg, hoje)
        self.assertTrue(any("SEMTESTE" in a for a in avisos))


class TestRegras(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = bot.abrir_banco(Path(self.tmp.name) / "t.db")
        self.cfg = {
            "regras": {"desconto_minimo": 0.10, "alerta_suspeito": 0.40, "dias_historico": 30,
                       "minimo_leituras": 1, "nao_repetir_horas": 24},
            "lojas": [{"id": l, "nome": l.upper(), "aprovada": True} for l in "abcd"]
                     + [{"id": "x", "nome": "X", "aprovada": False}],
            "produtos": [{"nome": "Box", "referencia_manual": 1000,
                          "ofertas": [{"loja": l, "url": f"http://{l}"} for l in "abcdx"]}],
        }

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def ler(self, loja, preco, estoque=1, vezes=2):
        for i in range(vezes):
            quando = bot.iso(bot.agora() - timedelta(minutes=30 * (vezes - i)))
            self.con.execute("INSERT INTO precos VALUES (?,?,?,?,?,?,?)",
                             ("Box", loja, f"http://{loja}", preco, estoque, None, quando))

    def test_filtros(self):
        self.ler("a", 850)            # 15% abaixo: aprovada
        self.ler("b", 500)            # 50% abaixo: suspeita
        self.ler("c", 950)            # 5% abaixo: desconto pequeno
        self.ler("d", 800, estoque=0)  # sem estoque
        self.ler("x", 700)            # loja não aprovada: ignorada
        aprovadas, descartadas = bot.avaliar(self.cfg, self.con)
        self.assertEqual([(o["loja"], o["preco"]) for o in aprovadas], [("a", 850)])
        motivos = {d["loja"]: d["motivo"] for d in descartadas}
        self.assertIn("suspeito", motivos["b"])
        self.assertIn("pequeno", motivos["c"])
        self.assertIn("estoque", motivos["d"])
        self.assertNotIn("x", motivos)

    def test_precisa_duas_leituras(self):
        self.ler("a", 850, vezes=1)
        aprovadas, descartadas = bot.avaliar(self.cfg, self.con)
        self.assertEqual(aprovadas, [])
        self.assertIn("2 leituras", descartadas[0]["motivo"])

    def test_nao_repete(self):
        self.con.execute("INSERT INTO postados VALUES (?,?,?,?,?)",
                         ("Box", "a", 850, "telegram", bot.iso(bot.agora())))
        self.assertTrue(bot.ja_postado(self.con, "Box", "a", 850, "telegram", 24))
        self.assertFalse(bot.ja_postado(self.con, "Box", "a", 800, "telegram", 24))


class TestRadar(unittest.TestCase):
    HTML = ('<div class="tgme_widget_message" data-post="canal/1">'
            '<div class="tgme_widget_message_text js-message_text">🔥 Booster Box Pokémon '
            'Escarlate 36 boosters por <b>R$ 749,90</b></div><time datetime="2026-10-31T10:00:00+00:00"></time></div>'
            '<div class="tgme_widget_message" data-post="canal/2"><div class="foto"></div>'
            '<time datetime="2026-10-31T11:00:00+00:00"></time></div>'
            '<div class="tgme_widget_message" data-post="canal/3">'
            '<div class="tgme_widget_message_text">Deck Magic por R$ 1.199,00</div>'
            '<time datetime="2026-10-31T12:00:00+00:00"></time></div>')

    def test_extrair_posts(self):
        posts = radar.extrair_posts(self.HTML)
        self.assertEqual([p[0] for p in posts], ["canal/1", "canal/3"])  # post só com foto ignorado
        self.assertIn("749,90", posts[0][1])
        self.assertEqual(radar.PRECO_RE.findall(posts[1][1]), ["1.199,00"])

    def test_casar_produto(self):
        produtos = [{"nome": "Booster Box Escarlate", "palavras": ["booster box", "pokemon", "36"]},
                    {"nome": "Deck Lorcana", "palavras": ["deck", "lorcana"]}]
        texto = radar.extrair_posts(self.HTML)[0][1]
        self.assertEqual(radar.casar_produto(texto, produtos)["nome"], "Booster Box Escarlate")
        self.assertIsNone(radar.casar_produto("Deck Magic por R$ 10", produtos))


class TestCarrossel(unittest.TestCase):
    def test_gera_slides(self):
        import carrossel
        o = {"produto": "Booster Box Teste", "jogo": "Pokémon", "descricao": "Lacrado",
             "loja": "a", "loja_nome": "Loja A", "preco": 850.0, "ref": 1000.0,
             "visto": "2026-10-31T12:00:00-03:00", "afiliado": True,
             "cupom": {"codigo": "ARCOS10", "descricao": "10% off"}}
        c = {"id": "t", "jogo": "Magic", "titulo": "Título de teste",
             "texto": "Primeira frase do fato. Segunda frase do fato.",
             "fonte_nome": "Fonte X", "fonte_url": "https://exemplo.org/a",
             "verificado_em": "2026-10-31"}
        with tempfile.TemporaryDirectory() as d:
            p, cred = carrossel.carrossel_promocao(o, None, Path(d))
            self.assertEqual(len(p), 4)
            self.assertIn("Imagem do produto: Loja A", cred)
            q, _ = carrossel.carrossel_curiosidade(c, None, Path(d))
            self.assertGreaterEqual(len(q), 4)
            self.assertTrue(all(x.exists() for x in p + q))


if __name__ == "__main__":
    unittest.main()


class TestNoticias(unittest.TestCase):
    RSS = b"""<?xml version="1.0"?><rss><channel>
      <item><title>New Pokemon TCG expansion revealed with 191 cards</title>
      <link>https://ex.com/a</link><pubDate>Sat, 31 Oct 2026 12:00:00 +0000</pubDate>
      <description>&lt;p&gt;The set launches on March 27 with 191 cards.&lt;/p&gt;</description></item>
    </channel></rss>"""
    ATOM = b"""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
      <entry><title>[Leak] Possible new Lorcana chapter</title>
      <link href="https://reddit.com/r/x/1"/><updated>2026-10-31T10:00:00+00:00</updated>
      <content type="html">rumor from a datamine</content></entry></feed>"""

    def test_ler_feeds(self):
        import noticias
        rss = noticias.ler_feed(self.RSS)
        self.assertEqual(rss[0]["link"], "https://ex.com/a")
        self.assertIn("191 cards", rss[0]["resumo"])
        self.assertIsNotNone(rss[0]["data"])
        atom = noticias.ler_feed(self.ATOM)
        self.assertEqual(atom[0]["link"], "https://reddit.com/r/x/1")

    def test_rumor(self):
        import noticias
        atom = noticias.ler_feed(self.ATOM)[0]
        rss = noticias.ler_feed(self.RSS)[0]
        self.assertTrue(noticias.eh_rumor(atom, {"tipo": "imprensa"}))
        self.assertTrue(noticias.eh_rumor(rss, {"tipo": "forum"}))
        self.assertFalse(noticias.eh_rumor(rss, {"tipo": "oficial"}))

    def test_checagem_de_numeros(self):
        import noticias
        original = "The set launches on March 27 with 191 cards."
        self.assertTrue(noticias.numeros_conferem("Coleção com 191 cartas sai em 27 de março", original))
        self.assertFalse(noticias.numeros_conferem("Coleção com 200 cartas sai em 27 de março", original))

    def test_story_e_carrossel(self):
        import carrossel
        n = {"titulo": "Nova coleção de Pokémon revelada", "resumo": "A coleção chega em 27 de março com 191 cartas.",
             "jogo": "Pokémon", "fonte": "Fonte Exemplo", "link": "https://ex.com/a", "rumor": True}
        with tempfile.TemporaryDirectory() as d:
            st = carrossel.story_noticia(n, Path(d))
            from PIL import Image
            self.assertEqual(Image.open(st).size, (1080, 1920))
            self.assertEqual(len(carrossel.carrossel_noticia(n, Path(d))), 3)


class TestGemini(unittest.TestCase):
    def test_escolhe_flash_estavel_mais_novo(self):
        import noticias
        modelos = [
            {"name": "models/gemini-1.5-flash", "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/gemini-9.0-flash-preview", "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/gemini-3.0-flash", "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/gemini-3.0-flash-lite", "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/gemini-3.0-pro", "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/embedding-001", "supportedGenerationMethods": ["embedContent"]},
        ]
        self.assertEqual(noticias.escolher_modelo_gemini(modelos), "gemini-3.0-flash")
        self.assertIsNone(noticias.escolher_modelo_gemini([]))


class TestFuroEQualidade(unittest.TestCase):
    def setUp(self):
        import noticias
        self.n = noticias
        self.cfg = {"telegram": {}, "instagram": {}, "noticias": {
            "max_stories_dia": 0, "max_posts_dia": 0, "palavras_relevantes": ["set"],
            "ia": {"provedor": "teste", "max_por_execucao": 10},
            "furo": {"ativo": True, "janela_minutos": 90, "max_por_dia": 10,
                     "tipos": ["oficial", "imprensa"], "palavras": ["revealed", "new set"]},
            "fontes": [{"nome": "Oficial X", "url": "u1", "tipo": "oficial", "jogo": "Magic"},
                       {"nome": "Forum Y", "url": "u2", "tipo": "forum", "jogo": "Magic"}]}}

    def item(self, titulo, minutos):
        return {"titulo": titulo, "link": f"https://ex.com/{abs(hash(titulo))}",
                "data": bot.agora() - timedelta(minutes=minutos),
                "resumo": "The new set with 250 cards was revealed today by the publisher."}

    def test_eh_furo(self):
        oficial, forum = self.cfg["noticias"]["fontes"]
        self.assertTrue(self.n.eh_furo(self.item("New set revealed", 30), oficial, self.cfg))
        self.assertFalse(self.n.eh_furo(self.item("New set revealed", 200), oficial, self.cfg))  # velho
        self.assertFalse(self.n.eh_furo(self.item("New set revealed", 30), forum, self.cfg))   # fórum
        self.assertFalse(self.n.eh_furo(self.item("New set revealed leak", 30), oficial, self.cfg))  # rumor

    def test_texto_ok(self):
        self.assertIsNone(self.n.texto_ok("URGENTE: nova coleção revelada", "A coleção tem 250 cartas e sai em março."))
        self.assertIsNone(self.n.texto_ok("NOVA COLEÇÃO REVELADA HOJE", "A coleção tem 250 cartas e sai em março."))
        t, r = self.n.texto_ok("Nova coleção de Magic é revelada!", "A coleção tem 250 cartas e sai em março")
        self.assertNotIn("!", t)
        self.assertTrue(r.endswith("."))

    def test_furo_passa_do_limite_e_vai_pro_feed(self):
        import json
        n = self.n
        feeds = {"u1": [self.item("New set revealed for Magic", 20)],
                 "u2": [self.item("Possible new set from datamine", 20)]}
        resposta = json.dumps({"titulo": "Nova coleção de Magic é revelada",
                               "resumo": "A editora revelou hoje a nova coleção, com 250 cartas."})
        orig_baixar, orig_ia = n.baixar_feed, n.chamar_ia
        n.baixar_feed = lambda fonte: feeds[fonte["url"]]
        n.chamar_ia = lambda cfg, prompt: resposta
        try:
            with tempfile.TemporaryDirectory() as d:
                con = bot.abrir_banco(Path(d) / "t.db")
                n.preparar_banco(con)
                orig_base, orig_fila = n.BASE, n.FILA
                n.BASE, n.FILA = Path(d), Path(d) / "fila.json"
                try:
                    fila = n.preparar(self.cfg, con)
                finally:
                    n.BASE, n.FILA = orig_base, orig_fila
                con.close()
        finally:
            n.baixar_feed, n.chamar_ia = orig_baixar, orig_ia
        self.assertEqual([f["formato"] for f in fila], ["furo"])  # limite 0, mas o furo saiu
        self.assertEqual(len(fila[0]["story"]), 1)               # vai pro story
        self.assertEqual(len(fila[0]["slides"]), 3)              # e pro feed (carrossel)
        self.assertFalse(fila[0]["rumor"])


class TestRumorSempreDito(unittest.TestCase):
    def test_titulo_de_rumor_comeca_com_rumor(self):
        import json
        import noticias as n
        cfg = {"telegram": {}, "instagram": {}, "noticias": {
            "max_stories_dia": 5, "max_posts_dia": 1, "palavras_relevantes": ["set"],
            "ia": {"provedor": "teste"}, "furo": {"ativo": True, "palavras": ["set"]},
            "fontes": [{"nome": "Forum Y", "url": "u", "tipo": "forum", "jogo": "Pokémon"}]}}
        item = {"titulo": "New set leaked", "link": "https://ex.com/r", "data": bot.agora(),
                "resumo": "A datamine suggests a new set with 180 cards."}
        resposta = json.dumps({"titulo": "Possível nova coleção de Pokémon",
                               "resumo": "Segundo um datamine, a coleção teria 180 cartas, ainda sem confirmação oficial."})
        ob, oi = n.baixar_feed, n.chamar_ia
        n.baixar_feed, n.chamar_ia = (lambda f: [item]), (lambda c, p: resposta)
        try:
            with tempfile.TemporaryDirectory() as d:
                con = bot.abrir_banco(Path(d) / "t.db")
                n.preparar_banco(con)
                obase, ofila = n.BASE, n.FILA
                n.BASE, n.FILA = Path(d), Path(d) / "f.json"
                try:
                    fila = n.preparar(cfg, con)
                finally:
                    n.BASE, n.FILA = obase, ofila
                con.close()
        finally:
            n.baixar_feed, n.chamar_ia = ob, oi
        self.assertEqual(fila[0]["formato"], "story")          # rumor nunca vai pro feed
        self.assertTrue(fila[0]["titulo"].startswith("Rumor: "))
        self.assertIn("RUMOR", n.legenda(fila[0], cfg, "telegram"))


class TestFuroDeRumor(unittest.TestCase):
    def test_rumor_quente_passa_do_limite_marcado(self):
        import json
        import noticias as n
        cfg = {"telegram": {}, "instagram": {}, "noticias": {
            "max_stories_dia": 0, "max_posts_dia": 0, "palavras_relevantes": ["set"],
            "ia": {"provedor": "teste"},
            "furo": {"ativo": True, "palavras": ["revealed"], "tipos": ["oficial", "imprensa"]},
            "furo_rumor": {"ativo": True, "janela_minutos": 90, "max_por_dia": 10,
                           "tambem_no_feed": False, "palavras": ["leak", "set list"]},
            "fontes": [{"nome": "Blog Z", "url": "u", "tipo": "blog", "jogo": "One Piece"}]}}
        quente = {"titulo": "OP-15 set list leak", "link": "https://ex.com/q",
                  "data": bot.agora() - timedelta(minutes=15),
                  "resumo": "A fan blog shared a possible set list with 120 cards."}
        velho = dict(quente, link="https://ex.com/v", titulo="Old set list leak OP-09",
                     data=bot.agora() - timedelta(hours=5))
        resposta = json.dumps({"titulo": "Possível lista de cartas de One Piece",
                               "resumo": "Um blog de fãs divulgou uma possível lista com 120 cartas, sem confirmação oficial."})
        ob, oi = n.baixar_feed, n.chamar_ia
        n.baixar_feed, n.chamar_ia = (lambda f: [quente, velho]), (lambda c, p: resposta)
        try:
            with tempfile.TemporaryDirectory() as d:
                con = bot.abrir_banco(Path(d) / "t.db")
                n.preparar_banco(con)
                obase, ofila = n.BASE, n.FILA
                n.BASE, n.FILA = Path(d), Path(d) / "f.json"
                try:
                    fila = n.preparar(cfg, con)
                finally:
                    n.BASE, n.FILA = obase, ofila
                con.close()
        finally:
            n.baixar_feed, n.chamar_ia = ob, oi
        self.assertEqual(len(fila), 1)                        # só o quente (o velho esbarra no limite 0)
        self.assertEqual(fila[0]["formato"], "furo_rumor")
        self.assertTrue(fila[0]["titulo"].startswith("Rumor: "))
        self.assertEqual(len(fila[0]["story"]), 1)
        self.assertEqual(fila[0]["slides"], fila[0]["story"])  # sem feed por padrão


class TestCotaInstagram(unittest.TestCase):
    def test_cota(self):
        import os
        import publicar

        class Resp:
            def __init__(self, uso):
                self.uso = uso

            def json(self):
                return {"data": [{"quota_usage": self.uso, "config": {"quota_total": 50}}]}

        cfg = {"instagram": {"conta_id": "1", "reserva_cota": 3}}
        os.environ.setdefault("INSTAGRAM_TOKEN", "teste")
        original = publicar.requests.get
        try:
            publicar.requests.get = lambda *a, **k: Resp(10)
            publicar.conferir_cota(cfg)  # sobra cota: segue
            publicar.requests.get = lambda *a, **k: Resp(48)
            with self.assertRaises(publicar.CotaInstagram):
                publicar.conferir_cota(cfg)  # quase no fim: guarda a reserva para os furos
        finally:
            publicar.requests.get = original


class TestFonteComCalma(unittest.TestCase):
    def test_pausa_quem_bloqueia_e_respeita_intervalo(self):
        import noticias as n
        chamadas = []

        def bloqueia(fonte):
            chamadas.append(fonte["nome"])
            raise n.FonteBloqueou("HTTP 429")
        original = n.baixar_feed
        n.baixar_feed = bloqueia
        try:
            with tempfile.TemporaryDirectory() as d:
                con = bot.abrir_banco(Path(d) / "t.db")
                n.preparar_banco(con)
                fonte = {"nome": "Reddit X", "url": "u", "intervalo_minutos": 30}
                self.assertEqual(n.ler_fonte_com_calma(con, fonte), [])
                self.assertEqual(n.ler_fonte_com_calma(con, fonte), [])  # pausada: nem tenta
                self.assertEqual(chamadas, ["Reddit X"])
                n.baixar_feed = lambda f: [{"titulo": "a"}]
                outra = {"nome": "Blog Y", "url": "v", "intervalo_minutos": 30}
                self.assertEqual(len(n.ler_fonte_com_calma(con, outra)), 1)
                self.assertEqual(n.ler_fonte_com_calma(con, outra), [])  # dentro do intervalo
                con.close()
        finally:
            n.baixar_feed = original


class TestSistemaPromocoes(unittest.TestCase):
    def test_achar_cupons(self):
        import cupons
        texto = cupons.limpar_html('<p>Use o cupom <b>BOOSTER15</b> e ganhe 15% OFF em boosters!</p>'
                                   '<p>Frete GRÁTIS acima de R$ 199</p><p>Código: TCG2026</p>')
        achados = {c: p for c, p, _ in cupons.achar_cupons(texto)}
        self.assertEqual(achados.get("BOOSTER15"), 15.0)
        self.assertIn("TCG2026", achados)
        self.assertNotIn("GRÁTIS", achados)
        self.assertNotIn("OFF", achados)

    def test_comandos_do_admin(self):
        import cupons
        with tempfile.TemporaryDirectory() as d:
            con = bot.abrir_banco(Path(d) / "t.db")
            cupons.preparar_banco(con)
            con.execute("INSERT INTO cupons VALUES ('a','BOOSTER15',NULL,NULL,NULL,'candidato',NULL,'u','t','x')")
            self.assertIn("aprovado", cupons.aplicar_comando(con, "/cupom_ok booster15 15 30/12/2026 199"))
            ativos = cupons.cupons_aprovados(con)
            self.assertEqual((ativos[0]["codigo"], ativos[0]["percentual"], ativos[0]["minimo"]),
                             ("BOOSTER15", 15.0, 199.0))
            self.assertIn("descartado", cupons.aplicar_comando(con, "/cupom_ruim BOOSTER15"))
            self.assertEqual(cupons.cupons_aprovados(con), [])
            self.assertIsNone(cupons.aplicar_comando(con, "oi robô"))
            con.close()

    def test_preco_com_cupom(self):
        self.assertEqual(afiliados.preco_com_cupom(200.0, {"percentual": 10}), 180.0)
        self.assertEqual(afiliados.preco_com_cupom(150.0, {"percentual": 10, "minimo": 199}), 150.0)
        self.assertEqual(afiliados.preco_com_cupom(150.0, None), 150.0)

    def test_cupom_muda_o_vencedor_e_confianca_barra_loja(self):
        hoje = bot.agora().date()
        with tempfile.TemporaryDirectory() as d:
            con = bot.abrir_banco(Path(d) / "t.db")
            cfg = {"regras": {"desconto_minimo": 0.10, "alerta_suspeito": 0.40, "dias_historico": 30,
                              "minimo_leituras": 1, "confianca_minima": 3, "cupom_teste_dias": 7},
                   "lojas": [{"id": "a", "nome": "A", "aprovada": True, "confianca": 4},
                             {"id": "b", "nome": "B", "aprovada": True, "confianca": 5},
                             {"id": "c", "nome": "C", "aprovada": True, "confianca": 2}],
                   "cupons": [{"loja": "b", "codigo": "B20", "percentual": 20,
                               "valido_ate": (hoje + timedelta(days=5)).isoformat(),
                               "testado_em": hoje.isoformat()}],
                   "produtos": [{"nome": "Box", "referencia_manual": 1000,
                                 "ofertas": [{"loja": l, "url": f"http://{l}"} for l in "abc"]}]}
            for loja, preco in [("a", 800), ("b", 880), ("c", 700)]:
                for i in range(2):
                    con.execute("INSERT INTO precos VALUES (?,?,?,?,?,?,?)",
                                ("Box", loja, f"http://{loja}", preco, 1, None,
                                 bot.iso(bot.agora() - timedelta(minutes=30 * (2 - i)))))
            aprovadas, descartadas = bot.avaliar(cfg, con)
            con.close()
        self.assertEqual(aprovadas[0]["loja"], "b")            # 880 com 20% = 704, vence a A (800)
        self.assertEqual(aprovadas[0]["preco_final"], 704.0)
        self.assertIn("confiança", {x["loja"]: x["motivo"] for x in descartadas}["c"])  # C barrada


class TestAntiGolpe(unittest.TestCase):
    def setUp(self):
        self.cfg = {"anti_golpe": {"lista_negra": [{"dominio": "clone-loja.com", "motivo": "site clonado"}]}}

    def test_lista_negra(self):
        self.assertEqual(bot.na_lista_negra(self.cfg, "https://www.clone-loja.com/booster"), "site clonado")
        self.assertTrue(bot.na_lista_negra(self.cfg, "http://ofertas.clone-loja.com/x"))
        self.assertIsNone(bot.na_lista_negra(self.cfg, "https://lojaboa.com.br/x"))
        self.assertIsNone(bot.na_lista_negra(self.cfg, "https://naoclone-loja.com/x"))

    def test_termo_suspeito_no_nome(self):
        html = ('<script type="application/ld+json">{"@type":"Product","name":"Carta Charizard '
                'Proxy Holo","offers":{"price":"20","priceCurrency":"BRL"}}</script>')
        self.assertEqual(bot.extrair_nome(html), "Carta Charizard Proxy Holo")
        self.assertEqual(bot.termo_suspeito({}, bot.extrair_nome(html)), "proxy")
        self.assertIsNone(bot.termo_suspeito({}, "Booster Box Pokémon Lacrada Copag"))
        self.assertIsNone(bot.termo_suspeito({}, "Elite Trainer Box Escarlate e Violeta"))

    def test_avaliar_descarta_loja_da_lista_negra(self):
        tmp = tempfile.TemporaryDirectory()
        con = bot.abrir_banco(Path(tmp.name) / "t.db")
        cfg = {"regras": {"desconto_minimo": 0.10, "alerta_suspeito": 0.40, "dias_historico": 30,
                          "minimo_leituras": 1, "nao_repetir_horas": 24},
               "lojas": [{"id": "a", "nome": "A", "aprovada": True}],
               "produtos": [{"nome": "Box", "referencia_manual": 1000,
                             "ofertas": [{"loja": "a", "url": "https://clone-loja.com/box"}]}],
               **self.cfg}
        for i in range(2):
            con.execute("INSERT INTO precos VALUES (?,?,?,?,?,?,?)",
                        ("Box", "a", "https://clone-loja.com/box", 850, 1, None,
                         bot.iso(bot.agora() - timedelta(minutes=30 * (2 - i)))))
        aprovadas, descartadas = bot.avaliar(cfg, con)
        self.assertEqual(aprovadas, [])
        self.assertIn("anti-golpe", descartadas[0]["motivo"])
        con.close()
        tmp.cleanup()


class TestTextoOferta(unittest.TestCase):
    def test_formato_de_oferta(self):
        o = {"produto": "Case Reinado Delta", "loja_nome": "Loja A & Cia", "preco": 432.0,
             "ref": 549.0, "preco_final": 410.4, "visto": bot.iso(bot.agora()), "url": "http://a",
             "link": "http://a?tag=x", "afiliado": True, "bandeira": "🇧🇷", "unidades": 12,
             "unidade_nome": "blisters triplos", "unidade_singular": "blister triplo",
             "reputacao": "+500 vendas", "frete_gratis": True,
             "cupom": {"codigo": "ARCOS5", "descricao": "5% off", "valido_ate": "2026-12-01"}}
        t = bot.texto_telegram(o)
        for trecho in ["🇧🇷 CASE REINADO DELTA", "(12 blisters triplos)", "<s>R$ 549,00</s>",
                       "<b>R$ 432,00</b>", "21% abaixo", "Cada blister triplo sai por <b>R$ 34,20</b>",
                       "<b>ARCOS5</b>", "Loja A &amp; Cia", "+500 vendas", "Frete grátis",
                       "Compre aqui: http://a?tag=x", "Link de afiliado"]:
            self.assertIn(trecho, t)
        self.assertNotIn("últimas unidades", t.lower())


class TestRadarSites(unittest.TestCase):
    def test_trechos_site(self):
        pagina = ("<html><script>var x='R$ 1,00'</script><div>Booster Box Pokémon 36 "
                  "pacotes por R$ 799,90</div><div>Sleeve por R$ 30</div></html>")
        posts = radar.trechos_site("https://www.exemplo.com/promo", pagina)
        self.assertEqual(len(posts), 2)
        self.assertTrue(posts[0][0].startswith("site:exemplo.com:"))
        self.assertIn("Booster Box", posts[0][1])


class TestPlataformaLiga(unittest.TestCase):
    PAG = (
        '<html><head><title>(PT-BR) Caixa de Booster - For&ccedil;as Temporais | Loja X</title>'
        '<meta property="og:image" content="//repo.exemplo.com/img.jpg"/></head><body>'
        '<div class="table-produtos-body">'
        '<div class="table-produtos-row"><div class="title-mobile">Condi&#231;&#227;o</div><div>Lacrado</div>'
        '<div class="title-mobile">Estoque</div><div> 2 unid. </div>'
        '<div class="title-mobile">Pre&#231;o</div><div>R$ 1.299,90</div></div>'
        '<div class="table-produtos-row"><div class="title-mobile">Condi&#231;&#227;o</div><div>Usado</div>'
        '<div class="title-mobile">Estoque</div><div> 1 unid. <span title="Item sob encomenda."></span></div>'
        '<div class="title-mobile">Pre&#231;o</div><div>R$ 999,90</div></div>'
        '</div><div class="table-produtos-footer"></div>'
        '<div class="price"><span>R$ 4,99</span></div></body></html>')

    def test_le_preco_estoque_e_imagem(self):
        preco, estoque, img = bot.extrair_oferta(self.PAG)
        self.assertEqual(preco, 1299.90)  # a linha que não é "Lacrado" não conta
        self.assertTrue(estoque)
        self.assertEqual(img, "https://repo.exemplo.com/img.jpg")
        self.assertEqual(bot.extrair_nome(self.PAG), "(PT-BR) Caixa de Booster - Forças Temporais")

    def test_pre_venda_nao_posta(self):
        pag = self.PAG.replace("<body>", "<body>Item se encontra em PRE ORDER. Previsão de envio: 06/11")
        self.assertFalse(bot.extrair_oferta(pag)[1])

    def test_sem_estoque(self):
        pag = self.PAG.replace(" 2 unid. ", " 0 unid. ")
        preco, estoque, _ = bot.extrair_oferta(pag)
        self.assertFalse(estoque)


class TestMarketplaces(unittest.TestCase):
    ITEM = {"id": "MLB123", "price": 899.9, "currency_id": "BRL", "condition": "new",
            "status": "active", "available_quantity": 3, "seller_id": 9, "title": "Booster Box",
            "pictures": [{"secure_url": "https://http2.mlstatic.com/x.jpg"}]}

    def test_codigo_mlb(self):
        self.assertEqual(marketplaces.ml_id("https://produto.mercadolivre.com.br/MLB-3456789012-box-_JM"),
                         "MLB3456789012")
        self.assertIsNone(marketplaces.ml_id("https://www.mercadolivre.com.br/sem-codigo"))

    def test_loja_oficial_passa(self):
        preco, est, img, _, selo = marketplaces.interpretar_item_ml({**self.ITEM, "official_store_id": 77}, {})
        self.assertEqual((preco, est, selo), (899.9, True, "Loja Oficial"))
        self.assertTrue(img.startswith("https://"))

    def test_platinum_verde_passa_e_vendedor_comum_e_barrado(self):
        bom = {"seller_reputation": {"power_seller_status": "platinum", "level_id": "5_green"}}
        self.assertEqual(marketplaces.interpretar_item_ml(self.ITEM, bom)[4], "MercadoLíder Platinum")
        comum = {"seller_reputation": {"power_seller_status": None, "level_id": "3_yellow"}}
        with self.assertRaises(ValueError):
            marketplaces.interpretar_item_ml(self.ITEM, comum)
        with self.assertRaises(ValueError):  # usado nunca
            marketplaces.interpretar_item_ml({**self.ITEM, "condition": "used", "official_store_id": 1}, {})

    def test_catalogo_escolhe_mais_barata_confiavel(self):
        ofertas = [{"item_id": "MLB1", "price": 300.0, "seller_id": 1, "condition": "new"},          # vendedor comum
                   {"item_id": "MLB2", "price": 349.9, "official_store_id": 236642, "condition": "new"},
                   {"item_id": "MLB3", "price": 360.0, "official_store_id": 999, "condition": "new"}]
        so_pokemon = {"ml_lojas_oficiais": [236642]}
        o, selo = marketplaces.escolher_oferta_catalogo(ofertas, {}, so_pokemon)
        self.assertEqual((o["item_id"], selo), ("MLB2", "Loja Oficial"))
        vend = {1: {"seller_reputation": {"power_seller_status": "gold", "level_id": "5_green"}}}
        o, selo = marketplaces.escolher_oferta_catalogo(ofertas, vend, {})
        self.assertEqual(o["item_id"], "MLB1")  # gold verde é aceito no modo geral
        self.assertEqual(marketplaces.ml_catalogo_id("https://www.mercadolivre.com.br/box/p/MLB74773271?x=1"), "MLB74773271")

    def test_aviso_de_compra_livre_em_todo_post(self):
        o = {"produto": "Box", "loja_nome": "Loja", "preco": 90.0, "ref": 100.0,
             "visto": bot.iso(bot.agora()), "url": "http://a", "afiliado": True, "descricao": "Lacrado"}
        self.assertIn("livre e espontânea", bot.texto_telegram(o))
        cfg = {"instagram": {"hashtags": []}}
        self.assertIn("não forçamos nem incentivamos", bot.texto_instagram(o, cfg))


class TestArteCarta(unittest.TestCase):
    def test_arte_mantem_a_carta_e_rumor_nao_busca_imagem(self):
        from PIL import Image
        import carrossel
        import noticias
        carta = Image.new("RGB", (734, 1024), (10, 200, 30))
        st = carrossel.arte_carta_story(carta, "Nova carta revelada", "Pokémon", "The Pokémon Company", semente=1)
        self.assertEqual(st.size, (1080, 1920))
        self.assertEqual(st.getpixel((540, 830))[:3], (10, 200, 30))  # centro da carta intacto
        self.assertIsNone(noticias.imagem_oficial({"link": "http://x"}, {"tipo": "forum"}))
        self.assertIsNone(noticias.imagem_oficial({"link": "http://x"}, {"tipo": "imprensa"}))

    def test_rss_com_imagem(self):
        import noticias
        xml = ('<rss xmlns:media="http://search.yahoo.com/mrss/"><channel><item><title>New card</title>'
               '<link>http://o.com/a</link><media:content url="http://o.com/c.jpg"/></item></channel></rss>')
        self.assertEqual(noticias.ler_feed(xml)[0]["imagem"], "http://o.com/c.jpg")


class TestComandoCentral(unittest.TestCase):
    def test_ajuda_e_comando_desconhecido(self):
        import arcos
        self.assertEqual(arcos.main([]), 0)
        self.assertEqual(arcos.main(["inexistente"]), 2)
        self.assertIn(("promocoes", "preparar"), arcos.COMANDOS)
        self.assertIn(("noticias", "fontes"), arcos.COMANDOS)
