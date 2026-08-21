# KrizDent

Sistema web para centro odontológico: pacientes, agenda, historial clínico con
radiografías y odontograma interactivo de 32 piezas.

**Flask + Supabase (PostgreSQL + Storage) + Bootstrap 5.**

---

## 1. Instalación

```bash
# 1. Entra a la carpeta del proyecto
cd krisdent

# 2. Crea un entorno virtual
python -m venv .venv

#    Windows
.venv\Scripts\activate
#    macOS / Linux
source .venv/bin/activate

# 3. Instala las dependencias
pip install -r requirements.txt
```

## 2. Configura Supabase

**a) Crea las tablas.** En tu proyecto de Supabase entra a **SQL Editor → New
query**, pega todo el contenido de `schema.sql` y pulsa **Run**.

**b) Crea el bucket de imágenes.** Ve a **Storage → New bucket**:

| Campo | Valor |
|---|---|
| Name | `historial` |
| Public bucket | activado |

**c) Copia tus credenciales.** En **Project Settings → Data API** está la
*Project URL*; en **Project Settings → API Keys** está la llave `service_role`
(la marcada como *secret*).

**d) Crea el archivo `.env`** a partir del ejemplo:

```bash
cp .env.example .env      # en Windows:  copy .env.example .env
```

Ábrelo y pega tus valores:

```
SUPABASE_URL=https://abcdefgh.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6...
SUPABASE_BUCKET=historial
SECRET_KEY=una-cadena-larga-y-aleatoria
FLASK_DEBUG=1
```

Para generar el `SECRET_KEY`:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

## 3. Ejecuta

```bash
python app.py
```

Abre **http://localhost:5000**.

Para que la segunda persona del consultorio entre desde otra PC de la misma red,
averigua la IP de esta máquina (`ipconfig` en Windows, `ip addr` en Linux) y que
abra `http://192.168.x.x:5000`. La app ya escucha en `0.0.0.0`.

---

## Estructura

```
krisdent/
├── app.py                      Arranque de Flask y registro de blueprints
├── requirements.txt
├── .env.example                Plantilla de variables de entorno
├── schema.sql                  Tablas para ejecutar en Supabase
├── routes/
│   ├── dashboard.py            Panel con cifras del día
│   ├── pacientes.py            ABM de pacientes + ficha
│   ├── citas.py                Agenda y cambio de estado
│   ├── historial.py            Entradas clínicas y subida de imágenes
│   └── odontograma.py          API JSON que consume el diagrama
├── services/
│   ├── supabase_client.py      Cliente único de Supabase
│   ├── storage.py              Subida y borrado de imágenes
│   ├── constantes.py           Estados de cita y de pieza dental
│   └── filtros.py              Filtros Jinja: |fecha, |edad, |iniciales…
├── templates/
│   ├── base.html               Layout con barra lateral
│   ├── index.html              Panel
│   ├── error.html
│   ├── partials/_flash.html
│   ├── pacientes/              lista · formulario · detalle
│   └── citas/                  lista · formulario
└── static/
    ├── css/krisdent.css
    └── js/odontograma.js       Dibuja y guarda el odontograma
```

---

## El odontograma

Se dibuja como SVG en el navegador: 32 piezas en notación FDI (11-18, 21-28,
31-38, 41-48), con la forma real de cada tipo de pieza — el canino tiene punta,
premolares y molares tienen surcos.

**Cómo se usa:** eliges un estado en la paleta y haces clic en las piezas. Cada
clic se guarda solo, sin recargar la página. También funciona con teclado: Tab
para recorrer las piezas, Enter o Espacio para marcarlas.

Los colores siguen la convención clínica y son la base de toda la paleta visual
del sistema:

| Estado | Color |
|---|---|
| Sano | blanco |
| Caries | rojo — patología por tratar |
| Obturado | azul petróleo — trabajo realizado |
| Corona | dorado |
| Ausente | gris con aspa |

**Ajustar el diagrama:** todas las coordenadas viven en el objeto `LAYOUT`, al
inicio de `static/js/odontograma.js`. Cambiando `anchoDiente`, `altoDiente`,
`separacion`, `filaSuperiorY` o `filaInferiorY` se reacomoda todo solo; el
`viewBox` se recalcula a partir de esos valores.

**Agregar un estado nuevo** (por ejemplo *Endodoncia*) requiere tres cambios:

1. `schema.sql` → añadirlo al `check (estado in (...))` de la tabla `odontograma`
2. `services/constantes.py` → añadirlo a `ESTADOS_PIEZA` con su color
3. Nada más: la paleta y la validación del backend lo toman de ahí

---

## Antes de usarlo con pacientes reales

Este es un prototipo funcional, no un sistema en producción. Tres cosas quedaron
fuera a propósito y son las que tienes que resolver antes:

**1. No hay login.** Cualquiera que llegue a la URL entra. Agrega Supabase Auth
y protege las rutas con un decorador antes de exponerlo fuera de tu red local.

**2. El bucket es público.** Una radiografía con URL pública es visible para
cualquiera que tenga el enlace. En producción deja el bucket privado y cambia
`services/storage.py` para usar `create_signed_url()` con expiración corta.

**3. RLS está desactivado.** El backend usa la llave `service_role`, que ignora
las políticas de seguridad de fila. Está bien mientras la llave viva solo en tu
servidor y nunca en el navegador, pero cuando agregues login conviene activar
RLS con políticas por usuario (el comentario en `schema.sql` tiene el ejemplo).

Además: un historial clínico es dato sensible bajo la Ley 29733. Vale la pena
que el consentimiento informado del paciente mencione que sus datos se almacenan
digitalmente en un servicio en la nube.

---

## Extensiones naturales

- **Recordatorios de cita** — la tabla `citas` ya tiene el campo pensado para
  esto. Un script con APScheduler que corra cada hora, busque citas de las
  próximas 24 h y mande el aviso por Telegram o correo.
- **Vista de calendario** — FullCalendar consumiendo un endpoint JSON de `citas`.
- **Presupuestos y pagos** — una tabla `tratamientos` ligada a `historial`, con
  costo y saldo por paciente.
