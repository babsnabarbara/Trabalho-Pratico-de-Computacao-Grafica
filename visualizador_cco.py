import os
import sys
import time
import pyvista as pv

class VisualizadorCCO:

    def __init__(self, arquivo, raio_tubo=None):

        # Malha original (linhas) convertida em tubos (superfícies com espessura)
        # Isso é necessário porque sombreamento (Flat/Gouraud/Phong) só faz
        # diferença visual em superfícies com normais, não em linhas puras.
        if not os.path.isfile(arquivo):
            raise FileNotFoundError(
                f"Arquivo nao encontrado: '{arquivo}'.\n"
                f"Verifique se o caminho esta correto e se o arquivo .vtk "
                f"foi colocado na pasta esperada."
            )

        try:
            malha_linhas = pv.read(arquivo)
        except Exception as erro:
            raise RuntimeError(
                f"Falha ao ler o arquivo '{arquivo}'. "
                f"Verifique se e um .vtk valido. Detalhe: {erro}"
            )

        # Guarda a malha original de LINHAS (antes de virar tubo). É ela que
        # tem a topologia "crua" do modelo CCO (pontos e segmentos), usada
        # pelo Módulo 1 (Leitura e Representação Geométrica) para calcular
        # número de pontos, número de segmentos e faixa de raio exigidos
        # no relatório. Depois de tubular, esses números mudam (o VTK gera
        # muito mais pontos/células só para desenhar a superfície do tubo),
        # então não podem ser lidos a partir de self.mesh.
        self.malha_linhas = malha_linhas
        self.arquivo = arquivo

        # Módulo 1 - Leitura e Representação Geométrica: calcula as
        # estatísticas exigidas no relatório (número de pontos, número de
        # segmentos, menor/maior raio) e já imprime no console assim que o
        # modelo é carregado.
        self.info_modelo = self.calcular_info_modelo()
        self.imprimir_info_modelo()

        # O tube() do PyVista só consegue variar a ESPESSURA GEOMÉTRICA do
        # tubo (não só a cor) se o atributo escalar estiver em point_data.
        # No arquivo original, "raio" vem em cell_data (um valor por
        # segmento). Convertemos aqui para point_data (interpolando o
        # valor entre os pontos vizinhos) só para essa finalidade -
        # continuamos usando o valor original de cell_data para as
        # estatísticas do Módulo 1 (mais fiel ao dado bruto).
        self.malha_linhas_pts = malha_linhas.cell_data_to_point_data()

        # Se o raio não for informado, calcula proporcionalmente ao tamanho
        # da árvore (0.3% da diagonal da bounding box). Esse valor agora é
        # usado como o raio MÍNIMO do tubo (não mais um raio fixo igual
        # para toda a árvore) - evita "bolhas" gigantes em árvores
        # pequenas ou tubos invisíveis em árvores grandes.
        if raio_tubo is None:
            raio_tubo = malha_linhas.length * 0.0015

        # Módulo 1 - representação por tubos com espessura geométrica real:
        # em vez de um raio de desenho igual para todos os segmentos, o
        # tube() varia a espessura de cada trecho proporcionalmente ao
        # valor do atributo "raio" daquele ponto (scalars="raio").
        # radius_factor controla a razão entre o tubo mais grosso e o mais
        # fino da árvore inteira (aqui, até 12x mais grosso no ponto de
        # maior raio do que no de menor raio).
        self.mesh = self.malha_linhas_pts.tube(
            radius=raio_tubo,
            scalars="raio",
            radius_factor=12,
            absolute=False,
        )

        self.plotter = pv.Plotter(window_size=(1200, 800))

        self.plotter.set_background("white")

        # Modulo 8 - registra o observador de profundidade (ver metodo
        # configurar_teste_profundidade) uma unica vez aqui. Ele fica
        # "ouvindo" o RenderWindow e roda antes de CADA frame desenhado,
        # entao nao precisa ser recriado a cada atualizar_cena().
        self.configurar_teste_profundidade()

        # Modulo 9 - a animacao de rotacao automatica NAO usa o timer
        # nativo do VTK (add_timer_event/CreateRepeatingTimer). Em algumas
        # instalacoes/plataformas (observado no Windows/Git Bash), esse
        # timer nunca dispara de verdade: o toggle troca o estado e
        # imprime normalmente, mas a arvore nunca gira - mesmo registrando
        # o timer so depois do interactor inicializado. Por isso usamos,
        # em vez disso, um LACO MANUAL de atualizacao dentro de executar()
        # (padrao "interactive_update" do PyVista): a cada iteracao do
        # loop, se self.animando estiver ligado, avancamos o angulo e
        # re-renderizamos manualmente, sem depender de timers do VTK.

        self.clip = False
        self.eixo_clip = "x"  # 'x' | 'y' | 'z'
        self.interpolacao = "gouraud"  # 'flat' | 'gouraud' | 'phong'

        # Modulo 8 - Remocao de Superficies Escondidas: liga/desliga o
        # teste de profundidade (Z-buffer) da GPU, para permitir comparar
        # visualmente a cena COM remocao de superficies escondidas (padrao)
        # e SEM ela (tecla 8). Ver configurar_teste_profundidade() logo
        # abaixo para detalhes de como isso e feito.
        self.sem_profundidade = False

        # Módulo 2 - Cores e Atributos Visuais: lista de mapas de cores
        # (colormaps) que podem ser alternados em tempo real com a tecla
        # M. Isso também é reaproveitado como o "recurso inovador" do
        # Módulo 9 (interface para trocar mapa de cores).
        self.mapas_cores = ["jet", "viridis", "plasma", "coolwarm", "rainbow"]
        self.indice_mapa_cor = 0

        # Módulo 3 - Transformações Geométricas: estado atual de
        # translação (deslocamento em X, Y, Z), rotação (ângulos em graus
        # em torno de X, Y, Z) e escala (fator uniforme) aplicados ao
        # modelo.
        #
        # ROTAÇÃO PADRÃO: no arquivo .vtk original, o vaso de maior raio
        # (a "raiz" da árvore) fica no topo e os ramos finos se abrem para
        # baixo - o que visualmente parece "de cabeça para baixo" para
        # quem espera uma árvore com o tronco embaixo. As coordenadas do
        # CCO não têm relação com "para cima/para baixo" do mundo real,
        # então giramos 180° em X só por preferência visual, deixando a
        # raiz embaixo tanto ao abrir o programa quanto ao apertar "0".
        self.rotacao_padrao = [180.0, 0.0, 0.0]
        self.translacao = [0.0, 0.0, 0.0]
        self.rotacao = list(self.rotacao_padrao)
        self.escala = 1.0

        # Tamanho de cada "passo" de transformação, proporcional ao
        # tamanho da árvore - assim o incremento faz sentido tanto para
        # árvores pequenas quanto grandes, sem precisar ajustar na mão.
        self.passo_translacao = malha_linhas.length * 0.05
        self.passo_rotacao = 10.0  # graus por tecla pressionada
        self.fator_escala = 1.1    # 10% de aumento/reducao por tecla

        # Modulo 9 (2a inovacao) - Animacao de rotacao automatica: gira o
        # modelo continuamente em torno do eixo Y, independente da rotacao
        # manual do Modulo 3 (por isso o angulo fica numa variavel PROPRIA,
        # em vez de mexer direto em self.rotacao - assim dar Play/Pause na
        # animacao nao interfere com a pose que o usuario ajustou a mao,
        # nem e apagado por um "resetar transformacoes").
        self.animando = False
        self.angulo_animacao = 0.0
        self.velocidade_animacao = 1.5  # graus por frame (~25 fps)
        self.ator_arvore = None  # referencia ao ator atual (ver atualizar_cena)

        # A luz é configurada dentro de atualizar_cena() (não aqui),
        # pois precisa ser recriada toda vez que a cena é redesenhada.
        self.atualizar_cena()

        self.configurar_teclado()

    # ----------------------------------
    # MODULO 1 - LEITURA E REPRESENTACAO GEOMETRICA
    # ----------------------------------

    def calcular_info_modelo(self):
        """Extrai as estatísticas do modelo exigidas no relatório do TP:
        número de pontos, número de segmentos e menor/maior valor de raio.

        Importante: no formato .vtk do CCO usado aqui, o raio é um atributo
        de CÉLULA (cell_data['raio']), ou seja, um valor por SEGMENTO da
        árvore - e não um valor por ponto. Por isso procuramos primeiro em
        cell_data e só depois em point_data, cobrindo os dois casos para
        que o código funcione mesmo se outro modelo CCO guardar o raio de
        forma diferente.
        """

        malha = self.malha_linhas

        n_pontos = malha.n_points
        n_segmentos = malha.n_cells

        # Procura um array chamado (ou parecido com) "raio"/"radius" em
        # cell_data primeiro (caso mais comum nos modelos fornecidos) e,
        # se não achar, em point_data.
        nomes_possiveis = ["raio", "radius", "Raio", "Radius", "RADIUS"]

        array_raio = None
        origem_raio = None

        for nome in nomes_possiveis:
            if nome in malha.cell_data:
                array_raio = malha.cell_data[nome]
                origem_raio = f"cell_data['{nome}'] (um valor por segmento)"
                break

        if array_raio is None:
            for nome in nomes_possiveis:
                if nome in malha.point_data:
                    array_raio = malha.point_data[nome]
                    origem_raio = f"point_data['{nome}'] (um valor por ponto)"
                    break

        if array_raio is not None:
            raio_min = float(array_raio.min())
            raio_max = float(array_raio.max())
            raio_medio = float(array_raio.mean())
        else:
            raio_min = raio_max = raio_medio = None
            origem_raio = "nao encontrado no arquivo .vtk"

        info = {
            "arquivo": os.path.basename(self.arquivo),
            "n_pontos": n_pontos,
            "n_segmentos": n_segmentos,
            "raio_min": raio_min,
            "raio_max": raio_max,
            "raio_medio": raio_medio,
            "origem_raio": origem_raio,
            # Comprimento total = soma do comprimento de todos os segmentos.
            # Serve tanto para o Módulo 1 (descrever a estrutura geométrica)
            # quanto pode ser reaproveitado depois no Módulo 9.
            "comprimento_total": float(malha.compute_cell_sizes(
                length=True, area=False, volume=False
            )["Length"].sum()),
            "bounds": malha.bounds,  # (xmin,xmax, ymin,ymax, zmin,zmax)
        }

        return info

    def imprimir_info_modelo(self):
        """Imprime no console as estatísticas exigidas pelo Módulo 1."""

        info = self.info_modelo
        xmin, xmax, ymin, ymax, zmin, zmax = info["bounds"]

        print("""
============================================
MODULO 1 - LEITURA E REPRESENTACAO GEOMETRICA
============================================""")
        print(f"Arquivo carregado .......... {info['arquivo']}")
        print(f"Numero de pontos ............ {info['n_pontos']}")
        print(f"Numero de segmentos (vasos) . {info['n_segmentos']}")

        if info["raio_min"] is not None:
            print(f"Raio minimo ................. {info['raio_min']:.6f}")
            print(f"Raio maximo ................. {info['raio_max']:.6f}")
            print(f"Raio medio ................... {info['raio_medio']:.6f}")
        else:
            print("Raio ........................ nao encontrado no arquivo")

        print(f"Origem do atributo de raio .. {info['origem_raio']}")
        print(f"Comprimento total da arvore .. {info['comprimento_total']:.6f}")
        print(
            "Dimensoes (bounding box) .... "
            f"X[{xmin:.4f}, {xmax:.4f}]  "
            f"Y[{ymin:.4f}, {ymax:.4f}]  "
            f"Z[{zmin:.4f}, {zmax:.4f}]"
        )
        print(
            "\nEstrutura: a arvore e representada como um grafo aciclico "
            "conectado (uma raiz e ramificacoes sucessivas), onde cada "
            "celula do tipo 'linha' liga dois pontos consecutivos e "
            "corresponde a um segmento de vaso sanguineo. O atributo de "
            "raio associado a cada segmento e usado no Modulo 2 para "
            "colorir a arvore proporcionalmente a espessura do vaso, e "
            "geometricamente para gerar os tubos (superficies) exibidos "
            "na cena.\n"
        )

        # Reforca a exibicao imediata no terminal (evita que a mensagem
        # fique presa em buffer ate a proxima interacao com a janela).
        sys.stdout.flush()

    def salvar_info_modelo(self, caminho="imagens/info_modelo.txt"):
        """Exporta as estatísticas para um .txt simples, para facilitar
        colar os números diretamente no relatório técnico (Módulo 1)."""

        os.makedirs(os.path.dirname(caminho), exist_ok=True)

        info = self.info_modelo
        xmin, xmax, ymin, ymax, zmin, zmax = info["bounds"]

        with open(caminho, "w", encoding="utf-8") as f:
            f.write("MODULO 1 - LEITURA E REPRESENTACAO GEOMETRICA\n")
            f.write("=" * 46 + "\n")
            f.write(f"Arquivo: {info['arquivo']}\n")
            f.write(f"Numero de pontos: {info['n_pontos']}\n")
            f.write(f"Numero de segmentos: {info['n_segmentos']}\n")
            if info["raio_min"] is not None:
                f.write(f"Raio minimo: {info['raio_min']:.6f}\n")
                f.write(f"Raio maximo: {info['raio_max']:.6f}\n")
                f.write(f"Raio medio: {info['raio_medio']:.6f}\n")
            f.write(f"Origem do atributo de raio: {info['origem_raio']}\n")
            f.write(
                f"Comprimento total da arvore: "
                f"{info['comprimento_total']:.6f}\n"
            )
            f.write(
                "Bounding box: "
                f"X[{xmin:.4f}, {xmax:.4f}] "
                f"Y[{ymin:.4f}, {ymax:.4f}] "
                f"Z[{zmin:.4f}, {zmax:.4f}]\n"
            )

        print(f"Informacoes do modelo salvas em: {caminho}")

    # ----------------------------------

    def configurar_luz(self):

        # Luz "headlight": acompanha sempre a posição da câmera, garantindo
        # que a árvore fique bem iluminada em QUALQUER ângulo de vista
        # (frontal, lateral, superior, isométrica). Sem isso, ao girar a
        # câmera, partes da árvore que ficam de costas para uma luz fixa
        # no espaço aparecem escuras — deixando a claridade inconsistente
        # entre as diferentes vistas da Parte A.
        self.luz_camera = pv.Light(
            light_type="headlight",
            color="white",
            intensity=0.6,
        )

        # Luz principal fixa na cena (requisito mínimo da Parte C: pelo
        # menos uma fonte de luz configurada). É ela que gera sombras e
        # reflexos direcionais reais, permitindo diferenciar visualmente
        # os modos de sombreamento Flat / Gouraud / Phong.
        self.luz = pv.Light(
            position=(1, 1, 1),
            focal_point=(0, 0, 0),
            color="white",
            intensity=0.8,
            light_type="scene light",
        )

        self.plotter.add_light(self.luz_camera)
        self.plotter.add_light(self.luz)

    # ----------------------------------
    # MODULO 8 - REMOCAO DE SUPERFICIES ESCONDIDAS
    # ----------------------------------

    def configurar_teste_profundidade(self):
        """Registra um observador de baixo nivel no RenderWindow que roda
        imediatamente ANTES de cada frame ser desenhado pela GPU.

        O PyVista/VTK ja faz remocao de superficies escondidas nativamente
        em qualquer cena 3D, usando o Z-BUFFER da placa de video: a cada
        pixel, a GPU testa a distancia (profundidade) de cada fragmento
        candido e so desenha o mais proximo da camera (glDepthFunc =
        GL_LEQUAL, que e o padrao usado internamente pelo VTK). E por isso
        que os tubos da arvore, mesmo se cruzando o tempo todo, aparecem
        corretamente sobrepostos - o de tras nunca "vaza" por cima do que
        esta na frente.

        Este metodo permite alternar esse teste em tempo real (tecla 8):
        - LIGADO  (GL_LEQUAL): comportamento padrao, com remocao correta
          de superficies escondidas.
        - DESLIGADO (GL_ALWAYS): qualquer fragmento passa no teste de
          profundidade, entao o que fica visivel na tela deixa de
          depender da distancia real a camera e passa a depender so da
          ORDEM em que a geometria foi enviada para desenho - produzindo
          sobreposicoes visualmente incorretas, especialmente nos varios
          cruzamentos de galhos do modelo CCO. E util para gerar a
          comparacao "com/sem Z-buffer" pedida no relatorio.
        """

        GL_LEQUAL = 0x0203  # padrao usado internamente pelo VTK
        GL_ALWAYS = 0x0207  # desativa o teste (tudo passa)

        def _ao_iniciar_frame(caller, event):
            estado_gl = self.plotter.ren_win.GetState()
            if self.sem_profundidade:
                estado_gl.vtkglDepthFunc(GL_ALWAYS)
            else:
                estado_gl.vtkglDepthFunc(GL_LEQUAL)

        self.plotter.ren_win.AddObserver("StartEvent", _ao_iniciar_frame)

    def toggle_profundidade(self):
        """Liga/desliga o teste de profundidade (Z-buffer) - tecla 8.

        Nao precisa reconstruir a cena (mesh, luzes, cores continuam os
        mesmos) - so re-renderizar, ja que o observador registrado em
        configurar_teste_profundidade() consulta self.sem_profundidade a
        cada frame e ajusta o comportamento da GPU automaticamente.
        """

        self.sem_profundidade = not self.sem_profundidade

        self.plotter.render()

        estado = (
            "DESLIGADO (sem Z-buffer - ordem de desenho manda)"
            if self.sem_profundidade
            else "LIGADO (com Z-buffer - padrao, remocao correta)"
        )
        print("Teste de profundidade (Modulo 8):", estado)
        sys.stdout.flush()

    # ----------------------------------

    def atualizar_cena(self):

        self.plotter.clear()

        # IMPORTANTE: self.plotter.clear() remove também as luzes da cena.
        # Por isso a luz precisa ser recriada aqui, toda vez que a cena
        # é redesenhada — caso contrário, a partir da segunda chamada
        # (troca de vista, sombreamento, clipping, etc.) a cena fica sem
        # luz e os modos Flat/Gouraud/Phong deixam de ter diferença visual.
        self.configurar_luz()

        # IMPORTANTE: usar .copy(deep=False) em vez de "mesh = self.mesh".
        # O PyVista, quando smooth_shading=True, calcula normais e as
        # grava PERMANENTEMENTE no point_data da malha passada
        # (add_mesh(..., smooth_shading=True) -> compute_normals(inplace=True)).
        # Sem essa cópia, self.mesh ficaria "contaminado" com normais suaves
        # já na primeira renderização em Gouraud/Phong, e o modo Flat nunca
        # mais conseguiria voltar a ficar realmente facetado (o VTK continuaria
        # usando as normais antigas, gravadas ali dentro, mesmo com
        # smooth_shading=False).
        mesh = self.mesh.copy(deep=False)

        # Remove normais eventualmente herdadas da cópia rasa acima, para
        # garantir que cada troca de modo (F/G/H) parta de um estado limpo
        # e o Flat realmente apareça facetado.
        if "Normals" in mesh.point_data:
            mesh.point_data.remove("Normals")

        if self.clip:
            mesh = mesh.clip(normal=self.eixo_clip)

        # Módulo 2 - Cores e Atributos Visuais: em vez de uma cor sólida
        # fixa, colorimos cada segmento (tubo) proporcionalmente ao seu
        # raio real (atributo "raio", vindo de cell_data). O tube() do
        # PyVista propaga automaticamente esse atributo da malha de linhas
        # original para a malha de tubos, então basta usar scalars="raio".
        #
        # clim é fixado com o raio mínimo/máximo do MODELO INTEIRO (não da
        # malha já recortada pelo clipping), para que a escala de cores
        # não mude quando o usuário ativa o clipping - assim a mesma cor
        # sempre representa o mesmo raio, em qualquer estado da cena.
        raio_min = self.info_modelo["raio_min"]
        raio_max = self.info_modelo["raio_max"]

        ator = self.plotter.add_mesh(
            mesh,
            scalars="raio",
            cmap=self.mapa_cor_atual,
            clim=[raio_min, raio_max] if raio_min is not None else None,
            smooth_shading=(self.interpolacao != "flat"),
            ambient=0.35,
            diffuse=0.65,
            specular=0.4,
            specular_power=20,
            scalar_bar_args={
                "title": f"Raio do vaso ({self.mapa_cor_atual})",
                "n_labels": 5,
            },
        )

        # Define o modo de interpolação real (Flat / Gouraud / Phong).
        # IMPORTANTE: evitamos "ator.prop.interpolation = self.interpolacao"
        # (atribuir uma string) porque, dependendo da versão do PyVista, esse
        # setter pode não reconhecer a string em minúsculas e falhar
        # SILENCIOSAMENTE — sem erro no terminal, mas também sem aplicar o
        # modo escolhido, fazendo Flat/Gouraud/Phong parecerem idênticos.
        # Chamar os métodos nativos do VTK diretamente é garantido:
        if self.interpolacao == "flat":
            ator.prop.SetInterpolationToFlat()
        elif self.interpolacao == "gouraud":
            ator.prop.SetInterpolationToGouraud()
        elif self.interpolacao == "phong":
            ator.prop.SetInterpolationToPhong()

        # Guarda a referencia do ator atual - necessaria para a animacao
        # (Modulo 9) poder girar o modelo a cada frame SEM precisar
        # reconstruir a cena inteira (o que seria lento demais a ~25 fps).
        self.ator_arvore = ator

        # Módulo 3 - Transformações Geométricas + Módulo 9 - Animação:
        # aplica translação, rotação (manual + automática) e escala
        # diretamente no ATOR (não na geometria da malha). Ver
        # _aplicar_transformacoes_no_ator() para detalhes.
        #
        # IMPORTANTE: como self.plotter.clear() (no início deste método)
        # apaga o ator antigo, isso precisa ser reaplicado AQUI, toda vez
        # que a cena é redesenhada - senão a árvore voltaria a
        # posição/rotação/escala original a cada troca de vista, cor,
        # sombreamento, etc.
        self._aplicar_transformacoes_no_ator()

        self.plotter.add_axes()

        self.plotter.render()

    # ----------------------------------

    def configurar_teclado(self):

        self.plotter.add_key_event("1", self.frontal)
        self.plotter.add_key_event("2", self.lateral)
        self.plotter.add_key_event("3", self.superior)
        self.plotter.add_key_event("4", self.isometrica)

        self.plotter.add_key_event("o", self.ortografica)
        self.plotter.add_key_event("p", self.perspectiva)

        self.plotter.add_key_event("f", self.flat)
        self.plotter.add_key_event("g", self.gouraud)
        self.plotter.add_key_event("h", self.phong)

        self.plotter.add_key_event("c", self.toggle_clip)
        self.plotter.add_key_event("x", lambda: self.definir_eixo_clip("x"))
        self.plotter.add_key_event("y", lambda: self.definir_eixo_clip("y"))
        self.plotter.add_key_event("z", lambda: self.definir_eixo_clip("z"))

        self.plotter.add_key_event("s", self.salvar)
        self.plotter.add_key_event("i", self.mostrar_info)
        self.plotter.add_key_event("m", self.proximo_mapa_cor)

        # Modulo 8 - Remocao de Superficies Escondidas
        self.plotter.add_key_event("8", self.toggle_profundidade)

        # Modulo 9 - Animacao de rotacao automatica (2a inovacao).
        # Registramos tanto "a" quanto "A" (maiusculo) como reforco: em
        # alguns layouts de teclado / com Caps Lock ativo, o VTK pode
        # reportar o keysym em maiusculo mesmo sem Shift ser pressionado.
        self.plotter.add_key_event("a", self.toggle_animacao)
        self.plotter.add_key_event("A", self.toggle_animacao)

        # Módulo 3 - Transformações Geométricas
        # Translação: setas do teclado (X/Y) + Page Up/Page Down (Z)
        self.plotter.add_key_event("Left", lambda: self.transladar("x", -1))
        self.plotter.add_key_event("Right", lambda: self.transladar("x", 1))
        self.plotter.add_key_event("Down", lambda: self.transladar("y", -1))
        self.plotter.add_key_event("Up", lambda: self.transladar("y", 1))
        self.plotter.add_key_event("Next", lambda: self.transladar("z", -1))
        self.plotter.add_key_event("Prior", lambda: self.transladar("z", 1))

        # Rotação: R/V (eixo X), T/B (eixo Y), U/N (eixo Z)
        self.plotter.add_key_event("r", lambda: self.rotacionar("x", 1))
        self.plotter.add_key_event("v", lambda: self.rotacionar("x", -1))
        self.plotter.add_key_event("t", lambda: self.rotacionar("y", 1))
        self.plotter.add_key_event("b", lambda: self.rotacionar("y", -1))
        self.plotter.add_key_event("u", lambda: self.rotacionar("z", 1))
        self.plotter.add_key_event("n", lambda: self.rotacionar("z", -1))

        # Escala: K aumenta, J diminui
        self.plotter.add_key_event("k", lambda: self.escalar(self.fator_escala))
        self.plotter.add_key_event("j", lambda: self.escalar(1 / self.fator_escala))

        # Reset das transformações
        self.plotter.add_key_event("0", self.resetar_transformacoes)

        # O VTK registra atalhos de teclado padrão por baixo dos panos
        # (ex: '3' alterna renderização estéreo, 'f' voa até o ponto sob
        # o cursor, 'c' alterna entre manipular câmera/ator com o mouse).
        # Esses atalhos disparam JUNTO com os nossos e causam efeitos
        # visuais indesejados (como o fundo magenta em modo estéreo).
        # Removemos os observadores padrão de CharEvent para que apenas
        # os atalhos definidos acima funcionem.
        self.plotter.iren.interactor.RemoveObservers("CharEvent")

    # ----------------------------------
    # MODULO 3 - TRANSFORMACOES GEOMETRICAS
    # (+ MODULO 9 - ANIMACAO DE ROTACAO AUTOMATICA)
    # ----------------------------------

    def _aplicar_transformacoes_no_ator(self):
        """Aplica translacao e escala (Modulo 3), a rotacao manual
        (Modulo 3) E o angulo da animacao automatica (Modulo 9) no ator
        atual, sem precisar reconstruir a cena.

        A rotacao automatica gira em torno do eixo Y (indice 1) e e
        somada a rotacao manual do usuario - por isso as duas convivem
        sem conflito: pausar a animacao nao muda a pose manual, e girar
        manualmente (R/V/T/B/U/N) nao afeta o angulo da animacao.
        """

        if self.ator_arvore is None:
            return

        rotacao_total = list(self.rotacao)
        rotacao_total[1] = (rotacao_total[1] + self.angulo_animacao) % 360

        self.ator_arvore.position = tuple(self.translacao)
        self.ator_arvore.orientation = tuple(rotacao_total)
        self.ator_arvore.scale = (self.escala, self.escala, self.escala)

    def _passo_animacao(self, step):
        """Callback do timer (registrado uma unica vez no __init__),
        chamado a cada ~40ms durante toda a execucao do programa.

        So gira o modelo de fato quando self.animando estiver ligado
        (tecla A) - do contrario, retorna imediatamente sem custo.
        """

        if not self.animando:
            return

        self.angulo_animacao = (
            self.angulo_animacao + self.velocidade_animacao
        ) % 360

        self._aplicar_transformacoes_no_ator()
        self.plotter.render()

    def toggle_animacao(self):
        """Liga/pausa a animacao de rotacao automatica - tecla A.

        Recurso inovador do Modulo 9 (2a inovacao do grupo, junto com a
        troca de mapa de cores do Modulo 2): demonstra a arvore girando
        continuamente, sem precisar de interacao manual do usuario -
        util especialmente para a apresentacao oral e para gravar um
        video/GIF da visualizacao.
        """

        self.animando = not self.animando

        estado = "LIGADA" if self.animando else "PAUSADA"
        print(f"Animacao de rotacao automatica (Modulo 9): {estado}")
        sys.stdout.flush()

    # ----------------------------------

    def transladar(self, eixo, sinal):
        """Desloca o modelo ao longo de um eixo (x, y ou z).
        sinal = +1 (sentido positivo) ou -1 (sentido negativo)."""

        indice = {"x": 0, "y": 1, "z": 2}[eixo]

        self.translacao[indice] += self.passo_translacao * sinal

        self.atualizar_cena()

        print(
            "Translacao (x,y,z):",
            tuple(round(v, 5) for v in self.translacao),
        )

    def rotacionar(self, eixo, sinal):
        """Rotaciona o modelo em torno de um eixo (x, y ou z), em passos
        de self.passo_rotacao graus. sinal = +1 ou -1 define o sentido."""

        indice = {"x": 0, "y": 1, "z": 2}[eixo]

        self.rotacao[indice] = (
            self.rotacao[indice] + self.passo_rotacao * sinal
        ) % 360

        self.atualizar_cena()

        print(
            "Rotacao em graus (x,y,z):",
            tuple(round(v, 1) for v in self.rotacao),
        )

    def escalar(self, fator):
        """Multiplica a escala atual do modelo pelo fator informado
        (ex: 1.1 aumenta 10%, 1/1.1 reduz 10%)."""

        self.escala *= fator

        # Evita que a escala chegue a zero ou fique negativa (o que
        # inverteria/sumiria com o modelo de forma confusa visualmente).
        self.escala = max(self.escala, 0.05)

        self.atualizar_cena()

        print(f"Escala: {self.escala:.3f}x")

    def resetar_transformacoes(self):
        """Volta translacao e escala ao estado original, e a rotacao para
        a pose padrao (raiz embaixo) - tecla 0."""

        self.translacao = [0.0, 0.0, 0.0]
        self.rotacao = list(self.rotacao_padrao)
        self.escala = 1.0

        self.atualizar_cena()

        print("Transformacoes resetadas (translacao=0, rotacao=padrao, escala=1)")

    # ----------------------------------
    # CAMERAS
    # ----------------------------------

    def frontal(self):
        self.plotter.view_xy()

    def lateral(self):
        self.plotter.view_yz()

    def superior(self):
        self.plotter.view_xz()

    def isometrica(self):
        self.plotter.camera_position = "iso"

    # ----------------------------------
    # PROJECAO
    # ----------------------------------

    def ortografica(self):

        self.plotter.enable_parallel_projection()

        self.plotter.render()

        print("Projecao Ortografica")

    def perspectiva(self):

        self.plotter.disable_parallel_projection()

        self.plotter.render()

        print("Projecao Perspectiva")

    # ----------------------------------
    # MODULO 2 - CORES E ATRIBUTOS VISUAIS
    # ----------------------------------

    @property
    def mapa_cor_atual(self):
        return self.mapas_cores[self.indice_mapa_cor]

    def proximo_mapa_cor(self):
        """Alterna para o proximo mapa de cores da lista (tecla M).

        Isso atende ao Modulo 2 (mapa de cores continuo) permitindo
        comparar visualmente diferentes paletas, e tambem serve como o
        recurso inovador do Modulo 9 (interface para trocar mapa de
        cores).
        """

        self.indice_mapa_cor = (self.indice_mapa_cor + 1) % len(self.mapas_cores)

        self.atualizar_cena()

        print("Mapa de cores:", self.mapa_cor_atual)

    # ----------------------------------
    # SOMBREAMENTO
    # ----------------------------------

    def flat(self):

        self.interpolacao = "flat"

        self.atualizar_cena()

        print("Sombreamento: Flat")

    def gouraud(self):

        self.interpolacao = "gouraud"

        self.atualizar_cena()

        print("Sombreamento: Gouraud")

    def phong(self):

        self.interpolacao = "phong"

        self.atualizar_cena()

        print("Sombreamento: Phong")

    # ----------------------------------
    # CLIPPING
    # ----------------------------------

    def toggle_clip(self):

        self.clip = not self.clip

        self.atualizar_cena()

        print("Clipping:", self.clip, "| Eixo:", self.eixo_clip.upper())

    def definir_eixo_clip(self, eixo):

        self.eixo_clip = eixo

        if self.clip:
            self.atualizar_cena()

        print("Eixo de clipping definido:", eixo.upper())

    # ----------------------------------
    # SCREENSHOT
    # ----------------------------------

    def salvar(self):

        nome = input("Nome da imagem: ")

        caminho = f"imagens/{nome}.png"

        self.plotter.screenshot(caminho)

        print("Imagem salva:", caminho)

    # ----------------------------------

    def mostrar_info(self):
        """Atalho (tecla I) para reimprimir as estatísticas do Módulo 1
        no console e salvá-las em imagens/info_modelo.txt, prontas para
        serem coladas no relatório técnico."""

        self.imprimir_info_modelo()
        self.salvar_info_modelo()

    # ----------------------------------

    def executar(self):

        print("""
============================================
VISUALIZADOR CCO
============================================

1 - Vista frontal

2 - Vista lateral

3 - Vista superior

4 - Vista isometrica

O - Ortografica

P - Perspectiva

F - Flat

G - Gouraud

H - Phong

C - Ativar/desativar clipping
X/Y/Z - Definir eixo do clipping

S - Salvar imagem
I - Mostrar/salvar informacoes do modelo (Modulo 1)
M - Trocar mapa de cores (jet/viridis/plasma/coolwarm/rainbow)
8 - Ligar/desligar teste de profundidade / Z-buffer (Modulo 8)
A - Ligar/pausar animacao de rotacao automatica (Modulo 9)

TRANSFORMACOES GEOMETRICAS (Modulo 3):
Setas - Translacao em X/Y
Page Up/Page Down - Translacao em Z
R/V - Rotacao em X (+/-)
T/B - Rotacao em Y (+/-)
U/N - Rotacao em Z (+/-)
K/J - Escala (+/-)
0 - Resetar transformacoes (volta a pose padrao, raiz embaixo)

Mouse:
Botao esquerdo -> Rotacionar
Botao direito -> Zoom
Botao do meio -> Pan

============================================
""")

        # Modulo 9 - Animacao de rotacao automatica: em vez de
        # plotter.show() bloqueante + timer do VTK (que nao disparava de
        # forma confiavel), usamos show(interactive_update=True). Isso
        # abre a janela SEM bloquear o programa, e devolve o controle
        # para o laco abaixo, que roda ate a janela ser fechada.
        #
        # A cada iteracao do laco (a ~25 fps):
        #   - se a animacao estiver ligada (tecla A), avancamos o angulo
        #     de rotacao e re-renderizamos via _passo_animacao();
        #   - senao, so processamos os eventos pendentes da janela
        #     (mouse, teclado) com plotter.update(), para a interface
        #     continuar respondendo normalmente mesmo com a animacao
        #     pausada.
        #
        # O laco termina sozinho quando a janela e fechada: nesse ponto,
        # qualquer chamada a plotter.update()/render() passa a falhar
        # (a janela do VTK ja foi destruida), e capturamos isso para
        # sair do laco sem mostrar um erro para o usuario.
        self.plotter.show(auto_close=False, interactive_update=True)

        intervalo_frame = 0.04  # ~25 fps

        while True:
            try:
                if self.animando:
                    self._passo_animacao(None)
                else:
                    self.plotter.update()
            except Exception:
                # Janela fechada pelo usuario (botao X) - encerra o laco.
                break

            time.sleep(intervalo_frame)

        self.plotter.close()