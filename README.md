# Documentação Técnica Completa, Decisões, Premissas e Guia de Execução — Asset Servicing (BTG Pactual)

Este documento consolida o projeto desenvolvido: a arquitetura do agente *code-first*, os códigos-fonte completos dos módulos (`schemas.py`, `validator.py`, `main.py`), as dependências (`requirements.txt`), as premissas de negócio, as escolhas arquiteturais e o guia passo a passo de execução para o processamento de avisos de eventos corporativos.

## 1. Visão Geral da Arquitetura e Pipeline

O agente foi desenhado sob uma abordagem **Code-First e Determinística**, priorizando a segurança regulatória e financeira do BTG Pactual. O pipeline divide-se em 5 camadas principais:

1. **Ingestão & Parsing (`pdfplumber`):** Extração programática e limpeza de texto de PDFs nativos da B3.

2. **Extração Estruturada com Rastreabilidade (`Pydantic` + LLM Local):** Uso de contratos estritos de schema onde cada campo extraído carrega o valor, um **score de confiança calibrado (0.0 a 1.0)** e o **trecho literal de origem (`source_snippet`)**, permitindo auditoria sem precisar reabrir o PDF.

3. **Validação Cruzada Determinística (`validator.py`):**

   * **Golden Records:** Cruzamento obrigatório de CNPJ, ISIN e Ticker contra a base de referência oficial (`golden_records.csv`).

   * **Coerência Cronológica:** Validação estrita da regra: $\text{Data de Aprovação} \le \text{Data Com} < \text{Data Ex} \le \text{Data de Pagamento}$

   * **Coerência Matemática & Crítica:** Conferência de cálculos de JCP (alíquota de IRRF de 17,5%), autocorreção determinística de valores líquidos ausentes e checagem de obrigatoriedade de campos essenciais (proibição de alucinação ou valores vazios).

4. **Em caso de incerteza, sugestão de análise manual:** Isola automaticamente divergências cadastrais, falhas lógicas, ausência de campos obrigatórios ou baixa confiança ($< 0.7$) para o `relatorio_excecoes.json`.

5. **Persistência Incremental:** Salvamento de um arquivo JSON por documento processado e geração do relatório consolidado de exceções.

## 2. Dependências do Projeto 
```text
python-dotenv==1.2.4
pdfplumber==0.11.10
pandas==3.1.1
pydantic==2.14.3
ollama==0.6.3
```

## 3. Premissas de Negócio e Regras Validadas

* **Validação Cadastral (`Golden Records`):** Cruzamento obrigatório de CNPJ, ISIN e Ticker com o `golden_records.csv`.
* **Coerência Cronológica:** Ordenação estrita de datas ($\text{Aprovação} \le \text{Data Com} < \text{Data Ex} \le \text{Pagamento}$).
* **Coerência Matemática (JCP):** Verificação da retenção de IRRF (17,5%) e autocorreção de valores líquidos ausentes.
* **Tolerância Zero para Invenção:** Proibição de preenchimento fictício (ex: `R$ 0,00`). Ausência de dados aciona malha fina.

## 4. Escolhas Arquiteturais e Trade-offs

* **Por que adotar uma abordagem Code-First em vez de Frameworks/ADKs pesados?** Pipelines financeiros exigem determinismo absoluto, previsibilidade e rastreabilidade rigorosa. Frameworks autônomos complexos ou Agent Development Kits (ADKs) introduzem loops autônomos e comportamento não determinístico que são perigosos em ambientes regulados. A arquitetura code-first garante que o fluxo de dados siga estritamente contratos determinísticos passo a passo: Extração estruturada $\rightarrow$ Validação cruzada $\rightarrow$ Checagem lógica/matemática $\rightarrow$ Roteamento de exceção, eliminando falhas sistêmicas e garantindo auditoria perfeita.
* **Uso de LLM Aberta via Ollama (Llama 3):** Execução totalmente local do modelo, eliminando custos por requisição (ao contrário de APIs comerciais pagas como OpenAI ou Google Gemini). Isso garante total previsibilidade orçamentária e máxima privacidade/segurança de dados financeiros sensíveis.
* **Saídas Estruturadas (Pydantic):** Garante um formato de dados padronizado e seguro para os sistemas seguintes.
* **Validação Determinística em Python:** Isola regras lógicas e cálculos fora da IA para eliminar alucinações numéricas.
* **Rastreabilidade por Trecho Literal (source_snippet):** Permite auditoria imediata sem reabrir o PDF.
* **Salvamento Incremental:** Gravação item a item para evitar perda de dados em caso de interrupções de lote.

## 5. Guia de Execução

### Passo 1: Clonar e Acessar o Repositório
Abra o terminal na pasta raiz do projeto.

### Passo 2: Criar e Ativar Ambiente Virtual
```bash
python3.11 -m venv venv
source venv/bin/activate 
```

### Passo 3: Instalar as Dependências
```bash
pip install -r requirements.txt
```

### Passo 4: Configurar o Motor Local (Ollama)
```bash
ollama pull llama3
```

### Passo 5: Organizar a Estrutura
* Garanta que os PDFs estão na pasta `documents/`
* Garanta que o arquivo de referência está em `golden_records/golden records.csv`

### Passo 6: Executar o Pipeline
```bash
python main.py
```
* **Saídas geradas:** JSONs individuais em `output_json/` e o relatório de exceções consolidado em `relatorio_excecoes.json`.