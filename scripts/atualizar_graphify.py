"""
Script de atualizacao do Graphify - Hub Central - SirReinato Brasfort

Executa uma atualizacao incremental do grafo de conhecimento, processando
apenas arquivos novos ou modificados desde a ultima execucao.

Uso:
    python scripts/atualizar_graphify.py

Requisitos:
    - graphify instalado (uv tool install graphifyy)
    - OLLAMA_BASE_URL configurado (opcional, para extracao semantica)
"""

import os
import subprocess
import sys
from datetime import datetime

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def atualizar_graphify():
    """Atualiza o Graphify incrementalmente."""
    print("=" * 60)
    print("  ATUALIZACAO DO GRAPHIFY - HUB CENTRAL - SIRREINATO BRASFORT")
    print("=" * 60)
    print(f"  Diretorio: {BASE_DIR}")
    print(f"  Iniciado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print("-" * 60)

    env = {**os.environ, "OLLAMA_BASE_URL": os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")}

    try:
        resultado = subprocess.run(
            ["graphify", ".", "--update"],
            capture_output=True,
            text=True,
            cwd=BASE_DIR,
            env=env,
            timeout=300
        )

        # Exibe saida relevante
        if resultado.stdout:
            for linha in resultado.stdout.strip().splitlines():
                if linha.strip():
                    print(f"  {linha}")

        if resultado.returncode == 0:
            print("-" * 60)
            print("  [SUCESSO] Graphify atualizado com sucesso!")
        else:
            print("-" * 60)
            print("  [AVISO] Graphify concluiu com possiveis avisos.")
            if resultado.stderr:
                for linha in resultado.stderr.strip().splitlines()[-5:]:
                    if linha.strip():
                        print(f"  {linha}")

    except subprocess.TimeoutExpired:
        print("-" * 60)
        print("  [ERRO] Tempo limite excedido (5 minutos).")
        return False
    except FileNotFoundError:
        print("-" * 60)
        print("  [ERRO] Graphify CLI nao encontrado.")
        print("  Instale com: uv tool install graphifyy")
        return False
    except Exception as e:
        print("-" * 60)
        print(f"  [ERRO] Falha inesperada: {e}")
        return False

    print(f"  Finalizado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print("=" * 60)
    return True


if __name__ == '__main__':
    sucesso = atualizar_graphify()
    sys.exit(0 if sucesso else 1)
