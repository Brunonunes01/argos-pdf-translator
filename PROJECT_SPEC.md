# PDF Bilingual Book Generator - Especificacao Detalhada

## 1. Objetivo do projeto

O objetivo do projeto e criar uma ferramenta local para Ubuntu que permita transformar um livro em PDF escrito em ingles em um novo PDF bilingue de estudo.

O novo PDF deve conter, para cada bloco de texto:

- o texto original em ingles;
- a traducao para portugues do Brasil logo abaixo;
- uma estrutura limpa, organizada e legivel;
- layout priorizando estudo e leitura, nao fidelidade visual absoluta ao PDF original.

A ferramenta nao deve editar o PDF original, nao deve escrever por cima das paginas originais e nao deve gerar uma camada sobreposta. Ela deve extrair o conteudo textual, reconstruir esse conteudo em HTML e entao gerar um novo PDF a partir desse HTML.

O uso previsto e pessoal e local. O projeto nao deve implementar compartilhamento publico, biblioteca online, upload para nuvem ou distribuicao de livros traduzidos.

## 2. Nome do produto

Nome atual:

```text
PDF Bilingual Book Generator
```

Nome anterior usado no inicio do projeto:

```text
PDF Bilingue Reader
```

O nome recomendado para a interface e documentacao daqui em diante e `PDF Bilingual Book Generator`.

## 3. Problema que a ferramenta resolve

O usuario possui livros grandes em PDF, possivelmente com 500 a 1000 paginas, e quer estudar o conteudo em ingles com traducao em portugues logo abaixo.

O fluxo manual seria muito trabalhoso:

1. copiar texto pagina por pagina;
2. mandar traduzir;
3. organizar EN/PT;
4. montar um novo documento;
5. repetir centenas de vezes.

A aplicacao automatiza esse fluxo, mantendo cache local para que o usuario possa processar o livro aos poucos.

## 4. Principios fundamentais

### 4.1. Nunca editar o PDF original

O PDF original deve ser tratado apenas como fonte de leitura.

Errado:

- abrir o PDF original e inserir traducao nas paginas;
- tentar sobrepor texto traduzido no layout original;
- salvar por cima do arquivo enviado.

Certo:

- extrair blocos de texto;
- gerar uma representacao HTML limpa;
- gerar um novo PDF bilingue.

### 4.2. Priorizar legibilidade

O novo PDF deve ser confortavel para estudo.

Prioridade alta:

- ordem correta dos blocos;
- ingles e portugues bem separados;
- margens confortaveis;
- fonte legivel;
- quebras de pagina previsiveis.

Prioridade baixa:

- copiar exatamente posicao visual do PDF original;
- preservar colunas complexas;
- preservar diagramas ou tabelas com fidelidade perfeita.

### 4.3. Processar livros grandes por partes

O app nao deve tentar processar 500 ou 1000 paginas de uma vez.

O processamento correto e por rodadas/lotes:

```text
1-10
11-20
21-30
...
```

ou, se houver falha em alguma pagina:

```text
pagina incompleta primeiro
depois volta ao lote normal
```

## 5. Stack obrigatoria

Backend:

```text
Python
```

Interface:

```text
Streamlit
```

Extracao do PDF:

```text
PyMuPDF / fitz
```

Template HTML:

```text
Jinja2
```

Geracao de PDF final:

```text
WeasyPrint
```

Banco local:

```text
SQLite
```

Traducao:

```text
Camada abstrata Translator
Implementacoes: Mock, Gemini, OpenAI
```

## 6. Estrutura atual do projeto

```text
pdf-bilingue-reader/
├── app.py
├── requirements.txt
├── README.md
├── PROJECT_SPEC.md
├── .env
├── .env.example
├── .gitignore
├── data/
│   ├── uploads/
│   ├── outputs/
│   └── pdf_reader.db
├── src/
│   ├── __init__.py
│   ├── config.py
│   ├── database.py
│   ├── models.py
│   ├── pdf_extractor.py
│   ├── text_chunker.py
│   ├── translator/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── mock_translator.py
│   │   ├── gemini_translator.py
│   │   └── openai_translator.py
│   ├── bilingual_service.py
│   ├── html_renderer.py
│   └── pdf_generator.py
└── templates/
    └── bilingual_book.html
```

## 7. Fluxo funcional desejado

### 7.1. Upload

O usuario envia um PDF original em ingles.

O sistema deve:

1. salvar o arquivo em `data/uploads/`;
2. calcular hash do arquivo;
3. verificar se o livro ja existe no banco;
4. registrar ou reutilizar o livro;
5. mostrar nome do arquivo e total de paginas.

O mesmo PDF enviado novamente deve reaproveitar o mesmo progresso.

### 7.2. Meta de processamento

Em vez de obrigar o usuario a pensar manualmente em muitos intervalos, a interface ideal deve perguntar:

```text
Traduzir ate a pagina: X
Paginas por rodada: N
Tradutor: Gemini/OpenAI/Mock
```

Exemplo:

```text
Traduzir ate a pagina: 100
Paginas por rodada: 10
Tradutor: Gemini
```

O usuario clica sempre no mesmo botao:

```text
Processar proxima rodada
```

O sistema decide automaticamente qual intervalo processar.

### 7.3. Rodadas/lotes

O comportamento ideal:

1. Se nao ha progresso, com meta 100 e rodada 10:

```text
Rodada atual: paginas 1 a 10
```

2. Se paginas 1 a 10 foram totalmente concluidas:

```text
Rodada atual: paginas 11 a 20
```

3. Se uma pagina anterior esta incompleta, por exemplo pagina 5:

```text
Primeira incompleta: 5
Rodada atual: paginas 5 a 5
```

Ou seja: o sistema deve terminar a pagina incompleta antes de avancar.

### 7.4. Conclusao

Quando nao houver mais paginas pendentes ate a meta:

```text
Traducao concluida ate a pagina X.
Proximo passo: gerar PDF consolidado.
```

O botao de processar deve ficar desabilitado.

## 8. Definicao de pagina concluida

Uma pagina esta concluida quando uma das condicoes abaixo e verdadeira:

1. A pagina foi analisada e nao possui texto extraivel.
2. A pagina possui chunks e todos estao com status `translated`.

Uma pagina nao esta concluida quando:

1. Nunca foi analisada.
2. Possui chunks com status `extracted`.
3. Possui chunks com status `failed`.
4. Possui parte dos chunks traduzidos e parte pendente.

## 9. Regra correta para proxima rodada

Entrada:

- livro;
- pagina meta;
- tamanho da rodada.

Saida:

- intervalo inicial/final da proxima rodada;
- ou nenhum intervalo, caso esteja tudo concluido.

Algoritmo desejado:

1. Olhar paginas de `1` ate `pagina_meta`.
2. Encontrar a primeira pagina nao concluida.
3. Se ela possui chunks falhados, processar somente essa pagina.
4. Se ela nunca foi analisada ou nao possui falhas registradas, processar dela ate `dela + tamanho_da_rodada - 1`, respeitando a meta.

Exemplos:

```text
Meta: 100
Rodada: 10
Nada processado
=> 1-10
```

```text
1-10 concluido
=> 11-20
```

```text
1-4 concluido
5 com falha
=> 5-5
```

```text
1 vazia, 2-10 concluido
=> 11-20
```

## 10. Por que nao simplesmente avancar 1-10, 11-20, 21-30 sempre?

Porque isso criaria buracos no PDF final.

Exemplo:

```text
1-10 processado
pagina 5 falhou
app avanca para 11-20
```

Resultado ruim:

- pagina 5 ficaria sem traducao;
- o usuario acharia que o lote 1-10 terminou;
- o PDF consolidado teria lacuna.

Por isso o comportamento correto e voltar na primeira pagina incompleta.

## 11. Banco de dados

### 11.1. books

Tabela para livros cadastrados.

Campos:

```text
id
filename
file_hash
total_pages
created_at
```

### 11.2. chunks

Tabela para blocos de texto extraidos.

Campos principais:

```text
id
book_id
page_number
block_index
original_text
original_hash
translated_text
status
created_at
updated_at
```

Status possiveis:

```text
extracted
translated
failed
```

### 11.3. book_pages

Tabela auxiliar para controlar status por pagina.

Campos:

```text
book_id
page_number
status
total_chunks
updated_at
```

Status esperados:

```text
empty
extracted
```

Essa tabela e importante porque uma pagina sem texto nao gera chunks. Sem ela, o app nao sabe se a pagina:

- ainda nao foi analisada;
- ou foi analisada e realmente nao tem texto.

## 12. Cache

O cache deve impedir retraducao desnecessaria.

Cada chunk deve ter:

```text
original_hash = sha256(texto_normalizado)
```

Antes de traduzir, o sistema deve verificar se o chunk ja esta `translated`.

Regras:

1. Chunk `translated` nao deve ser retraduzido.
2. Chunk `extracted` deve ser traduzido.
3. Chunk `failed` deve ser tentado novamente em rodada futura.
4. Chunks Mock devem ser limpos ou retraduzidos quando o usuario usar Gemini/OpenAI.

## 13. Extracao do PDF

Usar PyMuPDF:

```python
page.get_text("blocks")
```

Cada bloco deve ser ordenado por:

```text
posicao Y
posicao X
```

O sistema deve ignorar blocos vazios.

Heuristica simples para cabecalho/rodape:

- olhar blocos nas margens superior/inferior;
- se o mesmo texto aparece repetidamente em varias paginas do lote, ignorar.

Essa heuristica nao deve ser agressiva demais para evitar remover conteudo real.

## 14. Chunking

O texto extraido deve ser normalizado:

- remover quebras de linha artificiais;
- juntar hifenizacao simples;
- reduzir espacos repetidos;
- preservar ordem de leitura.

Blocos muito grandes devem ser divididos por sentencas ou tamanho maximo.

Um chunk nunca deve misturar paginas diferentes.

## 15. Traducao

Interface base:

```python
class Translator:
    def translate(self, text: str) -> str:
        raise NotImplementedError
```

Implementacoes:

- `MockTranslator`
- `GeminiTranslator`
- `OpenAITranslator`

Prompt obrigatorio:

```text
Traduza o texto do ingles para portugues do Brasil.
Nao resuma.
Nao explique.
Mantenha termos tecnicos.
Mantenha numeros, unidades e siglas.
Retorne apenas a traducao.
```

## 16. Gemini e quota

O Gemini pode falhar com quota/rate limit.

Quando isso acontecer, o comportamento correto e:

1. marcar apenas o chunk atual como `failed`;
2. parar a rodada;
3. nao continuar tentando dezenas de chunks;
4. mostrar aviso amigavel;
5. permitir tentar novamente depois.

Motivo:

Se a API ja bloqueou por quota, continuar tentando apenas cria muitas falhas artificiais e polui o log.

## 17. Renderizacao HTML

Estrutura desejada:

```html
<div class="page">
  <h2>Pagina X</h2>

  <div class="block">
    <div class="label">EN</div>
    <div class="en">Texto original</div>
    <div class="label">PT</div>
    <div class="pt">Traducao</div>
  </div>
</div>
```

CSS desejado:

```css
body {
  font-family: "DejaVu Serif", Georgia, serif;
}

.page {
  page-break-after: always;
}

.block {
  break-inside: avoid;
}

.en {
  font-weight: normal;
}

.pt {
  margin-top: 6px;
  color: #333;
}
```

## 18. Exportacao

A exportacao deve ficar visivel no topo da interface, antes da previa.

Botoes desejados:

```text
Gerar HTML do intervalo
Gerar PDF do intervalo
Gerar PDF consolidado
```

O PDF consolidado deve usar paginas ja traduzidas no cache.

Nome do arquivo:

```text
nome_bilingue_pag_1_20.pdf
```

## 19. Interface desejada

### 19.1. Topo

Mostrar:

```text
Nome do arquivo
Total de paginas
Chunks traduzidos
Paginas com traducao
```

### 19.2. Exportacao

Deve aparecer logo depois do resumo do livro.

### 19.3. Processamento

Campos:

```text
Traduzir ate a pagina
Paginas por rodada
Tradutor
```

Indicadores:

```text
Ultima pagina concluida
Primeira incompleta
Rodada atual
Meta
Chunks com falha
```

Botao:

```text
Processar proxima rodada
```

### 19.4. Logs

Logs devem ser claros, mas nao excessivos.

Exemplos:

```text
Pagina 2 extraida: 3 chunks.
Pagina 3 extraida: 7 chunks.
Chunk 0 da pagina 2 traduzido.
Quota atingida. Rodada pausada.
```

Em caso de quota, nao repetir dezenas de mensagens iguais.

### 19.5. Previa

Mostrar intervalo atual:

```text
Intervalo em exibicao: paginas X a Y
```

Para cada bloco:

```text
EN
texto original

PT
traducao
```

## 20. Botao de reset

A interface deve ter uma area de manutencao com:

```text
Limpar traducoes Mock salvas
Zerar banco
```

O botao `Zerar banco` deve exigir confirmacao.

Ele deve apagar:

- livros;
- chunks;
- status de paginas;
- traducoes;
- progresso salvo.

Ele nao precisa apagar obrigatoriamente arquivos em `uploads` e `outputs`, mas isso pode ser uma opcao futura.

## 21. Problemas observados durante o uso

### 21.1. Mock confundindo usuario

Problema:

O usuario via o texto em ingles repetido no campo PT.

Causa:

O `MockTranslator` nao traduz, apenas retorna:

```text
[TRADUCAO MOCK] texto original
```

Solucao:

Interface deve deixar claro que Mock e apenas teste.

### 21.2. Cache antigo do Streamlit

Problema:

Depois de alterar codigo, apareciam erros como:

```text
AttributeError: object has no attribute ...
```

Causa:

`@st.cache_resource` segurava instancia antiga.

Solucao:

Versionar a chamada:

```python
service = get_service("alguma-versao")
```

Ou limpar cache no menu do Streamlit.

### 21.3. Proxima rodada parecia errada

Problema:

Usuario esperava:

```text
1-10
11-20
```

Mas o app mostrava:

```text
5-5
```

Causa:

A pagina 5 estava incompleta por falha de quota.

Comportamento correto:

Voltar para a pagina 5 ate ela ficar concluida.

Melhoria necessaria:

A interface precisa explicar:

```text
A rodada volta na primeira pagina incompleta para evitar buracos no PDF final.
```

### 21.4. Quota gerando muitas falhas

Problema:

Quando a Gemini batia quota, o app seguia tentando muitos chunks e gerava dezenas de falhas.

Comportamento correto:

Parar no primeiro erro de quota e tentar novamente depois.

## 22. Criterios de aceite

A ferramenta esta correta quando:

1. O usuario sobe um PDF original.
2. O app registra o livro.
3. O app mostra total de paginas.
4. O usuario define meta, por exemplo pagina 100.
5. O usuario define paginas por rodada, por exemplo 10.
6. O app mostra rodada atual.
7. O app traduz a rodada.
8. O app salva progresso no SQLite.
9. O app nao retraduz chunks ja traduzidos.
10. Se houver falha, a proxima rodada volta na primeira pagina incompleta.
11. Quando tudo ate a meta termina, o app mostra mensagem de conclusao.
12. O usuario gera PDF consolidado.
13. O PDF consolidado contem EN e PT em layout limpo.

## 23. Testes manuais recomendados

### Teste 1: PDF pequeno

1. Subir PDF com texto selecionavel.
2. Meta: pagina 2.
3. Rodada: 2 paginas.
4. Tradutor: Mock ou Gemini.
5. Processar.
6. Ver EN/PT.
7. Gerar PDF.

### Teste 2: Cache

1. Processar paginas 1-2.
2. Processar novamente.
3. Confirmar que nao retraduz chunks ja traduzidos.

### Teste 3: Pagina vazia

1. Usar PDF com capa sem texto.
2. Processar.
3. Confirmar que pagina vazia nao trava a proxima rodada.

### Teste 4: Falha de quota

1. Simular ou provocar erro de quota.
2. Confirmar que a rodada para no primeiro erro de quota.
3. Confirmar que a proxima rodada volta na pagina incompleta.

### Teste 5: Conclusao

1. Traduzir ate pagina X.
2. Confirmar mensagem:

```text
Traducao concluida ate a pagina X.
```

3. Gerar PDF consolidado.

## 24. Melhorias futuras

1. Botao para retry apenas de chunks falhados.
2. Pausa automatica com cooldown quando Gemini bater quota.
3. Estimativa de custo e quantidade de chunks antes de processar.
4. OCR opcional para PDFs escaneados.
5. Painel por pagina com status:

```text
vazia
traduzida
pendente
falhou
```

6. Exportar somente paginas totalmente concluidas.
7. Melhor tratamento de tabelas.
8. Melhor suporte a livros com duas colunas.
9. Botao para apagar tambem uploads e outputs.

## 25. Estado ideal do produto

O usuario deveria sentir que o fluxo e simples:

1. Sobe o PDF.
2. Diz ate onde quer traduzir.
3. Clica em processar proxima rodada.
4. Se bater quota, espera e clica de novo.
5. Quando aparecer concluido, exporta.

O usuario nao deveria precisar entender:

- IDs de chunks;
- detalhes do SQLite;
- hash;
- como o lote e calculado internamente.

Esses detalhes devem existir no codigo, mas a interface deve apresentar apenas o necessario para operar com seguranca.
