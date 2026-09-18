from flask import Blueprint, redirect, url_for
from flask_login import current_user

from models import Usuario

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))

    return redirect(url_for('chamados.home'))