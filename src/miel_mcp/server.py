"""Servidor MCP de MIeL. Solo lectura: no publica nada en la plataforma."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer

from .client import MielClient, MielError, nombre_seguro

load_dotenv()

mcp = MCPServer(
    "miel",
    instructions="Acceso de solo lectura a MIeL (UNLaM): materias, contenidos, descargas y foros.",
)

_client: MielClient | None = None

# Pausa entre descargas para no castigar al servidor de la facultad.
PAUSA_DESCARGAS = 0.5


def client() -> MielClient:
    global _client
    if _client is None:
        _client = MielClient(os.getenv("MIEL_USUARIO", ""), os.getenv("MIEL_CLAVE", ""))
    return _client


def carpeta_descargas() -> Path:
    # `or`: una variable definida pero vacía en el .env también usa el default.
    return Path(os.getenv("MIEL_DESCARGAS") or Path.home() / "MIeL").expanduser().resolve()


def _ruta_estado() -> Path:
    return carpeta_descargas() / ".miel_estado.json"


def _leer_estado() -> dict:
    try:
        return json.loads(_ruta_estado().read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _guardar_estado(estado: dict) -> None:
    ruta = _ruta_estado()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8")


def _error(e: Exception) -> dict:
    return {"error": str(e)}


@mcp.tool()
def listar_materias(incluir_ocultas: bool = False) -> list[dict] | dict:
    """Lista las materias del alumno en MIeL con su id de comisión, detalle
    (código y comisión), herramientas disponibles y mensajes sin leer del foro."""
    try:
        return [m.to_dict() for m in client().materias(incluir_ocultas)]
    except MielError as e:
        return _error(e)


@mcp.tool()
def listar_archivos(materia: str, tipo: str = "todos", buscar: str = "") -> dict:
    """Lista los contenidos (archivos y enlaces) de una materia.

    Args:
        materia: id de comisión o parte del nombre (ej. "inteligencia", "ingles").
        tipo: "todos", "teoria", "practicas" o "enlaces".
        buscar: palabra clave opcional para filtrar.
    """
    try:
        m = client().resolver_materia(materia)
        archivos = client().archivos(m.id, tipo, buscar)
        return {"materia": m.nombre, "comision": m.id, "archivos": [a.to_dict() for a in archivos]}
    except MielError as e:
        return _error(e)


@mcp.tool()
def descargar_archivo(materia: str, archivo_id: str) -> dict:
    """Descarga un archivo de una materia a la carpeta local de MIeL y devuelve
    la ruta, para poder leerlo después. `archivo_id` sale de listar_archivos."""
    try:
        m = client().resolver_materia(materia)
        archivo = next((a for a in client().archivos(m.id) if a.id == archivo_id), None)
        if archivo is None:
            return _error(MielError(f"No existe el archivo {archivo_id} en {m.nombre}."))
        destino = carpeta_descargas() / nombre_seguro(m.nombre) / nombre_seguro(archivo.carpeta or "General")
        ruta = client().descargar(archivo, destino)
        return {"archivo": archivo.nombre, "ruta": str(ruta), "bytes": ruta.stat().st_size}
    except MielError as e:
        return _error(e)


def _sincronizar(materia_id: str, nombre: str, estado: dict) -> dict:
    descargados = estado.setdefault(materia_id, {}).setdefault("descargados", {})
    nuevos, enlaces, errores = [], [], []
    for a in client().archivos(materia_id):
        if a.es_enlace:
            enlaces.append({"nombre": a.nombre, "url": a.url})
            continue
        if a.id in descargados and Path(descargados[a.id]).exists():
            continue
        destino = carpeta_descargas() / nombre_seguro(nombre) / nombre_seguro(a.carpeta or "General")
        try:
            ruta = client().descargar(a, destino)
        except Exception as e:  # un archivo roto no frena la sincronización
            errores.append({"nombre": a.nombre, "error": str(e)})
            continue
        descargados[a.id] = str(ruta)
        nuevos.append(str(ruta))
        time.sleep(PAUSA_DESCARGAS)
    return {
        "materia": nombre,
        "carpeta": str(carpeta_descargas() / nombre_seguro(nombre)),
        "nuevos": nuevos,
        "ya_descargados": len(descargados) - len(nuevos),
        "enlaces_externos": enlaces,
        "errores": errores,
    }


@mcp.tool()
def sincronizar_materia(materia: str = "") -> list[dict] | dict:
    """Descarga solo los archivos nuevos de una materia (o de todas las materias
    activas si `materia` está vacío) a la carpeta local. Los enlaces externos se
    listan pero no se descargan."""
    try:
        estado = _leer_estado()
        if materia:
            objetivos = [client().resolver_materia(materia)]
        else:
            objetivos = client().materias()
        resultado = []
        for m in objetivos:
            resultado.append(_sincronizar(m.id, m.nombre, estado))
            _guardar_estado(estado)
        return resultado
    except MielError as e:
        return _error(e)


@mcp.tool()
def listar_temas_foro(materia: str) -> dict:
    """Lista los temas del foro de una materia con cantidad de mensajes,
    fecha del último mensaje y cuántos hay sin leer."""
    try:
        m = client().resolver_materia(materia)
        return {"materia": m.nombre, "temas": [t.to_dict() for t in client().temas_foro(m.id)]}
    except MielError as e:
        return _error(e)


@mcp.tool()
def leer_tema_foro(materia: str, tema_id: str) -> dict:
    """Devuelve los mensajes de un tema del foro (autor, rol, fecha, texto y
    enlaces). `tema_id` sale de listar_temas_foro. Leerlo puede marcarlo como
    leído en MIeL."""
    try:
        m = client().resolver_materia(materia)
        mensajes = client().mensajes_foro(m.id, tema_id)
        return {"materia": m.nombre, "tema": tema_id, "mensajes": [x.to_dict() for x in mensajes]}
    except MielError as e:
        return _error(e)


@mcp.tool()
def novedades() -> list[dict] | dict:
    """Muestra qué cambió desde la última consulta en cada materia activa:
    archivos nuevos y temas del foro con mensajes nuevos. La primera vez
    toma todo como visto y devuelve el estado inicial."""
    try:
        estado = _leer_estado()
        resultado = []
        for m in client().materias():
            datos = estado.setdefault(m.id, {})
            primera_vez = "vistos" not in datos
            vistos = set(datos.get("vistos", []))
            temas_previos = datos.get("temas", {})

            archivos = client().archivos(m.id)
            nuevos = [a.to_dict() for a in archivos if a.id not in vistos]
            temas = client().temas_foro(m.id)
            temas_nuevos = [
                t.to_dict()
                for t in temas
                if t.mensajes > temas_previos.get(t.id, {}).get("mensajes", 0)
            ]

            datos["vistos"] = sorted(vistos | {a.id for a in archivos})
            datos["temas"] = {t.id: {"mensajes": t.mensajes, "ultimo": t.ultimo_mensaje} for t in temas}

            if primera_vez:
                resultado.append({"materia": m.nombre, "primera_vez": True,
                                  "archivos": len(archivos), "temas": len(temas)})
            elif nuevos or temas_nuevos:
                resultado.append({"materia": m.nombre, "archivos_nuevos": nuevos,
                                  "temas_con_mensajes_nuevos": temas_nuevos})
        _guardar_estado(estado)
        return resultado or [{"mensaje": "Sin novedades desde la última consulta."}]
    except MielError as e:
        return _error(e)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
