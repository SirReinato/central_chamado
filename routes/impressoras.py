from flask import Blueprint, render_template, request, redirect, url_for
from services.impressoras_services import ImpressorasService

impressoras_bp = Blueprint(
    "impressoras",
    __name__,
    url_prefix="/impressoras"
)

@impressoras_bp.route("/")
def index():
    impressoras = ImpressorasService.listar_impressoras()
    
    return render_template(
        "impressoras/impressoras.html",
        impressoras=impressoras
    )
    
    
@impressoras_bp.route("/nova", methods=["GET", "POST"])
def nova_impressora():

    if request.method == "POST":

        nome = request.form.get("nome")
        ip = request.form.get("ip")
        modelo = request.form.get("modelo")

        ImpressorasService.adicionar_impressora(
            nome,
            ip,
            modelo
        )

        return redirect(
            url_for("impressoras.index")
        )

    return render_template(
        "impressoras/nova_impressora.html"
    )
    