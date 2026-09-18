import sqlite3
import shutil
import os
from datetime import datetime

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
INSTANCE_DIR = os.path.join(BASE_DIR, 'instance')
CHAMADOS_DB = os.path.join(INSTANCE_DIR, 'chamados.db')
ESTOQUE_DB = os.path.join(INSTANCE_DIR, 'estoque_suprimentos.db')

def backup_file(filepath):
    if not os.path.exists(filepath):
        print(f"[AVISO] Arquivo {filepath} não existe para backup.")
        return None
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f"{filepath}.backup_{timestamp}"
    shutil.copy2(filepath, backup_path)
    print(f"[BACKUP] Criado backup com sucesso: {backup_path}")
    return backup_path

def migrar():
    print("=== INICIANDO MIGRAÇÃO SEGURA DOS BANCOS ===")
    
    # 1. Backups
    bkp_chamados = backup_file(CHAMADOS_DB)
    bkp_estoque = backup_file(ESTOQUE_DB)
    
    if not os.path.exists(CHAMADOS_DB) or not os.path.exists(ESTOQUE_DB):
        raise FileNotFoundError("Ambos os bancos devem existir para a migração!")

    # 2. Conectar aos bancos
    conn_chamados = sqlite3.connect(CHAMADOS_DB)
    cur_chamados = conn_chamados.cursor()
    
    conn_estoque = sqlite3.connect(ESTOQUE_DB)
    cur_estoque = conn_estoque.cursor()
    
    # 3. Criar tabelas de estoque em chamados.db se nao existirem
    cur_chamados.execute("""
    CREATE TABLE IF NOT EXISTS estoque_suprimentos (
        id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
        nome_familia VARCHAR(100) NOT NULL UNIQUE,
        quantidade_toner INTEGER NOT NULL DEFAULT 0,
        quantidade_cilindro INTEGER NOT NULL DEFAULT 0,
        estoque_minimo INTEGER NOT NULL DEFAULT 2
    );
    """)
    
    cur_chamados.execute("""
    CREATE TABLE IF NOT EXISTS historico_suprimentos (
        id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
        impressora_id INTEGER,
        familia_id INTEGER,
        tipo_insumo VARCHAR(20) NOT NULL,
        quantidade INTEGER NOT NULL DEFAULT -1,
        usuario_responsavel VARCHAR(100) NOT NULL,
        data_retirada DATETIME,
        FOREIGN KEY(impressora_id) REFERENCES impressoras (id),
        FOREIGN KEY(familia_id) REFERENCES estoque_suprimentos (id)
    );
    """)
    conn_chamados.commit()

    # 4. Copiar dados de estoque_suprimentos
    cur_estoque.execute("SELECT id, nome_familia, quantidade_toner, quantidade_cilindro, estoque_minimo FROM estoque_suprimentos")
    familias = cur_estoque.fetchall()
    print(f"[ESTOQUE] Transferindo {len(familias)} famílias de suprimentos...")
    
    for fam in familias:
        cur_chamados.execute("""
        INSERT OR REPLACE INTO estoque_suprimentos (id, nome_familia, quantidade_toner, quantidade_cilindro, estoque_minimo)
        VALUES (?, ?, ?, ?, ?)
        """, fam)
    
    # 5. Copiar dados de historico_suprimentos
    cur_estoque.execute("SELECT id, impressora_id, familia_id, tipo_insumo, quantidade, usuario_responsavel, data_retirada FROM historico_suprimentos")
    historicos = cur_estoque.fetchall()
    print(f"[HISTÓRICO] Transferindo {len(historicos)} registros de histórico...")
    
    for hist in historicos:
        cur_chamados.execute("""
        INSERT OR REPLACE INTO historico_suprimentos (id, impressora_id, familia_id, tipo_insumo, quantidade, usuario_responsavel, data_retirada)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, hist)
    
    conn_chamados.commit()

    # 6. Atualizar colunas de auditoria na tabela chamados
    cur_chamados.execute("PRAGMA table_info(chamados)")
    colunas_chamados = [c[1] for c in cur_chamados.fetchall()]
    
    if 'tecnico_id' not in colunas_chamados:
        print("[CHAMADOS] Adicionando coluna 'tecnico_id'...")
        cur_chamados.execute("ALTER TABLE chamados ADD COLUMN tecnico_id INTEGER REFERENCES usuarios(id)")
    
    if 'data_atualizacao' not in colunas_chamados:
        print("[CHAMADOS] Adicionando coluna 'data_atualizacao'...")
        cur_chamados.execute("ALTER TABLE chamados ADD COLUMN data_atualizacao DATETIME")
        cur_chamados.execute("UPDATE chamados SET data_atualizacao = data_abertura WHERE data_atualizacao IS NULL")
        
    if 'data_fechamento' not in colunas_chamados:
        print("[CHAMADOS] Adicionando coluna 'data_fechamento'...")
        cur_chamados.execute("ALTER TABLE chamados ADD COLUMN data_fechamento DATETIME")
        cur_chamados.execute("UPDATE chamados SET data_fechamento = data_abertura WHERE status IN ('Resolvido', 'Fechado') AND data_fechamento IS NULL")

    conn_chamados.commit()

    # 7. Validação cruzada final
    cur_chamados.execute("SELECT count(*) FROM usuarios")
    cnt_usuarios = cur_chamados.fetchone()[0]
    
    cur_chamados.execute("SELECT count(*) FROM impressoras")
    cnt_impressoras = cur_chamados.fetchone()[0]
    
    cur_chamados.execute("SELECT count(*) FROM chamados")
    cnt_chamados = cur_chamados.fetchone()[0]
    
    cur_chamados.execute("SELECT count(*) FROM estoque_suprimentos")
    cnt_estoque = cur_chamados.fetchone()[0]
    
    cur_chamados.execute("SELECT count(*) FROM historico_suprimentos")
    cnt_historico = cur_chamados.fetchone()[0]

    conn_estoque.close()
    conn_chamados.close()

    print("\n=== RESULTADO DA VALIDAÇÃO FINAL ===")
    print(f"  Usuários:              {cnt_usuarios} (esperado: >= 4)")
    print(f"  Impressoras:           {cnt_impressoras} (esperado: >= 23)")
    print(f"  Chamados:              {cnt_chamados} (esperado: >= 5)")
    print(f"  Famílias Suprimentos:  {cnt_estoque} (esperado: {len(familias)})")
    print(f"  Histórico Suprimentos: {cnt_historico} (esperado: {len(historicos)})")

    assert cnt_usuarios >= 4, "Falha na contagem de usuários!"
    assert cnt_impressoras >= 23, "Falha na contagem de impressoras!"
    assert cnt_chamados >= 5, "Falha na contagem de chamados!"
    assert cnt_estoque == len(familias), "Falha na contagem de famílias de estoque!"
    assert cnt_historico == len(historicos), "Falha na contagem de histórico de estoque!"

    print("\n[SUCESSO] MIGRACAO CONCLUIDA COM 100% DE SUCESSO E ZERO PERDA DE DADOS!")

if __name__ == '__main__':
    migrar()

