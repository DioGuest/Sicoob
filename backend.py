import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from CompletoInputALLB import F5Manager, TokenManager
from Pesquisar_Cluster.Pesquisar import pesquisar, obter_maquinas_producao
from mensagens_integracao import sugerir_mensagem_integracao, detectar_tipo_mensagem
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt
from rich.panel import Panel
from rich.text import Text
from rich import box
from features.ssh_automation import clean_opt_disk
from features.outofmemory import move_files_ssh
import threading
import asyncio

console = Console()

# Lista global para acompanhar restarts em andamento
restart_jobs = []

# Lista global para acompanhar limpezas em andamento
clean_jobs = []

class RestartJob:
    def __init__(self, node, manager_f5, user_info):
        self.node = node
        self.manager_f5 = manager_f5
        self.user_info = user_info
        self.status = "PENDENTE"
        self.result = None
        self.thread = threading.Thread(target=self.run)
        self.start_time = time.strftime("%H:%M:%S")
        self.end_time = None

    def start(self):
        self.thread.start()

    def run(self):
        try:
            self.status = "EXECUTANDO"
            result = restart_completo(self.manager_f5, self.node, self.user_info)
            if result is True:
                self.status = "FINALIZADO (SUCESSO)"
                self.result = {"success": True}
            else:
                self.status = "FINALIZADO (ERRO)"
                self.result = {"success": False, "detail": result}
        except Exception as e:
            self.status = f"ERRO: {str(e)}"
        self.end_time = time.strftime("%H:%M:%S")

class CleanJob:
    def __init__(self, node, cluster_name, user_info):
        self.node = node
        self.cluster_name = cluster_name
        self.user_info = user_info
        self.status = "PENDENTE"
        self.result = None
        self.thread = threading.Thread(target=self.run)
        self.start_time = time.strftime("%H:%M:%S")
        self.end_time = None

    def start(self):
        self.thread.start()

    def run(self):
        try:
            self.status = "EXECUTANDO"
            from Restart_Funcoes.restart_Clear import restart_CleanDisk
            result = restart_CleanDisk(self.cluster_name, self.node, self.user_info["jenkins_user"], self.user_info["jenkins_token"])
            if result.get("status") == "STARTED" and result.get("job_url"):
                sucesso = aguardar_job_jenkins(result.get("job_url"), self.user_info["jenkins_user"], self.user_info["jenkins_token"], node=self.node, component="Limpeza")
                if sucesso:
                    self.status = "FINALIZADO (SUCESSO)"
                else:
                    self.status = "FINALIZADO (ERRO)"
            else:
                self.status = f"ERRO: {result.get('message', 'Falha ao iniciar')}"
        except Exception as e:
            self.status = f"ERRO: {str(e)}"
        self.end_time = time.strftime("%H:%M:%S")

def ler_credenciais_arquivo():
    cred_path = os.path.join(os.path.dirname(__file__), "credenciais.txt")
    if not os.path.exists(cred_path):
        print(f"Arquivo de credenciais não encontrado: {cred_path}")
        print("Crie um arquivo 'credenciais.txt' na raiz com o seguinte formato:")
        print("usuario_f5=SEU_USUARIO")
        print("senha_f5=SUA_SENHA")
        print("usuario_jenkins=SEU_USUARIO_JENKINS")
        print("token_jenkins=SEU_TOKEN_JENKINS")
        sys.exit(1)
    cred = {}
    with open(cred_path, encoding="utf-8") as f:
        for line in f:
            if "=" in line:
                k, v = line.strip().split("=", 1)
                cred[k.strip()] = v.strip()
    required = ["usuario_f5", "senha_f5", "usuario_jenkins", "token_jenkins"]
    if not all(k in cred and cred[k] for k in required):
        print("Arquivo de credenciais incompleto. Verifique se todos os campos estão preenchidos.")
        sys.exit(1)
    # também aceita chaves alternativas/maiúsculas para ADM Sicoob
    adm_user = cred.get('ADM-SICOOB') or cred.get('adm-sicoob') or cred.get('adm_sicoob') or cred.get('adm')
    adm_pass = cred.get('SENHA-ADM') or cred.get('senha-adm') or cred.get('senha_adm') or cred.get('senha')

    return {
        "username": cred["usuario_f5"],
        "password": cred["senha_f5"],
        "jenkins_user": cred["usuario_jenkins"],
        "jenkins_token": cred["token_jenkins"],
        "adm_user": adm_user,
        "adm_pass": adm_pass,
    }

def executar_em_paralelo(balancers, func, *args, **kwargs):
    resultados = []
    with ThreadPoolExecutor(max_workers=len(balancers)) as executor:
        future_to_balancer = {
            executor.submit(func, balancer, *args, **kwargs): balancer
            for balancer in balancers
        }
        for future in as_completed(future_to_balancer):
            balancer = future_to_balancer[future]
            try:
                resultado = future.result()
                if resultado is None:
                    print(f"[{balancer.name}] Token expirado ou inválido. Ignorando este balanceador.")
                    continue
            except Exception as e:
                resultado = f"Erro: {e}"
            resultados.append((balancer.name, resultado))
    return resultados

def consultar_status_node(balancer, node):
    return balancer.get_node_status(node)

def forcar_offline_node(balancer, node):
    return balancer.force_offline_node(node)

def habilitar_node(balancer, node):
    return balancer.enable_node(node)

def listar_pools(balancer):
    return balancer.get_available_pools()

def listar_membros_pool(balancer, pool):
    return balancer.get_pool_members(pool)

def restart_completo(manager_f5, node, user_info):
    # Fluxo para um único node (mantido para uso interno)
    console.print(Panel(f"=== RESTART COMPLETO: [bold yellow]{node}[/bold yellow] ===", style="bold cyan", box=box.DOUBLE))
    console.print(Panel(f"[bold magenta][RESTART COMPLETO][/bold magenta] Isolando node [bold yellow]{node}[/bold yellow] em todos os balanceadores...", style="magenta"))

    resultados_offline = executar_em_paralelo(manager_f5.authenticated_balancers, forcar_offline_node, node)
    offline_table = Table(title="Resultado - Offline", box=box.SIMPLE)
    offline_table.add_column("Balanceador", style="bold cyan")
    offline_table.add_column("Resultado", style="bold yellow")
    for nome, result in resultados_offline:
        offline_table.add_row(nome, str(result))
    console.print(offline_table)

    # Adiciona espera de 3 minutos para nodes TRNP após isolamento
    node_prefix = node[:4].upper()
    if node_prefix == "TRNP":
        console.print(Panel("[bold yellow]Node TRNP isolado. Aguardando 3 minutos devido à persistência...[/bold yellow]", style="yellow"))
        for i in range(3, 0, -1):
            console.print(f"[yellow]Aguardando {i} minuto(s)...[/yellow]")
            time.sleep(60)

    console.print(Panel("[bold blue]Aguardando conexões zerarem...[/bold blue]", style="blue"))
    max_attempts = 60
    sleep_interval = 10
    for attempt in range(max_attempts):
        resultados_status = executar_em_paralelo(manager_f5.authenticated_balancers, consultar_status_node, node)
        total_conns = 0
        detalhes = []
        todos_zero = True
        for nome, status in resultados_status:
            conns = status.get("connections", 0) if isinstance(status, dict) else 0
            detalhes.append(f"[bold]{nome}[/bold]: [green]{conns}[/green] conexões")
            if conns > 0:
                todos_zero = False
                total_conns += conns
        console.print(f"[yellow]Conexões ativas:[/yellow] [bold]{total_conns}[/bold] | Detalhes: {', '.join(detalhes)}")
        if todos_zero:
            console.print(Panel("[bold green]Todas as conexões zeradas![/bold green]", style="green"))
            break
        time.sleep(sleep_interval)
    else:
        console.print(Panel("[bold red]Timeout esperando conexões zerarem. Abortando restart.[/bold red]", style="red"))
        return False

    console.print(Panel(f"[bold blue]Executando restart via Jenkins para máquina {node}...[/bold blue]", style="blue"))
    from Restart_Funcoes.Restart_Websphere import restart_Websphere, check_job_status
    from Restart_Funcoes.Restart_SWS import restart_SWS
    from Restart_Funcoes.Restart_Liberty import restart_liberty
    host, cluster_name = pesquisar(node)
    if not cluster_name:
        console.print(Panel("[bold red]Cluster não encontrado para o node.[/bold red]", style="red"))
        return False
    node_prefix = node[:4].upper()
    login = user_info["jenkins_user"]
    senha = user_info["jenkins_token"]
    sucesso = False

    if node_prefix in ['WASP', 'TRNP']:
        console.print(Panel(f"[bold cyan]Restartando Websphere na máquina {node}...[/bold cyan]", style="cyan"))
        result = restart_Websphere("PARALELO", cluster_name, node, login, senha)
        console.print(Panel(f"[bold cyan]Resultado Websphere ({node}):[/bold cyan] {result}", style="cyan"))
        if result.get("status") == "STARTED" and result.get("job_url"):
            sucesso = aguardar_job_jenkins(result.get("job_url"), login, senha, node=node, component="Websphere")
        else:
            sucesso = False
    elif node_prefix == 'CTRP':
        # Para CTRP executa Websphere, SRTB e Liberty
        from Restart_Funcoes.Restart_SRTB import restart_SRTB
        component_results = {}

        console.print(Panel(f"[bold cyan]Restartando Websphere na máquina {node}...[/bold cyan]", style="cyan"))
        result_ws = restart_Websphere("PARALELO", cluster_name, node, login, senha)
        console.print(Panel(f"[bold cyan]Resultado Websphere ({node}):[/bold cyan] {result_ws}", style="cyan"))
        if result_ws.get("status") == "STARTED" and result_ws.get("job_url"):
            component_results['Websphere'] = aguardar_job_jenkins(result_ws.get("job_url"), login, senha, node=node, component="Websphere")
        else:
            component_results['Websphere'] = False

        console.print(Panel(f"[bold cyan]Restartando SRTB na máquina {node}...[/bold cyan]", style="cyan"))
        result_srtb = restart_SRTB("PARALELO", cluster_name, node, login, senha)
        console.print(Panel(f"[bold cyan]Resultado SRTB ({node}):[/bold cyan] {result_srtb}", style="cyan"))
        if result_srtb.get("status") == "STARTED" and result_srtb.get("job_url"):
            component_results['SRTB'] = aguardar_job_jenkins(result_srtb.get("job_url"), login, senha, node=node, component="SRTB")
        else:
            component_results['SRTB'] = False

        console.print(Panel(f"[bold cyan]Restartando Liberty na máquina {node}...[/bold cyan]", style="cyan"))
        result_lib = restart_liberty("PARALELO", cluster_name, node, login, senha)
        console.print(Panel(f"[bold cyan]Resultado Liberty ({node}):[/bold cyan] {result_lib}", style="cyan"))
        if result_lib.get("status") == "STARTED" and result_lib.get("job_url"):
            component_results['Liberty'] = aguardar_job_jenkins(result_lib.get("job_url"), login, senha, node=node, component="Liberty")
        else:
            component_results['Liberty'] = False

        sucesso = all(component_results.values())
        # Mostrar resumo por componente
        for comp, ok in component_results.items():
            if ok:
                console.print(Panel(f"[bold green]{comp} finalizado com sucesso em {node}[/bold green]", style="green"))
            else:
                console.print(Panel(f"[bold red]{comp} NÃO finalizado com sucesso em {node}[/bold red]", style="red"))
    else:
        console.print(Panel("[bold red]Prefixo de node não reconhecido para restart.[/bold red]", style="red"))
        return False

    if sucesso:
        console.print(Panel(f"[bold green]Restart de {node} concluído com sucesso. Habilitando node em todos os balanceadores...[/bold green]", style="green"))
        resultados_enable = executar_em_paralelo(manager_f5.authenticated_balancers, habilitar_node, node)
        enable_table = Table(title="Resultado - Enable", box=box.SIMPLE)
        enable_table.add_column("Balanceador", style="bold cyan")
        enable_table.add_column("Resultado", style="bold green")
        for nome, result in resultados_enable:
            enable_table.add_row(nome, str(result))
        console.print(enable_table)
        console.print(Panel("[bold green]Restart completo realizado com sucesso![/bold green]", style="green"))
    else:
        console.print(Panel(f"[bold red]Falha ao iniciar ou concluir restart via Jenkins para {node}. Processo NÃO COMPLETO.[/bold red]", style="red"))
    return sucesso

def aguardar_job_jenkins(job_url, login, senha, node=None, component=None, max_attempts=60, sleep_interval=10):
    from Restart_Funcoes.Restart_Websphere import check_job_status
    label = f"{component} - {node}" if component or node else "Jenkins Job"
    for attempt in range(max_attempts):
        status = check_job_status(job_url, login, senha)
        if status.get("status") == "RUNNING":
            console.print(f"[yellow]Job {label} em execução... ({attempt+1}/{max_attempts})[/yellow]")
        elif status.get("status") == "SUCCESS":
            console.print(Panel(f"[bold green]Job {label} finalizado com sucesso![/bold green]", style="green"))
            return True
        elif status.get("status") in ["FAILURE", "ERROR"]:
            console.print(Panel(f"[bold red]Job {label} falhou: {status.get('message', '')}[/bold red]", style="red"))
            return False
        time.sleep(sleep_interval)
    console.print(Panel(f"[bold red]Timeout aguardando conclusão do job {label}.[/bold red]", style="red"))
    return False

def restart_completo_multi(manager_f5, nodes, user_info):
    # Executa o restart completo de múltiplos nodes em paralelo
    def worker(node):
        restart_completo(manager_f5, node, user_info)
    with ThreadPoolExecutor(max_workers=len(nodes)) as executor:
        futures = [executor.submit(worker, node) for node in nodes]
        for future in as_completed(futures):
            pass

def verificar_balancers_autenticados(manager_f5):
    # Verifica TODOS os balanceadores configurados (exige que todos estejam com token válido)
    failed = []
    for balancer in manager_f5.balancers:
        if not balancer.ensure_valid_token():
            failed.append(balancer)
    if not failed:
        return True

    # Filtra os que ainda não tiveram tentativa de reautenticação
    to_try = [b for b in failed if getattr(b, 'reauth_attempts', 0) == 0]
    if to_try:
        print("\nATENÇÃO: Tokens inválidos/expirados detectados nos seguintes balanceadores:")
        for b in failed:
            print(f"- {b.name}")
        # Solicita credenciais ADM para tentar reautenticar (uma única vez)
        user = Prompt.ask("Usuário ADM Sicoob para reautenticar", default="")
        pwd = Prompt.ask("Senha ADM Sicoob para reautenticar", password=True)
        if not user or not pwd:
            print("Credenciais não informadas. Nenhuma ação será permitida.")
            return False
        manager_f5.auth_specific([b.name for b in to_try], user, pwd)

        # Reavaliar após tentativa
        still_failed = [b for b in manager_f5.balancers if not b.ensure_valid_token()]
        if still_failed:
            print("\nERRO: Ainda não foi possível autenticar os seguintes balanceadores:")
            for b in still_failed:
                print(f"- {b.name}")
            print("Nenhuma ação será permitida até que todos estejam autenticados.")
            return False
        return True

    # Se chegou aqui, significa que já tentamos reautenticar esses balanceadores uma vez
    print("\nERRO: Alguns balanceadores estão sem autenticação e já foi tentada reautenticação uma vez. Reinicie o programa ou contate o suporte.")
    for b in failed:
        print(f"- {b.name}")
    return False

def limpar_disco_e_outofmemory(nodes, adm_user, adm_pass):
    from concurrent.futures import ThreadPoolExecutor, as_completed
    hosts = [node.strip() for node in nodes.split(',')]
    results = []

    def worker(host):
        result_opt = clean_opt_disk(host, adm_user, adm_pass)
        result_oom = move_files_ssh(host, adm_user, adm_pass)
        return host, result_opt, result_oom

    with ThreadPoolExecutor(max_workers=len(hosts)) as executor:
        futures = [executor.submit(worker, host) for host in hosts]
        for future in as_completed(futures):
            host, result_opt, result_oom = future.result()
            results.append((host, result_opt, result_oom))
    return results

def main_menu(manager_f5, user_info):
    while True:
        console.print("\n[bold cyan]=== MENU PRINCIPAL ===[/bold cyan]")
        console.print("[yellow]1.[/yellow] Consultar status de node")
        console.print("[yellow]2.[/yellow] Forçar node offline")
        console.print("[yellow]3.[/yellow] Habilitar node")
        console.print("[yellow]4.[/yellow] Restart completo de node")
        console.print("[yellow]5.[/yellow] Listar pools disponíveis")
        console.print("[yellow]6.[/yellow] Listar membros de um pool")
        console.print("[yellow]7.[/yellow] Sair")
        console.print("[yellow]8.[/yellow] Limpeza Disco-Opt + OutOfMemory")
        console.print("[yellow]9.[/yellow] Acompanhar operações em andamento")
        console.print("[yellow]10.[/yellow] Limpeza Jenkins sem isolamento")
        opcao = Prompt.ask("Escolha uma opção", choices=["1","2","3","4","5","6","7","8","9","10"])
        # Verifica se todos os balanceadores estão autenticados antes de qualquer ação
        if opcao in ['1','2','3','4','5','6']:
            if not verificar_balancers_autenticados(manager_f5):
                continue
        if opcao == '1':
            nodes = Prompt.ask("Nome(s) do node (separados por vírgula)").strip().upper().replace(" ", "")
            table = Table(title="Status dos Nodes")
            table.add_column("Node", style="bold yellow")
            table.add_column("Cluster", style="bold magenta")
            table.add_column("Resumo", style="bold cyan")
            for node in nodes.split(","):
                host, cluster_name = pesquisar(node)
                resultados = executar_em_paralelo(manager_f5.authenticated_balancers, consultar_status_node, node)
                for nome, status in resultados:
                    if isinstance(status, dict) and status.get("found"):
                        resumo = (
                            f"[bold yellow]Servidor {status.get('servidor')}[/bold yellow] - "
                            f"Status [bold green]{status.get('status')}[/bold green] - "
                            f"connections [bold blue]{status.get('connections', 0)}[/bold blue]"
                        )
                    else:
                        resumo = "[red]Não encontrado ou erro[/red]"
                    table.add_row(
                        f"[bold]{node}[/bold]",
                        f"[magenta]{cluster_name if cluster_name else '-'}[/magenta]",
                        resumo
                    )
            console.print(table)
        elif opcao == '2':
            nodes = Prompt.ask("Nome(s) do node (separados por vírgula)").strip().upper().replace(" ", "")
            table = Table(title="Nodes Offline")
            table.add_column("Balanceador")
            table.add_column("Resultado")
            for node in nodes.split(","):
                resultados = executar_em_paralelo(manager_f5.authenticated_balancers, forcar_offline_node, node)
                for nome, result in resultados:
                    table.add_row(nome, str(result))
            console.print(table)
        elif opcao == '3':
            nodes = Prompt.ask("Nome(s) do node (separados por vírgula)").strip().upper().replace(" ", "")
            table = Table(title="Nodes Habilitados")
            table.add_column("Balanceador")
            table.add_column("Resultado")
            for node in nodes.split(","):
                resultados = executar_em_paralelo(manager_f5.authenticated_balancers, habilitar_node, node)
                for nome, result in resultados:
                    table.add_row(nome, str(result))
            console.print(table)
        elif opcao == '4':
            nodes = Prompt.ask("Nome(s) do node para restart completo (separados por vírgula)").strip().upper().replace(" ", "")
            node_list = nodes.split(",")
            
            # Verificar cluster e perguntar sobre mensagem de integração no início
            primeiro_node = node_list[0].strip()
            host, cluster_name = pesquisar(primeiro_node)
            
            # Sugerir mensagem apropriada baseada no node e cluster
            sugerir_mensagem_integracao(primeiro_node, cluster_name if cluster_name else "")
            
            console.print(Panel(
                f"[bold cyan]Iniciando restart completo...[/bold cyan]",
                style="cyan"
            ))
            
            for node in node_list:
                job = RestartJob(node, manager_f5, user_info)
                restart_jobs.append(job)
                job.start()
            console.print(Panel("[bold blue]Restart(s) iniciado(s) em segundo plano![/bold blue]\nUse a opção 9 para acompanhar.", style="blue"))
        elif opcao == '5':
            sub = Prompt.ask("Opção 5 - Escolha: 1) Listar todos pools  2) Pesquisar pools", choices=["1","2"], default="1")
            if sub == '1':
                resultados = executar_em_paralelo(manager_f5.authenticated_balancers, listar_pools)
                table = Table(title="Pools Disponíveis", box=box.SIMPLE)
                table.add_column("Balanceador")
                table.add_column("Pools")
                for nome, pools in resultados:
                    table.add_row(nome, ", ".join(pools) if pools else "Nenhum")
                console.print(table)
            else:
                termo = Prompt.ask("Termo de busca (ex: CREDITO CORE ou RISCO LIMITE)").strip().lower()
                if not termo:
                    console.print("[red]Termo vazio. Cancelando pesquisa.[/red]")
                    continue
                palavras = [w for w in termo.split() if w]
                resultados = executar_em_paralelo(manager_f5.authenticated_balancers, listar_pools)
                table = Table(title=f"Pools correspondentes: '{termo}'", box=box.SIMPLE)
                table.add_column("Balanceador")
                table.add_column("Pools")
                any_match = False
                for nome, pools in resultados:
                    if not pools:
                        table.add_row(nome, "-")
                        continue
                    matches = []
                    for p in pools:
                        norm = p.replace('-', ' ').replace('_', ' ').lower()
                        # exigir que todas as palavras do termo apareçam no nome do pool
                        if all(w in norm for w in palavras):
                            matches.append(p)
                    table.add_row(nome, ", ".join(matches) if matches else "-")
                    if matches:
                        any_match = True
                if not any_match:
                    console.print(Panel(f"[yellow]Nenhum pool encontrado para '{termo}'[/yellow]", style="yellow"))
                console.print(table)
        elif opcao == '6':
            pool = Prompt.ask("Nome do pool (incluindo 'pool-')").strip()
            resultados = executar_em_paralelo(manager_f5.authenticated_balancers, listar_membros_pool, pool)
            table = Table(title=f"Membros do Pool {pool}", box=box.SIMPLE_HEAVY)
            table.add_column("Balanceador", style="bold cyan")
            table.add_column("Membros")

            for nome, members in resultados:
                if not members:
                    table.add_row(nome, "Nenhum membro ou erro", end_section=True)
                    continue
                try:
                    # Construir lista de linhas para esse balanceador
                    balancer_entries = []
                    for entry in members:
                        mems = entry.get('members', []) if isinstance(entry, dict) else []
                        for m in mems:
                            state = (m.get('state') or '').lower()
                            status = (m.get('status') or '').lower()
                            state_col = f"[green]{state}[/green]" if state == 'up' else (f"[yellow]{state}[/yellow]" if state == 'unknown' else f"[red]{state}[/red]")
                            status_col = f"[green]{status}[/green]" if status in ('enabled', 'up') else (f"[yellow]{status}[/yellow]" if status in ('disabled', 'down') else f"[red]{status}[/red]")
                            conns = m.get('connections', 0)
                            line = f"{m.get('name')}  state: {state_col}  status: {status_col}  address: {m.get('address')}  port: {m.get('port')}  connections: {conns}"
                            balancer_entries.append(line)

                    if not balancer_entries:
                        table.add_row(nome, "Nenhum membro", end_section=True)
                        continue

                    # Contagem de membros e classificação (ativo/offline)
                    total = len(balancer_entries)
                    active_count = 0
                    offline_count = 0
                    # Recontar baseado em texto construído (mais robust seria contar no loop acima)
                    for entry_line in balancer_entries:
                        # procura por marcação de cor que usamos para state/status
                        if '[green]up' in entry_line or 'state: [green]up' in entry_line or 'status: [green]enabled' in entry_line or 'status: [green]up' in entry_line:
                            active_count += 1
                        # offline quando houver indicação de red
                        if '[red]' in entry_line and ('off' in entry_line or 'down' in entry_line or 'disabled' in entry_line):
                            offline_count += 1

                    # Monta cabeçalho com cores: total em vermelho se houver offline
                    if offline_count > 0:
                        total_str = f"[red]{total}[/red]"
                    else:
                        total_str = f"[green]{total}[/green]"

                    nome_com_contador = f"{nome} ({total_str})"
                    counts_suffix = f" [green]{active_count} active[/green] [red]{offline_count} offline[/red]"

                    # Adiciona as linhas: primeiro com o nome do balancer (incluindo contador), últimas com end_section=True
                    for i, line in enumerate(balancer_entries):
                        is_last = (i == len(balancer_entries) - 1)
                        if i == 0:
                            table.add_row(nome_com_contador + counts_suffix, line, end_section=is_last)
                        else:
                            table.add_row("", line, end_section=is_last)

                except Exception:
                    table.add_row(nome, str(members), end_section=True)
            console.print(table)
        elif opcao == '7':
            console.print("[bold red]Saindo...[/bold red]")
            manager_f5.cleanup()
            break
        elif opcao == '8':
            # Tenta obter ADM do arquivo de credenciais (retornado em user_info)
            adm_user = None
            adm_pass = None
            try:
                adm_user = user_info.get('adm_user') if user_info else None
                adm_pass = user_info.get('adm_pass') if user_info else None
            except Exception:
                adm_user = None
                adm_pass = None

            # Se não existir no arquivo, solicitar ao usuário
            if not adm_user or not adm_pass:
                adm_user = Prompt.ask("[bold magenta]Usuário ADM Sicoob[/bold magenta]")
                adm_pass = Prompt.ask("[bold magenta]Senha ADM Sicoob[/bold magenta]", password=True)

            nodes = Prompt.ask("[bold magenta]Máquina(s) para limpeza (separadas por vírgula)[/bold magenta]").strip()
            console.print(Panel("[bold blue]Executando limpeza Disco-Opt + OutOfMemory...[/bold blue]", style="blue"))
            resultados = limpar_disco_e_outofmemory(nodes, adm_user, adm_pass)
            for host, result_opt, result_oom in resultados:
                panel_text = f"[bold yellow]{host}[/bold yellow]\n\n"
                panel_text += f"[bold green]Disco-Opt:[/bold green]\n{result_opt['message'] if isinstance(result_opt, dict) else result_opt}\n\n"
                panel_text += f"[bold magenta]OutOfMemory:[/bold magenta]\n{result_oom['message'] if isinstance(result_oom, dict) else result_oom}\n"
                console.print(Panel(panel_text, style="cyan"))
        elif opcao == '9':
            table = Table(title="Acompanhamento de Operações", box=box.SIMPLE)
            table.add_column("Tipo", style="bold magenta")
            table.add_column("Node", style="bold yellow")
            table.add_column("Status", style="bold cyan")
            table.add_column("Início", style="green")
            table.add_column("Fim", style="red")
            for job in restart_jobs:
                # Colorir status: sucesso=verde, erro=vermelho, executando=amarelo
                st = (job.status or "").upper()
                if "SUCESSO" in st or "FINALIZADO (SUCESSO)" in st:
                    status_col = f"[green]{job.status}[/green]"
                elif "EXECUTANDO" in st or "RUNNING" in st:
                    status_col = f"[yellow]{job.status}[/yellow]"
                else:
                    # tratar como erro/falha por padrão
                    status_col = f"[red]{job.status}[/red]"

                table.add_row(
                    "Restart",
                    job.node,
                    status_col,
                    job.start_time,
                    job.end_time if job.end_time else "-"
                )
            for job in clean_jobs:
                # Colorir status: sucesso=verde, erro=vermelho, executando=amarelo
                st = (job.status or "").upper()
                if "SUCESSO" in st or "FINALIZADO (SUCESSO)" in st:
                    status_col = f"[green]{job.status}[/green]"
                elif "EXECUTANDO" in st or "RUNNING" in st:
                    status_col = f"[yellow]{job.status}[/yellow]"
                else:
                    # tratar como erro/falha por padrão
                    status_col = f"[red]{job.status}[/red]"

                table.add_row(
                    "Limpeza",
                    job.node,
                    status_col,
                    job.start_time,
                    job.end_time if job.end_time else "-"
                )
            console.print(table)
        elif opcao == '10':
            nodes = Prompt.ask("Nome(s) do node (separados por vírgula)").strip().upper().replace(" ", "")
            for node in nodes.split(","):
                host, cluster_name = pesquisar(node)
                if not cluster_name:
                    console.print(Panel("[bold red]Cluster não encontrado para o node.[/bold red]", style="red"))
                    continue
                job = CleanJob(node, cluster_name, user_info)
                clean_jobs.append(job)
                job.start()
                console.print(Panel(f"[bold green]Limpeza iniciada para {node} em background.[/bold green]", style="green"))
        else:
            console.print("[red]Opção inválida.[/red]")

def main():
    print("=== SISTEMA F5 TERMINAL ===")
    user_info = ler_credenciais_arquivo()
    manager_f5 = F5Manager()
    # Pre-configura username/password e token_manager em cada balancer
    for balancer in manager_f5.balancers:
        balancer.username = user_info["username"]
        balancer.password = user_info["password"]
        balancer.token_manager = TokenManager(balancer)

    # Autentica todos os balanceadores (assíncrono, com timeout interno)
    try:
        asyncio.run(manager_f5.authenticate_all())
    except Exception as e:
        print(f"Erro ao autenticar balanceadores: {e}")

    if not manager_f5.authenticated_balancers:
        print("Nenhum balanceador autenticado. Verifique suas credenciais.")
        sys.exit(1)
    print(f"{len(manager_f5.authenticated_balancers)} balanceadores autenticados.")
    main_menu(manager_f5, user_info)

if __name__ == "__main__":
    main()