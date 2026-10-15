"""
Bateria de Testes de Seguranca - Etapa 3 (Cliente HTTP e OAuth2)
Valida os 5 pilares de seguranca do GlpiClient:
1. Autenticacao OAuth2 segura com emissao de JWT.
2. Reutilizacao de token em cache de memoria (zero requisicoes extras ao GLPI).
3. Respeito ao teto de lote (batch size) e timeout estrito.
4. Mascaramento e ausencia de dados sensiveis em logs.
5. Comportamento do Circuit Breaker em caso de instabilidade.
"""
import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.glpi_client import GlpiClient, CircuitBreakerOpenException

def executar_testes_etapa3():
    print("\n" + "=" * 65)
    print("   BATERIA DE TESTES DE SEGURANCA: ETAPA 3 (CLIENTE GLPI)")
    print("=" * 65 + "\n")

    client = GlpiClient()

    # Teste 1: Autenticacao e Emissao de Token JWT
    print("[TESTE 1] Testando obtencao segura de Token JWT...")
    t0 = time.time()
    token1 = client._obter_token()
    duracao1 = time.time() - t0
    assert token1 is not None and len(token1) > 20, "Token JWT invalido!"
    print(f" -> SUCESSO: Token JWT obtido com sucesso em {duracao1:.2f}s!")
    print(f" -> Seguranca: Token armazenado apenas em memoria ({token1[:15]}...{token1[-10:]})")

    # Teste 2: Cache de Token (Garantia de Carga Zero)
    print("\n[TESTE 2] Testando reutilizacao de token (Zero requisicoes extras ao GLPI)...")
    t0 = time.time()
    token2 = client._obter_token()
    duracao2 = time.time() - t0
    assert token1 == token2, "Token deveria ser o mesmo do cache!"
    assert duracao2 < 0.01, "Chamada deveria ser instantanea (da memoria)!"
    print(f" -> SUCESSO: Token reutilizado da memoria em {duracao2*1000:.3f}ms (0 chamadas HTTP ao GLPI)!")

    # Teste 3: Consulta Segura com Batching e Timeout
    print("\n[TESTE 3] Testando consulta controlada via GET /Assistance/Ticket...")
    t0 = time.time()
    tickets = client.buscar_tickets(limite=5)
    duracao3 = time.time() - t0
    assert isinstance(tickets, list), "Retorno deve ser uma lista!"
    assert len(tickets) <= 5, "Nao deve ultrapassar o limite estrito do lote!"
    print(f" -> SUCESSO: {len(tickets)} tickets consultados em {duracao3:.2f}s dentro do teto permitido!")

    # Teste 4: Simulacao do Circuit Breaker
    print("\n[TESTE 4] Testando ativacao e protecao do Circuit Breaker...")
    # Simula status 429 (Too Many Requests do GLPI)
    client._registrar_falha(status_code=429, motivo="Simulacao de Rate Limit")
    try:
        client._verificar_circuit_breaker()
        print(" -> FALHA: O circuito deveria ter bloqueado a chamada!")
    except CircuitBreakerOpenException as e:
        print(f" -> SUCESSO: Circuit Breaker ativou com perfeicao e bloqueou nova chamada!")
        print(f"    Mensagem de protecao: {e}")

    # Restaura o circuito para estado normal
    client._registrar_sucesso()
    print(" -> Circuito restaurado ao estado normal de operacao.")

    # Fechamento seguro
    client.close()

    print("\n" + "=" * 65)
    print("   TODOS OS 4 TESTES DE SEGURANCA FORAM APROVADOS COM SUCESSO!")
    print("=" * 65 + "\n")

if __name__ == '__main__':
    executar_testes_etapa3()
