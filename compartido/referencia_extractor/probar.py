"""Prueba el prototipo contra páginas reales.

Uso:
  python -I probar.py --cache <carpeta>      lee páginas ya descargadas (JSON {url, estado, html})
  python -I probar.py --urls urls.txt        descarga cada URL UNA vez (no guarda las páginas)

Escribe resultados.json y resultados.txt junto a este archivo. Nunca guarda el HTML.
"""
import json
import os
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import extractor_generico as eg  # noqa: E402
from descarga import descargar, crear_abridor, parece_bloqueo  # noqa: E402
from selector_css import generar_selector, validar_selector  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402


def paginas(args):
    if args[0] == "--cache":
        for f in sorted(os.listdir(args[1])):
            yield json.load(open(os.path.join(args[1], f), encoding="utf-8"))
    else:
        for url in [l.strip() for l in open(args[1], encoding="utf-8-sig") if l.strip() and not l.startswith("#")]:
            estado, final, html = descargar(url, crear_abridor())
            yield {"url": url, "estado": estado, "final": final, "html": html}
            time.sleep(2)


def main():
    esperados = json.load(open(os.path.join(AQUI, "esperados.json"), encoding="utf-8"))
    filas = []
    for pag in paginas(sys.argv[1:]):
        url, html = pag["url"], pag["html"]
        fila = {"url": url, "estado": pag["estado"]}
        if parece_bloqueo(pag["estado"], html) or pag["estado"] != 200:
            fila["resultado"] = "bloqueada (no se intenta saltar)"
            filas.append(fila)
            continue
        esperado = esperados.get(url, {}).get("precio")
        fila["esperado"] = esperado
        fila["nota"] = esperados.get(url, {}).get("nota", "")
        t0 = time.time()
        completo = eg.extraer(html, url, usar_basico=True)
        ciego = eg.extraer(html, url, usar_basico=False)
        # Solo heurística visible: sin plataforma ni estado (para medir la heurística sola)
        guardado = eg.PLATAFORMAS.copy()
        eg.PLATAFORMAS.clear()
        solo_vis = eg.extraer(html, url, usar_basico=False)
        eg.PLATAFORMAS.update(guardado)
        fila["segundos"] = round(time.time() - t0, 2)
        fila["plataformas"] = completo["plataformas"]
        fila["completo"] = {"precio": completo["precio"], "fuente": completo["fuente"]}
        fila["sin_jsonld_ni_metas"] = {"precio": ciego["precio"], "fuente": ciego["fuente"], "confianza": ciego["confianza"]}
        fila["solo_heuristica_visible"] = {"precio": solo_vis["precio"], "fuente": solo_vis["fuente"]}
        fila["ocultos"] = ciego["ocultos"][:8]
        fila["candidatos"] = solo_vis["candidatos"][:6]
        fila["lista_para_usuario"] = [eg.describir_candidato(c) for c in solo_vis["candidatos"][:5]]
        fila["anclas"] = solo_vis.get("anclas")
        for clave in ("completo", "sin_jsonld_ni_metas", "solo_heuristica_visible"):
            p = fila[clave]["precio"]
            fila[clave]["acierta"] = (p == esperado) if esperado is not None else (p is None)
        # Selector CSS para el mejor candidato visible (simula «el usuario elige el primero»)
        if solo_vis.get("elemento") is not None or solo_vis["candidatos"]:
            sopa = BeautifulSoup(html, "html.parser")
            vis, _ = eg.candidatos_visibles(sopa)
            vis.sort(key=lambda c: -c.puntos)
            objetivo = next((c for c in vis if c.valor == esperado), None)
            if objetivo is not None:
                sel, atributo = generar_selector(objetivo.elemento, sopa)
                fila["selector_generado"] = {"css": sel, "atributo": atributo,
                                             "valido": validar_selector(sopa, sel, atributo, esperado)}
        filas.append(fila)
        print(url, "->", fila["sin_jsonld_ni_metas"], "| visible:", fila["solo_heuristica_visible"]["precio"], "| esperado:", esperado, flush=True)

    probadas = [f for f in filas if "esperado" in f]
    resumen = {k: sum(1 for f in probadas if f[k]["acierta"]) for k in ("completo", "sin_jsonld_ni_metas", "solo_heuristica_visible")}
    falsos = {k: sum(1 for f in probadas if f[k]["precio"] is not None and not f[k]["acierta"]) for k in resumen}
    salida = {"paginas": len(filas), "probadas": len(probadas), "bloqueadas": len(filas) - len(probadas),
              "aciertos": resumen, "precios_falsos": falsos, "filas": filas}
    json.dump(salida, open(os.path.join(AQUI, "resultados.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    with open(os.path.join(AQUI, "resultados.txt"), "w", encoding="utf-8") as f:
        f.write("Páginas probadas: %d. Bloqueadas: %d.\n" % (len(probadas), len(filas) - len(probadas)))
        for k in resumen:
            f.write("%s: %d aciertos de %d, %d precios falsos.\n" % (k, resumen[k], len(probadas), falsos[k]))
        f.write("\n")
        for fi in probadas:
            f.write("- %s\n" % fi["url"])
            f.write("  Esperado: %s. %s\n" % (fi["esperado"], fi["nota"]))
            f.write("  Plataformas: %s\n" % ", ".join(fi["plataformas"]))
            for k in ("completo", "sin_jsonld_ni_metas", "solo_heuristica_visible"):
                f.write("  %s: %s (%s) %s\n" % (k, fi[k]["precio"], fi[k]["fuente"], "acierta" if fi[k]["acierta"] else "FALLA"))
            if fi.get("selector_generado"):
                s = fi["selector_generado"]
                f.write("  Selector generado: %s%s, válido: %s\n" % (s["css"], " (atributo %s)" % s["atributo"] if s["atributo"] else "", s["valido"]))
            f.write("  Lista que vería el usuario:\n")
            for linea in fi["lista_para_usuario"]:
                f.write("    - %s\n" % linea)
    print(json.dumps({k: salida[k] for k in ("paginas", "probadas", "bloqueadas", "aciertos", "precios_falsos")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
