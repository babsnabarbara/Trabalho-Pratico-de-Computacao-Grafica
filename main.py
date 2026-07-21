import sys
import os

# Forca o terminal a exibir cada linha impressa IMEDIATAMENTE, em vez de
# acumular num buffer interno que so e liberado quando o programa termina
# ou quando ha alguma interacao especifica com a janela. Sem isso, em
# alguns terminais (ex: Git Bash/MINGW64 no Windows), todas as mensagens
# de print() - incluindo as de troca de vista, animacao, Z-buffer, etc. -
# ficam "presas" e so aparecem de uma vez quando o visualizador e fechado.
sys.stdout.reconfigure(line_buffering=True)

from visualizador_cco import VisualizadorCCO

NOME_MODELO_PADRAO = "tree3D_Nterm512.vtk"

# Pasta onde este script (main.py) está localizado. Usar isso em vez de
# um caminho relativo "cru" evita erros quando o programa é executado
# a partir de outra pasta (ex: rodando "python main.py" de fora do
# diretório do projeto).
PASTA_SCRIPT = os.path.dirname(os.path.abspath(__file__))

# Lugares em que o modelo padrão pode estar. Tentamos cada um, na ordem,
# até achar o primeiro que exista. Isso permite tanto organizar os .vtk
# numa subpasta "dados_modelos3D/" quanto deixá-los soltos junto do
# código, sem precisar editar o main.py em cada caso.
PASTAS_CANDIDATAS = [
    PASTA_SCRIPT,
    os.path.join(PASTA_SCRIPT, "dados_modelos3D"),
    os.getcwd(),
    os.path.join(os.getcwd(), "dados_modelos3D"),
]

os.makedirs(os.path.join(PASTA_SCRIPT, "imagens"), exist_ok=True)


def localizar_modelo_padrao():
    """Procura o modelo padrão nas pastas candidatas e retorna o primeiro
    caminho encontrado. Se não encontrar em nenhuma, retorna o caminho
    mais "natural" (ao lado do script) só para a mensagem de erro do
    VisualizadorCCO ficar clara sobre onde ele procurou."""

    for pasta in PASTAS_CANDIDATAS:
        candidato = os.path.join(pasta, NOME_MODELO_PADRAO)
        if os.path.isfile(candidato):
            return candidato

    return os.path.join(PASTA_SCRIPT, NOME_MODELO_PADRAO)


if __name__ == "__main__":

    # Permite escolher o modelo pela linha de comando, ex:
    #   python main.py dados_modelos3D/tree3D_Nterm016.vtk
    #   python main.py tree3D_Nterm016.vtk
    # Se nenhum argumento for passado, usa o modelo padrão (procurado
    # automaticamente entre as pastas candidatas acima).
    if len(sys.argv) > 1:
        model_path = sys.argv[1]
    else:
        model_path = localizar_modelo_padrao()

    try:
        app = VisualizadorCCO(model_path)
        app.executar()
    except (FileNotFoundError, RuntimeError) as erro:
        print("\nErro ao iniciar o visualizador:")
        print(erro)
        sys.exit(1)