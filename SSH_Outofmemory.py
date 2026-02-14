import paramiko
import time
from flask import Blueprint, render_template, request
from concurrent.futures import ThreadPoolExecutor, as_completed

# Criação do Blueprint para mover arquivos
move_bp = Blueprint('SSH_Outofmemory', __name__)

@move_bp.route('/SSH_Outofmemory', methods=['GET'])
def move_files():
    return render_template('limpe_SSH.html')  # Renderiza a página desejada

def move_files_ssh(host, username, password):
    port = 22
    sudo_password = password
    result_message = "Outofmemory - Movendo dados<br>"

    # Cria a sessão SSH
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        # Conecta ao servidor
        ssh.connect(host, port, username, password)
        result_message += f"Conectado ao servidor {host}<br>"

        # Comando para listar o conteúdo da pasta antes da movimentação
        list_before_command = 'ls -lh /opt/IBM/WAS/WebSphere/AppServer/profiles/sicoob/'
        stdin, stdout, stderr = ssh.exec_command(list_before_command)
        files_before = stdout.read().decode()
        result_message += f"Arquivos ANTES da movimentação:<br>{files_before}<br>"

        # Comando para mover os arquivos
        move_command = 'cd /opt/IBM/WAS/WebSphere/AppServer/profiles/sicoob/ && sudo mv *.dmp *.txt *.phd *.trc /media/dump/'
        stdin, stdout, stderr = ssh.exec_command(move_command)
        stdin.write(sudo_password + '\n')
        stdin.flush()
        time.sleep(2)  # Aguardar o tempo necessário para o comando ser executado

        # Exibe a saída do comando de mover arquivos
        output = stdout.read().decode()
        result_message += f"Resultado do comando sudo (mover arquivos):<br>{output}<br>"

        # Exibe qualquer erro retornado
        error_output = stderr.read().decode()
        if error_output:
            result_message += f"Erro: {error_output}<br>"

        # Comando para listar o conteúdo da pasta depois da movimentação
        list_after_command = 'ls -lh /opt/IBM/WAS/WebSphere/AppServer/profiles/sicoob/'
        stdin, stdout, stderr = ssh.exec_command(list_after_command)
        files_after = stdout.read().decode()
        result_message += f"Arquivos DEPOIS da movimentação:<br>{files_after}<br>"

    except Exception as e:
        result_message += f"Erro ao conectar ou executar o comando no servidor {host}: {str(e)}<br>"

    finally:
        ssh.close()

    return result_message

# Rota para processar a solicitação (POST)
@move_bp.route('/SSH_Outofmemory', methods=['POST'])
def move_files_action():
    # Recebe os dados do formulário
    hosts = request.form.getlist('Numero')  # Supondo que você envie uma lista de números
    username = request.form.get('Name')
    password = request.form.get('PassWord')

    result_messages = []
    
    if not hosts or not username or not password:
        result_message = "Parâmetros inválidos!"
        return result_message

    # Usando ThreadPoolExecutor para executar comandos em paralelo
    with ThreadPoolExecutor() as executor:
        future_to_host = {executor.submit(move_files_ssh, host, username, password): host for host in hosts}
        
        for future in as_completed(future_to_host):
            host = future_to_host[future]
            try:
                result = future.result()
                result_messages.append(result)
            except Exception as e:
                result_messages.append(f"Erro ao processar o servidor {host}: {str(e)}")

    # Retorna os resultados concatenados
    return "<br>".join(result_messages)
