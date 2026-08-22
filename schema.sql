-- =====================================================================
-- KrizDent — Esquema de base de datos (PostgreSQL / Supabase)
-- Ejecutar completo en: Supabase → SQL Editor → New query → Run
-- =====================================================================

-- ---------------------------------------------------------------------
-- 0. PROFESIONALES (odontólogos que se asignan a citas y tratamientos)
-- ---------------------------------------------------------------------
create table if not exists profesionales (
    id        bigserial primary key,
    nombre    text not null,
    activo    boolean not null default true,
    creado_en timestamptz not null default now()
);

-- ---------------------------------------------------------------------
-- 1. PACIENTES
-- ---------------------------------------------------------------------
create table if not exists pacientes (
    id            bigserial primary key,
    nombre        text not null,               -- nombre completo
    documento     varchar(15),                 -- DNI / CE (opcional pero útil para búsquedas)
    fecha_nac     date,
    telefono      varchar(25),
    email         text,
    direccion     text,
    alergias      text,                        -- texto libre: "Penicilina, látex"
    activo        boolean not null default true, -- baja lógica: nunca borramos historial clínico
    -- 'nino' = dentición temporal (20 piezas, FDI 51-85); 'adulto' = dentición
    -- permanente (32 piezas, FDI 11-48). Define qué odontograma se dibuja.
    tipo_paciente text not null default 'adulto'
                  check (tipo_paciente in ('nino', 'adulto')),
    -- Tipo de mordida aproximado (clasificación de Angle + variantes clínicas comunes).
    -- Si agregas un tipo nuevo, actualiza también TIPOS_MORDIDA en services/constantes.py
    mordida       text
                  check (mordida in ('clase_i', 'clase_ii', 'clase_iii', 'cruzada', 'abierta',
                                      'borde_a_borde', 'sobremordida', 'resalte')),
    creado_en     timestamptz not null default now()
);

-- ---------------------------------------------------------------------
-- 2. CITAS
-- ---------------------------------------------------------------------
create table if not exists citas (
    id            bigserial primary key,
    paciente_id   bigint not null references pacientes(id) on delete restrict,
    fecha_hora    timestamptz not null,
    duracion_min  int not null default 30,
    motivo        text,
    -- Estados permitidos. Si agregas uno nuevo, actualiza también ESTADOS_CITA en services/constantes.py
    estado        text not null default 'pendiente'
                  check (estado in ('pendiente', 'completada', 'cancelada')),
    notas         text,
    -- El recordatorio se envía manualmente por WhatsApp (enlace wa.me con el
    -- mensaje ya escrito); esto solo evita reenviarlo dos veces por error.
    recordatorio_enviado boolean not null default false,
    profesional_id bigint references profesionales(id) on delete set null,
    creado_en     timestamptz not null default now()
);

-- ---------------------------------------------------------------------
-- 3. HISTORIAL CLÍNICO
-- ---------------------------------------------------------------------
create table if not exists historial (
    id            bigserial primary key,
    paciente_id   bigint not null references pacientes(id) on delete restrict,
    fecha         date not null default current_date,
    diagnostico   text,
    tratamiento   text,
    notas         text,
    creado_en     timestamptz not null default now()
);

-- Imágenes asociadas a una entrada del historial (radiografías, fotos intraorales).
-- El archivo vive en Supabase Storage; aquí solo guardamos la ruta y la URL pública.
create table if not exists historial_imagenes (
    id            bigserial primary key,
    historial_id  bigint not null references historial(id) on delete cascade,
    storage_path  text not null,               -- ruta dentro del bucket: "3/uuid.jpg"
    url           text not null,               -- URL pública lista para <img src="">
    nombre_orig   text,
    subido_en     timestamptz not null default now()
);

-- Recetas médicas: el "Rp." se guarda como texto libre y se genera un PDF
-- con membrete al vuelo (services/receta_pdf.py), no se guarda el PDF en sí.
create table if not exists recetas (
    id                 bigserial primary key,
    paciente_id        bigint not null references pacientes(id) on delete restrict,
    fecha              date not null default current_date,
    contenido          text not null,
    odontologo_nombre  text,
    odontologo_cop     text,
    creado_en          timestamptz not null default now()
);
create index if not exists idx_recetas_paciente on recetas (paciente_id, fecha desc);

-- ---------------------------------------------------------------------
-- 4. ODONTOGRAMA
-- Una fila por pieza dental registrada. Las piezas sin fila se consideran "sano".
-- Notación FDI: 11-18, 21-28, 31-38, 41-48 (32 piezas permanentes).
-- ---------------------------------------------------------------------
create table if not exists odontograma (
    id             bigserial primary key,
    paciente_id    bigint not null references pacientes(id) on delete cascade,
    pieza          smallint not null,          -- número FDI
    -- 'remanente_radicular' = solo queda la raíz, la corona está destruida o perdida
    -- (distinto de 'ausente', donde no queda nada de la pieza).
    -- 'corona_buena'/'corona_mala' = estado de la corona protésica (no confundir
    -- con la corona anatómica del diente propio).
    estado         text not null default 'sano'
                   check (estado in ('sano', 'caries', 'ausente', 'obturado',
                                      'corona_buena', 'corona_mala', 'remanente_radicular')),
    -- El perno (poste/muñón) es independiente de la corona: puede haber perno sin
    -- corona (a la espera de una), o corona sin perno (retenida solo en la pieza).
    con_perno      boolean not null default false,
    actualizado_en timestamptz not null default now(),
    -- Un paciente no puede tener dos registros de la misma pieza.
    -- Esto habilita el "upsert" que usa la app al hacer clic en un diente.
    unique (paciente_id, pieza)
);

-- Estado por CARA de la pieza (mesial, distal, oclusal, vestibular, lingual).
-- Se usa para marcar caries/obturaciones localizadas, en vez de la pieza entera.
-- Los estados de toda la pieza (ausente, corona) siguen viviendo en "odontograma".
create table if not exists odontograma_caras (
    id             bigserial primary key,
    paciente_id    bigint not null references pacientes(id) on delete cascade,
    pieza          smallint not null,
    cara           text not null
                   check (cara in ('oclusal', 'vestibular', 'lingual', 'mesial', 'distal')),
    -- 'obturado' = obturación en buen estado; 'obturado_mal' = obturación deteriorada,
    -- filtrada o con caries secundaria — se distingue con color propio en la paleta.
    estado         text not null default 'sano'
                   check (estado in ('sano', 'caries', 'obturado', 'obturado_mal')),
    actualizado_en timestamptz not null default now(),
    unique (paciente_id, pieza, cara)
);
create index if not exists idx_odont_caras_paciente on odontograma_caras (paciente_id);

-- Aparatos de ortodoncia (norma NTS 188-MINSA, secciones 6.1.1 y 6.1.2):
-- 'fijo' se dibuja como una línea recta entre pieza_desde y pieza_hasta;
-- 'removible' como una línea en zigzag sobre toda la arcada en tratamiento.
-- Azul (bueno) o rojo (malo) según el estado del aparato.
create table if not exists ortodoncia_aparatos (
    id            bigserial primary key,
    paciente_id   bigint not null references pacientes(id) on delete cascade,
    tipo          text not null check (tipo in ('fijo', 'removible')),
    estado        text not null default 'bueno' check (estado in ('bueno', 'malo')),
    pieza_desde   smallint,
    pieza_hasta   smallint,
    arcada        text check (arcada in ('superior', 'inferior')),
    creado_en     timestamptz not null default now()
);
create index if not exists idx_ortodoncia_paciente on ortodoncia_aparatos (paciente_id);

-- ---------------------------------------------------------------------
-- 4b. ALMACÉN — productos (insumos de salud) + kardex de movimientos
-- ---------------------------------------------------------------------
create table if not exists productos_almacen (
    id              bigserial primary key,
    nombre          text not null,
    descripcion     text,
    -- Agrupación clínica de insumos de salud.
    categoria       text not null default 'otros'
                    check (categoria in ('material_curacion', 'proteccion_personal',
                                          'anestesia_desechables', 'insumos_dentales',
                                          'medicamentos', 'instrumental', 'otros')),
    unidad_medida   text not null default 'unidad'
                    check (unidad_medida in ('unidad', 'paquete', 'caja', 'frasco', 'ml', 'mg', 'gr')),
    tiene_vencimiento boolean not null default false,
    fecha_vencimiento date,
    -- Stock en la MISMA unidad_medida. Numeric admite fracciones: "medio paquete" = 0.5.
    stock_actual    numeric(10,2) not null default 0,
    stock_minimo    numeric(10,2),           -- umbral para avisar "stock bajo" (opcional)
    activo          boolean not null default true,
    creado_en       timestamptz not null default now()
);
create index if not exists idx_productos_categoria on productos_almacen (categoria);
create index if not exists idx_productos_vencimiento on productos_almacen (fecha_vencimiento)
    where tiene_vencimiento;

-- Kardex: una fila por cada entrada o salida. saldo_resultante deja el
-- historial auditable sin tener que recalcular sumas cada vez.
create table if not exists movimientos_almacen (
    id                bigserial primary key,
    producto_id       bigint not null references productos_almacen(id) on delete cascade,
    tipo              text not null check (tipo in ('entrada', 'salida')),
    cantidad          numeric(10,2) not null check (cantidad > 0),
    saldo_resultante  numeric(10,2) not null,
    -- Solo tiene sentido en 'entrada': cuánto costó esa compra, para poder
    -- sumar "cuánto gasté en este material" a lo largo del tiempo.
    costo_unitario    numeric(10,2),
    motivo            text,
    creado_en         timestamptz not null default now()
);
create index if not exists idx_movimientos_producto on movimientos_almacen (producto_id, creado_en desc);

-- ---------------------------------------------------------------------
-- 4c. PRESUPUESTOS Y PAGOS
-- ---------------------------------------------------------------------
create table if not exists tratamientos (
    id           bigserial primary key,
    paciente_id  bigint not null references pacientes(id) on delete cascade,
    descripcion  text not null,
    costo        numeric(10,2) not null check (costo >= 0),
    fecha        date not null default current_date,
    estado       text not null default 'pendiente'
                 check (estado in ('pendiente', 'en_proceso', 'completado', 'cancelado')),
    profesional_id bigint references profesionales(id) on delete set null,
    -- Vincula la línea de presupuesto con la pieza que la originó, para poder
    -- crear el presupuesto directo desde un hallazgo del odontograma.
    pieza        smallint,
    creado_en    timestamptz not null default now()
);
create index if not exists idx_tratamientos_paciente on tratamientos (paciente_id);

create table if not exists pagos (
    id             bigserial primary key,
    paciente_id    bigint not null references pacientes(id) on delete cascade,
    tratamiento_id bigint references tratamientos(id) on delete set null,
    monto          numeric(10,2) not null check (monto > 0),
    metodo         text not null default 'efectivo'
                   check (metodo in ('efectivo', 'yape_plin', 'tarjeta', 'transferencia', 'otro')),
    fecha          date not null default current_date,
    notas          text,
    creado_en      timestamptz not null default now()
);
create index if not exists idx_pagos_paciente on pagos (paciente_id);

-- ---------------------------------------------------------------------
-- 4d. CONSENTIMIENTO INFORMADO CON FIRMA
-- ---------------------------------------------------------------------
create table if not exists consentimientos (
    id            bigserial primary key,
    paciente_id   bigint not null references pacientes(id) on delete cascade,
    titulo        text not null default 'Consentimiento informado',
    texto         text not null,
    firma_url     text not null,     -- PNG de la firma, en el bucket de Storage
    firmado_en    timestamptz not null default now()
);
create index if not exists idx_consentimientos_paciente on consentimientos (paciente_id);

-- ---------------------------------------------------------------------
-- 4e. LABORATORIO DENTAL
-- ---------------------------------------------------------------------
create table if not exists trabajos_laboratorio (
    id                bigserial primary key,
    paciente_id       bigint not null references pacientes(id) on delete cascade,
    laboratorio       text,
    descripcion       text not null,
    fecha_envio       date not null default current_date,
    fecha_estimada    date,
    fecha_recibido    date,
    estado            text not null default 'enviado'
                      check (estado in ('enviado', 'en_proceso', 'listo', 'entregado')),
    notas             text,
    creado_en         timestamptz not null default now()
);
create index if not exists idx_laboratorio_paciente on trabajos_laboratorio (paciente_id);

-- ---------------------------------------------------------------------
-- 4f. VERSIONES DEL ODONTOGRAMA (Inicial / Alta — "Evolución" es lo vivo)
-- ---------------------------------------------------------------------
create table if not exists odontograma_versiones (
    id                bigserial primary key,
    paciente_id       bigint not null references pacientes(id) on delete cascade,
    tipo              text not null check (tipo in ('inicial', 'alta')),
    fecha             date not null default current_date,
    odontograma       jsonb not null,
    odontograma_caras jsonb not null,
    ortodoncia        jsonb not null default '[]',
    creado_en         timestamptz not null default now(),
    unique (paciente_id, tipo)
);

-- ---------------------------------------------------------------------
-- 4g. PERIODONTOGRAMA (carta periodontal: placa, sangrado, sondaje)
-- ---------------------------------------------------------------------
create table if not exists periodontogramas (
    id                 bigserial primary key,
    paciente_id        bigint not null references pacientes(id) on delete cascade,
    fecha              date not null default current_date,
    indice_placa       numeric(5,2) not null default 0,
    indice_sangrado    numeric(5,2) not null default 0,
    sitios_supuracion  int not null default 0,
    datos              jsonb not null default '{}',
    notas              text,
    creado_en          timestamptz not null default now()
);
create index if not exists idx_periodontogramas_paciente on periodontogramas (paciente_id, fecha desc);

-- ---------------------------------------------------------------------
-- 5. ÍNDICES
-- ---------------------------------------------------------------------
create index if not exists idx_citas_fecha        on citas (fecha_hora);
create index if not exists idx_citas_paciente     on citas (paciente_id);
create index if not exists idx_historial_paciente on historial (paciente_id, fecha desc);
create index if not exists idx_odont_paciente     on odontograma (paciente_id);
create index if not exists idx_pacientes_nombre   on pacientes (lower(nombre));

-- ---------------------------------------------------------------------
-- 6. SEGURIDAD (RLS)
-- ---------------------------------------------------------------------
-- El prototipo se conecta con la clave 'service_role' desde el backend Flask,
-- que ignora RLS. Por eso NO habilitamos RLS todavía: si lo activas sin
-- políticas, la app dejará de leer datos.
--
-- Cuando pases a producción con login de usuarios en Supabase Auth, activa:
--   alter table pacientes enable row level security;
--   create policy "personal_autenticado" on pacientes
--     for all to authenticated using (true) with check (true);
-- ...y repite para cada tabla.

-- ---------------------------------------------------------------------
-- 7. STORAGE
-- ---------------------------------------------------------------------
-- Crea el bucket desde el panel: Storage → New bucket
--   Nombre: historial
--   Public bucket: activado (el prototipo usa URLs públicas)
--
-- Para un consultorio real, deja el bucket PRIVADO y cambia
-- services/storage.py para usar URLs firmadas (create_signed_url),
-- porque una radiografía es un dato de salud.
--
-- Storage tiene RLS propio (además del de las tablas). Como el backend usa
-- la llave 'anon' (sin login todavía), hace falta una política explícita
-- o toda subida de imagen/firma falla con "row violates row-level security
-- policy". Ejecuta esto también:
--   create policy "anon_lee_historial" on storage.objects
--       for select to anon using (bucket_id = 'historial');
--   create policy "anon_sube_historial" on storage.objects
--       for insert to anon with check (bucket_id = 'historial');
--   create policy "anon_borra_historial" on storage.objects
--       for delete to anon using (bucket_id = 'historial');

-- ---------------------------------------------------------------------
-- 8. DATOS DE EJEMPLO (opcional — bórralo antes de usarlo de verdad)
-- ---------------------------------------------------------------------
insert into pacientes (nombre, documento, fecha_nac, telefono, email, direccion, alergias)
values
  ('María Fernanda Quispe Rojas', '45872103', '1991-04-17', '987654321', 'mf.quispe@example.com', 'Av. Arequipa 1520, Lince', 'Penicilina'),
  ('Jorge Luis Ramírez Salas',    '09871234', '1978-11-02', '956231447', 'jl.ramirez@example.com', 'Jr. Puno 340, Cercado',   'Ninguna conocida'),
  ('Camila Andrade Bustos',       '71234598', '2005-08-25', '921004583', 'camila.ab@example.com',  'Calle Los Pinos 88, SJM', 'Látex')
on conflict do nothing;
