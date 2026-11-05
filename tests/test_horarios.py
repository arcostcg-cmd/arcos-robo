from datetime import datetime, timedelta, timezone

import curiosidades

BR = timezone(timedelta(hours=-3))


def test_quinta_9h_sim_10h_nao():
    cfg = {"instagram": {"horarios_feed": curiosidades.PADRAO_HORARIOS}}
    assert curiosidades.horario_do_dia(cfg, datetime(2026, 11, 5, 9, 20, tzinfo=BR)) == 9
    assert curiosidades.horario_do_dia(cfg, datetime(2026, 11, 5, 10, 5, tzinfo=BR)) is None
    assert curiosidades.horario_do_dia(cfg, datetime(2026, 11, 8, 21, 0, tzinfo=BR)) == 21
