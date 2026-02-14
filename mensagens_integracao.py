"""
Módulo para gerenciar mensagens padrão de integração por tipo de máquina
Suporta: ATM, APP PJ (CTRP Empresarial), APP PF (CTRP Pessoal), etc
"""

def obter_mensagens_disponiveis():
    """
    Retorna dicionário com todas as mensagens disponíveis
    """
    return {
        "ATM": {
            "titulo": "ATM - Terminal de Auto Atendimento",
            "cluster": "TRNP",
            "conteudo": """*ATM* - Terminal de Auto Atendimento

*Incidente*: Rejeições para as transações da utilização da ATM

*Hora Inicio*: 

*Impacto*: Instabilidade para as transações da ATM

*Causa*: Intermitência nos servidores que atendem a ATM.

*Acionados*: Área de Operações de TI

*Obs*: Executada ações de 1º nível para regularização

*Regularizado*: """
        },
        
        "APP_PJ": {
            "titulo": "Canais de Atendimento - APP Sicoob PJ",
            "cluster": "CTRP",
            "tipo": "EMPRESARIAL",
            "conteudo": """*Canais de Atendimento* - APP Sicoob PJ

*Incidente*: Instabilidade para utilização do APP Sicoob PJ

*Hora inicio*: 

*Impacto*: Utilização do APP Sicoob PJ

*Causa*: Instabilidade nos servidores 

*Acionados*: Área de Operações de TI

*Obs*: Executada ações de 1º nível para regularização .

*Regularizado*:"""
        },
        
        "APP_PF": {
            "titulo": "Canais de Atendimento - APP PF",
            "cluster": "CTRP",
            "tipo": "PESSOAL",
            "conteudo": """*Canais de Atendimento - APP PF*
 
*Incidente*: Instabilidade para utilização do APP PF
 
*Hora inicio*: 
 
*Impacto*: Utilização do APP PF
 
*Causa*: Em análise
 
*Acionados*: Área de Operações de TI
 
*Obs*: Executando ações de 1º nível para regularização.
 
*Regularizado*: """
        },

        "SISBR_COBRANCA": {
            "titulo": "Sisbr - Cobrança Administrativa",
            "cluster": "WASP",
            "conteudo": """*Sisbr* - Cobrança Administrativa
 
*Incidente*: Instabilidade nas transações com integração no COBADM
 
*Hora Inicio*: 
 
*Impacto*: MANTER FICHA DEVEDOR SERVIÇO
 
*Causa*: Instabilidade no servidor do conta corrente. 
 
*Acionados*: Área de Operações de TI
 
*Obs*: Regularizado após ações de 1º nível
 
*Regularizado*: """
        }
    }

def detectar_tipo_mensagem(node, cluster_name):
    """
    Detecta qual mensagem usar baseado no node e cluster
    
    Args:
        node: Nome do node (ex: TRNP2501, CTRP1234)
        cluster_name: Nome do cluster retornado pela pesquisa
        
    Returns:
        tuple: (tipo_mensagem, dados_mensagem) ou (None, None) se não encontrar
    """
    
    node_upper = node.upper()
    cluster_upper = cluster_name.upper() if cluster_name else ""
    
    # Verificar máquinas específicas para Sisbr Cobrança
    if node_upper in ["WASP4068", "WASP2095", "WASP2094"]:
        return "SISBR_COBRANCA", obter_mensagens_disponiveis()["SISBR_COBRANCA"]
    
    # Verificar ATM (TRNP + FrontofficeTransacionalATMCluster)
    if node_upper.startswith("TRNP"):
        if "FRONTOFFICE" in cluster_upper and "TRANSACIONAL" in cluster_upper and "ATM" in cluster_upper:
            return "ATM", obter_mensagens_disponiveis()["ATM"]
        # Fallback: se começar com TRNP, pode ser ATM
        elif "ATM" in cluster_upper:
            return "ATM", obter_mensagens_disponiveis()["ATM"]
    
    # Verificar APP PJ - CTRP + FrontofficeValidacionalCelularEmpresarialCluster
    if node_upper.startswith("CTRP"):
        # Empresarial
        if "VALIDACIONAL" in cluster_upper and "CELULAR" in cluster_upper and "EMPRESARIAL" in cluster_upper:
            return "APP_PJ", obter_mensagens_disponiveis()["APP_PJ"]
        
        # Pessoal - FrontofficeValidacionalCelularPessoalCluster
        elif "VALIDACIONAL" in cluster_upper and "CELULAR" in cluster_upper and "PESSOAL" in cluster_upper:
            return "APP_PF", obter_mensagens_disponiveis()["APP_PF"]
        
        # Fallback: detectar por palavras-chave simples
        elif "EMPRESARIAL" in cluster_upper or "PJ" in cluster_upper or "EMPR" in cluster_upper:
            return "APP_PJ", obter_mensagens_disponiveis()["APP_PJ"]
        
        elif "PESSOAL" in cluster_upper or "PF" in cluster_upper:
            return "APP_PF", obter_mensagens_disponiveis()["APP_PF"]
    
    return None, None

def obter_mensagem_atm_padrao():
    """
    Retorna a mensagem padrão para máquinas ATM
    (mantém compatibilidade com código anterior)
    """
    return obter_mensagens_disponiveis()["ATM"]["conteudo"]

def eh_maquina_atm(cluster_name):
    """
    Verifica se a máquina pertence a um cluster ATM que começa com TRNP
    
    Args:
        cluster_name: Nome do cluster da máquina
        
    Returns:
        bool: True se é uma máquina ATM com cluster começando com TRNP
    """
    if not cluster_name:
        return False
    
    cluster_upper = cluster_name.upper()
    return 'ATM' in cluster_upper and cluster_upper.startswith('TRNP')

def exibir_mensagem_em_arquivo(mensagem, titulo="MENSAGEM DE INTEGRAÇÃO"):
    """
    Exibe a mensagem em um arquivo de texto temporário mantendo formatação
    
    Args:
        mensagem: Conteúdo da mensagem
        titulo: Título do arquivo
        
    Returns:
        bool: True se conseguiu exibir
    """
    import tempfile
    import subprocess
    
    try:
        # Criar arquivo temporário
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.txt',
            delete=False,
            encoding='utf-8'
        ) as tmp_file:
            tmp_file.write(f"{titulo}\n")
            tmp_file.write("="*80 + "\n\n")
            tmp_file.write(mensagem)
            tmp_path = tmp_file.name
        
        # Abrir com Notepad (Windows)
        subprocess.Popen(['notepad.exe', tmp_path])
        return True
    except Exception as e:
        print(f"Erro ao exibir arquivo: {e}")
        return False

def exibir_mensagem_gui(mensagem, titulo="MENSAGEM DE INTEGRAÇÃO"):
    """
    Exibe a mensagem em uma janela GUI (tkinter) mantendo formatação
    
    Args:
        mensagem: Conteúdo da mensagem
        titulo: Título da janela
        
    Returns:
        bool: True se conseguiu exibir
    """
    try:
        import tkinter as tk
        from tkinter import scrolledtext
        
        janela = tk.Tk()
        janela.title(titulo)
        janela.geometry("900x600")
        
        # Frame para botões
        frame_botoes = tk.Frame(janela, bg="#f0f0f0")
        frame_botoes.pack(fill=tk.X, padx=10, pady=10)
        
        # Botão copiar
        def copiar_mensagem():
            janela.clipboard_clear()
            # Copia exatamente como está (sem alterar)
            janela.clipboard_append(mensagem.strip())
            label_status.config(text="✓ Mensagem copiada para o clipboard com formatação preservada!", fg="green")
            janela.after(4000, lambda: label_status.config(text=""))
        
        btn_copiar = tk.Button(
            frame_botoes,
            text="📋 Copiar para Clipboard",
            command=copiar_mensagem,
            bg="#4CAF50",
            fg="white",
            padx=20,
            pady=8,
            font=("Arial", 10, "bold"),
            relief=tk.RAISED,
            cursor="hand2"
        )
        btn_copiar.pack(side=tk.LEFT, padx=5)
        
        btn_fechar = tk.Button(
            frame_botoes,
            text="✕ Fechar",
            command=janela.destroy,
            bg="#f44336",
            fg="white",
            padx=20,
            pady=8,
            font=("Arial", 10, "bold"),
            relief=tk.RAISED,
            cursor="hand2"
        )
        btn_fechar.pack(side=tk.LEFT, padx=5)
        
        label_status = tk.Label(
            frame_botoes, 
            text="Clique em 'Copiar para Clipboard' para copiar a mensagem", 
            fg="#666666",
            font=("Arial", 9)
        )
        label_status.pack(side=tk.LEFT, padx=20)
        
        # Caixa de texto com scroll - MONOESPACIAL para preservar formatação
        text_widget = scrolledtext.ScrolledText(
            janela,
            wrap=tk.WORD,
            font=("Courier New", 11),
            padx=20,
            pady=20,
            bg="#ffffff",
            fg="#000000",
            relief=tk.FLAT,
            insertwidth=2
        )
        text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Inserir mensagem - exatamente como está
        text_widget.insert("1.0", mensagem.strip())
        text_widget.config(state=tk.DISABLED)  # Somente leitura
        
        # Centralizar janela na tela
        janela.update_idletasks()
        largura = janela.winfo_width()
        altura = janela.winfo_height()
        x = (janela.winfo_screenwidth() // 2) - (largura // 2)
        y = (janela.winfo_screenheight() // 2) - (altura // 2)
        janela.geometry(f'{largura}x{altura}+{x}+{y}')
        
        janela.mainloop()
        return True
    except ImportError:
        return False

def sugerir_mensagem_integracao(node, cluster_name):
    """
    Detecta e sugere ao usuário a mensagem apropriada
    
    Args:
        node: Nome do node
        cluster_name: Nome do cluster
        
    Returns:
        bool: True se o usuário aceitou usar a mensagem
    """
    from rich.console import Console
    from rich.prompt import Prompt
    from rich.panel import Panel
    
    console = Console()
    
    # Detectar tipo de mensagem
    tipo_msg, dados_msg = detectar_tipo_mensagem(node, cluster_name)
    
    if tipo_msg and dados_msg:
        console.print(Panel(
            f"[bold blue]Mensagem detectada![/bold blue]\n"
            f"[cyan]Tipo: {dados_msg.get('titulo', 'Integração')}[/cyan]\n"
            f"[cyan]Node: {node} | Cluster: {cluster_name if cluster_name else 'Não encontrado'}[/cyan]",
            style="blue"
        ))
        
        resposta = Prompt.ask(
            "[bold cyan]Usar mensagem padrão para integração?[/bold cyan]",
            choices=["1", "2"],
            default="1"
        )
        
        if resposta == "1":
            mensagem = dados_msg["conteudo"]
            
            # Tentar abrir em GUI
            console.print(Panel(
                "[bold cyan]Abrindo janela com a mensagem...[/bold cyan]",
                style="cyan"
            ))
            
            titulo_janela = f"MENSAGEM - {dados_msg.get('titulo', 'Integração')}"
            
            # Tentar exibir em GUI
            if exibir_mensagem_gui(mensagem, titulo_janela):
                console.print(Panel(
                    "[bold green]✓ Janela aberta! Clique em 'Copiar para Clipboard'[/bold green]",
                    style="green"
                ))
                return True
            else:
                # Se GUI falhar, tenta arquivo
                console.print(Panel(
                    "[bold yellow]Abrindo em arquivo de texto...[/bold yellow]",
                    style="yellow"
                ))
                if exibir_mensagem_em_arquivo(mensagem, titulo_janela):
                    console.print(Panel(
                        "[bold green]✓ Arquivo aberto no Notepad[/bold green]",
                        style="green"
                    ))
                    return True
                else:
                    # Última opção: exibir no terminal
                    console.print(Panel(
                        f"[bold green]{dados_msg.get('titulo')}:[/bold green]\n" + mensagem,
                        style="green"
                    ))
                    try:
                        import pyperclip
                        pyperclip.copy(mensagem.strip())
                        console.print("[bold green]✓ Mensagem copiada para o clipboard![/bold green]")
                    except ImportError:
                        console.print("[yellow]Nota: Para copiar automaticamente, instale: pip install pyperclip[/yellow]")
                    return True
        
        return False
    
    return False
