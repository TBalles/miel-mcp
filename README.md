# miel-mcp

Servidor [MCP](https://modelcontextprotocol.io) para consultar **MIeL** (Materias Interactivas en Línea, UNLaM) desde Claude u otro cliente MCP: listar materias, ver y descargar contenidos, sincronizarlos a una carpeta local y leer los foros.

> Proyecto no oficial, hecho por un alumno para uso personal. No está afiliado a la UNLaM.
> Es **solo lectura**: no publica mensajes ni modifica nada en MIeL.

## Tools

| Tool | Qué hace |
|---|---|
| `listar_materias` | Materias activas (o también las ocultas), con id de comisión y mensajes sin leer del foro. |
| `listar_archivos` | Contenidos de una materia, con filtro por tipo (`teoria`, `practicas`, `enlaces`) y palabra clave. |
| `descargar_archivo` | Baja un archivo a la carpeta local y devuelve la ruta. |
| `sincronizar_materia` | Baja solo lo nuevo de una materia, o de todas si no se indica ninguna. |
| `listar_temas_foro` | Temas del foro con cantidad de mensajes y sin leer. |
| `leer_tema_foro` | Mensajes de un tema (autor, fecha, texto, enlaces). |
| `novedades` | Archivos y mensajes de foro nuevos desde la última consulta. |

`materia` acepta el id de comisión o parte del nombre, sin importar acentos ni mayúsculas (`"ingles"`, `"inteligencia"`).

## Instalación

Requiere [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/TBalles/miel-mcp.git
cd miel-mcp
uv sync
```

Copiá `.env.example` a `.env` y completá tus datos:

```env
MIEL_USUARIO=tu_dni_o_usuario
MIEL_CLAVE=tu_clave
# Opcional, por defecto ~/MIeL
MIEL_DESCARGAS=D:/Facultad/MIeL
```

El `.env` está en `.gitignore`: tus credenciales nunca se suben al repo.

## Uso con Claude Code

```bash
claude mcp add miel -- uv --directory /ruta/a/miel-mcp run miel-mcp
```

## Uso con Claude Desktop

En `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "miel": {
      "command": "uv",
      "args": ["--directory", "C:/ruta/a/miel-mcp", "run", "miel-mcp"]
    }
  }
}
```

Después podés pedir cosas como *"¿hay novedades en MIeL?"*, *"bajame todo lo de Inteligencia Artificial"* o *"¿qué dijeron en el foro de Inglés?"*.

## Cómo funciona

MIeL renderiza todo del lado del servidor, así que alcanza con `httpx` + `BeautifulSoup`, sin navegador:

- Login por `POST /principal/event/login/` y verificación con `/principal/event/isLogged/`. Si la sesión vence, se reloguea sola.
- Materias: `/principal/interno/`
- Contenidos: `/contenido/archivos/comision/{id}`
- Foro: `/forov2/temas/comision/{id}` y `/forov2/mensajes/comision/{id}/tema/{tema}`

Los archivos se guardan en `MIEL_DESCARGAS/<Materia>/<Carpeta>/`. El estado de sincronización y novedades vive en `MIEL_DESCARGAS/.miel_estado.json`.

Hay una pausa de 0,5 s entre descargas para no cargar al servidor de la facultad. Usalo con moderación y respetá el [aviso legal de MIeL](https://miel.unlam.edu.ar/principal/legal/).

## Tests

```bash
uv run pytest
```

Los tests usan fixtures HTML anonimizados en `tests/fixtures/`, con la misma estructura que las páginas reales. Si MIeL cambia su HTML y algo se rompe, actualizar el fixture y el parser en `src/miel_mcp/parsers.py`.

## Licencia

MIT
