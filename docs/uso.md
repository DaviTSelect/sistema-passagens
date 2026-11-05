# Guia de uso

## Requisitos

- Windows com Python 3.11 ou superior.
- Dependências Python: `pip install -r requirements.txt` (leitura de PDF, OCR, Excel e PySide6).
- **Opcional:** [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) com o idioma português (`por`), necessário só para PDFs digitalizados (sem texto selecionável).

## Instalação

```powershell
py -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Executar pela interface

```powershell
.\venv\Scripts\python.exe src\passagem\main.py
```

No topo do cartão, escolha **Conferir fatura** ou **Extrair trechos**.

### Conferir fatura

1. Selecione a pasta com os PDFs dos bilhetes.
2. Selecione o PDF da fatura.
3. Escolha a pasta onde salvar o relatório (`conferencia_AAAAMMDD_HHMMSS.csv`).
4. Clique em **Iniciar conferência**.

Ao final, uma mensagem mostra quantos bilhetes foram processados e até 10 avisos (PDFs ilegíveis, sem texto etc.).

### Extrair trechos

1. Selecione a pasta com os PDFs das passagens.
2. Escolha a planilha `.xlsx`, nova ou existente.
3. Clique em **Iniciar extração**.

A planilha recebe uma linha por trecho, na aba `Trechos`, identificada por bilhete e número do trecho. Executar de novo não duplica linhas: trechos iguais ficam como estão e os alterados são atualizados. Feche a planilha no Excel antes de iniciar. PDFs digitalizados passam por OCR local, sem precisar do Tesseract, e a primeira leitura pode levar mais de um minuto.

### Status da versão

No canto superior direito, a bolinha **verde** confirma que esta é a versão mais recente. Amarela indica verificação, download ou versão nova disponível; cinza indica que não foi possível verificar. Nada disso impede a conferência, exceto durante o download da atualização.

Também é possível iniciar como módulo:

```powershell
$env:PYTHONPATH = "src"
.\venv\Scripts\python.exe -m passagem.main
```

## Executar pela linha de comando

```powershell
.\venv\Scripts\python.exe src\passagem\main.py --bilhetes "C:\Documentos\pdf" --fatura "C:\Documentos\fatura" --saida "C:\Documentos\conferencia.csv"
```

| Parâmetro | Descrição |
|---|---|
| `--bilhetes` | Pasta com os PDFs dos bilhetes |
| `--fatura` | Pasta com os PDFs das faturas, ou o PDF de uma fatura |
| `--saida` | Caminho do CSV a gerar (pastas são criadas se necessário) |

Os três são obrigatórios quando qualquer um é usado. Sem parâmetros, a interface gráfica abre.

Para extrair os trechos para o Excel:

```powershell
.\venv\Scripts\python.exe src\passagem\main.py --trechos "C:\Documentos\pdf" --planilha "C:\Documentos\trechos.xlsx"
```

Na extração, o código de saída é `1` também quando algum PDF não pôde ser lido, mesmo que os demais tenham sido gravados.

**Códigos de saída:** `0` sucesso (mesmo com avisos), `1` erro (pasta vazia, nenhum bilhete lido etc.), `2` parâmetros inválidos. Avisos são impressos como `AVISO: ...`.

## Como a conferência funciona

- Cada bilhete é procurado nas faturas pelo **número do bilhete**; se não encontrar, pelo **localizador**. Valores e ordem das linhas nunca são usados para casar registros.
- Bilhetes duplicados (mesmo número) são considerados uma vez só.
- Campos conferidos: número do bilhete, localizador, passageiro, voos e total.
- Na comparação de texto, maiúsculas, espaços extras e os pronomes `MR`/`MRS` são ignorados.
- No total, diferenças de até **R$ 0,01** são consideradas OK.
- Em faturas G3 com TARIFA, TAXA, FEE e SUB-TOTAL, o total da fatura é o **SUB-TOTAL**, que já inclui o fee.
- Um PDF que falha na leitura vira um aviso e não interrompe a conferência.

## Lendo o relatório

Uma linha por campo conferido de cada bilhete.

| Coluna | Conteúdo |
|---|---|
| `numero_bilhete` | Número do bilhete (ou `NÃO EXTRAÍDO`) |
| `campo` | Número do bilhete, Localizador, Passageiro, Voos ou Total |
| `valor_bilhete` | Valor lido no PDF do bilhete |
| `valor_fatura` | Valor lido na fatura (`SEM CORRESPONDÊNCIA` se o bilhete não está na fatura) |
| `resultado` | Status da conferência (tabela abaixo) |
| `divergencia` | Explicação da diferença, quando houver |
| `arquivo_bilhete` / `arquivo_fatura` | Nome dos PDFs de origem |

| Resultado | Significado |
|---|---|
| `OK` | Valores iguais |
| `DIVERGENTE` | Valores diferentes; veja a coluna `divergencia` |
| `NÃO ENCONTRADO` | O bilhete não aparece em nenhuma fatura |
| `NÃO CONFERIDO` | Um dos PDFs não teve o total extraído; confira manualmente |

O arquivo usa `;` como separador e UTF-8 com BOM, para abrir no Excel em português com os acentos corretos.

## OCR de PDFs digitalizados

Quando um PDF tem menos de 40 caracteres de texto selecionável, o programa tenta OCR automaticamente (páginas renderizadas em 3x, idiomas `por` e/ou `eng`).

O Tesseract é procurado, nesta ordem:

1. no caminho da variável de ambiente `TESSERACT_CMD`;
2. em `C:\Program Files\Tesseract-OCR\tesseract.exe`;
3. no `PATH` do sistema.

```powershell
$env:TESSERACT_CMD = "D:\Ferramentas\Tesseract-OCR\tesseract.exe"
```

## Problemas comuns

| Sintoma | Causa provável |
|---|---|
| `Nenhum PDF encontrado na pasta...` | Pasta errada ou arquivos sem extensão `.pdf` |
| `Tesseract OCR não encontrado` | PDF digitalizado sem Tesseract instalado; instale ou defina `TESSERACT_CMD` |
| `PDF protegido por senha` | Remova a senha do PDF antes de conferir |
| Campo como `NÃO EXTRAÍDO` | Modelo de PDF ainda não suportado; veja [desenvolvimento.md](desenvolvimento.md#como-adicionar-um-novo-modelo-de-pdf) |
