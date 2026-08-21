"""
Almacén: productos (insumos de salud) y su kardex de movimientos.

El stock vive en dos lugares que se mantienen sincronizados:
  - productos_almacen.stock_actual: el saldo actual, para no tener que sumar
    todo el kardex cada vez que se lista el almacén.
  - movimientos_almacen: una fila por cada entrada o salida, con el saldo
    que quedó en ese momento — es el historial auditable ("¿cuándo se acabó
    el algodón?", "¿cuánto gasté en anestesia este mes?").

Cada movimiento actualiza el saldo del producto en la misma operación.
"""

from datetime import date

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from services.constantes import CATEGORIAS_ALMACEN, TIPOS_MOVIMIENTO, UNIDADES_MEDIDA
from services.supabase_client import sb

bp = Blueprint("almacen", __name__, url_prefix="/almacen")


@bp.route("/")
def lista():
    """
    Listado de productos con búsqueda y filtro por categoría.
    Marca "stock bajo" (si tiene stock_minimo) y "por vencer" (30 días) en Python:
    el volumen de un almacén de consultorio es chico, no hace falta SQL para esto.
    """
    q = (request.args.get("q") or "").strip()
    categoria = request.args.get("categoria") or ""

    consulta = sb.table("productos_almacen").select("*").eq("activo", True)
    if categoria in CATEGORIAS_ALMACEN:
        consulta = consulta.eq("categoria", categoria)
    if q:
        consulta = consulta.ilike("nombre", f"%{q}%")

    productos = consulta.order("nombre").execute().data or []

    hoy = date.today()
    for p in productos:
        p["stock_bajo"] = p["stock_minimo"] is not None and float(p["stock_actual"]) <= float(p["stock_minimo"])
        if p["tiene_vencimiento"] and p["fecha_vencimiento"]:
            dias = (date.fromisoformat(p["fecha_vencimiento"]) - hoy).days
            p["dias_para_vencer"] = dias
            p["por_vencer"] = 0 <= dias <= 30
            p["vencido"] = dias < 0
        else:
            p["dias_para_vencer"] = None
            p["por_vencer"] = False
            p["vencido"] = False

    return render_template(
        "almacen/lista.html",
        productos=productos, q=q, categoria=categoria,
        categorias=CATEGORIAS_ALMACEN,
    )


@bp.route("/nuevo", methods=["GET", "POST"])
def nuevo():
    if request.method == "POST":
        datos = _campos_del_formulario(request.form)
        if not datos["nombre"]:
            flash("El producto necesita un nombre.", "danger")
            return render_template("almacen/formulario.html", producto=datos, modo="nuevo",
                                    categorias=CATEGORIAS_ALMACEN, unidades=UNIDADES_MEDIDA)

        stock_inicial = datos.pop("stock_inicial")
        creado = sb.table("productos_almacen").insert(datos).execute().data[0]

        if stock_inicial > 0:
            _registrar_movimiento(creado["id"], "entrada", stock_inicial,
                                  motivo="Stock inicial", costo_unitario=None)

        flash(f"«{creado['nombre']}» agregado al almacén.", "success")
        return redirect(url_for("almacen.detalle", producto_id=creado["id"]))

    return render_template("almacen/formulario.html", producto={}, modo="nuevo",
                            categorias=CATEGORIAS_ALMACEN, unidades=UNIDADES_MEDIDA)


@bp.route("/<int:producto_id>/editar", methods=["GET", "POST"])
def editar(producto_id):
    producto = _obtener_producto(producto_id)

    if request.method == "POST":
        datos = _campos_del_formulario(request.form)
        datos.pop("stock_inicial")     # el stock ya no se toca desde "editar"
        if not datos["nombre"]:
            flash("El producto necesita un nombre.", "danger")
            return render_template("almacen/formulario.html", producto=producto, modo="editar",
                                    categorias=CATEGORIAS_ALMACEN, unidades=UNIDADES_MEDIDA)

        sb.table("productos_almacen").update(datos).eq("id", producto_id).execute()
        flash("Producto actualizado.", "success")
        return redirect(url_for("almacen.detalle", producto_id=producto_id))

    return render_template("almacen/formulario.html", producto=producto, modo="editar",
                            categorias=CATEGORIAS_ALMACEN, unidades=UNIDADES_MEDIDA)


@bp.route("/<int:producto_id>")
def detalle(producto_id):
    """Ficha del producto: stock actual + kardex completo + total gastado."""
    producto = _obtener_producto(producto_id)
    movimientos = (
        sb.table("movimientos_almacen").select("*")
        .eq("producto_id", producto_id)
        .order("creado_en", desc=True).execute().data or []
    )

    total_gastado = sum(
        float(m["cantidad"]) * float(m["costo_unitario"])
        for m in movimientos if m["tipo"] == "entrada" and m["costo_unitario"]
    )
    total_consumido = sum(float(m["cantidad"]) for m in movimientos if m["tipo"] == "salida")

    return render_template(
        "almacen/detalle.html",
        producto=producto, movimientos=movimientos,
        total_gastado=total_gastado, total_consumido=total_consumido,
        categorias=CATEGORIAS_ALMACEN, unidades=UNIDADES_MEDIDA, tipos_movimiento=TIPOS_MOVIMIENTO,
    )


@bp.route("/<int:producto_id>/entrada", methods=["POST"])
def entrada(producto_id):
    """Ingresa stock nuevo (compra, donación, etc.), con costo opcional."""
    try:
        cantidad = float(request.form.get("cantidad") or 0)
    except ValueError:
        cantidad = 0
    if cantidad <= 0:
        flash("La cantidad tiene que ser mayor a cero.", "danger")
        return redirect(url_for("almacen.detalle", producto_id=producto_id))

    costo = request.form.get("costo_unitario")
    costo_unitario = float(costo) if costo else None
    motivo = (request.form.get("motivo") or "").strip() or "Ingreso de stock"

    _registrar_movimiento(producto_id, "entrada", cantidad, motivo, costo_unitario)
    flash(f"Ingresaron {cantidad} unidades.", "success")
    return redirect(url_for("almacen.detalle", producto_id=producto_id))


@bp.route("/<int:producto_id>/salida", methods=["POST"])
def salida(producto_id):
    """Descuenta stock por uso. No deja bajar de cero."""
    producto = _obtener_producto(producto_id)
    try:
        cantidad = float(request.form.get("cantidad") or 0)
    except ValueError:
        cantidad = 0
    if cantidad <= 0:
        flash("La cantidad tiene que ser mayor a cero.", "danger")
        return redirect(url_for("almacen.detalle", producto_id=producto_id))
    if cantidad > float(producto["stock_actual"]):
        flash(f"No hay suficiente stock (quedan {producto['stock_actual']}).", "danger")
        return redirect(url_for("almacen.detalle", producto_id=producto_id))

    motivo = (request.form.get("motivo") or "").strip() or "Uso en consultorio"
    _registrar_movimiento(producto_id, "salida", cantidad, motivo, costo_unitario=None)
    flash(f"Se descontaron {cantidad} unidades.", "success")
    return redirect(url_for("almacen.detalle", producto_id=producto_id))


@bp.route("/<int:producto_id>/baja", methods=["POST"])
def baja(producto_id):
    """Baja lógica: deja de aparecer en el listado, pero conserva el kardex."""
    producto = _obtener_producto(producto_id)
    sb.table("productos_almacen").update({"activo": False}).eq("id", producto_id).execute()
    flash(f"«{producto['nombre']}» se quitó del almacén activo.", "info")
    return redirect(url_for("almacen.lista"))


# --- Utilidades internas ---------------------------------------------------

def _campos_del_formulario(form) -> dict:
    def limpio(clave):
        valor = (form.get(clave) or "").strip()
        return valor or None

    tiene_vencimiento = form.get("tiene_vencimiento") == "si"
    try:
        stock_inicial = float(form.get("stock_inicial") or 0)
    except ValueError:
        stock_inicial = 0
    try:
        stock_minimo = float(form.get("stock_minimo")) if limpio("stock_minimo") else None
    except ValueError:
        stock_minimo = None

    return {
        "nombre": (form.get("nombre") or "").strip(),
        "descripcion": limpio("descripcion"),
        "categoria": form.get("categoria") if form.get("categoria") in CATEGORIAS_ALMACEN else "otros",
        "unidad_medida": form.get("unidad_medida") if form.get("unidad_medida") in UNIDADES_MEDIDA else "unidad",
        "tiene_vencimiento": tiene_vencimiento,
        "fecha_vencimiento": limpio("fecha_vencimiento") if tiene_vencimiento else None,
        "stock_minimo": stock_minimo,
        "stock_inicial": stock_inicial,   # se usa solo en "nuevo"; editar() lo descarta
    }


def _registrar_movimiento(producto_id, tipo, cantidad, motivo, costo_unitario):
    """Inserta el movimiento y actualiza productos_almacen.stock_actual en el mismo paso."""
    producto = _obtener_producto(producto_id)
    stock_previo = float(producto["stock_actual"])
    nuevo_stock = stock_previo + cantidad if tipo == "entrada" else stock_previo - cantidad
    nuevo_stock = round(nuevo_stock, 2)

    sb.table("movimientos_almacen").insert({
        "producto_id": producto_id,
        "tipo": tipo,
        "cantidad": cantidad,
        "saldo_resultante": nuevo_stock,
        "costo_unitario": costo_unitario,
        "motivo": motivo,
    }).execute()

    sb.table("productos_almacen").update({"stock_actual": nuevo_stock}).eq("id", producto_id).execute()


def _obtener_producto(producto_id: int) -> dict:
    resp = sb.table("productos_almacen").select("*").eq("id", producto_id).limit(1).execute()
    if not resp.data:
        abort(404)
    return resp.data[0]
