import requests
import time
import logging
import os

# Garante que o diretório de log exista
if not os.path.exists('log'):
    os.makedirs('log')

# Configuração do Logger
logging.basicConfig(
    filename='log/restart_websphere.log',
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M',
    encoding='utf-8'
)

def _trigger_websphere_job(params, login, senha):
    """Função interna para disparar o job do Websphere com parâmetros específicos."""
    jenkins_url = 'https://deploy.sicoob.com.br/job/Restart/job/Websphere/job/websphere-cluster-action/buildWithParameters'
    try:
        logging.info(f"Disparando job do Websphere com parâmetros: {params}")
        response = requests.post(jenkins_url, params=params, auth=(login, senha), verify=False)

        if response.status_code == 201:
            queue_url = response.headers.get('Location')
            logging.info(f"Build iniciado para: {params.get('SELECIONADOS') or params.get('NOMECLUSTER')}")
            
            max_attempts = 15
            for _ in range(max_attempts):
                job_url = get_job_url(queue_url, login, senha)
                if job_url:
                    return {"status": "STARTED", "message": "Build iniciado", "job_url": job_url}
                time.sleep(2)
            return {"status": "ERROR", "message": "Timeout aguardando URL do job"}
        else:
            return {"status": "ERROR", "message": f"Falha ao iniciar build: {response.status_code}"}
    except Exception as e:
        return {"status": "ERROR", "message": f"Erro no trigger: {str(e)}"}

def restart_Websphere(Modo, valor_cluster, valor_codigo, Login, Senha):
    """Função original para restart, usada pelo index.html. Ação é sempre RESTART."""
    params = {
        'ACAO': 'RESTART',
        'MODO': Modo,
        'NOMECLUSTER': valor_cluster,
        'AMBIENTE': 'PRODUCAO',
        'SELECIONADOS': valor_codigo
    }
    return _trigger_websphere_job(params, Login, Senha)

def stop_websphere(Modo, valor_cluster, valor_codigo, Login, Senha):
    """Nova função para PARAR o Websphere, usada pelo processamento.html."""
    params = {
        'ACAO': 'STOP',
        'MODO': Modo,
        'NOMECLUSTER': valor_cluster,
        'AMBIENTE': 'PRODUCAO',
        'SELECIONADOS': valor_codigo
    }
    return _trigger_websphere_job(params, Login, Senha)

def start_websphere(Modo, valor_cluster, valor_codigo, Login, Senha):
    """Nova função para INICIAR o Websphere, usada pelo processamento.html."""
    params = {
        'ACAO': 'RESTART',
        'MODO': Modo,
        'NOMECLUSTER': valor_cluster,
        'AMBIENTE': 'PRODUCAO',
        'SELECIONADOS': valor_codigo
    }
    return _trigger_websphere_job(params, Login, Senha)

def get_job_url(queue_url: str, login: str, senha: str) -> str:
    """Obtém a URL do job a partir da URL da fila."""
    try:
        response = requests.get(queue_url + 'api/json', auth=(login, senha), verify=False)
        if response.status_code == 200:
            data = response.json()
            if 'executable' in data and 'url' in data['executable']:
                return data['executable']['url']
    except:
        pass
    return None

def check_job_status(job_url, login, senha):
    """Verifica o status atual do job."""
    try:
        response = requests.get(job_url + 'api/json', auth=(login, senha), verify=False)
        if response.status_code == 200:
            job_info = response.json()
            return {
                "status": "RUNNING" if job_info.get('building', True) else job_info.get('result', 'UNKNOWN'),
                "building": job_info.get('building', True)
            }
    except Exception as e:
        return {"status": "ERROR", "building": False, "message": str(e)}