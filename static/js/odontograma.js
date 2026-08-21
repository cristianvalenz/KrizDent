/* =====================================================================
   KrizDent — Odontograma interactivo

   Dibuja las 32 piezas permanentes (notación FDI) como SVG y guarda el
   estado de cada una en Supabase apenas se hace clic.

   Cómo funciona:
     1. Se elige un estado en la paleta ("pincel").
     2. Se hace clic en una pieza y esta toma ese estado.
     3. El cambio se envía al backend con fetch; no se recarga la página.

   TODAS las coordenadas son ajustables desde el objeto LAYOUT de abajo.
   ===================================================================== */

(function () {
    "use strict";

    // -----------------------------------------------------------------
    // 1. LAYOUT — ajusta aquí el tamaño y la posición del diagrama
    // -----------------------------------------------------------------
    const LAYOUT = {
        radioDiente: 13,      // mitad del lado del cuadro clickeable de cada pieza
        separacion: 6,        // espacio horizontal entre piezas
        margenIzq: 26,        // margen izquierdo del diagrama
        altoDiente: 30,        // alto de la corona (silueta anatómica, decorativa)
        anchoDiente: 26,       // ancho de la silueta anatómica
        altoRaiz: 9,           // alto de la raíz (decorativa), apoyada en el cuello de la corona
        separacionArcadas: 10, // espacio extra entre el hemiarco derecho e izquierdo
        // De afuera hacia la línea media: [línea de ortodoncia] → raíz → corona
        // → espacio → cuadro de caras → espacio → número.
        // filaSuperiorY / filaInferiorY son el centro del cuadro (clickeable).
        ortoSuperiorY: 14,      // altura de la línea/zigzag de ortodoncia superior
        raizSuperiorY: 22,      // Y donde empieza (arriba) la raíz superior
        dienteSuperiorY: 31,    // Y donde empieza (arriba) la corona superior
        filaSuperiorY: 79,
        numeroSuperiorY: 105,   // baseline del número, entre el cuadro y la línea media
        filaInferiorY: 151,
        numeroInferiorY: 125,
        dienteInferiorY: 169,   // Y donde empieza (arriba) la corona inferior
        raizInferiorY: 199,     // Y donde empieza (arriba) la raíz inferior
        ortoInferiorY: 216,     // altura de la línea/zigzag de ortodoncia inferior
        alturaTotal: 230,
    };

    // Orden de las piezas tal como se ven en un odontograma frente al paciente.
    // Arriba: cuadrante 1 (der. del paciente) | cuadrante 2 (izq. del paciente)
    // Abajo:  cuadrante 4                     | cuadrante 3
    // Adulto: dentición permanente, 32 piezas (8 por cuadrante).
    const FILA_SUPERIOR_ADULTO = [18, 17, 16, 15, 14, 13, 12, 11, 21, 22, 23, 24, 25, 26, 27, 28];
    const FILA_INFERIOR_ADULTO = [48, 47, 46, 45, 44, 43, 42, 41, 31, 32, 33, 34, 35, 36, 37, 38];
    // Niño: dentición temporal, 20 piezas (5 por cuadrante, sin premolares).
    const FILA_SUPERIOR_NINO = [55, 54, 53, 52, 51, 61, 62, 63, 64, 65];
    const FILA_INFERIOR_NINO = [85, 84, 83, 82, 81, 71, 72, 73, 74, 75];

    const SVG_NS = "http://www.w3.org/2000/svg";

    /** El último dígito del número FDI indica el tipo de pieza. La dentición
     *  temporal (piezas 51-85) no tiene premolares: solo incisivo/canino/molar. */
    function tipoDePieza(fdi) {
        const n = fdi % 10;
        const esTemporal = fdi >= 51;
        if (n <= 2) return "incisivo";
        if (n === 3) return "canino";
        if (esTemporal) return "molar";
        if (n <= 5) return "premolar";
        return "molar";
    }

    /**
     * Silueta anatómica decorativa (sin interacción): la cara oclusal/incisal
     * queda en la base (abajo), el cuello hacia arriba. Solo de referencia
     * visual, no cambia de color ni recibe clics.
     */
    function pathSilueta(tipo, x, y, w, h) {
        const r = 4;
        const cuello = w * 0.16;

        if (tipo === "incisivo") {
            return `M ${x + cuello} ${y}
                    L ${x + w - cuello} ${y}
                    L ${x + w} ${y + h - r}
                    Q ${x + w} ${y + h} ${x + w - r} ${y + h}
                    L ${x + r} ${y + h}
                    Q ${x} ${y + h} ${x} ${y + h - r} Z`;
        }
        if (tipo === "canino") {
            return `M ${x + cuello} ${y}
                    L ${x + w - cuello} ${y}
                    L ${x + w} ${y + h * 0.62}
                    L ${x + w / 2} ${y + h}
                    L ${x} ${y + h * 0.62} Z`;
        }
        if (tipo === "premolar") {
            return `M ${x + cuello} ${y}
                    L ${x + w - cuello} ${y}
                    Q ${x + w} ${y + h * 0.5} ${x + w - 2} ${y + h - r}
                    Q ${x + w - 2} ${y + h} ${x + w - r - 2} ${y + h}
                    L ${x + r + 2} ${y + h}
                    Q ${x + 2} ${y + h} ${x + 2} ${y + h - r}
                    Q ${x} ${y + h * 0.5} ${x + cuello} ${y} Z`;
        }
        // molar: más ancho y cuadrado
        return `M ${x + cuello * 0.5} ${y}
                L ${x + w - cuello * 0.5} ${y}
                Q ${x + w} ${y} ${x + w} ${y + r}
                L ${x + w} ${y + h - r}
                Q ${x + w} ${y + h} ${x + w - r} ${y + h}
                L ${x + r} ${y + h}
                Q ${x} ${y + h} ${x} ${y + h - r}
                L ${x} ${y + r}
                Q ${x} ${y} ${x + cuello * 0.5} ${y} Z`;
    }

    /**
     * Silueta de la raíz, decorativa: un solo cono para incisivo/canino/premolar,
     * dos prongs (bifurcada) para molar. Ocupa la porción superior del recuadro,
     * apoyada sobre el cuello de la corona.
     */
    function pathRaiz(tipo, x, y, w, h) {
        if (tipo === "molar") {
            const mid = x + w / 2;
            return `M ${x + w * 0.26} ${y + h} L ${x + w * 0.16} ${y}
                    L ${mid - 1} ${y + h * 0.35} L ${mid + 1} ${y + h * 0.35}
                    L ${x + w * 0.84} ${y} L ${x + w * 0.74} ${y + h} Z`;
        }
        const base = w * 0.5;
        return `M ${x + (w - base) / 2} ${y + h}
                L ${x + w / 2} ${y}
                L ${x + (w + base) / 2} ${y + h} Z`;
    }

    function crear(tag, atributos) {
        const el = document.createElementNS(SVG_NS, tag);
        for (const [k, v] of Object.entries(atributos)) el.setAttribute(k, v);
        return el;
    }

    /**
     * Centro X de la pieza i-ésima de una fila, con hueco en la línea media.
     * porHemiarco: cuántas piezas hay antes del hueco (8 en adulto, 5 en niño).
     */
    function centroX(i, porHemiarco) {
        const { radioDiente: r, separacion: s, margenIzq, separacionArcadas } = LAYOUT;
        const paso = 2 * r + s;
        return margenIzq + r + i * paso + (i >= porHemiarco ? separacionArcadas : 0);
    }

    /**
     * Devuelve los 5 polígonos de las caras de una pieza: un cuadrado dividido
     * por una cruz en un centro (oclusal/incisal) y 4 triángulos (vestibular,
     * lingual, mesial, distal) — la notación clásica de un odontograma clínico.
     */
    function poligonosCaras(cx, cy, L) {
        const h = L / 2;
        const li = L * 0.21; // medio lado del cuadrado interior (oclusal)
        const p = function (x, y) { return `${x},${y}`; };

        const TL = [cx - h, cy - h], TR = [cx + h, cy - h];
        const BL = [cx - h, cy + h], BR = [cx + h, cy + h];
        const iTL = [cx - li, cy - li], iTR = [cx + li, cy - li];
        const iBL = [cx - li, cy + li], iBR = [cx + li, cy + li];

        return {
            vestibular: [TL, TR, iTR, iTL].map(function (pt) { return p(pt[0], pt[1]); }).join(" "),
            lingual: [BL, BR, iBR, iBL].map(function (pt) { return p(pt[0], pt[1]); }).join(" "),
            mesial: [TL, BL, iBL, iTL].map(function (pt) { return p(pt[0], pt[1]); }).join(" "),
            distal: [TR, BR, iBR, iTR].map(function (pt) { return p(pt[0], pt[1]); }).join(" "),
            oclusal: [iTL, iTR, iBR, iBL].map(function (pt) { return p(pt[0], pt[1]); }).join(" "),
        };
    }

    // -----------------------------------------------------------------
    // 2. Construcción del diagrama — de la línea media hacia afuera:
    //    número FDI → cuadro de caras clickeable → silueta anatómica (referencia).
    // -----------------------------------------------------------------
    function dibujarFila(svg, piezas, esSuperior, porHemiarco) {
        const { radioDiente: mitadCaja, altoDiente: h, anchoDiente: w, altoRaiz: hr } = LAYOUT;
        const yCentro = esSuperior ? LAYOUT.filaSuperiorY : LAYOUT.filaInferiorY;
        const yNumero = esSuperior ? LAYOUT.numeroSuperiorY : LAYOUT.numeroInferiorY;
        const yDiente = esSuperior ? LAYOUT.dienteSuperiorY : LAYOUT.dienteInferiorY;
        const yRaiz = esSuperior ? LAYOUT.raizSuperiorY : LAYOUT.raizInferiorY;
        const L = mitadCaja * 2;

        piezas.forEach(function (fdi, i) {
            const cx = centroX(i, porHemiarco);
            const tipo = tipoDePieza(fdi);

            // --- Silueta anatómica decorativa (corona + raíz, no interactiva) ---
            // Cada caja se espeja sobre sí misma para la arcada inferior, de modo
            // que la cara oclusal siempre quede pegada al cuadro de caras.
            const grupoSilueta = crear("g", {
                class: "diente-silueta",
                "data-pieza": fdi,
                "data-estado": "sano",
                "pointer-events": "none",
            });

            const cajaCorona = crear("g", esSuperior
                ? {}
                : { transform: `translate(0 ${2 * yDiente + h}) scale(1 -1)` });
            cajaCorona.appendChild(crear("path", {
                class: "silueta-corona",
                d: pathSilueta(tipo, cx - w / 2, yDiente, w, h),
            }));
            grupoSilueta.appendChild(cajaCorona);

            const cajaRaiz = crear("g", esSuperior
                ? {}
                : { transform: `translate(0 ${2 * yRaiz + hr}) scale(1 -1)` });
            cajaRaiz.appendChild(crear("path", {
                class: "silueta-raiz",
                d: pathRaiz(tipo, cx - w / 2, yRaiz, w, hr),
            }));
            grupoSilueta.appendChild(cajaRaiz);

            svg.appendChild(grupoSilueta);

            // --- Cuadro de caras clickeable -------------------------------
            const g = crear("g", {
                class: "diente",
                "data-pieza": fdi,
                "data-estado": "sano",
                "data-perno": "false",
                tabindex: "0",
                role: "button",
                "aria-label": `Pieza ${fdi}, estado sano`,
            });

            g.appendChild(crear("rect", {
                class: "borde-diente",
                x: cx - mitadCaja, y: yCentro - mitadCaja, width: L, height: L,
            }));

            const caras = poligonosCaras(cx, yCentro, L);
            Object.entries(caras).forEach(function ([nombre, puntos]) {
                g.appendChild(crear("polygon", {
                    class: "cara-diente",
                    "data-cara": nombre,
                    "data-estado": "sano",
                    points: puntos,
                }));
            });

            // Aspa que marca la pieza ausente (oculta por CSS hasta que aplique)
            const d = mitadCaja * 0.85;
            const aspa = crear("g", { class: "marca-ausente", "pointer-events": "none" });
            aspa.appendChild(crear("line", { x1: cx - d, y1: yCentro - d, x2: cx + d, y2: yCentro + d }));
            aspa.appendChild(crear("line", { x1: cx + d, y1: yCentro - d, x2: cx - d, y2: yCentro + d }));
            g.appendChild(aspa);

            // Marca de perno: un mango con cabeza redondeada apoyado en el cuello
            // de la pieza (oculta por CSS hasta que la pieza tenga con_perno = true).
            const signo = esSuperior ? -1 : 1;
            const yBordeCuello = yCentro + signo * mitadCaja;
            const yCabeza = yBordeCuello + signo * 6.5;
            const grupoPerno = crear("g", { class: "marca-perno", "pointer-events": "none" });
            grupoPerno.appendChild(crear("line", {
                class: "perno-mango",
                x1: cx, y1: yBordeCuello,
                x2: cx, y2: yBordeCuello + signo * 4,
            }));
            grupoPerno.appendChild(crear("ellipse", {
                class: "perno-cabeza",
                cx: cx + 0.6, cy: yCabeza, rx: 2.3, ry: 3.1,
                transform: `rotate(${signo * 18} ${cx + 0.6} ${yCabeza})`,
            }));
            g.appendChild(grupoPerno);

            // Número FDI, entre el cuadro y la línea media.
            g.appendChild(crear("text", {
                class: "numero-pieza",
                x: cx,
                y: yNumero,
            })).textContent = fdi;

            svg.appendChild(g);
        });
    }

    function dibujarEjes(svg, totalPiezas, porHemiarco) {
        const { margenIzq, numeroSuperiorY, numeroInferiorY } = LAYOUT;
        const xMedio = (centroX(porHemiarco - 1, porHemiarco) + centroX(porHemiarco, porHemiarco)) / 2;
        const ancho = centroX(totalPiezas - 1, porHemiarco) + margenIzq;
        const yMedio = (numeroSuperiorY + numeroInferiorY) / 2;

        // Línea media vertical
        svg.appendChild(crear("line", {
            class: "kd-eje-central",
            x1: xMedio, y1: 2,
            x2: xMedio, y2: LAYOUT.alturaTotal - 2,
        }));
        // Línea horizontal que separa arcada superior de inferior
        svg.appendChild(crear("line", {
            class: "kd-eje-central",
            x1: margenIzq - 10, y1: yMedio,
            x2: ancho - margenIzq + 10, y2: yMedio,
        }));
    }

    /**
     * Dibuja los aparatos de ortodoncia (NTS 188-MINSA 6.1.1 y 6.1.2):
     * "fijo" = cuadrito con cruz en cada extremo, unidos por una línea recta.
     * "removible" = línea en zigzag sobre toda la arcada en tratamiento.
     * Azul (bueno) o rojo (malo). mapaPiezas: fdi -> {cx, esSuperior}.
     */
    function dibujarOrtodoncia(svg, aparatos, mapaPiezas, coloresOrto) {
        const grupo = crear("g", { id: "capa-ortodoncia" });

        function marcaExtremo(cx, y, color) {
            const l = 5;
            grupo.appendChild(crear("rect", {
                x: cx - l, y: y - l, width: 2 * l, height: 2 * l,
                fill: "#fff", stroke: color, "stroke-width": 1.2,
            }));
            grupo.appendChild(crear("line", { x1: cx - l, y1: y, x2: cx + l, y2: y, stroke: color, "stroke-width": 1 }));
            grupo.appendChild(crear("line", { x1: cx, y1: y - l, x2: cx, y2: y + l, stroke: color, "stroke-width": 1 }));
        }

        aparatos.forEach(function (aparato) {
            const info = coloresOrto[aparato.estado] || coloresOrto.bueno;
            const color = info.color;

            if (aparato.tipo === "fijo") {
                const desde = mapaPiezas[aparato.pieza_desde];
                const hasta = mapaPiezas[aparato.pieza_hasta];
                if (!desde || !hasta) return;
                const y = desde.esSuperior ? LAYOUT.ortoSuperiorY : LAYOUT.ortoInferiorY;
                grupo.appendChild(crear("line", {
                    x1: desde.cx, y1: y, x2: hasta.cx, y2: y,
                    stroke: color, "stroke-width": 1.4,
                }));
                marcaExtremo(desde.cx, y, color);
                marcaExtremo(hasta.cx, y, color);
            } else {
                const esSuperior = aparato.arcada === "superior";
                const piezas = esSuperior ? FILA_SUPERIOR_ACTUAL : FILA_INFERIOR_ACTUAL;
                if (!piezas || !piezas.length) return;
                const y = esSuperior ? LAYOUT.ortoSuperiorY : LAYOUT.ortoInferiorY;
                const amplitud = 4;
                let puntos = "";
                piezas.forEach(function (fdi, i) {
                    const info2 = mapaPiezas[fdi];
                    if (!info2) return;
                    const yy = y + (i % 2 === 0 ? -amplitud : amplitud);
                    puntos += `${info2.cx},${yy} `;
                });
                grupo.appendChild(crear("polyline", {
                    points: puntos.trim(), fill: "none",
                    stroke: color, "stroke-width": 1.4, "stroke-linejoin": "round",
                }));
            }
        });

        svg.appendChild(grupo);
    }

    // Filas actualmente dibujadas (se fijan en iniciar() según tipo de paciente),
    // las necesita dibujarOrtodoncia() para saber qué piezas abarca "removible".
    let FILA_SUPERIOR_ACTUAL = null;
    let FILA_INFERIOR_ACTUAL = null;

    // -----------------------------------------------------------------
    // 3. Inicialización
    // -----------------------------------------------------------------
    function iniciar() {
        const contenedor = document.getElementById("odontograma");
        if (!contenedor) return;   // la página actual no tiene odontograma

        const pacienteId = contenedor.dataset.pacienteId;
        const esNino = contenedor.dataset.tipoPaciente === "nino";
        const estados = JSON.parse(contenedor.dataset.estados || "{}");
        const caras = JSON.parse(contenedor.dataset.caras || "{}");
        const colores = JSON.parse(contenedor.dataset.colores || "{}");
        const nombresCara = JSON.parse(contenedor.dataset.nombresCara || "{}");
        let ortodoncia = JSON.parse(contenedor.dataset.ortodoncia || "[]");
        const coloresOrto = JSON.parse(contenedor.dataset.estadosOrto || "{}");
        const aviso = document.getElementById("odontograma-aviso");

        const filaSuperior = esNino ? FILA_SUPERIOR_NINO : FILA_SUPERIOR_ADULTO;
        const filaInferior = esNino ? FILA_INFERIOR_NINO : FILA_INFERIOR_ADULTO;
        const porHemiarco = esNino ? 5 : 8;
        const totalPiezas = filaSuperior.length;
        FILA_SUPERIOR_ACTUAL = filaSuperior;
        FILA_INFERIOR_ACTUAL = filaInferior;

        const anchoTotal = centroX(totalPiezas - 1, porHemiarco) + LAYOUT.margenIzq + LAYOUT.radioDiente;

        const svg = crear("svg", {
            viewBox: `0 0 ${anchoTotal} ${LAYOUT.alturaTotal}`,
            xmlns: SVG_NS,
            role: "group",
            "aria-label": "Odontograma del paciente",
        });

        dibujarEjes(svg, totalPiezas, porHemiarco);
        dibujarFila(svg, filaSuperior, true, porHemiarco);
        dibujarFila(svg, filaInferior, false, porHemiarco);
        contenedor.appendChild(svg);

        // Mapa fdi -> {cx, esSuperior}, para ubicar los extremos de los aparatos.
        const mapaPiezas = {};
        filaSuperior.forEach(function (fdi, i) { mapaPiezas[fdi] = { cx: centroX(i, porHemiarco), esSuperior: true }; });
        filaInferior.forEach(function (fdi, i) { mapaPiezas[fdi] = { cx: centroX(i, porHemiarco), esSuperior: false }; });

        function redibujarOrtodoncia() {
            const capaVieja = svg.querySelector("#capa-ortodoncia");
            if (capaVieja) capaVieja.remove();
            dibujarOrtodoncia(svg, ortodoncia, mapaPiezas, coloresOrto);
        }
        redibujarOrtodoncia();

        // --- Pintado ---------------------------------------------------
        // Nivel pieza: sano/ausente/corona → toda la pieza toma un solo color
        // y se oculta la distinción por cara mientras dure ese estado.
        function pintarPieza(fdi, estado) {
            const g = svg.querySelector(`.diente[data-pieza="${fdi}"]`);
            if (!g) return;
            const info = colores[estado] || colores.sano;
            g.dataset.estado = estado;
            g.classList.toggle("marcado", estado !== "sano");
            g.setAttribute("aria-label", `Pieza ${fdi}, estado ${info.etiqueta.toLowerCase()}`);

            // La silueta anatómica (corona + raíz) refleja el mismo estado:
            // "ausente" apaga toda la silueta, "remanente_radicular" apaga
            // solo la corona y resalta la raíz.
            const silueta = svg.querySelector(`.diente-silueta[data-pieza="${fdi}"]`);
            if (silueta) silueta.dataset.estado = estado;

            if (estado === "sano") {
                // Vuelven a verse los colores individuales de cada cara.
                g.querySelectorAll(".cara-diente").forEach(function (poligono) {
                    const infoC = colores[poligono.dataset.estado] || colores.sano;
                    poligono.style.fill = infoC.color;
                });
            } else {
                g.querySelectorAll(".cara-diente").forEach(function (poligono) {
                    poligono.style.fill = info.color;
                });
            }
        }

        // Nivel cara: caries/obturado → solo el sector donde se hizo clic.
        function pintarCara(fdi, cara, estado) {
            const g = svg.querySelector(`.diente[data-pieza="${fdi}"]`);
            if (!g) return;
            const poligono = g.querySelector(`.cara-diente[data-cara="${cara}"]`);
            if (!poligono) return;
            poligono.dataset.estado = estado;
            // Si la pieza está marcada como ausente/corona, ese color manda
            // visualmente; el cambio de cara igual se guarda por debajo.
            if (g.dataset.estado === "sano") {
                const info = colores[estado] || colores.sano;
                poligono.style.fill = info.color;
            }
        }

        // Perno: independiente del estado, solo cambia una marca visual.
        function pintarPerno(fdi, tienePerno) {
            const g = svg.querySelector(`.diente[data-pieza="${fdi}"]`);
            if (!g) return;
            g.dataset.perno = tienePerno ? "true" : "false";
        }

        // Estado inicial que llegó desde la base de datos
        Object.entries(caras).forEach(function ([fdi, porCara]) {
            Object.entries(porCara).forEach(function ([cara, estado]) {
                pintarCara(fdi, cara, estado);
            });
        });
        Object.entries(estados).forEach(function ([fdi, info]) {
            pintarPieza(fdi, info.estado);
            pintarPerno(fdi, info.perno);
        });

        // --- Paleta de estados ("pincel") ------------------------------
        // Cada botón trae su nivel (data-nivel="pieza" o "cara") además del estado.
        let pincel = "caries";
        let nivelPincel = "cara";
        const botones = document.querySelectorAll(".kd-pincel");
        botones.forEach(function (btn) {
            btn.addEventListener("click", function () {
                pincel = btn.dataset.estado;
                nivelPincel = btn.dataset.nivel;
                botones.forEach(function (b) { b.classList.remove("activo"); });
                btn.classList.add("activo");
            });
        });
        const inicial = document.querySelector(`.kd-pincel[data-estado="${pincel}"]`);
        if (inicial) inicial.classList.add("activo");

        // --- Guardado ----------------------------------------------------
        function mostrarAviso(texto, esError) {
            if (!aviso) return;
            aviso.textContent = texto;
            aviso.classList.toggle("error", !!esError);
            aviso.classList.add("visible");
            clearTimeout(aviso._t);
            aviso._t = setTimeout(function () { aviso.classList.remove("visible"); }, 1800);
        }

        function aplicarPieza(g) {
            const fdi = g.dataset.pieza;
            const anterior = g.dataset.estado;
            if (anterior === pincel) return;

            pintarPieza(fdi, pincel);   // respuesta visual inmediata

            fetch(`/odontograma/${pacienteId}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ pieza: Number(fdi), estado: pincel }),
            })
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    if (data.ok) {
                        mostrarAviso(`Pieza ${fdi} guardada`);
                    } else {
                        pintarPieza(fdi, anterior);
                        mostrarAviso(data.error || "No se pudo guardar", true);
                    }
                })
                .catch(function () {
                    pintarPieza(fdi, anterior);
                    mostrarAviso("Sin conexión con el servidor", true);
                });
        }

        function aplicarCara(fdi, poligono) {
            const cara = poligono.dataset.cara;
            const anterior = poligono.dataset.estado;
            if (anterior === pincel) return;

            pintarCara(fdi, cara, pincel);   // respuesta visual inmediata

            fetch(`/odontograma/${pacienteId}/cara`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ pieza: Number(fdi), cara, estado: pincel }),
            })
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    const nombreCara = nombresCara[cara] || cara;
                    if (data.ok) {
                        mostrarAviso(`Pieza ${fdi} · ${nombreCara} guardada`);
                    } else {
                        pintarCara(fdi, cara, anterior);
                        mostrarAviso(data.error || "No se pudo guardar", true);
                    }
                })
                .catch(function () {
                    pintarCara(fdi, cara, anterior);
                    mostrarAviso("Sin conexión con el servidor", true);
                });
        }

        function aplicarPerno(g) {
            const fdi = g.dataset.pieza;
            const anterior = g.dataset.perno === "true";
            const nuevo = !anterior;

            pintarPerno(fdi, nuevo);   // respuesta visual inmediata

            fetch(`/odontograma/${pacienteId}/perno`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ pieza: Number(fdi), perno: nuevo }),
            })
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    if (data.ok) {
                        mostrarAviso(`Pieza ${fdi} · ${nuevo ? "con perno" : "sin perno"}`);
                    } else {
                        pintarPerno(fdi, anterior);
                        mostrarAviso(data.error || "No se pudo guardar", true);
                    }
                })
                .catch(function () {
                    pintarPerno(fdi, anterior);
                    mostrarAviso("Sin conexión con el servidor", true);
                });
        }

        function manejarClic(objetivo) {
            const g = objetivo.closest(".diente");
            if (!g) return;

            if (nivelPincel === "cara") {
                const poligono = objetivo.closest(".cara-diente");
                if (poligono) aplicarCara(g.dataset.pieza, poligono);
            } else if (nivelPincel === "perno") {
                aplicarPerno(g);
            } else {
                aplicarPieza(g);
            }
        }

        svg.addEventListener("click", function (e) { manejarClic(e.target); });

        // Accesibilidad: se puede recorrer con Tab y marcar con Enter o Espacio.
        svg.addEventListener("keydown", function (e) {
            if (e.key !== "Enter" && e.key !== " ") return;
            const g = e.target.closest(".diente");
            if (!g) return;
            e.preventDefault();
            manejarClic(e.target);
        });

        // --- Reiniciar odontograma -----------------------------------
        const btnReiniciar = document.getElementById("odontograma-reiniciar");
        if (btnReiniciar) {
            btnReiniciar.addEventListener("click", function () {
                if (!confirm("Se marcarán las 32 piezas como sanas. ¿Continuar?")) return;
                fetch(`/odontograma/${pacienteId}/reiniciar`, { method: "POST" })
                    .then(function (r) { return r.json(); })
                    .then(function () {
                        svg.querySelectorAll(".diente").forEach(function (g) {
                            g.querySelectorAll(".cara-diente").forEach(function (poligono) {
                                poligono.dataset.estado = "sano";
                            });
                            pintarPieza(g.dataset.pieza, "sano");
                            pintarPerno(g.dataset.pieza, false);
                        });
                        mostrarAviso("Odontograma reiniciado");
                    });
            });
        }

        // --- Tipo de mordida ------------------------------------------
        const selectMordida = document.getElementById("mordida-select");
        const avisoMordida = document.getElementById("mordida-aviso");
        if (selectMordida) {
            selectMordida.addEventListener("change", function () {
                const valor = selectMordida.value;
                fetch(`/pacientes/${pacienteId}/mordida`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ mordida: valor || null }),
                })
                    .then(function (r) { return r.json(); })
                    .then(function (data) {
                        if (!avisoMordida) return;
                        avisoMordida.textContent = data.ok ? "Guardado" : (data.error || "No se pudo guardar");
                        avisoMordida.classList.toggle("error", !data.ok);
                        avisoMordida.classList.add("visible");
                        clearTimeout(avisoMordida._t);
                        avisoMordida._t = setTimeout(function () {
                            avisoMordida.classList.remove("visible");
                        }, 1800);
                    });
            });
        }

        // --- Aparato ortodóntico ---------------------------------------
        const selectTipo = document.getElementById("orto-tipo");
        const selectDesde = document.getElementById("orto-desde");
        const selectHasta = document.getElementById("orto-hasta");
        const selectArcada = document.getElementById("orto-arcada");
        const selectEstadoOrto = document.getElementById("orto-estado");
        const camposFijo = document.getElementById("orto-campos-fijo");
        const listaOrto = document.getElementById("ortodoncia-lista");
        const btnAgregarOrto = document.getElementById("orto-agregar");
        const avisoOrto = document.getElementById("ortodoncia-aviso");

        if (selectTipo && selectDesde && selectHasta && selectArcada) {
            // "Desde"/"Hasta" solo muestran las piezas de la arcada elegida arriba.
            function poblarPiezasPorArcada() {
                const piezas = selectArcada.value === "superior" ? filaSuperior : filaInferior;
                const anteriorDesde = selectDesde.value;
                const anteriorHasta = selectHasta.value;
                selectDesde.innerHTML = "";
                selectHasta.innerHTML = "";
                piezas.forEach(function (fdi) {
                    selectDesde.appendChild(new Option(fdi, fdi));
                    selectHasta.appendChild(new Option(fdi, fdi));
                });
                if (piezas.includes(Number(anteriorDesde))) selectDesde.value = anteriorDesde;
                if (piezas.includes(Number(anteriorHasta))) selectHasta.value = anteriorHasta;
            }
            selectArcada.addEventListener("change", poblarPiezasPorArcada);
            poblarPiezasPorArcada();

            function actualizarCamposOrto() {
                const esFijo = selectTipo.value === "fijo";
                camposFijo.style.display = esFijo ? "flex" : "none";
            }
            selectTipo.addEventListener("change", actualizarCamposOrto);
            actualizarCamposOrto();

            function mostrarAvisoOrto(texto, esError) {
                if (!avisoOrto) return;
                avisoOrto.textContent = texto;
                avisoOrto.classList.toggle("error", !!esError);
                avisoOrto.classList.add("visible");
                clearTimeout(avisoOrto._t);
                avisoOrto._t = setTimeout(function () { avisoOrto.classList.remove("visible"); }, 1800);
            }

            function pintarListaOrto() {
                listaOrto.innerHTML = "";
                if (!ortodoncia.length) {
                    const vacio = document.createElement("span");
                    vacio.className = "small text-muted";
                    vacio.textContent = "Sin aparato de ortodoncia registrado.";
                    listaOrto.appendChild(vacio);
                    return;
                }
                ortodoncia.forEach(function (aparato) {
                    const fila = document.createElement("div");
                    fila.className = "d-flex align-items-center gap-2 small";

                    const muestra = document.createElement("span");
                    muestra.style.cssText = "width:12px;height:12px;border-radius:3px;display:inline-block;background:" +
                        (coloresOrto[aparato.estado] || coloresOrto.bueno).color;
                    fila.appendChild(muestra);

                    const texto = document.createElement("span");
                    const estadoTxt = (coloresOrto[aparato.estado] || {}).etiqueta || aparato.estado;
                    texto.textContent = aparato.tipo === "fijo"
                        ? `Fijo · piezas ${aparato.pieza_desde}–${aparato.pieza_hasta} · ${estadoTxt}`
                        : `Removible · arcada ${aparato.arcada} · ${estadoTxt}`;
                    fila.appendChild(texto);

                    const btnEliminar = document.createElement("button");
                    btnEliminar.type = "button";
                    btnEliminar.className = "btn btn-link btn-sm text-decoration-none p-0 text-muted";
                    btnEliminar.style.fontSize = ".76rem";
                    btnEliminar.textContent = "Eliminar";
                    btnEliminar.addEventListener("click", function () {
                        fetch(`/odontograma/ortodoncia/${aparato.id}`, { method: "DELETE" })
                            .then(function (r) { return r.json(); })
                            .then(function () {
                                ortodoncia = ortodoncia.filter(function (a) { return a.id !== aparato.id; });
                                pintarListaOrto();
                                redibujarOrtodoncia();
                                mostrarAvisoOrto("Aparato eliminado");
                            });
                    });
                    fila.appendChild(btnEliminar);

                    listaOrto.appendChild(fila);
                });
            }
            pintarListaOrto();

            if (btnAgregarOrto) {
                btnAgregarOrto.addEventListener("click", function () {
                    const tipo = selectTipo.value;
                    const cuerpo = { tipo, estado: selectEstadoOrto.value };
                    if (tipo === "fijo") {
                        cuerpo.pieza_desde = Number(selectDesde.value);
                        cuerpo.pieza_hasta = Number(selectHasta.value);
                    } else {
                        cuerpo.arcada = selectArcada.value;
                    }

                    fetch(`/odontograma/${pacienteId}/ortodoncia`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify(cuerpo),
                    })
                        .then(function (r) { return r.json(); })
                        .then(function (data) {
                            if (data.ok) {
                                ortodoncia.push(data.aparato);
                                pintarListaOrto();
                                redibujarOrtodoncia();
                                mostrarAvisoOrto("Aparato registrado");
                            } else {
                                mostrarAvisoOrto(data.error || "No se pudo guardar", true);
                            }
                        })
                        .catch(function () {
                            mostrarAvisoOrto("Sin conexión con el servidor", true);
                        });
                });
            }
        }
    }

    document.addEventListener("DOMContentLoaded", iniciar);
})();
