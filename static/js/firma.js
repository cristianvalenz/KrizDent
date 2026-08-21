/* =====================================================================
   KrizDent — Captura de firma en <canvas>

   Dibuja con mouse o dedo/lápiz (touch). Al enviar el formulario, exporta
   el canvas como PNG en base64 y lo pone en el campo oculto "firma".
   ===================================================================== */

(function () {
    "use strict";

    function iniciar() {
        const canvas = document.getElementById("lienzo-firma");
        if (!canvas) return;

        const ctx = canvas.getContext("2d");
        ctx.lineWidth = 2.2;
        ctx.lineCap = "round";
        ctx.strokeStyle = "#16232E";

        let dibujando = false;
        let huboTrazo = false;

        function posicion(e) {
            const rect = canvas.getBoundingClientRect();
            const escalaX = canvas.width / rect.width;
            const escalaY = canvas.height / rect.height;
            const punto = e.touches ? e.touches[0] : e;
            return {
                x: (punto.clientX - rect.left) * escalaX,
                y: (punto.clientY - rect.top) * escalaY,
            };
        }

        function empezar(e) {
            e.preventDefault();
            dibujando = true;
            huboTrazo = true;
            const p = posicion(e);
            ctx.beginPath();
            ctx.moveTo(p.x, p.y);
        }

        function trazar(e) {
            if (!dibujando) return;
            e.preventDefault();
            const p = posicion(e);
            ctx.lineTo(p.x, p.y);
            ctx.stroke();
        }

        function terminar() { dibujando = false; }

        canvas.addEventListener("mousedown", empezar);
        canvas.addEventListener("mousemove", trazar);
        window.addEventListener("mouseup", terminar);

        canvas.addEventListener("touchstart", empezar, { passive: false });
        canvas.addEventListener("touchmove", trazar, { passive: false });
        canvas.addEventListener("touchend", terminar);

        const btnLimpiar = document.getElementById("btn-limpiar-firma");
        if (btnLimpiar) {
            btnLimpiar.addEventListener("click", function () {
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                huboTrazo = false;
            });
        }

        const form = document.getElementById("form-consentimiento");
        const campoOculto = document.getElementById("firma-datauri");
        if (form && campoOculto) {
            form.addEventListener("submit", function (e) {
                if (!huboTrazo) {
                    e.preventDefault();
                    alert("Falta la firma. Dibújala en el recuadro antes de guardar.");
                    return;
                }
                campoOculto.value = canvas.toDataURL("image/png");
            });
        }
    }

    document.addEventListener("DOMContentLoaded", iniciar);
})();
