import paramiko
import time
from flask import Blueprint, render_template, request
from concurrent.futures import ThreadPoolExecutor, as_completed

# Criação do Blueprint para reiniciar
ssh_bp = Blueprint('ssh_bp', __name__)

@ssh_bp.route('/ssh_disco_opt', methods=['GET'])
def ssh_disco_opt():
    return render_template('limpe_SSH.html')  # Renderiza a página desejada

def execute_ssh_commands(host, username, password):
    port = 22  # Definido como 22 para SSH
    sudo_password = password  # Reutiliza a senha para comandos sudo
    result_message = "Limpeza Disco-Opt - Na pasta Temp<br>"
    
    print(f"\n[DEBUG] Tentando conectar ao host: {host}")
    print(f"[DEBUG] Usando usuário: {username}")

    # Cria uma sessão SSH
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        print(f"[DEBUG] Iniciando conexão SSH com {host}")
        # Conecta ao servidor
        ssh.connect(host, port, username, password)
        print(f"[SUCCESS] Conectado ao servidor {host}")
        result_message += f"Conectado ao servidor {host}<br>"

        # Executa o comando para verificar o tamanho da pasta temp ANTES da exclusão
        print(f"[DEBUG] Verificando tamanho inicial da pasta temp")
        size_command_before = 'du -sh /opt/IBM/WAS/WebSphere/AppServer/temp'
        stdin, stdout, stderr = ssh.exec_command(size_command_before)
        size_before = stdout.read().decode().strip()
        error_before = stderr.read().decode().strip()
        
        if error_before:
            print(f"[WARNING] Erro ao verificar tamanho inicial: {error_before}")
        
        print(f"[INFO] Tamanho inicial da pasta temp: {size_before}")
        result_message += f"Tamanho da pasta temp ANTES da exclusão: {size_before}<br>"

        # Atualiza o comando para deletar arquivos temporários, arquivos que começam com "C", arquivos .ttf e arquivos .pdf
        print(f"[DEBUG] Executando comando de limpeza")
        delete_command = '''sudo find /opt/IBM/WAS/WebSphere/AppServer/temp -name "*.tmp" -delete; 
                          sudo find /opt/IBM/WAS/WebSphere/AppServer/temp -name "C*" -delete; 
                          sudo find /opt/IBM/WAS/WebSphere/AppServer/temp -name "*.ttf" -delete; 
                          sudo find /opt/IBM/WAS/WebSphere/AppServer/temp -name "*.pdf" -delete'''
        
        stdin, stdout, stderr = ssh.exec_command(delete_command)
        stdin.write(sudo_password + '\n')
        stdin.flush()
        
        print("[DEBUG] Aguardando resultado do comando de limpeza")
        # Verifica o resultado do comando
        output = stdout.read().decode().strip()
        error = stderr.read().decode().strip()
        
        if error:
            print(f"[WARNING] Erro durante a limpeza: {error}")
            result_message += f"Aviso durante a limpeza: {error}<br>"

        # Executa o comando para verificar o tamanho da pasta temp DEPOIS da exclusão
        print(f"[DEBUG] Verificando tamanho final da pasta temp")
        size_command_after = 'du -sh /opt/IBM/WAS/WebSphere/AppServer/temp'
        stdin, stdout, stderr = ssh.exec_command(size_command_after)
        size_after = stdout.read().decode().strip()
        error_after = stderr.read().decode().strip()
        
        if error_after:
            print(f"[WARNING] Erro ao verificar tamanho final: {error_after}")
            
        print(f"[INFO] Tamanho final da pasta temp: {size_after}")
        result_message += f"Tamanho da pasta temp DEPOIS da exclusão: {size_after}<br>"

        print(f"[SUCCESS] Limpeza concluída para {host}")
        
    except Exception as e:
        error_msg = f"Erro ao conectar ou executar comando no servidor {host}: {str(e)}"
        print(f"[ERROR] {error_msg}")
        print(f"[ERROR] Tipo da exceção: {type(e).__name__}")
        import traceback
        print(f"[ERROR] Traceback completo:\n{traceback.format_exc()}")
        result_message += f"Erro: {error_msg}<br>"

    finally:
        print(f"[DEBUG] Fechando conexão SSH com {host}")
        ssh.close()

    return result_message

# Rota para processar a solicitação (POST)
@ssh_bp.route('/ssh_disco_opt', methods=['POST'])
def ssh_clean():
    # Recebe os dados do formulário
    hosts_string = request.form.get('Numero')  # Pega a string de hosts
    username = request.form.get('Name')
    password = request.form.get('PassWord')

    # Separa os hosts por vírgula e remove espaços em branco
    hosts = [host.strip() for host in hosts_string.split(',')] if hosts_string else []

    result_messages = []
    
    if not hosts or not username or not password:
        result_message = "Parâmetros inválidos!"
        return result_message

    # Usando ThreadPoolExecutor para executar comandos em paralelo
    with ThreadPoolExecutor() as executor:
        future_to_host = {executor.submit(execute_ssh_commands, host, username, password): host for host in hosts}
        
        for future in as_completed(future_to_host):
            host = future_to_host[future]
            try:
                result = future.result()
                result_messages.append(result)
            except Exception as e:
                result_messages.append(f"Erro ao processar o servidor {host}: {str(e)}")

    # Retorna os resultados concatenados
    return "<br>".join(result_messages)
