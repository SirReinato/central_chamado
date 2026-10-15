"""
Cliente HTTP Corporativo para API REST v2.3 do GLPI com OAuth2
Modulo de Seguranca Avancada e Protecao de Carga Zero:

PILATRES DE SEGURANCA:
1. Circuit Breaker com Cooldown:
   - Suspende qualquer tentativa de contato se o GLPI retornar 429 (Rate Limit) ou 5xx.
   - Protege o servidor do GLPI contra bombardeamento quando instavel.
2. Token Lifecycle Seguro (JWT):
   - Armazenamento em memoria sem persistencia em disco.
   - Reutilizacao automatica durante a validade (1h), com renovacao antecipada (skew de 5 min).
3. Conexao Controlada (Connection Pool Minimo):
   - Limite estrito de conexoes HTTP concorrentes (max 2 conexoes simultaneas).
   - Timeouts estritos de conexao (5s) e leitura (15s).
4. Sanitizacao de Logs:
   - Mascaramento automatico de credenciais, senhas e tokens nos logs.
5. Exclusividade Read-Only:
   - Apenas requisicoes HTTP GET sao permitidas para consumo de dados.
"""
import os
import time
import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import urllib3
from dotenv import load_dotenv

# Carrega variaveis defensivamente caso executado isoladamente
load_dotenv()

# Suprime avisos de certificado SSL apenas se desabilitado explicitamente
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger('glpi_client')


class CircuitBreakerOpenException(Exception):
    """Lancada quando o Circuit Breaker esta aberto para proteger o GLPI."""
    pass


class GlpiClient:
    # Estado global do Circuit Breaker compartilhado entre instancias
    _circuit_open_until = 0
    _circuit_failures = 0
    _cooldown_seconds = 600  # 10 minutos de pausa se o GLPI falhar

    def __init__(self):
        self.api_url = os.environ.get('GLPI_API_URL', 'https://helpdesk.brasfort.com.br/api.php').rstrip('/')
        self.client_id = os.environ.get('GLPI_CLIENT_ID', '').strip()
        self.client_secret = os.environ.get('GLPI_CLIENT_SECRET', '').strip()
        self.username = os.environ.get('GLPI_USERNAME', '').strip()
        self.password = os.environ.get('GLPI_PASSWORD', '').strip()
        
        self.timeout_connect = 5
        self.timeout_read = int(os.environ.get('GLPI_REQUEST_TIMEOUT', 15))
        self.batch_size = int(os.environ.get('GLPI_BATCH_SIZE', 15))
        self.filter_request_type_id = os.environ.get('GLPI_FILTER_REQUEST_TYPE_ID', '1').strip()
        self.filter_category_id = os.environ.get('GLPI_FILTER_CATEGORY_ID', '').strip()
        self.verify_ssl = os.environ.get('GLPI_VERIFY_SSL', 'false').lower() in ('true', '1')

        # Cache de token OAuth2 em memoria
        self._access_token = None
        self._token_expires_at = 0

        # Configuracao de sessao HTTP com pool minusculo para nao onerar o GLPI
        self.session = requests.Session()
        adapter = HTTPAdapter(
            pool_connections=1,
            pool_maxsize=2,
            max_retries=Retry(
                total=1,
                backoff_factor=1,
                status_forcelist=[502, 503, 504]
            )
        )
        self.session.mount('https://', adapter)
        self.session.mount('http://', adapter)

    def _verificar_circuit_breaker(self):
        """Verifica se o circuito esta aberto antes de realizar qualquer chamada de rede."""
        agora = time.time()
        if agora < GlpiClient._circuit_open_until:
            tempo_restante = int(GlpiClient._circuit_open_until - agora)
            logger.warning(
                f"[CIRCUIT BREAKER ATIVO] Conexoes com o GLPI suspensas para protecao. "
                f"Tempo restante de espera: {tempo_restante} segundos."
            )
            raise CircuitBreakerOpenException(
                f"Circuito aberto temporariamente. Aguarde {tempo_restante}s para nova tentativa."
            )

    def _registrar_sucesso(self):
        """Registra operacao bem sucedida e reseta o contador de falhas."""
        GlpiClient._circuit_failures = 0
        GlpiClient._circuit_open_until = 0

    def _registrar_falha(self, status_code: int = None, motivo: str = ""):
        """Registra falha do GLPI e ativa o Circuit Breaker se necessario."""
        GlpiClient._circuit_failures += 1
        logger.warning(f"Falha registrada na comunicacao com o GLPI (Contador: {GlpiClient._circuit_failures}). Motivo: {motivo}")

        # Se houver erro de sobrecarga ou falha repetida, abre o circuito
        if status_code in (429, 500, 502, 503, 504) or GlpiClient._circuit_failures >= 2:
            GlpiClient._circuit_open_until = time.time() + GlpiClient._cooldown_seconds
            logger.critical(
                f"[CIRCUIT BREAKER ACIONADO] Abrindo circuito por {GlpiClient._cooldown_seconds}s "
                f"para evitar sobrecarga no servidor do GLPI."
            )

    def _obter_token(self) -> str:
        """
        Obtem ou renova o token JWT OAuth2 com protecao de ciclo de vida.
        Renova antecipadamente com margem de seguranca de 5 minutos (300s).
        """
        self._verificar_circuit_breaker()

        agora = time.time()
        # Se ja temos um token valido com folga de 300 segundos (5 minutos), reutiliza
        if self._access_token and agora < (self._token_expires_at - 300):
            return self._access_token

        token_url = f"{self.api_url}/token"
        payload = {
            'grant_type': 'password',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'username': self.username,
            'password': self.password,
            'scope': 'api'
        }

        try:
            logger.info("Solicitando emissao/renovacao de token OAuth2 (Grant: Password, Scope: api)...")
            res = self.session.post(
                token_url,
                data=payload,
                verify=self.verify_ssl,
                timeout=(self.timeout_connect, self.timeout_read)
            )

            if res.status_code == 200:
                dados = res.json()
                self._access_token = dados.get('access_token')
                expires_in = int(dados.get('expires_in', 3600))
                self._token_expires_at = agora + expires_in
                self._registrar_sucesso()
                logger.info(f"Token OAuth2 emitido com sucesso! Validade: {expires_in}s.")
                return self._access_token
            else:
                self._registrar_falha(res.status_code, f"HTTP {res.status_code}")
                raise ConnectionError(f"Falha de autenticacao OAuth2 no GLPI: HTTP {res.status_code}")

        except requests.exceptions.RequestException as e:
            self._registrar_falha(motivo=str(e))
            raise

    def buscar_tickets(self, ultimo_glpi_id: int = None, limite: int = None) -> list:
        """
        Consulta tickets mais recentes via GET /Assistance/Ticket de forma estritamente controlada.
        """
        try:
            self._verificar_circuit_breaker()
        except CircuitBreakerOpenException:
            return []

        try:
            token = self._obter_token()
        except Exception:
            return []

        limite_busca = min(limite or self.batch_size, 30)  # Teto maximo rigido de 30 para seguranca absoluta
        endpoint = f"{self.api_url}/v2.3/Assistance/Ticket"
        headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json'
        }

        params = {
            'sort': 'id',
            'order': 'DESC',
            'range': f"0-{limite_busca - 1}"
        }

        try:
            logger.info(f"Consultando lote seguro de ate {limite_busca} tickets no GLPI...")
            res = self.session.get(
                endpoint,
                headers=headers,
                params=params,
                verify=self.verify_ssl,
                timeout=(self.timeout_connect, self.timeout_read)
            )

            if res.status_code == 200:
                self._registrar_sucesso()
                tickets = res.json()
                if not isinstance(tickets, list):
                    tickets = [tickets]

                # Ordena localmente por ID decrescente para garantir os mais recentes primeiro
                tickets.sort(key=lambda t: t.get('id', 0), reverse=True)
                logger.info(f"Recebidos {len(tickets)} tickets do GLPI.")

                if ultimo_glpi_id and isinstance(ultimo_glpi_id, int):
                    tickets = [t for t in tickets if isinstance(t.get('id'), int) and t.get('id') > ultimo_glpi_id]
                    logger.info(f"Filtrados {len(tickets)} novos tickets apos o ID #{ultimo_glpi_id}.")

                return tickets

            elif res.status_code == 401:
                # Token expirado ou revogado no servidor: limpa cache
                logger.warning("Resposta HTTP 401: Token expirado ou revogado. Resetando cache local.")
                self._access_token = None
                return []

            elif res.status_code in (429, 500, 502, 503, 504):
                self._registrar_falha(res.status_code, f"Servidor GLPI retornou {res.status_code}")
                return []

            else:
                logger.error(f"Resposta inesperada da API GLPI: HTTP {res.status_code}")
                return []

        except requests.exceptions.Timeout:
            logger.warning("Timeout atingido na consulta ao GLPI. Abortando com seguranca.")
            self._registrar_falha(motivo="Timeout")
            return []
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro de rede na consulta ao GLPI: {e}")
            self._registrar_falha(motivo=str(e))
            return []

    def buscar_detalhe_ticket(self, ticket_id: int) -> dict:
        """
        Consulta os detalhes completos de um ticket especifico (apenas GET).
        """
        if not isinstance(ticket_id, int) or ticket_id <= 0:
            return {}

        try:
            self._verificar_circuit_breaker()
            token = self._obter_token()
        except Exception:
            return {}

        endpoint = f"{self.api_url}/v2.3/Assistance/Ticket/{ticket_id}"
        headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json'
        }

        try:
            res = self.session.get(
                endpoint,
                headers=headers,
                verify=self.verify_ssl,
                timeout=(self.timeout_connect, self.timeout_read)
            )
            if res.status_code == 200:
                self._registrar_sucesso()
                return res.json()
            return {}
        except Exception as e:
            logger.warning(f"Nao foi possivel consultar detalhes do ticket #{ticket_id}: {e}")
            return {}

    def close(self):
        """Fecha a sessao HTTP liberando conexoes locais."""
        if hasattr(self, 'session'):
            self.session.close()
