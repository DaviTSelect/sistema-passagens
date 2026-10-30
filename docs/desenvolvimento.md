# Guia de desenvolvimento

## Ambiente local

```powershell
py -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

Para instalar como pacote editável (habilita o comando `conferencia-passagens`):

```powershell
.\venv\Scripts\python.exe -m pip install -e ".[build]"
```

## Testes

Execute todos os testes antes de enviar qualquer mudança:

```powershell
$env:PYTHONPATH = "src"
.\venv\Scripts\python.exe -m unittest discover -s tests -v
```

| Arquivo | Cobre |
|---|---|
| `tests/test_normalization.py` | Conversão de valores monetários e normalização de texto |
| `tests/test_report.py` | Regras de comparação e conferência ponta a ponta com PDFs sintéticos |
| `tests/test_pdf_models.py` | Extração de cada modelo de PDF suportado |
| `tests/test_auto_update.py` | Comparação de versões e status de atualização exibido na janela |
| `tests/test_cli.py` | Parâmetros e códigos de saída do terminal |
| `tests/test_extract.py` | Regras de leitura de valores, voos, passageiros e layouts de tarifa |
| `tests/test_gui.py` | Mensagens de resumo, nomes de arquivo e estados da janela |
| `tests/test_version.py` | Fonte única da versão |
| `tests/test_trechos.py` | Extração de trechos, atualização da planilha, parâmetros de terminal e troca de função na janela |
| `tests/helpers.py` | Caminhos compartilhados e configuração do `sys.path` |

### Testes com documentos reais

Os PDFs reais (`pdf/`, `fatura/`) e os valores esperados deles ficam **fora do git**, pois contêm dados pessoais. Os valores esperados ficam em `tests/real_documents.json` (ignorado), no formato abaixo:

```json
{
  "tickets":  { "bilhete_gol_01.pdf": { "number": "...", "locator": "...", "total": "1250.00" } },
  "invoices": { "fatura_gol_01.pdf":  { "entry_count": 10, "entries": { "<número>": { "total": "..." } } } }
}
```

Em `tickets`, informe só os campos que quer conferir (`number`, `locator`, `passenger`, `flights`, `fare`, `taxes`, `total`). Valores monetários vão como texto, para virar `Decimal` sem perda.

Sem esse arquivo (como no CI), os testes de documentos reais são **pulados**. Rode-os localmente sempre que mexer em `extract.py`.

Dê aos PDFs reais nomes neutros, por modelo (`bilhete_gol_01.pdf`, `bilhete_latam_02.pdf`, `fatura_gol_01.pdf`), sem nomes de passageiros. Isso também garante que a extração não dependa do nome do arquivo.

### PDFs sintéticos

São criados em uma pasta temporária a cada execução dos testes, usam somente dados fictícios e trazem a marca visível `NÃO É FATURA NEM DOCUMENTO FISCAL`. O conteúdo deles está em `tests/generate_example_invoices.py`.

## Como adicionar um novo modelo de PDF

1. **Inspecione o texto extraído**, que costuma ser diferente do que aparece na tela:
   ```powershell
   $env:PYTHONPATH = "src"
   .\venv\Scripts\python.exe -c "from passagem.extract import ler_pdf; print(ler_pdf(r'caminho\do\arquivo.pdf'))"
   ```
2. **Registre o resultado esperado primeiro**: para um PDF real, coloque-o em `pdf/` ou `fatura/` com nome neutro e adicione os valores esperados em `tests/real_documents.json`. Se possível, crie também uma versão sintética, com dados fictícios, em `tests/generate_example_invoices.py` e um teste em `tests/test_pdf_models.py`.
3. **Ajuste a função do campo** em `extract.py` (`_buscar_*` ou `_extrair_*`). Acrescente o novo padrão **depois** dos existentes, ou o restrinja ao layout novo, para não alterar os modelos atuais.
4. **Comente a regra** com um exemplo do texto que ela trata.
5. **Rode a suíte completa** com os PDFs reais presentes.
6. Atualize a tabela de modelos suportados no `README.md` e o `CHANGELOG.md`.

## Padrões de código

- **Dinheiro sempre em `Decimal`**, nunca `float`.
- **Camadas**: `models` ← `extract`/`report` ← `conference` ← `gui`/`main`. A regra de negócio não importa PySide6.
- **Funções em português, pequenas e nomeadas pelo que fazem**; funções internas do módulo começam com `_`.
- **Constantes nomeadas** para limites e textos de status (por exemplo `TOTAL_TOLERANCE`, `STATUS_OK`), em vez de valores soltos no código.
- **Docstrings e comentários em português**, explicando o porquê (layout tratado, armadilha do PDF), não o óbvio.
- **Type hints** em todas as funções públicas.
- **Falha por arquivo vira aviso**, não exceção que interrompe o lote.
- **Paleta da interface**: fundo `#203447`, texto `#efede5`, ação `#e94c1f`. Não altere sem alinhar com os demais painéis.

## Gerar o executável

O script `build_exe.bat` empacota toda a aplicação em um único arquivo `.exe` para Windows. Não é preciso ter Python instalado na máquina que vai rodar o executável.

**Pré-requisito:** o `venv` deve existir e as dependências devem estar instaladas (veja *Ambiente local*).

```powershell
.\build_exe.bat
```

O que o script faz, passo a passo:

1. Verifica se `venv\Scripts\python.exe` existe; aborta com mensagem se não encontrar.
2. Instala o PyInstaller no `venv`, caso ainda não esteja presente.
3. Chama o PyInstaller com `--onefile --windowed`:
   - `--onefile`: gera um único `ConferenciaPassagens.exe`, sem pasta de arquivos ao lado.
   - `--windowed`: não abre janela de console ao executar.
   - `--icon logo.ico`: aplica o ícone ao executável e à barra de tarefas.
   - `--collect-all`: empacota pymupdf, pypdfium2 e rapidocr_onnxruntime com todos os seus dados internos (modelos de OCR, fontes, etc.).
4. Salva o resultado em `dist\ConferenciaPassagens.exe`.

A pasta `build\` e o arquivo `.spec` gerados são temporários e estão no `.gitignore`; podem ser apagados a qualquer momento.

**Tempo estimado:** 2–5 minutos na primeira vez (download de dependências); menos de 1 minuto nas seguintes.

**Tamanho esperado:** ~220–250 MB (inclui Python, PySide6, modelos de OCR e todas as bibliotecas).

## Publicar uma nova versão

Este é o passo a passo completo para lançar uma nova versão, do código ao executável distribuído. Ao abrir, a janela verifica automaticamente o repositório `DaviTSelect/sistema-passagens` e oferece a atualização.

### 1. Atualizar o número de versão

Edite **somente** o arquivo [src/passagem/version.py](../src/passagem/version.py):

```python
__version__ = "1.1.0"   # era "1.0.0"
```

Esse arquivo é a fonte única da versão: o `pyproject.toml` e a janela leem daqui. Não altere em mais nenhum lugar.

Use o formato `MAJOR.MINOR.PATCH` (ex.: `1.0.0` → `1.1.0` para nova função, `1.0.1` para correção de bug).

### 2. Registrar as mudanças no changelog

Abra o [CHANGELOG.md](../CHANGELOG.md) e adicione uma seção no topo:

```markdown
## [1.1.0] – 2026-10-30

### Adicionado
- Suporte à fatura Azul.

### Corrigido
- Leitura do total em bilhetes LATAM com classe J/P.
```

### 3. Gerar o executável

```powershell
.\build_exe.bat
```

Aguarde a conclusão. O arquivo `dist\ConferenciaPassagens.exe` é o que será distribuído.

### 4. Criar a Release no GitHub

1. Acesse **https://github.com/DaviTSelect/sistema-passagens/releases/new**.
2. No campo **Tag**, digite exatamente `v1.1.0` (com o `v` minúsculo). Clique em *Create new tag*.
3. No campo **Release title**, escreva `v1.1.0` ou um nome descritivo.
4. No campo de descrição, cole o trecho do `CHANGELOG.md` desta versão.
5. Em **Attach binaries**, arraste o arquivo `dist\ConferenciaPassagens.exe`. O nome do arquivo deve ser exatamente `ConferenciaPassagens.exe` — não renomeie.
6. Clique em **Publish release**.

> **Por que o nome do arquivo importa?** O atualizador procura na lista de assets da release um arquivo chamado `ConferenciaPassagens.exe`. Se o nome estiver diferente, o download falha e a bolinha fica cinza.

### 5. Verificar a atualização automática

Depois de publicar, abra a versão antiga do executável. Em alguns segundos:

- A bolinha fica **amarela** enquanto verifica e baixa.
- Aparece uma caixa de diálogo perguntando se deseja reiniciar agora.
- Ao confirmar, o programa fecha, o novo executável substitui o antigo e reabre automaticamente.
- A bolinha fica **verde**, confirmando que a versão instalada é a mais recente.

| Bolinha | Significado |
|---|---|
| Verde | Versão mais recente confirmada |
| Amarela | Verificando, baixando ou nova versão disponível |
| Cinza | Falha na verificação ou asset ausente na release |

### Resumo rápido (versões seguintes)

```
1. Edite version.py
2. Atualize CHANGELOG.md
3. .\build_exe.bat
4. GitHub → Releases → Nova release com tag vX.Y.Z → anexe ConferenciaPassagens.exe
```

## Fluxo de contribuição

1. Crie um branch a partir de `main` (`feature/novo-modelo-azul`, `fix/total-latam`).
2. Faça commits pequenos com mensagens no imperativo (`Adiciona leitura da fatura Azul`).
3. Garanta que os testes passam localmente.
4. Abra um Pull Request descrevendo o modelo ou o problema tratado. O CI roda os testes automaticamente.

## Checklist antes do commit

- [ ] Testes passando (`unittest discover`), inclusive com os PDFs reais
- [ ] Nenhum PDF real, CSV gerado ou executável adicionado ao git
- [ ] README/docs atualizados se mudou parâmetro, requisito ou modelo suportado
- [ ] Entrada no `CHANGELOG.md`
