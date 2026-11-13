from datetime import date

from farmared import reloj


def test_hoy_fijo_por_variable(monkeypatch):
    monkeypatch.setenv("FARMARED_HOY", "2026-10-13")
    assert reloj.hoy() == date(2026, 10, 13)


def test_hoy_real_sin_variable(monkeypatch):
    monkeypatch.delenv("FARMARED_HOY", raising=False)
    assert isinstance(reloj.hoy(), date)


def test_limites_de_mes():
    assert reloj.inicio_mes(date(2026, 11, 13)) == date(2026, 11, 1)
    assert reloj.inicio_mes_siguiente(date(2026, 12, 31)) == date(2027, 1, 1)
    assert reloj.inicio_mes_siguiente(date(2026, 2, 28)) == date(2026, 3, 1)
