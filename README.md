# Visualizador CCO — Árvores Arteriais em 3D

Trabalho Prático Final da disciplina de **Computação Gráfica** (UFOP — Departamento de Computação/DECOM), sob orientação do Prof. Dr. Rafael Alves Bonfim de Queiroz.

Aplicação interativa em **Python + PyVista** para visualização, análise e exploração de árvores arteriais geradas pelo método **CCO (Constrained Constructive Optimization)**, a partir de modelos no formato `.vtk`.

---

## Sobre o projeto

Vasos sanguíneos formam estruturas em árvore altamente ramificadas, cuja geometria pode ser gerada computacionalmente pelo método CCO. Este projeto lê esses modelos e os representa como tubos 3D com espessura geométrica proporcional ao raio real de cada vaso, permitindo explorar a árvore por diferentes câmeras, projeções, modos de iluminação, cores, recortes e transformações — cobrindo o pipeline gráfico clássico estudado na disciplina.

## Funcionalidades

- **Leitura e representação geométrica** — carrega o `.vtk` e extrai estatísticas do modelo (número de pontos, número de segmentos, raio mínimo/máximo, comprimento total da árvore); representação por tubos com espessura proporcional ao raio real de cada segmento.
- **Cores e atributos visuais** — coloração contínua proporcional ao raio dos vasos, com 5 mapas de cores (colormaps) alternáveis em tempo real.
- **Transformações geométricas** — translação, rotação e escala do modelo, controladas por teclado.
- **Câmera e posicionamento do observador** — vistas frontal, lateral, superior e isométrica.
- **Projeções** — alternância entre projeção ortográfica e perspectiva.
- **Iluminação e sombreamento** — modos Flat, Gouraud e Phong, com luz de câmera e luz de cena.
- **Recorte (clipping)** — corte interativo da árvore por qualquer um dos eixos X/Y/Z.
- **Remoção de superfícies escondidas** — teste de profundidade (Z-buffer) ativável/desativável para comparação visual.
- **Recurso inovador** — animação de rotação automática da árvore + interface para troca de mapa de cores.

## Tecnologias

- [Python 3](https://www.python.org/)
- [PyVista](https://docs.pyvista.org/) (visualização 3D baseada em VTK)

## Modelos disponíveis

Modelos de árvores CCO em `.vtk`, com número crescente de terminais (`Nterm`):

```
tree3D_Nterm016.vtk
tree3D_Nterm032.vtk
tree3D_Nterm064.vtk
tree3D_Nterm128.vtk
tree3D_Nterm256.vtk
tree3D_Nterm512.vtk
```

## Como executar

```bash
pip install pyvista

# roda com o modelo padrão
python main.py

# ou escolhendo outro modelo
python main.py tree3D_Nterm016.vtk
```

## Controles

| Tecla | Ação |
|---|---|
| `1` / `2` / `3` / `4` | Vista frontal / lateral / superior / isométrica |
| `O` / `P` | Projeção ortográfica / perspectiva |
| `F` / `G` / `H` | Sombreamento Flat / Gouraud / Phong |
| `C` | Ativa/desativa o recorte (clipping) |
| `X` / `Y` / `Z` | Define o eixo do recorte |
| `M` | Alterna o mapa de cores |
| `8` | Liga/desliga o teste de profundidade (Z-buffer) |
| `A` | Liga/pausa a animação de rotação automática |
| `S` | Salva um screenshot da cena atual |
| `I` | Mostra e salva as informações do modelo carregado |
| Setas, `Page Up` / `Page Down` | Translação nos eixos X, Y, Z |
| `R`/`V`, `T`/`B`, `U`/`N` | Rotação nos eixos X, Y, Z (+/−) |
| `K` / `J` | Aumenta/diminui a escala |
| `0` | Reseta as transformações |
| Mouse (botão esquerdo / direito / meio) | Rotaciona / zoom / pan da câmera |

## Estrutura do repositório

```
.
├── main.py                  # ponto de entrada da aplicação
├── visualizador_cco.py       # classe VisualizadorCCO (lógica principal)
├── dados_modelos3D/          # modelos .vtk de árvores CCO
├── imagens/                  # screenshots e informações exportadas
└── README.md
```

## Autores

- Bárbara Rodrigues Mateus — 20.2.4185
- Luisa Ribeiro Notaro — 22.1.4161
- Luiz Victor da Silva Lima — 22.2.4070
- Gabriel Carlos Silva — 23.1.4016

