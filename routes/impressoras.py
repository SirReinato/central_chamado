from flask import Blueprint, render_template
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