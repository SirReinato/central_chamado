"""
Script de Migracao Segura - Integracao GLPI
Adiciona colunas necessarias na tabela `chamados` e cria a tabela `glpi_sync_logs`
sem perda de dados e de forma 100% idempotente (pode rodar multiplas vezes).
"""
import os
import sqlite3

def migrar_banco():
    db_paths = [
        os.path.join("instance", "chamados.db"),
        "chamados.db"
    ]
    
    db_path = None
    for path in db_paths:
        if os.path.exists(path):
            db_path = path
            break
            
    if not db_path:
        print("[ERRO] Arquivo de banco de dados nao encontrado em instance/chamados.db nem na raiz.")
        return False

    print(f"[INFO] Conectando ao banco de dados: {db_path}")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    try:
        # 1. Verificar colunas atuais da tabela 'chamados'
        cur.execute("PRAGMA table_info(chamados);")
        colunas_existentes = [col[1] for col in cur.fetchall()]
        print(f"[INFO] Colunas atuais em 'chamados': {colunas_existentes}")

        # 2. Adicionar 'origem' se nao existir
        if "origem" not in colunas_existentes:
            print("[INFO] Adicionando coluna 'origem'...")
            cur.execute("ALTER TABLE chamados ADD COLUMN origem VARCHAR(20) DEFAULT 'local' NOT NULL;")
        else:
            print("[INFO] Coluna 'origem' ja existe.")

        # 3. Adicionar 'glpi_id' se nao existir
        if "glpi_id" not in colunas_existentes:
            print("[INFO] Adicionando coluna 'glpi_id'...")
            cur.execute("ALTER TABLE chamados ADD COLUMN glpi_id INTEGER;")
        else:
            print("[INFO] Coluna 'glpi_id' ja existe.")

        # 4. Adicionar 'glpi_numero' se nao existir
        if "glpi_numero" not in colunas_existentes:
            print("[INFO] Adicionando coluna 'glpi_numero'...")
            cur.execute("ALTER TABLE chamados ADD COLUMN glpi_numero VARCHAR(50);")
        else:
            print("[INFO] Coluna 'glpi_numero' ja existe.")

        # 5. Criar indice unico para glpi_id
        print("[INFO] Garantindo indice unico para 'glpi_id'...")
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_chamados_glpi_id ON chamados(glpi_id);")

        # 6. Criar tabela 'glpi_sync_logs' se nao existir
        print("[INFO] Criando tabela 'glpi_sync_logs'...")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS glpi_sync_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_execucao DATETIME NOT NULL,
            tickets_encontrados INTEGER DEFAULT 0,
            tickets_importados INTEGER DEFAULT 0,
            status VARCHAR(30) NOT NULL DEFAULT 'Sucesso',
            mensagem TEXT,
            ultimo_ticket_id INTEGER,
            ultima_data_ticket DATETIME
        );
        """)

        conn.commit()
        print("[SUCESSO] Migracao concluida com sucesso!")
        return True

    except Exception as e:
        conn.rollback()
        print(f"[ERRO] Falha durante a migracao: {e}")
        return False
    finally:
        conn.close()

if __name__ == '__main__':
    migrar_banco()
