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

@impressoras_bp.route("/descobrir")
def descobrir_impressoras():

    ImpressorasService.descobrir_impressoras()

    return redirect(
        url_for("impressoras.index")
    )
    
@impressoras_bp.route("/sincronizar")
def sincronizar():

    ImpressorasService.sincronizar_dc1()
    ImpressorasService.atualizar_ips_dc1()
    ImpressorasService.atualizar_status()

    return redirect(
        url_for("impressoras.index")
    )
    
    
@impressoras_bp.route("/atualizar-status")
def atualizar_status():

    ImpressorasService.atualizar_status()

    return redirect(
        url_for("impressoras.index")
    )
    
@impressoras_bp.route("/teste-web")
def teste_web():

    resultado = ImpressorasService.consultar_interface_web(
        "10.90.1.16"
    )

    return resultado
