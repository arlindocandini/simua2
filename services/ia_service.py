import base64
import openai
import os
import json
from flask import current_app


class IAService:
    """Serviço otimizado para classificação de imagens usando GPT-4-Vision."""

    # ============================================================
    # 🔹 Codificação da imagem
    # ============================================================
    @staticmethod
    def encode_image(image_path):
        """Codifica imagem em base64."""
        image_path = os.path.normpath(image_path)
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Imagem não encontrada: {image_path}")

        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")

    # ============================================================
    # 🔹 Classificação da imagem
    # ============================================================
    @staticmethod
    def classificar_imagem(image_path):
        """
        Classifica a imagem retornando **todas** as ocorrências detectadas.

        Retorna uma lista normalizada de dicionários:
        [
            {
                "categoria": str,   # ex: "animal_na_pista"
                "urgencia": str,    # ex: "urgente"
                "descricao": str,   # breve descrição (1–3 frases)
                "confidence": float
            },
            ...
        ]

        Caso nada seja detectado, retorna uma lista vazia.
        """
        try:
            # Configuração da API
            openai.api_key = current_app.config["OPENAI_API_KEY"]

            # Codificar imagem
            current_app.logger.info(f"📸 Processando imagem: {image_path}")
            base64_image = IAService.encode_image(image_path)
            current_app.logger.info(f"✅ Imagem codificada ({len(base64_image)} chars)")

            # ============================================================
            # 🔹 Prompt otimizado (curto, objetivo e econômico)
            # ============================================================
            prompt = """
Você é um sistema de CLASSIFICAÇÃO ROBÓTICA de imagens urbanas.

Analise a imagem e identifique **todas** as ocorrências presentes, usando os códigos abaixo.

CATEGORIAS (use APENAS o código de 4 letras):
- asfd → Asfalto danificado ou buraco na pista
- clcd → Calçada danificada
- ilmp → Iluminação pública com defeito
- fxep → Fiação exposta ou caída
- lxir → Lixo ou entulho irregular
- arvd → Árvore caída ou galhos obstruindo via
- mtal → Mato alto
- podn → Ponto de ônibus danificado
- vzma → Vazamento de água
- frtp → Frutas ou resíduos na pista
- plcd → Placa de trânsito danificada
- smfd → Semáforo com defeito
- sgap → Sinalização apagada
- objp → Objeto ou obstáculo na pista
- anmp → Animais soltos ou atravessando vias
- buen → Bueiro entupido
- bued → Bueiro danificado
- qumd → Queimada ou foco de incêndio
- obir → Obra irregular
- desconhecido → Caso nada se aplique

NÍVEL DE URGÊNCIA (use APENAS o código de 3 letras):
- emg → Emergência (risco imediato)
- urg → Urgente (precisa de atenção rápida)
- pcu → Pouco Urgente (sem risco imediato)
- nau → Não Urgente (pode aguardar)

INSTRUÇÕES DE RESPOSTA:
1. Responda SOMENTE com o JSON puro.
2. Liste todas as ocorrências encontradas; se nenhuma, retorne "ocorrencias": [].
3. Descrição curta: até 3 frases objetivas e claras.

Formato exato de resposta:
{
  "ocorrencias": [
    {
      "categoria": "codigo_curto_de_4_letras_ex: anmp",
      "urgencia": "codigo_curto_de_3_letras_ex: urg",
      "descricao": "Descrição curta (máximo 3 frases).",
      "confidence": 0.95
    }
  ]
}
"""

            # ============================================================
            # 🔹 Chamada ao modelo
            # ============================================================
            current_app.logger.info("🤖 Enviando requisição à OpenAI...")
            response = openai.chat.completions.create(
                model=current_app.config["OPENAI_MODEL"],
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt.strip()},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                },
                            },
                        ],
                    }
                ],
                max_tokens=200,
                temperature=0.2,
            )

            # ============================================================
            # 🔹 Processar resposta
            # ============================================================
            result_text = response.choices[0].message.content.strip()
            current_app.logger.info(f"📝 Resposta bruta: {result_text[:200]}")

            if result_text.startswith("```"):
                result_text = "\n".join(result_text.split("\n")[1:-1])
            if result_text.startswith("json"):
                result_text = result_text[4:].strip()

            result = json.loads(result_text)

            # Garantir que tenhamos uma lista de ocorrências
            if isinstance(result, dict) and "ocorrencias" in result:
                ocorrencias_brutas = result.get("ocorrencias") or []
            elif isinstance(result, list):
                ocorrencias_brutas = result
            elif isinstance(result, str) and result.lower().strip() == "sem ocorrencias":
                ocorrencias_brutas = []
            else:
                ocorrencias_brutas = []

            # ============================================================
            # 🔹 Mapeamento para ENUMs do banco
            # ============================================================
            CODIGOS_CATEGORIAS = {
                "asfd": "asfalto_dano",
                "clcd": "calcada_dano",
                "ilmp": "iluminacao_publica",
                "fxep": "fiacao_exposta",
                "lxir": "lixo_irregular",
                "arvd": "arvore_dano",
                "mtal": "mato_alto",
                "podn": "ponto_onibus_dano",
                "vzma": "vazamento_agua",
                "frtp": "fruta_na_pista",
                "plcd": "placa_dano",
                "smfd": "semaforo_defeito",
                "sgap": "sinalizacao_apagada",
                "objp": "objeto_na_pista",
                "anmp": "animal_na_pista",
                "buen": "bueiro_entupido",
                "bued": "bueiro_dano",
                "qumd": "queimada",
                "obir": "obra_irregular",
            }

            CODIGOS_URGENCIA = {
                "emg": "emergencia",
                "urg": "urgente",
                "pcu": "pouco_urgente",
                "nau": "nao_urgente",
                "des": "nao_urgente",
            }

            ocorrencias_normalizadas = []
            for ocorrencia in ocorrencias_brutas:
                if not isinstance(ocorrencia, dict):
                    continue

                cat = ocorrencia.get("categoria", "").strip().lower()
                urg = ocorrencia.get("urgencia", "").strip().lower()
                desc = (ocorrencia.get("descricao", "") or "").strip()

                categoria_final = CODIGOS_CATEGORIAS.get(cat, "desconhecido")
                urgencia_final = CODIGOS_URGENCIA.get(urg, "nao_urgente")

                ocorrencias_normalizadas.append({
                    "categoria": categoria_final,
                    "urgencia": urgencia_final,
                    "descricao": desc[:400],  # evita overflow
                    "confidence": min(max(float(ocorrencia.get("confidence", 0.5)), 0.0), 1.0),
                })

            current_app.logger.info(
                f"✅ Classificação retornou {len(ocorrencias_normalizadas)} ocorrência(s)"
            )

            return ocorrencias_normalizadas

        # ============================================================
        # 🔹 Tratamento de erros
        # ============================================================
        except json.JSONDecodeError as e:
            current_app.logger.error(f"❌ Erro ao decodificar JSON: {e}")
            current_app.logger.error(
                f"📄 Resposta: {result_text if 'result_text' in locals() else 'N/A'}"
            )
            return []

        except Exception as e:
            import traceback
            current_app.logger.error(f"❌ Erro na classificação IA: {e}")
            current_app.logger.error(traceback.format_exc())
            return []