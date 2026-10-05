import os
from flask import Blueprint, redirect, url_for, send_from_directory, current_app, render_template
from flask_login import current_user

from models import Usuario

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))

    if current_user.is_tecnico_impressora:
        return redirect(url_for('impressoras.index'))

    return redirect(url_for('chamados.home'))


# ==========================================
# ROTAS PWA (Progressive Web App)
# ==========================================

@main_bp.route('/manifest.json')
def manifest():
    """Serve o Web App Manifest do PWA."""
    return send_from_directory(
        current_app.static_folder,
        'manifest.json',
        mimetype='application/manifest+json'
    )


@main_bp.route('/sw.js')
def service_worker():
    """
    Serve o Service Worker no escopo raiz '/', permitindo controlar
    todas as páginas do sistema.
    """
    response = send_from_directory(
        current_app.static_folder,
        'sw.js',
        mimetype='application/javascript'
    )
    # Permite escopo raiz para todo o aplicativo
    response.headers['Service-Worker-Allowed'] = '/'
    # Impede cache permanente para garantir que atualizações do SW sejam detectadas
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response


@main_bp.route('/offline')
def offline():
    """Página amigável exibida quando o servidor ou internet estiver inacessível."""
    return render_template('offline.html')


@main_bp.route('/favicon.ico')
def favicon():
    """Favicon oficial do sistema para navegadores e atalhos."""
    return send_from_directory(
        os.path.join(current_app.static_folder, 'icons'),
        'favicon.ico',
        mimetype='image/x-icon'
    )