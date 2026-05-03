# PDF Bilingual Book Generator

Ferramenta local para Ubuntu que recebe um PDF, extrai texto, divide em blocos, traduz com Argos Translate e gera HTML/PDF bilingue para estudo. O documento original nao e editado: a aplicacao reconstrui o conteudo em HTML e exporta um novo arquivo com o texto original e a traducao.

Uso previsto: pessoal e local. A ferramenta nao implementa compartilhamento publico, biblioteca online, upload para nuvem ou distribuicao de livros traduzidos.

## Recursos

- Traducao local/offline com Argos Translate
- Suporte a ingles -> portugues e portugues -> ingles
- OCR opcional com Tesseract para PDFs escaneados
- Cache em SQLite para continuar de onde parou
- Processamento por rodadas para livros grandes
- Modo automatico com pausa/retomada
- Exportacao de HTML e PDF bilingue
- Tradutor Mock para testar o fluxo sem traduzir
- Tradutores Gemini/OpenAI opcionais para comparacao

## Stack

- Python
- Streamlit para interface local
- PyMuPDF para extracao de texto
- Jinja2 para HTML
- WeasyPrint para gerar PDF
- SQLite para cache e retomada
- Traducao principal com Argos local/offline
- Camada abstrata de traducao com Mock e tradutores opcionais via API
- Tesseract OCR para PDFs baseados em imagem

## Instalar no Ubuntu

Instale dependencias de sistema usadas pelo WeasyPrint:

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip libpango-1.0-0 libpangoft2-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 libffi-dev shared-mime-info
```

Para PDFs escaneados ou baseados em imagem, instale tambem o Tesseract OCR:

```bash
sudo apt install -y tesseract-ocr tesseract-ocr-eng tesseract-ocr-por
```

Crie o ambiente virtual e instale as dependencias Python:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Rode a aplicacao:

```bash
streamlit run app.py
```

Abra a URL local mostrada pelo Streamlit, normalmente `http://localhost:8501`.

## Uso

1. Suba um arquivo `.pdf`.
2. Escolha `Argos` como tradutor.
3. Se o PDF estiver em portugues e voce quiser traduzir para ingles, ative `Traduzir portugues -> ingles`.
4. Defina `Traduzir ate a pagina`.
5. Use `Processar proxima rodada` para traduzir um lote.
6. Use `Automatico: iniciar` para processar pagina por pagina ate a meta.
7. Acompanhe a previa bilingue.
8. Gere HTML/PDF do intervalo ou PDF consolidado.

Para livros grandes, processe em lotes pequenos. Com OCR, 1 a 5 paginas por rodada costuma ser mais estavel.

## Traducao Mock

O tradutor Mock nao chama API externa e nao traduz de verdade. Ele serve apenas para validar o fluxo inteiro sem custo: upload, extracao, chunking, cache, previa, HTML e PDF. Ele retorna:

```text
[TRADUCAO MOCK] texto original
```

Se o texto em `PT` aparecer em ingles com esse prefixo, a aplicacao esta em modo Mock. Para traducao real, use `Argos`.

## Traducao local com Argos

O tradutor `Argos` usa a biblioteca Argos Translate no proprio computador. Depois que os pacotes de idioma sao baixados, a traducao roda localmente, sem limite de API, quota ou custo por chamada.

Pares ja usados no projeto:

- `en -> pt`
- `pt -> en`

Na primeira traducao de um par novo, o app tenta baixar e instalar automaticamente o pacote de idioma.

Se quiser impedir instalacao automatica de pacote de idioma, configure:

```env
ARGOS_AUTO_INSTALL=0
```

## PDFs escaneados e OCR

PDFs baseados em imagem nao possuem texto embutido. Para esses arquivos, o app usa OCR com Tesseract. Instale no Ubuntu:

```bash
sudo apt install -y tesseract-ocr tesseract-ocr-eng tesseract-ocr-por
```

Confirme os idiomas instalados:

```bash
tesseract --list-langs
```

Os idiomas esperados sao:

```text
eng
por
```

Se um livro ja foi marcado como vazio antes de instalar OCR, use `Manutencao do cache` -> `Limpar paginas vazias deste livro` e processe novamente.

## Tradutores via API opcionais

O app ainda possui suporte a Gemini e OpenAI para comparacao, mas o fluxo recomendado e usar `Argos`. Para exibir esses tradutores na interface, abra `Tradutores via API` e marque `Mostrar Gemini/OpenAI`.

### Configurar Gemini

Copie `.env.example` para `.env`:

```bash
cp .env.example .env
```

Preencha:

```env
GEMINI_API_KEY=sua-chave
GEMINI_MODEL=gemini-flash-lite-latest
```

Depois selecione `Gemini` na interface.

### Configurar OpenAI

Copie `.env.example` para `.env`:

```bash
cp .env.example .env
```

Preencha:

```env
OPENAI_API_KEY=sua-chave
OPENAI_MODEL=gpt-4.1-mini
```

Depois selecione `OpenAI` na interface. Nenhuma chave fica hardcoded no codigo.

Prompt usado internamente:

```text
Traduza o texto abaixo do ingles para portugues do Brasil. Mantenha o sentido tecnico, nao resuma, nao adicione explicacoes, preserve numeros, formulas, unidades, nomes proprios e siglas. Retorne somente a traducao.
```

## Variaveis de ambiente

Copie `.env.example` para `.env` se quiser customizar:

```bash
cp .env.example .env
```

Opcoes principais:

```env
ARGOS_AUTO_INSTALL=1
OCR_ENABLED=1
OCR_ZOOM=2.0
```

`OCR_ZOOM` controla a resolucao usada para renderizar a pagina antes do OCR. Valores maiores podem melhorar leitura, mas deixam o processamento mais lento.

## Cache e retomada

O banco SQLite fica em:

```text
data/pdf_reader.db
```

Cada chunk e salvo com status:

- `extracted`
- `translated`
- `failed`

Ao processar novamente o mesmo PDF e o mesmo intervalo, chunks ja traduzidos nao sao retraduzidos. Use `Reprocessar intervalo` apenas quando quiser apagar a traducao cacheada daquele intervalo e traduzir de novo.

Controles uteis:

- `Processar proxima rodada`: processa o proximo lote de paginas.
- `Automatico: iniciar`: processa uma pagina por ciclo e continua sozinho.
- `Parar automatico`: pausa o automatico.
- `Limpar chunks com falha`: libera chunks marcados como erro.
- `Limpar paginas vazias deste livro`: remove paginas marcadas como sem texto, util apos instalar OCR.
- `Zerar banco`: apaga livros, chunks, traducoes e progresso salvo.

## Saidas

Uploads locais:

```text
data/uploads/
```

Arquivos gerados:

```text
data/outputs/
```

Nome dos PDFs exportados:

```text
nome-original_bilingue_pag_1_20.pdf
```

O app bloqueia exportacao vazia quando o intervalo ainda nao tem texto processado.

## Limitacoes conhecidas

- Imagens do livro original ainda nao sao incluidas no PDF gerado.
- A reconstrucao preserva a ordem dos blocos, mas nao tenta replicar fielmente o layout visual do PDF original.
- OCR pode errar caracteres, pontuacao e quebras de paragrafo.
- OCR em livros grandes pode ser lento.
- Cabecalhos e rodapes sao classificados de forma simples; a ferramenta evita logica fragil para remover conteudo automaticamente.
- Tabelas complexas, notas laterais e multiplas colunas podem exigir revisao manual.
- A qualidade do Argos pode variar conforme o texto.

## Testes manuais obrigatorios

Teste 1:

1. Rode `streamlit run app.py`.
2. Suba um PDF pequeno com texto selecionavel.
3. Selecione `Mock (teste - nao traduz)` ou `Argos`.
4. Em `Modo avancado`, processe paginas 1 a 2.
5. Confira a previa bilingue.
6. Clique em `Gerar PDF do intervalo`.
7. Baixe o PDF gerado.

Teste 2:

1. Rode novamente o mesmo PDF.
2. Processe as mesmas paginas.
3. Confirme nos logs a mensagem de cache: `Todos os chunks deste intervalo ja estavam traduzidos no cache.`
4. Confirme que os chunks nao foram retraduzidos.

Teste 3:

1. Escolha um intervalo invalido, como pagina inicial maior que pagina final.
2. Clique em `Processar intervalo manual`.
3. Confirme a mensagem amigavel de intervalo invalido.

Teste 4:

1. Suba um PDF escaneado ou sem texto selecionavel.
2. Processe uma pagina.
3. Se Tesseract estiver instalado, confirme que o OCR extrai texto e envia para traducao.
4. Se Tesseract nao estiver instalado, confirme a mensagem pedindo `tesseract-ocr`.

## Estrutura

```text
pdf-bilingue-reader/
├── app.py
├── requirements.txt
├── README.md
├── .env.example
├── data/
│   ├── uploads/
│   ├── outputs/
│   └── pdf_reader.db
├── src/
│   ├── config.py
│   ├── database.py
│   ├── models.py
│   ├── pdf_extractor.py
│   ├── text_chunker.py
│   ├── translator/
│   ├── bilingual_service.py
│   ├── html_renderer.py
│   └── pdf_generator.py
└── templates/
    └── bilingual_book.html
```

O arquivo `data/pdf_reader.db` e criado automaticamente na primeira execucao.

## Arquivos que normalmente nao entram no Git

Os arquivos abaixo sao dados locais de execucao e costumam ficar fora do repositorio:

```text
.venv/
data/uploads/
data/outputs/
data/*.db
__pycache__/
```

## Uso responsavel

Este projeto foi criado para uso pessoal e local, como apoio a estudo. Ele nao implementa biblioteca publica, compartilhamento de livros, upload para nuvem ou distribuicao de obras traduzidas.
