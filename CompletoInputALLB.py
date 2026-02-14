import requests
import json
import urllib3
import base64
import asyncio
import concurrent.futures
import signal
import time
import threading
from datetime import datetime
import logging
import os

# Desabilitar avisos SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Pool de conexões HTTP global
def get_http_session():
    session = requests.Session()
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[502, 503, 504])
    adapter = HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=retries)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

http_session = get_http_session()

# Logging estruturado
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)
logger = logging.getLogger("f5monitor")

class TokenManager:
    def __init__(self, f5_monitor):
        self.f5_monitor = f5_monitor
        self.current_token = None
        self.backup_token = None
        self.current_expiry = None
        self.backup_expiry = None
        self.lock = threading.Lock()
        self.running = True
        self.background_task = None
        
    def start(self):
        """Inicia o gerenciamento de tokens em background"""
        self.background_task = threading.Thread(target=self._token_manager_loop, daemon=True)
        self.background_task.start()
        
    def stop(self):
        """Para o gerenciamento de tokens"""
        self.running = False
        if self.background_task:
            self.background_task.join(timeout=1)
            
    def _token_manager_loop(self):
        """Loop em background para gerenciar tokens"""
        while self.running:
            try:
                # Tenta obter novo token se necessário
                self._refresh_tokens()
                # Espera 5 minutos antes da próxima verificação
                time.sleep(300)
            except Exception as e:
                logger.error(f"Erro no gerenciamento de token: {str(e)}")
                time.sleep(60)  # Espera 1 minuto em caso de erro
                
    def _refresh_tokens(self):
        """Atualiza os tokens quando necessário"""
        with self.lock:
            current_time = time.time()
            
            # Se não há token atual ou está próximo de expirar
            if not self.current_token or (self.current_expiry and current_time + 600 >= self.current_expiry):
                if self.backup_token and self.backup_expiry and current_time + 300 < self.backup_expiry:
                    # Usa o token de backup se estiver válido
                    self.current_token = self.backup_token
                    self.current_expiry = self.backup_expiry
                    self.backup_token = None
                    self.backup_expiry = None
                    
                # Obtém novo token de backup
                self._get_new_backup_token()
                
    def _get_new_backup_token(self):
        """Obtém um novo token de backup"""
        try:
            auth_url = f"{self.f5_monitor.base_url}/mgmt/shared/authn/login"
            payload = {
                "username": self.f5_monitor.username,
                "password": self.f5_monitor.password,
                "loginProviderName": "tmos"
            }

            # Definir timeout maior para autenticação (atualizado para 300 segundos)
            response = http_session.post(
                auth_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                verify=False,
                timeout=300
            )

            if response.status_code == 200:
                self.backup_token = response.json()['token']['token']
                self.backup_expiry = time.time() + self.f5_monitor.token_refresh_interval

        except requests.exceptions.ReadTimeout:
            logger.error(f"Timeout ao tentar obter token de backup em {self.f5_monitor.name} ({self.f5_monitor.base_url})")
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Erro de conexão ao obter token de backup em {self.f5_monitor.name}: {str(e)}")
        except Exception as e:
            logger.error(f"Erro ao obter token de backup: {str(e)}")
            
    def get_valid_token(self):
        """Retorna um token válido"""
        with self.lock:
            if self.current_token and self.current_expiry and time.time() < self.current_expiry:
                return self.current_token
            if self.backup_token and self.backup_expiry and time.time() < self.backup_expiry:
                self.current_token = self.backup_token
                self.current_expiry = self.backup_expiry
                self.backup_token = None
                self.backup_expiry = None
                return self.current_token
        return None

class F5Monitor:
    def __init__(self, base_url, name):
        self.base_url = base_url
        self.name = name  # Nome do balanceador
        self.username = None  # Removida credencial fixa
        self.password = None  # Removida credencial fixa
        self.token = None
        self.token_expiry = None
        self.token_refresh_interval = 1200
        self.headers = {
            'Content-Type': 'application/json',
        }
        self.token_manager = None
        # Controle de tentativas de reautenticação para evitar múltiplas tentativas
        self.reauth_attempts = 0

    def set_credentials(self, username, password):
        """Define as credenciais do usuário e autentica imediatamente"""
        self.username = username
        self.password = password
        self.token_manager = TokenManager(self)
        self.get_auth_token()  # Autentica e obtém o token inicial
        self.start_token_manager()  # Inicia auto-gerenciamento do token

    def is_authenticated(self):
        """Verifica se há credenciais definidas e token válido"""
        return bool(self.username and self.password and self.token)

    def start_token_manager(self):
        """Inicia o gerenciamento de tokens"""
        self.token_manager.start()
        
    def stop_token_manager(self):
        """Para o gerenciamento de tokens"""
        self.token_manager.stop()
        
    def clear_auth_tokens(self):
        """Limpa tokens antigos do usuário"""
        try:
            url = f"{self.base_url}/mgmt/shared/authz/tokens"
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Basic {base64.b64encode(f"{self.username}:{self.password}".encode()).decode()}'
            }
            response = http_session.delete(url, headers=headers, verify=False)
            if response.status_code in [200, 201, 204]:
                logger.info(f"Tokens antigos limpos com sucesso no {self.name}")
                return True
            return False
        except Exception as e:
            logger.error(f"Erro ao limpar tokens: {str(e)}")
            return False

    def check_and_kill_active_sessions(self):
        """Verifica e derruba sessões ativas do usuário"""
        try:
            url = f"{self.base_url}/mgmt/shared/authz/tokens"
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Basic {base64.b64encode(f"{self.username}:{self.password}".encode()).decode()}'
            }
            response = http_session.get(url, headers=headers, verify=False)
            if response.status_code == 200:
                tokens = response.json().get('items', [])
                for token in tokens:
                    if token.get('userName') == self.username:
                        # Deletar token ativo
                        token_id = token.get('token')
                        delete_url = f"{url}/{token_id}"
                        del_response = http_session.delete(delete_url, headers=headers, verify=False)
                        if del_response.status_code in [200, 201, 204]:
                            logger.info(f"Sessão antiga removida no {self.name}")
            return True
        except Exception as e:
            logger.error(f"Erro ao verificar sessões: {str(e)}")
            return False

    def check_token_expiry(self):
        """Verifica se o token precisa ser renovado"""
        if not self.token or not self.token_expiry:
            return True
        # Renova quando faltar 5 minutos para expirar
        return time.time() + 300 >= self.token_expiry

    def ensure_valid_token(self):
        """Garante que há um token válido disponível"""
        token = self.token_manager.get_valid_token()
        if token:
            self.token = token
            self.headers['X-F5-Auth-Token'] = token
            return True
        # NÃO chama get_auth_token novamente!
        logger.error(f"Token expirado ou inválido para {self.name}. Reinicie o programa para nova autenticação.")
        return False

    def get_auth_token(self):
        """Obter token de autenticação"""
        try:
            logger.info(f"Tentando autenticar no balanceador {self.name}...")

            # Verificar e derrubar sessões ativas antes de tentar autenticar
            self.check_and_kill_active_sessions()

            # Limpar tokens antigos
            self.clear_auth_tokens()

            auth_url = f"{self.base_url}/mgmt/shared/authn/login"

            payload = {
                "username": self.username,
                "password": self.password,
                "loginProviderName": "tmos"
            }

            response = http_session.post(
                auth_url,
                json=payload,
                headers=self.headers,
                verify=False,
                timeout=300
            )

            if response.status_code == 200:
                self.token = response.json()['token']['token']
                self.token_expiry = time.time() + self.token_refresh_interval
                self.headers['X-F5-Auth-Token'] = self.token
                # CORREÇÃO: Salva também no TokenManager!
                if self.token_manager:
                    self.token_manager.current_token = self.token
                    self.token_manager.current_expiry = self.token_expiry
                logger.info(f"Autenticação bem sucedida no {self.name}")
                return True

            logger.error(f"Falha na autenticação do {self.name}. Status code: {response.status_code}")
            logger.error(f"Resposta: {response.text}")
            return False

        except Exception as e:
            logger.error(f"Erro na autenticação do {self.name}: {str(e)}")
            return False

    def get_node_status(self, node_name):
        try:
            if not self.ensure_valid_token():
                logger.error(f"Falha na renovação do token para {self.name}")
                return None
                
            # Obter status do node
            url = f"{self.base_url}/mgmt/tm/ltm/node/{node_name}/stats"
            
            response = http_session.get(
                url,
                headers=self.headers,
                verify=False
            )
            
            if response.status_code == 200:
                data = response.json()
                stats = data['entries'][f'https://localhost/mgmt/tm/ltm/node/~Common~{node_name}/stats']['nestedStats']['entries']
                enabled_state = stats['status.enabledState']['description']
                # Obter conexões ativas
                current_connections = stats.get('serverside.curConns', {}).get('value', 0)
                
                return {
                    "servidor": node_name,
                    "status": enabled_state,
                    "found": True,
                    "connections": current_connections  # Adicionado número de conexões
                }
            elif response.status_code == 404:
                logger.warning(f"Node '{node_name}' não encontrado neste balanceador")
                return {"servidor": node_name, "status": "não encontrado", "found": False, "connections": 0}
            else:
                logger.error(f"Erro ao consultar node: {response.status_code}")
                if 'message' in response.json():
                    logger.error(f"Detalhes: {response.json()['message']}")
                return None
                
        except Exception as e:
            logger.error(f"Erro na requisição: {str(e)}")
            return None

    def force_offline_node(self, node_name):
        try:
            # Verifica e renova o token se necessário
            if not self.ensure_valid_token():
                logger.error(f"Falha na renovação do token para {self.name}")
                return None
                
            url = f"{self.base_url}/mgmt/tm/ltm/node/~Common~{node_name}"
            
            response = http_session.patch(
                url,
                json={"session": "user-disabled", "state": "user-down"},
                headers=self.headers,
                verify=False
            )
            
            if response.status_code in [200, 201]:
                return {"servidor": node_name, "status": "disabled", "found": True}
            elif response.status_code == 404:
                return {"servidor": node_name, "status": "não encontrado", "found": False}
            else:
                logger.error(f"Erro: {response.status_code}")
                logger.error(f"Response: {response.text}")
                return {"servidor": node_name, "status": "erro", "found": False}
                
        except Exception as e:
            logger.error(f"Erro ao forçar offline: {str(e)}")
            return {"servidor": node_name, "status": "erro", "found": False}

    def enable_node(self, node_name):
        try:
            # Verifica e renova o token se necessário
            if not self.ensure_valid_token():
                logger.error(f"Falha na renovação do token para {self.name}")
                return None
                
            url = f"{self.base_url}/mgmt/tm/ltm/node/~Common~{node_name}"
            
            response = http_session.patch(
                url,
                json={"session": "user-enabled", "state": "user-up"},
                headers=self.headers,
                verify=False
            )
            
            if response.status_code in [200, 201]:
                return {"servidor": node_name, "status": "enabled", "found": True}
            elif response.status_code == 404:
                return {"servidor": node_name, "status": "não encontrado", "found": False}
            else:
                logger.error(f"Erro: {response.status_code}")
                logger.error(f"Response: {response.text}")
                return {"servidor": node_name, "status": "erro", "found": False}
                
        except Exception as e:
            logger.error(f"Erro ao habilitar node: {str(e)}")
            return {"servidor": node_name, "status": "erro", "found": False}

    def get_pool_members(self, pool_name):
        try:
            # Verifica e renova o token se necessário
            if not self.ensure_valid_token():
                logger.error(f"Falha na renovação do token para {self.name}")
                return None
                
            url = f"{self.base_url}/mgmt/tm/ltm/pool/~Common~{pool_name}/members"
            response = http_session.get(url, headers=self.headers, verify=False)
            
            if response.status_code == 200:
                data = response.json()
                members = []
                
                for member in data.get('items', []):
                    try:
                        name = member['name']
                        address = member['address']
                        port = name.split(':')[1] if ':' in name else 'N/A'
                        
                        status_url = f"{self.base_url}/mgmt/tm/ltm/pool/~Common~{pool_name}/members/~Common~{name}/stats"
                        status_response = http_session.get(status_url, headers=self.headers, verify=False)
                        
                        if status_response.status_code == 200:
                            status_data = status_response.json()
                            stats = status_data['entries'][f'https://localhost/mgmt/tm/ltm/pool/~Common~{pool_name}/members/~Common~{name}/stats']['nestedStats']['entries']
                            availability = stats['status.availabilityState']['description']
                            enabled_state = stats['status.enabledState']['description']
                            
                            # Padronizar estados para o frontend
                            state = 'up' if availability.lower() == 'available' else 'down'
                            status = 'enabled' if enabled_state.lower() == 'enabled' else 'disabled'
                            # Obter conexões ativas do membro, se disponível
                            current_connections = stats.get('serverside.curConns', {}).get('value', 0)

                            members.append({
                                "name": name,
                                "state": state,
                                "status": status,
                                "address": address,
                                "port": port,
                                "connections": current_connections
                            })
                            
                    except KeyError as e:
                        logger.error(f"Erro ao processar membro do pool: {str(e)}")
                        continue
                
                return [{
                    "balancer": self.name,
                    "members": members
                }]
                
            return None
                
        except Exception as e:
            logger.error(f"Erro ao listar membros do pool: {str(e)}")
            return None

    def get_available_pools(self):
        try:
            # Verifica e renova o token se necessário
            if not self.ensure_valid_token():
                logger.error(f"Falha na renovação do token para {self.name}")
                return None
                
            url = f"{self.base_url}/mgmt/tm/ltm/pool"
            
            response = http_session.get(
                url,
                headers=self.headers,
                verify=False
            )
            
            if response.status_code == 200:
                data = response.json()
                pools = []
                for pool in data.get('items', []):
                    name = pool['name']
                    # Retorna apenas pools que começam com 'pool-'
                    if name.startswith('pool-'):
                        pools.append(name)
                return pools
            else:
                logger.error(f"Erro ao listar pools: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Erro ao listar pools: {str(e)}")
            return None

    def log_action(self, action, details):
        """Registra ações com timestamp e nome do balanceador"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"[{timestamp}] [{self.name}] {action}: {details}")

    def logout(self):
        """Faz logout da API"""
        try:
            if self.token:
                url = f"{self.base_url}/mgmt/shared/authz/tokens/{self.token}"
                response = http_session.delete(url, headers=self.headers, verify=False)
                if response.status_code in [200, 201, 204]:
                    logger.info(f"Logout realizado com sucesso no {self.name}")
                self.token = None
                self.headers.pop('X-F5-Auth-Token', None)
        except Exception as e:
            logger.error(f"Erro ao fazer logout no {self.name}: {str(e)}")

    def force_offline_pool_member(self, pool_name, member_name):
        """Força um membro do pool para offline"""
        try:
            if not self.ensure_valid_token():
                logger.error(f"Falha na renovação do token para {self.name}")
                return None
                
            url = f"{self.base_url}/mgmt/tm/ltm/pool/~Common~{pool_name}/members/~Common~{member_name}"
            
            response = http_session.patch(
                url,
                json={"session": "user-disabled", "state": "user-down"},
                headers=self.headers,
                verify=False
            )
            
            if response.status_code in [200, 201]:
                return {
                    "name": member_name,
                    "state": "down",
                    "status": "disabled",
                    "message": "Successfully disabled"
                }
            elif response.status_code == 404:
                logger.warning(f"Membro {member_name} não encontrado no pool {pool_name}")
                return None
            else:
                logger.error(f"Erro: {response.status_code}")
                logger.error(f"Response: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Erro ao forçar offline membro do pool: {str(e)}")
            return None

    def enable_pool_member(self, pool_name, member_name):
        """Habilita um membro do pool"""
        try:
            if not self.ensure_valid_token():
                logger.error(f"Falha na renovação do token para {self.name}")
                return None
                
            url = f"{self.base_url}/mgmt/tm/ltm/pool/~Common~{pool_name}/members/~Common~{member_name}"
            
            response = http_session.patch(
                url,
                json={"session": "user-enabled", "state": "user-up"},
                headers=self.headers,
                verify=False
            )
            
            if response.status_code in [200, 201]:
                return {
                    "name": member_name,
                    "state": "up",
                    "status": "enabled",
                    "message": "Successfully enabled"
                }
            elif response.status_code == 404:
                logger.warning(f"Membro {member_name} não encontrado no pool {pool_name}")
                return None
            else:
                logger.error(f"Erro: {response.status_code}")
                logger.error(f"Response: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Erro ao habilitar membro do pool: {str(e)}")
            return None

class F5Manager:
    def __init__(self):
        self.balancers = [
            F5Monitor("https://bigip01-cyoi.sicoob.com.br", "BIGIP-CYOI"),
            F5Monitor("https://bigip01-ccs.sicoob.com.br", "BIGPI02-CCS"),
            F5Monitor("https://bigp2007.sicoob.com.br", "BIGP2007"),
            F5Monitor("https://bigp4007.sicoob.com.br", "BIGP4007"),
            F5Monitor("https://bigp2006.sicoob.com.br", "BIGP2006"),
            F5Monitor("https://bigp4006.sicoob.com.br", "BIGP4006")
        ]
        self.authenticated_balancers = []
        self.running = True
        self.max_workers = 10
        self.auth_timeout = 300
        signal.signal(signal.SIGINT, self.signal_handler)

    def auth_specific(self, names, username, password):
        """Tenta reautenticar uma lista específica de balanceadores (apenas uma tentativa por balancer).
        names: lista de nomes dos balanceadores a reautenticar
        username/password: credenciais para tentativa
        """
        print(f"Tentando reautenticar balanceadores: {', '.join(names)}")
        to_auth = [b for b in self.balancers if b.name in names]
        for balancer in to_auth:
            # Não tentar mais de uma vez
            if getattr(balancer, 'reauth_attempts', 0) >= 1:
                print(f"[{balancer.name}] Já tentou reautenticar anteriormente. Pulando.")
                continue
            balancer.reauth_attempts = getattr(balancer, 'reauth_attempts', 0) + 1
            try:
                balancer.set_credentials(username, password)
                # set_credentials já tenta obter token; verificar resultado
                if balancer.token:
                    if balancer not in self.authenticated_balancers:
                        balancer.start_token_manager()
                        self.authenticated_balancers.append(balancer)
                    print(f"[{balancer.name}] Reautenticação bem sucedida.")
                else:
                    print(f"[{balancer.name}] Falha na reautenticação.")
            except Exception as e:
                print(f"[{balancer.name}] Erro ao reautenticar: {e}")

    def signal_handler(self, signum, frame):
        print("\n\nEncerrando programa...")
        self.running = False
        self.cleanup()

    def cleanup(self):
        print("\nRealizando logout dos balanceadores...")
        for balancer in self.authenticated_balancers:
            balancer.stop_token_manager()
            balancer.logout()
        self.authenticated_balancers = []

    async def _auth_balancer(self, balancer):
        """Autentica um balanceador com timeout"""
        try:
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                # Executa a autenticação com timeout
                result = await asyncio.wait_for(
                    loop.run_in_executor(executor, balancer.get_auth_token),
                    timeout=self.auth_timeout
                )
                return balancer, result
        except asyncio.TimeoutError:
            logger.warning(f"Timeout na autenticação do {balancer.name}")
            return balancer, False
        except Exception as e:
            logger.error(f"Erro na autenticação do {balancer.name}: {str(e)}")
            return balancer, False

    async def authenticate_all(self):
        """Autentica todos os balanceadores e inicia gerenciamento de tokens"""
        print("\nIniciando autenticação em paralelo...")
        start_time = time.time()

        # Cria as tarefas de autenticação
        auth_tasks = [
            self._auth_balancer(balancer) 
            for balancer in self.balancers
        ]

        # Executa todas as autenticações em paralelo
        results = await asyncio.gather(*auth_tasks, return_exceptions=True)
        
        # Filtra balanceadores autenticados e inicia gerenciamento de tokens
        self.authenticated_balancers = []
        for balancer, success in results:
            if success and not isinstance(success, Exception):
                balancer.start_token_manager()
                self.authenticated_balancers.append(balancer)

        end_time = time.time()
        print(f"\n✅ Autenticação concluída em {end_time - start_time:.2f} segundos")
        print(f"✅ {len(self.authenticated_balancers)} de {len(self.balancers)} balanceadores autenticados")
        
        print("\nBalanceadores autenticados:")
        for balancer in self.authenticated_balancers:
            print(f"- {balancer.name}")

if __name__ == "__main__":
    # Remover menu_interativo, pois agora o backend.py faz o menu
    pass