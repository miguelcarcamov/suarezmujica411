# Votaciones de la comunidad Suárez Mujica 411

Sitio informativo (GitHub Pages) + herramienta de padrón para votar con
[Belenios](https://www.belenios.org). El voto se emite **siempre en Belenios**;
este sitio solo muestra antecedentes, plazos, instructivo y el botón "Ir a votar".

El repositorio es público. No lleva RUT, nombres, correos de copropietarios
ni claves. El padrón real se queda en el computador de quien arma la elección.

## Instalación (una sola vez)

1. Crea un repo en GitHub y sube esta carpeta.
2. En el repo: **Settings → Pages → Source: GitHub Actions**.
3. Edita `config.yaml` (nombre de la comunidad, correo de contacto, color).

Cada `push` a `main` publica el sitio automáticamente.

## Nueva votación (4 pasos)

1. **Ficha:** copia `ejemplos/plantilla-eleccion.yaml` a `elecciones/AAAA-MM-tema.yaml`
   y edita título, fechas, antecedentes y preguntas. Deja `borrador: true` hasta
   que fechas, antecedentes y el enlace de Belenios estén listos: así el sitio
   no muestra un botón de votar.
   Indica el `tipo_sesion` según la materia. El sitio enlaza el [artículo 15 de la Ley 21.442](https://www.bcn.cl/leychile/navegar?idNorma=1174663&idParte=10326608) (texto vigente, Biblioteca del Congreso Nacional):

   | tipo_sesion | Para constituir | Para aprobar |
   |---|---|---|
   | `ordinaria` | ≥ 33 % de los derechos | mayoría absoluta de quienes participan |
   | `absoluta` | > 50 % de los derechos | > 50 % de los derechos del condominio |
   | `reforzada` | ≥ 66 % de los derechos | ≥ 66 % de los derechos del condominio |

   El sitio muestra cuántos deptos deben votar y cuántos votos a favor se necesitan,
   a partir de `total_unidades` en `config.yaml`.
   Para validar sin publicar, ejecuta `python build.py --check`.
2. **Padrón (en tu computador, nunca en GitHub):** deja en `datos_info/` el Excel de
   residentes y el de morosas, y genera el CSV + valida en un solo paso:
   ```
   python padron_desde_excel.py --y-validar --ponderado --tipo reforzada
   ```
   Eso escribe `padron/padron.csv` (una fila por unidad, correo del dueño,
   morosas en `habilitado=no`), `padron/avisos_desde_excel.txt` y
   `padron/pendientes_correo.csv` (deptos habilitados sin mail de dueño). Los
   correos que se repiten entre deptos son normales si es el mismo dueño:
   Belenios manda una credencial por unidad. Si solo quieres armar el CSV:
   ```
   python padron_desde_excel.py
   python padron.py padron/padron.csv --ponderado --tipo reforzada
   ```
   `padron.py` valida correos/deptos (y RUT si viene), y genera
   `padron/belenios_votantes.txt` más `padron/reporte.txt` con los quórums.
3. **Belenios:** crea la elección en el servidor público con las mismas preguntas.
   En "Votantes", pega `belenios_votantes.txt` y luego envía las credenciales.
   Copia el enlace de la elección en `url_belenios` del YAML y haz push.
4. **Cierre:** cuando cierre la votación, descifra el resultado en Belenios y evalúa
   si se aprobó:
   ```
   python quorum.py --tipo absoluta --total 40 --participan 31 --a-favor 24
   ```
   Luego pega el enlace de resultados en `url_resultados` y haz push.

**Decisiones de esta comunidad, a contrastar con el reglamento antes de abrir:**
(a) voto ponderado por prorrateo (alícuota de cada unidad);
(b) las máquinas expendedoras se tratan con mayoría reforzada (66 % de los derechos);
(c) los quórums se calculan sobre el total de unidades, incluidas las no habilitadas;
(d) en una consulta ordinaria, "asistentes" equivale a quienes votan.
`total_unidades` en `config.yaml` sigue vacío a propósito: el sitio muestra el
porcentaje y no un número de departamentos sin confirmar.

El estado de la votación (Próximamente / Abierta / Cerrada) y la cuenta regresiva
se calculan en el navegador con las fechas del YAML, así que no hace falta
volver a publicar para que cambien.

## Privacidad

- `padron/` está en `.gitignore`, salvo `padron/ejemplo.csv`. Ese CSV es ficticio
  (unidades de ejemplo y RUT de prueba); el padrón real nunca se sube al repo.
- A Belenios solo llegan el correo, el número de depto (como login) y el peso.
  El RUT se usa únicamente para el crosscheck local.

## Pesos en Belenios (solo con --ponderado)

Con el formato `correo,login,peso`, el peso es un entero. El script acepta
prorrateo como porcentaje (suma ≈ 100) o como fracción/alícuota (suma ≈ 1).
Ejemplo con alícuota 0,004554 (suma de todas ≈ 1): peso 4554. Con porcentaje
0,4554 (suma de todas ≈ 100): peso 4554. Usa
`python padron.py padron/padron.csv --ponderado`. Haz una votación de prueba
con 3–4 personas antes de la real.

## Desarrollo local

```
pip install -r requirements.txt
python build.py && python -m http.server -d _site
```
