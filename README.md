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
   Indica el `tipo_sesion` según la materia (art. 15, Ley 21.442):

   | tipo_sesion | Para constituir | Para aprobar |
   |---|---|---|
   | `ordinaria` | ≥ 33 % de los derechos | mayoría absoluta de quienes participan |
   | `absoluta` | > 50 % de los derechos | > 50 % de los derechos del condominio |
   | `reforzada` | ≥ 66 % de los derechos | ≥ 66 % de los derechos del condominio |

   El sitio muestra cuántos deptos deben votar y cuántos votos a favor se necesitan,
   a partir de `total_unidades` en `config.yaml`.
   Para validar sin publicar, ejecuta `python build.py --check`.
2. **Padrón (en tu computador, nunca en GitHub):** exporta la lista de propietarios
   (p. ej. desde ComunidadFeliz) a `padron/padron.csv` con las columnas
   `depto,nombre,rut,email[,habilitado]` y ejecuta:
   ```
   python padron.py padron/padron.csv               # un voto por depto
   python padron.py padron/padron.csv --ponderado   # si algún día se pondera (requiere columna prorrateo)
   ```
   El script valida RUT (dígito verificador), correos y deptos duplicados. Genera `padron/belenios_votantes.txt` y
   `padron/reporte.txt`, este último con las unidades habilitadas y los quórums
   de cada tipo de sesión (o solo del tipo indicado con `--tipo absoluta`).
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
(a) un voto por departamento, porque todas las unidades pesan igual;
(b) las máquinas expendedoras se tratan con mayoría reforzada (66 %);
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

Con el formato `correo,login,peso`, el peso es un entero igual al
prorrateo × 10 000 (un 0,8523 % queda como 8523). Antes de la primera votación
real, confirma en la documentación de Belenios que el servidor que usen acepta
pesos con ese formato, y haz una votación de prueba con 3–4 personas.

## Desarrollo local

```
pip install -r requirements.txt
python build.py && python -m http.server -d _site
```
