from pydantic import BaseModel, Field
from typing import Optional, List

class CampoExtraido(BaseModel):
    valor: Optional[str | float] = Field(
        None, 
        description="O valor extraído e limpo correspondente. NUNCA deixe como null se a informação existir no texto."
    )
    confianca: float = Field(
        ..., 
        description="Score de confiança de 0.0 a 1.0 baseado na clareza da informação no texto."
    )
    trecho_origem: str = Field(
        ..., 
        description="ATENÇÃO: Copie a frase ou linha ESPECÍFICA exata do texto do PDF de onde este valor foi extraído (ex: 'Valor bruto por ação ON R$ 0,2050'). NUNCA repita o título geral do documento."
    )

class EventoCorporativoSchema(BaseModel):
    emissor: CampoExtraido
    cnpj: CampoExtraido
    isin: CampoExtraido
    ticker: CampoExtraido
    tipo_evento: CampoExtraido
    data_aprovacao: Optional[CampoExtraido] = None
    data_com: CampoExtraido
    data_ex: CampoExtraido
    data_pagamento: CampoExtraido
    valor_bruto: Optional[CampoExtraido] = None
    valor_liquido: Optional[CampoExtraido] = None
    percentual_irrf: Optional[CampoExtraido] = None
    moeda: CampoExtraido
    status_golden_record: bool = False
    status_coerencia_logica: bool = True
    erros_validacao: List[str] = []
    precisa_revisao_humana: bool = False
    justificativa_revisao: Optional[str] = None