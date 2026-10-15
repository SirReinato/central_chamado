"""
Script de Teste / Dry-Run da Integracao GLPI
Permite testar a sincronizacao de forma segura.
Uso:
  python scripts/testar_glpi_sync.py           -> Roda em modo SIMULACAO (Dry-Run, nao altera o banco)
  python scripts/testar_glpi_sync.py --executar -> Roda importando de verdade para o banco
"""
import sys
import os

# Adiciona a raiz do projeto ao path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app
from services.glpi_sync import executar_sincronizacao

if __name__ == '__main__':
    dry_run = True
    if len(sys.argv) > 1 and sys.argv[1] == '--executar':
        dry_run = False

    modo = "SIMULACAO (Dry-Run - sem gravar no banco)" if dry_run else "REAL (gravando no banco)"
    print(f"\n=======================================================")
    print(f"   TESTE DE INTEGRACAO GLPI -> CENTRAL DE CHAMADOS")
    print(f"   Modo: {modo}")
    print(f"=======================================================\n")

    with app.app_context():
        res = executar_sincronizacao(dry_run=dry_run)
        print("\nResultado da operacao:")
        for k, v in res.items():
            print(f"  * {k}: {v}")
        print("\n=======================================================\n")
