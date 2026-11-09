import pandas as pd
from datetime import datetime

class ValidadorFinanceiro:
    def __init__(self, golden_csv_path: str):
        self.df_golden = pd.read_csv(golden_csv_path)

    def validar_golden_record(self, cnpj: str, isin: str, ticker: str) -> tuple[bool, str]:
        match = self.df_golden[
            (self.df_golden['cnpj'].str.strip() == cnpj.strip()) & 
            (self.df_golden['isin'].str.strip() == isin.strip()) & 
            (self.df_golden['ticker'].str.strip() == ticker.strip())
        ]
        if match.empty:
            return False, f"Incompatibilidade cadastral: CNPJ {cnpj}, ISIN {isin} ou Ticker {ticker} não encontrados no golden_records.csv."
        return True, "Dados cadastrais validados com sucesso."

    def _parse_data(self, data_str: str) -> datetime | None:
        """Tenta converter string de data em vários formatos (inclusive por extenso)."""
        if not data_str or str(data_str).lower() in ["none", "null", "a definir", "não informado"]:
            return None
        
        formatos = ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"]
        for fmt in formatos:
            try:
                return datetime.strptime(str(data_str).strip(), fmt)
            except ValueError:
                continue
        
        meses = {
            'janeiro': '01', 'fevereiro': '02', 'março': '03', 'abril': '04',
            'maio': '05', 'junho': '06', 'julho': '07', 'agosto': '08',
            'setembro': '09', 'outubro': '10', 'novembro': '11', 'dezembro': '12'
        }
        try:
            partes = str(data_str).lower().split()
            dia = partes[0].zfill(2)
            mes = meses.get(partes[2])
            ano = partes[4]
            if mes:
                return datetime.strptime(f"{dia}/{mes}/{ano}", "%d/%m/%Y")
        except Exception:
            pass
        return None

    def validar_coerencia(self, dados: dict) -> tuple[bool, list[str]]:
        erros = []
        
        try:
            fmt = "%d/%m/%Y"
            
            dt_com_obj = dados.get('data_com')
            dt_ex_obj = dados.get('data_ex')
            dt_pag_obj = dados.get('data_pagamento')
            val_com = dt_com_obj.get('valor') if isinstance(dt_com_obj, dict) else None
            val_ex = dt_ex_obj.get('valor') if isinstance(dt_ex_obj, dict) else None
            val_pag = dt_pag_obj.get('valor') if isinstance(dt_pag_obj, dict) else None
            dt_com = self._parse_data(val_com)
            dt_ex = self._parse_data(val_ex)
            dt_pag = self._parse_data(val_pag)

            if dt_com and dt_ex and dt_com >= dt_ex:
                erros.append(f"Incoerência de datas: Data Com ({dt_com.strftime(fmt)}) deve ser anterior à Data Ex ({dt_ex.strftime(fmt)}).")
            
            if dt_ex and dt_pag and dt_ex > dt_pag:
                erros.append(f"Incoerência de datas: Data Ex ({dt_ex.strftime(fmt)}) não pode ser posterior ao Pagamento ({dt_pag.strftime(fmt)}).")

            tipo_ev_obj = dados.get('tipo_evento')
            tipo_evento_str = tipo_ev_obj.get('valor', '') if isinstance(tipo_ev_obj, dict) else ''
            
            if tipo_evento_str and ("Juros sobre o Capital" in str(tipo_evento_str) or "jcp" in str(tipo_evento_str).lower()):
                v_bruto_obj = dados.get('valor_bruto')
                v_liq_obj = dados.get('valor_liquido')
                p_ir_obj = dados.get('percentual_irrf')
                v_bruto = v_bruto_obj.get('valor') if isinstance(v_bruto_obj, dict) else None
                v_liq = v_liq_obj.get('valor') if isinstance(v_liq_obj, dict) else None
                p_ir = p_ir_obj.get('valor') if isinstance(p_ir_obj, dict) else None
                
                if v_bruto is not None and v_liq is None and p_ir is not None:
                    try:
                        taxa = float(str(p_ir).replace('%', '').replace(',', '.').strip()) / 100.0
                        calculado = round(float(v_bruto) * (1 - taxa), 8)
                        
                        if isinstance(v_liq_obj, dict):
                            v_liq_obj['valor'] = calculado
                            v_liq_obj['trecho_origem'] = "Calculado deterministicamente via regra de IRRF do JCP"
                            v_liq_obj['confianca'] = 0.95
                            v_liq = calculado
                    except Exception:
                        pass

                if v_bruto is not None and v_liq is not None and p_ir is not None:
                    try:
                        taxa = float(str(p_ir).replace('%', '').replace(',', '.').strip()) / 100.0
                        liquido_calculado = round(float(v_bruto) * (1 - taxa), 8)
                        liquido_informado = round(float(v_liq), 8)
                        if abs(liquido_calculado - liquido_informado) > 0.0001:
                            erros.append(f"Divergência matemática no JCP: Líquido informado ({v_liq}) difere do calculado ({liquido_calculado}).")
                    except Exception:
                        pass

        except Exception as e:
            erros.append(f"Erro sistêmico nas regras de coerência: {str(e)}")

        is_valido = len(erros) == 0
        return is_valido, erros