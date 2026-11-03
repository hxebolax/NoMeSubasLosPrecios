"""Notificaciones con el ``wx.adv.NotificationMessage`` real (sin mostrarlas en pantalla)."""

from __future__ import annotations

import wx
import wx.adv

from app.ui import notificaciones


def test_hay_enlazadores_de_eventos_en_esta_version_de_wx():
	# En wxPython 4.3.2 no existe wx.adv.EVT_NOTIFICATION_MESSAGE_CLICK: se crea desde wxEVT_...
	assert notificaciones.EVT_PULSADA is not None
	assert notificaciones.EVT_DESCARTADA is not None


def test_mostrar_y_pulsar_abre_el_producto(app_wx, monkeypatch):
	monkeypatch.setattr(wx.adv.NotificationMessage, "Show", lambda self, tiempo=0: True)
	marco = wx.Frame(None)
	pulsados: list[int | None] = []
	try:
		notificador = notificaciones.Notificador(marco, pulsados.append)
		assert notificador.mostrar("Ha bajado de precio", "Producto: de 10,00 € a 9,00 €", producto_id=7) is True
		notificacion = notificador._vivas[-1]
		evento = wx.CommandEvent(notificaciones.EVT_PULSADA.typeId)
		evento.SetEventObject(notificacion)
		notificacion.ProcessEvent(evento)
		assert pulsados == [7]
	finally:
		marco.Destroy()


def test_un_fallo_de_wx_no_rompe_la_comprobacion(app_wx, monkeypatch):
	def falla(self, tiempo=0):
		raise AttributeError("simulado")

	monkeypatch.setattr(wx.adv.NotificationMessage, "Show", falla)
	marco = wx.Frame(None)
	try:
		assert notificaciones.Notificador(marco, lambda _p: None).mostrar("Título", "Mensaje") is False
	finally:
		marco.Destroy()
