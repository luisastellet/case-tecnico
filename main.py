import os
import json
import re
import pdfplumber
from pathlib import Path
from validator import ValidadorFinanceiro
from schemas import EventoCorporativoSchema
import ollama

PASTA_DOCUMENTOS = "documents"
CSV_GOLDEN = "golden_records/golden records.csv"

def extrair_texto_pdf(caminho_pdf: str) -> str:
    texto = ""
    with pdfplumber.open(caminho_pdf) as pdf:
        for pagina in pdf.pages:
            t = pagina.extract_text()
            if t:
                t_limpo = re.sub(r'\.{3,}', ' : ', t)
                texto += t_limpo + "\n"
    return texto

def processar_lote():
    validador = ValidadorFinanceiro(CSV_GOLDEN)
    os.makedirs("output_json", exist_ok=True)
    arquivos_pdf = list(Path(PASTA_DOCUMENTOS).glob("*.pdf"))
    print(f"Total de {len(arquivos_pdf)} documentos encontrados para processar.")
    relatorio_excecoes = []

    for pdf_path in arquivos_pdf:
        print(f"\nProcessando {pdf_path.name}")
        
        try:
            texto_pdf = extrair_texto_pdf(str(pdf_path))
            response = ollama.chat(
                model='llama3', 
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Você é um especialista em Asset Servicing da B3. "
                            "Extraia as informações do documento e preencha estritamente o schema fornecido.\n\n"

                            "REGRAS DE EXTRAÇÃO:\n"
                            "1. FIDELIDADE AO DOCUMENTO:\n"
                            "   - Utilize exclusivamente informações explicitamente presentes no texto.\n"
                            "   - NUNCA invente, deduza, complete ou presuma informações, mesmo que sejam previsíveis pelo contexto ou conhecimento de mercado.\n"
                            "   - Se uma informação estiver ausente, incompleta ou ambígua, retorne null e confiança 0.0. Nunca tente reconstruí-la.\n\n"

                            "2. VALOR E TRECHO DE ORIGEM:\n"
                            "   - 'trecho_origem' deve ser uma transcrição literal de um trecho existente no PDF. Nunca crie ou reescreva evidências.\n"
                            "   - 'valor' deve conter exclusivamente a informação solicitada, isolada do restante do texto.\n"
                            "   - Todo valor preenchido deve estar diretamente comprovado pelo respectivo trecho_origem.\n\n"

                            "3. DISTINÇÃO SEMÂNTICA:\n"
                            "   - Identifique corretamente cada informação, sem confundir CNPJ, ISIN, ticker, tipos de evento, datas, valores e percentuais.\n"
                            "   - Não classifique uma data apenas pelo seu formato ou proximidade com outra informação. Identifique sua finalidade explícita.\n"
                            "   - Não confunda percentual de bonificação com percentual de IRRF.\n"
                            "   - Não confunda custo fiscal com valor bruto ou líquido distribuído aos acionistas.\n"
                            "   - O campo 'moeda' deve conter exclusivamente o símbolo ou código da moeda (ex: 'R$', 'BRL', 'USD'), nunca uma quantia monetária.\n"
                            "   - Não calcule valores, percentuais ou datas a partir de outras informações.\n\n"

                            "4. TRATAMENTO DE AUSÊNCIAS:\n"
                            "   - Expressões como 'A definir', 'A ser divulgado' e 'Vide aviso complementar' não são valores válidos. Retorne null e confiança 0.0, preservando o trecho original quando aplicável.\n"
                            "   - Não confunda ausência de informação com valor zero.\n"
                            "   - Não preencha campos apenas para evitar valores nulos.\n\n"

                            "5. CONFIANÇA:\n"
                            "   - 1.0: informação explícita, completa e inequívoca.\n"
                            "   - 0.7 a 0.9: informação presente, mas com alguma ambiguidade.\n"
                            "   - 0.0 a 0.6: informação ausente, incompleta ou não identificável.\n\n"

                            "EXEMPLOS DE EXTRAÇÃO:\n\n"

                            "Exemplo 1:\n"
                            "Texto: 'Empresa XPTO S.A. | CNPJ 00.000...'\n"
                            "emissor.valor: 'Empresa XPTO S.A.'\n"
                            "cnpj.valor: null (CNPJ incompleto; não completar os dígitos).\n\n"

                            "Exemplo 2:\n"
                            "Texto: 'Custo atribuído (base fiscal) R$ 7,820000 por ação'\n"
                            "moeda.valor: 'R$'\n"
                            "valor_bruto.valor: null (custo fiscal não é necessariamente distribuição ao acionista).\n\n"

                            "Exemplo 3:\n"
                            "Texto: 'Proporção de 1 ação nova para cada 20 ações (5%)'\n"
                            "percentual_irrf.valor: null (5% representa a proporção da bonificação).\n\n"

                            "Exemplo 4:\n"
                            "Texto: 'Data de pagamento: A definir (vide aviso complementar)'\n"
                            "data_pagamento: null (preservar o trecho original e atribuir confiança 0.0).\n\n"

                            "Exemplo 5:\n"
                            "Texto: 'Valor bruto por ação: R$ 0,50. Valor líquido por ação: R$ 0,425, após retenção de IRRF.'\n"
                            "valor_bruto.valor: 'R$ 0,50'\n"
                            "valor_liquido.valor: 'R$ 0,425'\n"
                            "percentual_irrf.valor: null (não calcular o percentual a partir dos valores bruto e líquido).\n"
                            "Regra: procure explicitamente por expressões como 'valor líquido', 'valor líquido por ação' e 'valor após retenção de IRRF'. "
                            "Quando o valor líquido estiver informado, extraia-o independentemente do valor bruto. "
                            "Não copie o valor bruto para o campo valor_liquido e não calcule o valor líquido por conta própria.\n\n"

                            "REGRA FINAL: Nunca sacrifique a fidelidade ao documento para preencher um campo. "
                            "Na dúvida, retorne null."
                        )
                    },
                    {
                        "role": "user",
                        "content": f"Extraia os dados estruturados do seguinte aviso aos acionistas da B3:\n\n{texto_pdf}"
                    }
                ],
                format=EventoCorporativoSchema.model_json_schema(),
                options={
                    'temperature': 0.0,
                    'seed': 42
                }
            )

            extracao_llm = EventoCorporativoSchema.model_validate_json(response['message']['content'])
            cnpj_extraido = extracao_llm.cnpj.valor or ""
            isin_extraido = extracao_llm.isin.valor or ""
            ticker_extraido = extracao_llm.ticker.valor or ""
            status_golden, msg_golden = validador.validar_golden_record(cnpj_extraido, isin_extraido, ticker_extraido)
            dados_dict = extracao_llm.model_dump()
            status_coerencia, lista_erros = validador.validar_coerencia(dados_dict)
            extracao_llm.status_golden_record = status_golden
            extracao_llm.status_coerencia_logica = status_coerencia
            
            erros_totais = []
            if not status_golden:
                erros_totais.append(msg_golden)
            erros_totais.extend(lista_erros)

            tipo_ev_str = str(extracao_llm.tipo_evento.valor).lower() if extracao_llm.tipo_evento and extracao_llm.tipo_evento.valor else ""
            
            if "dividendo" in tipo_ev_str or "juros sobre o capital" in tipo_ev_str or "jcp" in tipo_ev_str or "provento" in tipo_ev_str:
                if not extracao_llm.valor_bruto or extracao_llm.valor_bruto.valor is None or str(extracao_llm.valor_bruto.valor) in ["0", "0.0", "R$ 0,00"]:
                    erros_totais.append("CRÍTICO: Valor Bruto ausente ou não informado no documento. Requer análise manual.")
                if not extracao_llm.valor_liquido or extracao_llm.valor_liquido.valor is None or str(extracao_llm.valor_liquido.valor) in ["0", "0.0", "R$ 0,00"]:
                    erros_totais.append("CRÍTICO: Valor Líquido ausente ou não informado no documento. Requer análise manual.")

            if not extracao_llm.data_com or not extracao_llm.data_com.valor:
                erros_totais.append("CRÍTICO: Data Com ausente.")
            if not extracao_llm.data_ex or not extracao_llm.data_ex.valor:
                erros_totais.append("CRÍTICO: Data Ex ausente.")
            if not extracao_llm.data_pagamento or not extracao_llm.data_pagamento.valor:
                erros_totais.append("CRÍTICO: Data de Pagamento ausente.")

            extracao_llm.erros_validacao = erros_totais
            precisa_revisao = (
                not status_golden or 
                not status_coerencia or 
                len(erros_totais) > 0 or 
                any(campo and campo.confianca < 0.7 for campo in [extracao_llm.isin, extracao_llm.data_com, extracao_llm.data_ex, extracao_llm.valor_bruto])
            )
            
            extracao_llm.precisa_revisao_humana = precisa_revisao
            if precisa_revisao:
                extracao_llm.justificativa_revisao = " | ".join(erros_totais) if erros_totais else "Baixa confiança detectada em campos críticos."
            else:
                extracao_llm.justificativa_revisao = "Documento totalmente validado, íntegro e coerente."

            output_json_path = Path("output_json") / f"{pdf_path.stem}.json"
            with open(output_json_path, "w", encoding="utf-8") as f:
                f.write(extracao_llm.model_dump_json(indent=4, ensure_ascii=False))
            print(f"  Salvo em {output_json_path}")

            if precisa_revisao:
                relatorio_excecoes.append({
                    "documento": pdf_path.name,
                    "motivos": extracao_llm.justificativa_revisao
                })

        except Exception as e:
            print(f"  -> [ERRO] Falha ao processar {pdf_path.name}: {str(e)}")
            relatorio_excecoes.append({
                "documento": pdf_path.name,
                "motivos": f"Erro sistêmico ou de schema: {str(e)}"
            })

    with open("relatorio_excecoes.json", "w", encoding="utf-8") as f:
        json.dump(relatorio_excecoes, f, ensure_ascii=False, indent=4)
    print("\nProcessamento dos arquivos concluído.")

if __name__ == "__main__":
    processar_lote()