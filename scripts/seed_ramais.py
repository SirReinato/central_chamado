import os
import sys

# Adiciona o diretório raiz ao path para importar app e models
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app
from models import db, Ramal

# Dados oficiais de ramais da Brasfort (coluna "Ramal - Atual")
RAMAIS_DATA = [
    {"andar": "SubSolo / Térreo", "departamento": "Dep. Operacional Adm", "nome": "Delfino Silva", "ramal": "2013"},
    {"andar": "SubSolo / Térreo", "departamento": "Dep. Operacional Adm", "nome": "Rafael Rocha", "ramal": "2041"},
    {"andar": "SubSolo / Térreo", "departamento": "Dep. Operacional Adm", "nome": "Marlon Honesko", "ramal": "2014"},
    {"andar": "SubSolo / Térreo", "departamento": "Dep. Operacional Adm", "nome": "Carlos Neto", "ramal": "2043"},
    {"andar": "SubSolo / Térreo", "departamento": "Dep. Operacional Adm", "nome": "Jhonatan Brito", "ramal": "2045"},
    {"andar": "SubSolo / Térreo", "departamento": "Dep. Operacional Adm", "nome": "Edson Cruz", "ramal": "2042"},
    {"andar": "SubSolo / Térreo", "departamento": "Dep. Operacional Adm", "nome": "Laura Silva", "ramal": "2046"},
    {"andar": "SubSolo / Térreo", "departamento": "Dep. Operacional Adm", "nome": "Ingrid Lopes", "ramal": "2012"},
    {"andar": "SubSolo / Térreo", "departamento": "Dep. Operacional Adm", "nome": "Kezia Santos", "ramal": "2013"},
    {"andar": "SubSolo / Térreo", "departamento": "Dep. Operacional Adm", "nome": "--Mesa Operacional Fis", "ramal": "2014"},
    {"andar": "SubSolo / Térreo", "departamento": "Dep. Operacional Adm", "nome": "--Fiscais", "ramal": "2015"},
    {"andar": "SubSolo / Térreo", "departamento": "Dep. Operacional Adm", "nome": "--Gestão", "ramal": "2017"},
    {"andar": "SubSolo / Térreo", "departamento": "Dep. Operacional Adm", "nome": "--Mesa de operações Adm", "ramal": "2044"},
    {"andar": "SubSolo / Térreo", "departamento": "Dep. Operacional Adm", "nome": "--Supervisor Adm", "ramal": "2047"},
    {"andar": "SubSolo / Térreo", "departamento": "Dep. Seg. Eletrônica", "nome": "Luciano", "ramal": "2020"},
    {"andar": "SubSolo / Térreo", "departamento": "Dep. Seg. Eletrônica", "nome": "Marco Ramos", "ramal": "2028"},
    {"andar": "SubSolo / Térreo", "departamento": "Dep. Seg. Eletrônica", "nome": "Rayssen Braga", "ramal": "2027"},
    {"andar": "SubSolo / Térreo", "departamento": "Dep. Seg. Eletrônica", "nome": "Quely", "ramal": "2022"},
    {"andar": "SubSolo / Térreo", "departamento": "Dep. Seg. Eletrônica", "nome": "Andreia", "ramal": "2022"},
    {"andar": "SubSolo / Térreo", "departamento": "Dep. Seg. Eletrônica", "nome": "Marcos Maia", "ramal": "2029"},
    {"andar": "SubSolo / Térreo", "departamento": "Dep. Seg. Eletrônica", "nome": "--Técnico", "ramal": "2024"},
    {"andar": "SubSolo / Térreo", "departamento": "Dep. Seg. Eletrônica", "nome": "--Operador 1", "ramal": "2021"},
    {"andar": "SubSolo / Térreo", "departamento": "Dep. Seg. Eletrônica", "nome": "--Operador 2", "ramal": "2026"},
    {"andar": "SubSolo / Térreo", "departamento": "Dep. Tecnologia Sup.", "nome": "Arthur", "ramal": "2323"},
    {"andar": "SubSolo / Térreo", "departamento": "Dep. Tecnologia Sup.", "nome": "Renato", "ramal": "2321"},
    {"andar": "SubSolo / Térreo", "departamento": "Dep. Tecnologia Sup.", "nome": "Matheus", "ramal": "2324"},
    {"andar": "SubSolo / Térreo", "departamento": "Dep. Tecnologia Sup.", "nome": "--T.I Geral", "ramal": "2325"},
    {"andar": "SubSolo / Térreo", "departamento": "Dep. Logística", "nome": "Felipe Benevides", "ramal": "2030"},
    {"andar": "SubSolo / Térreo", "departamento": "Dep. Logística", "nome": "Rogerio Nunes", "ramal": "2031"},
    {"andar": "SubSolo / Térreo", "departamento": "Dep. Logística", "nome": "Luis Figueiredo", "ramal": "2032"},
    {"andar": "SubSolo / Térreo", "departamento": "Dep. Logística", "nome": "Eron Medeiros", "ramal": "2033"},
    {"andar": "SubSolo / Térreo", "departamento": "Dep. Logística", "nome": "Feran Santos", "ramal": "2036"},
    {"andar": "1ª Andar", "departamento": "Diretoria Adm. e Fin.", "nome": "Cristiene Travassos", "ramal": "2210"},
    {"andar": "1ª Andar", "departamento": "Diretoria Operacional", "nome": "Stefanya", "ramal": "2040"},
    {"andar": "2ª Andar", "departamento": "Dep. Pessoal", "nome": "Simone", "ramal": "2260"},
    {"andar": "2ª Andar", "departamento": "Dep. Pessoal", "nome": "Adriana Mendes", "ramal": "2269"},
    {"andar": "2ª Andar", "departamento": "Dep. Pessoal", "nome": "Cassia Santos", "ramal": "2261"},
    {"andar": "2ª Andar", "departamento": "Dep. Pessoal", "nome": "Gleiton Montalvao", "ramal": "2272"},
    {"andar": "2ª Andar", "departamento": "Dep. Pessoal", "nome": "Lorena Braga", "ramal": "2264"},
    {"andar": "2ª Andar", "departamento": "Dep. Pessoal", "nome": "Thais Sena", "ramal": "2277"},
    {"andar": "2ª Andar", "departamento": "Dep. Pessoal", "nome": "Creiciane Araujo", "ramal": "2265"},
    {"andar": "2ª Andar", "departamento": "Dep. Pessoal", "nome": "Gustavo Prado", "ramal": "2275"},
    {"andar": "2ª Andar", "departamento": "Dep. Pessoal", "nome": "Wandherson", "ramal": "2266"},
    {"andar": "2ª Andar", "departamento": "Dep. Pessoal", "nome": "--SESMT", "ramal": "2267"},
    {"andar": "2ª Andar", "departamento": "Dep. Juridico", "nome": "Marcelo Silva", "ramal": "2243"},
    {"andar": "2ª Andar", "departamento": "Dep. Juridico", "nome": "Fred Barros", "ramal": "2241"},
    {"andar": "2ª Andar", "departamento": "Dep. Juridico", "nome": "Irinalva Barbosa", "ramal": "2242"},
    {"andar": "2ª Andar", "departamento": "Dep. Juridico", "nome": "Caroline Silva", "ramal": "2244"},
    {"andar": "2ª Andar", "departamento": "Dep. Juridico", "nome": "Guilherme Terto", "ramal": "2246"},
    {"andar": "2ª Andar", "departamento": "Dep. Juridico", "nome": "--Geral Juridica", "ramal": "2220"},
    {"andar": "2ª Andar", "departamento": "Dep. Comercial Pub/Pri", "nome": "Denilma Bomfim", "ramal": "2251"},
    {"andar": "2ª Andar", "departamento": "Dep. Comercial Pub/Pri", "nome": "Joao Brito", "ramal": "2331"},
    {"andar": "2ª Andar", "departamento": "Dep. Comercial Pub/Pri", "nome": "Breno Esteves", "ramal": "2294"},
    {"andar": "2ª Andar", "departamento": "Dep. Comercial Pub/Pri", "nome": "Paulo Medeiros", "ramal": "2293"},
    {"andar": "2ª Andar", "departamento": "Dep. Comercial Pub/Pri", "nome": "Nathalia Silva", "ramal": "2053"},
    {"andar": "2ª Andar", "departamento": "Dep. Comercial Pub/Pri", "nome": "Regislane Trindade", "ramal": "2252"},
    {"andar": "2ª Andar", "departamento": "Dep. Comercial Pub/Pri", "nome": "Anna Morais", "ramal": "2054"},
    {"andar": "2ª Andar", "departamento": "Dep. Comercial Pub/Pri", "nome": "Maria Guimaraes", "ramal": "2332"},
    {"andar": "2ª Andar", "departamento": "Dep. Comercial Pub/Pri", "nome": "Adrya Alves", "ramal": "2336"},
    {"andar": "2ª Andar", "departamento": "Dep. Comercial Pub/Pri", "nome": "Leandra Weber", "ramal": "2295"},
    {"andar": "2ª Andar", "departamento": "Dep. Financeiro", "nome": "Clodoaldo Valerio", "ramal": "2221"},
    {"andar": "2ª Andar", "departamento": "Dep. Financeiro", "nome": "Valeria Moreira", "ramal": "2212"},
    {"andar": "2ª Andar", "departamento": "Dep. Financeiro", "nome": "Ana Karine", "ramal": "2217"},
    {"andar": "2ª Andar", "departamento": "Dep. Financeiro", "nome": "Ana Micaela", "ramal": "2219"},
    {"andar": "2ª Andar", "departamento": "Dep. Financeiro", "nome": "Daiane Silva", "ramal": "2216"},
    {"andar": "2ª Andar", "departamento": "Dep. Financeiro", "nome": "Raquel Santos", "ramal": "2218"},
    {"andar": "2ª Andar", "departamento": "Dep. Financeiro", "nome": "Grasiele Turial", "ramal": "2222"},
    {"andar": "2ª Andar", "departamento": "Dep. Financeiro", "nome": "Maria Santos", "ramal": "2215"},
    {"andar": "2ª Andar", "departamento": "Dep. Financeiro", "nome": "Julia Santos", "ramal": "2211"},
    {"andar": "2ª Andar", "departamento": "Dep. Financeiro", "nome": "Beatriz Sampaio", "ramal": "2214"},
    {"andar": "2ª Andar", "departamento": "Dep. Gente e Gestão", "nome": "Laiciane Rosa", "ramal": "2050"},
    {"andar": "2ª Andar", "departamento": "Dep. Gente e Gestão", "nome": "Ana Rocha", "ramal": "2053"},
    {"andar": "2ª Andar", "departamento": "Dep. Gente e Gestão", "nome": "Angelica", "ramal": "2051"},
    {"andar": "2ª Andar", "departamento": "Dep. Gente e Gestão", "nome": "Mirla Silva", "ramal": "2057"},
    {"andar": "2ª Andar", "departamento": "Dep. Gente e Gestão", "nome": "Williani Carvalho", "ramal": "2055"},
    {"andar": "2ª Andar", "departamento": "Dep. Gente e Gestão", "nome": "Mariana Gonçalves", "ramal": "2052"},
    {"andar": "2ª Andar", "departamento": "Dep. Gente e Gestão", "nome": "Rafaela Brito", "ramal": "2054"},
    {"andar": "3ª Andar", "departamento": "Presidência / Diretoria", "nome": "Regina Frota De Negreiros", "ramal": "2310"},
    {"andar": "3ª Andar", "departamento": "Presidência / Diretoria", "nome": "Francisca Ferreira", "ramal": "2311"},
    {"andar": "3ª Andar", "departamento": "Diretoria Inovação e Processos", "nome": "Glenda Negreiros", "ramal": "2330"},
    {"andar": "3ª Andar", "departamento": "Dep. Qualidade e Processos", "nome": "Luana", "ramal": "2337"},
    {"andar": "3ª Andar", "departamento": "Dep. Qualidade e Processos", "nome": "Meirielen", "ramal": "2337"},
    {"andar": "3ª Andar", "departamento": "Dep. Qualidade e Processos", "nome": "Moises", "ramal": "2333"},
    {"andar": "3ª Andar", "departamento": "Dep. Qualidade e Processos", "nome": "Danilo", "ramal": "2334"}
]


def seed_ramais():
    """Popula a tabela de ramais sem duplicar registros existentes."""
    with app.app_context():
        # Garante que a tabela existe (idempotente)
        db.create_all()

        inseridos = 0
        ignorados = 0
        erros = 0

        for dados in RAMAIS_DATA:
            try:
                # Verifica se já existe (por nome + departamento + ramal) para evitar duplicatas
                existente = Ramal.query.filter_by(
                    nome=dados['nome'],
                    departamento=dados['departamento'],
                    ramal=dados['ramal']
                ).first()

                if existente:
                    ignorados += 1
                    continue

                ramal = Ramal(
                    nome=dados['nome'],
                    departamento=dados['departamento'],
                    ramal=dados['ramal'],
                    andar=dados.get('andar')
                )
                db.session.add(ramal)
                inseridos += 1

            except Exception as e:
                erros += 1
                print(f"[ERRO] Falha ao inserir {dados.get('nome', '?')}: {e}")

        db.session.commit()

        total = Ramal.query.count()

        print("\n" + "=" * 60)
        print("  SEED DE RAMAIS BRASFORT - CONCLUÍDO")
        print("=" * 60)
        print(f"  Registros inseridos:   {inseridos}")
        print(f"  Registros ignorados:   {ignorados} (já existiam)")
        print(f"  Erros:                 {erros}")
        print(f"  Total na tabela:       {total}")
        print("=" * 60 + "\n")


if __name__ == '__main__':
    seed_ramais()
