"""Gráfica de línea del precio en el tiempo (decorativa para el lector de pantalla).

Lo importante ya está en el resumen hablado y en la lista del historial; la
gráfica es para quien ve la pantalla. Por eso no recibe el foco (no hay que
pasar por ella con Tab) y su nombre accesible explica qué es. Se dibuja con
los colores del sistema para respetar el alto contraste.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import wx

from app.services.importes import formato_importe
from app.services.repositorio import leer_fecha


class GraficaPrecios(wx.Panel):
	"""Panel que dibuja la evolución del precio."""

	def __init__(self, padre: wx.Window, historial: Sequence[Mapping[str, Any]], moneda: str = "EUR") -> None:
		super().__init__(padre, size=padre.FromDIP(wx.Size(520, 180)), name="Gráfica del precio (decorativa)")
		self.historial = list(historial)
		self.moneda = moneda
		self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
		self.Bind(wx.EVT_PAINT, self._al_pintar)
		self.Bind(wx.EVT_SIZE, lambda evento: (self.Refresh(), evento.Skip()))

	def AcceptsFocus(self) -> bool:  # noqa: N802 - API de wx
		return False

	def AcceptsFocusFromKeyboard(self) -> bool:  # noqa: N802 - API de wx
		return False

	def puntos(self) -> list[tuple[float, float]]:
		"""(segundos desde el primero, precio) de las filas con precio."""
		datos = []
		for fila in self.historial:
			fecha, precio = leer_fecha(fila.get("fecha")), fila.get("precio")
			if fecha is not None and precio is not None:
				datos.append((fecha.timestamp(), float(precio)))
		return datos

	def _al_pintar(self, _evento: wx.PaintEvent) -> None:
		dc = wx.AutoBufferedPaintDC(self)
		fondo = wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOW)
		texto = wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOWTEXT)
		linea = wx.SystemSettings.GetColour(wx.SYS_COLOUR_HIGHLIGHT)
		dc.SetBackground(wx.Brush(fondo))
		dc.Clear()
		dc.SetTextForeground(texto)
		ancho, alto = self.GetClientSize()
		puntos = self.puntos()
		if len(puntos) < 1:
			dc.DrawText("Sin datos para la gráfica", 10, 10)
			return
		margen_izq, margen = self.FromDIP(80), self.FromDIP(14)
		x0, y0, x1, y1 = margen_izq, margen, ancho - margen, alto - margen * 2
		if x1 <= x0 or y1 <= y0:
			return
		tiempos = [t for t, _p in puntos]
		precios = [p for _t, p in puntos]
		t_min, t_max = min(tiempos), max(tiempos)
		p_min, p_max = min(precios), max(precios)
		if p_max == p_min:
			p_min, p_max = p_min * 0.95, p_max * 1.05 or 1
		if t_max == t_min:
			t_max = t_min + 1

		def a_pantalla(t: float, p: float) -> wx.Point:
			x = x0 + (t - t_min) / (t_max - t_min) * (x1 - x0)
			y = y1 - (p - p_min) / (p_max - p_min) * (y1 - y0)
			return wx.Point(int(x), int(y))

		dc.SetPen(wx.Pen(texto, 1))
		dc.DrawLine(x0, y0, x0, y1)
		dc.DrawLine(x0, y1, x1, y1)
		dc.DrawText(formato_importe(max(precios), self.moneda), 4, y0 - 6)
		dc.DrawText(formato_importe(min(precios), self.moneda), 4, y1 - 12)
		# Escalones: el precio se mantiene hasta el siguiente cambio.
		trazo: list[wx.Point] = []
		for indice, (t, p) in enumerate(puntos):
			if indice:
				trazo.append(a_pantalla(t, puntos[indice - 1][1]))
			trazo.append(a_pantalla(t, p))
		trazo.append(a_pantalla(t_max, puntos[-1][1]))
		dc.SetPen(wx.Pen(linea, self.FromDIP(2)))
		if len(trazo) > 1:
			dc.DrawLines(trazo)
		dc.SetBrush(wx.Brush(linea))
		for t, p in puntos:
			dc.DrawCircle(a_pantalla(t, p), self.FromDIP(3))
