import requests

# Função para obter os dados dos clusters e hosts de PRODUCAO
def obter_maquinas_producao():
    url = "https://delivery.sicoob.com.br/sicoob-entrega-continua/configuracoes-clusters?count=1000&page=1"
    response = requests.get(url)
    data = response.json()
    
    clusters_maquinas_producao = []
    
    for cluster in data["resultado"]["dados"]:
        nome_cluster = cluster.get("nomeCluster")
        hosts_producao = [host.get("hostname") for host in cluster.get("hosts", []) if host.get("ambiente") == "PRODUCAO"]
        
        if hosts_producao:
            clusters_maquinas_producao.append({
                "nomeCluster": nome_cluster,
                "hostsProducao": hosts_producao
            })
    
    return clusters_maquinas_producao

# Função de pesquisa usando os dados do endpoint
def pesquisar(Numero):
    # Obter os dados de produção dos clusters
    maquinas_producao = obter_maquinas_producao()
    
    # Procurar pelo número da máquina nos hosts de PRODUCAO
    for cluster in maquinas_producao:
        for host in cluster["hostsProducao"]:
            if Numero.lower() in host.lower():
                # Retornar o host encontrado e o cluster ao qual ele pertence
                return host, cluster["nomeCluster"]
    
    # Se a máquina não for encontrada
    print(f"Máquina {Numero} não encontrada em PRODUCAO.")
    return None, None

