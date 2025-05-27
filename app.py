# app.py (Versão final com separação de templates e arquivos estáticos)
import os
import json
from flask import Flask, request, jsonify, render_template # Adicionado render_template
import google.generativeai as genai
import numpy as np
from dotenv import load_dotenv
from scipy.spatial.distance import cosine
import re
import logging
import time

# --- Configuração de Logging ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[
                        logging.FileHandler("app_errors.log"),
                        logging.StreamHandler()
                    ])

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

app = Flask(__name__)

# --- Configuração da API do Google Gemini ---
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    logging.error("A variável de ambiente GOOGLE_API_KEY não está configurada.")
    raise ValueError("A variável de ambiente GOOGLE_API_KEY não está configurada.")

genai.configure(api_key=GOOGLE_API_KEY)

EMBEDDING_MODEL = "models/embedding-001"
GENERATIVE_MODEL = "models/gemini-1.5-pro-latest" # Ou "models/gemini-pro" se preferir

# Variável global para armazenar os dados carregados
PROCESSED_DOCS = []

def load_documentation():
    """
    Carrega a documentação processada (documentos completos com embeddings de título/resumo).
    Retorna True se o carregamento for bem-sucedido, False caso contrário.
    """
    global PROCESSED_DOCS
    try:
        with open('processed_docs.json', 'r', encoding='utf-8') as f:
            PROCESSED_DOCS = json.load(f)
        logging.info(f"Carregados {len(PROCESSED_DOCS)} documentos indexados da documentação.")
        return True
    except FileNotFoundError:
        logging.error("Arquivo 'processed_docs.json' não encontrado. Por favor, execute 'generate_embeddings.py' primeiro.")
        return False
    except json.JSONDecodeError as e:
        logging.error(f"Erro ao decodificar JSON do arquivo de documentação: {e}")
        return False
    except Exception as e:
        logging.error(f"Erro inesperado ao carregar documentação: {e}")
        return False

def generate_embedding(text):
    """Gera um embedding para o texto fornecido."""
    try:
        response = genai.embed_content(model=EMBEDDING_MODEL, content=text)
        return response['embedding']
    except Exception as e:
        logging.error(f"Erro ao gerar embedding para o texto (primeiros 50 caracteres: '{text[:50]}'): {e}", exc_info=True)
        return None

def get_relevant_documents(query_embedding, top_k=5):
    """
    Encontra os documentos mais relevantes com base na similaridade de cosseno
    entre o embedding da pergunta e o embedding de título/resumo de cada documento.
    Retorna uma lista de tuplas: (similaridade, doc_info).
    """
    similarities = []
    for doc_info in PROCESSED_DOCS:
        doc_embedding = np.array(doc_info.get("embedding"))
        
        if doc_embedding is not None and len(doc_embedding) > 0 and len(query_embedding) == len(doc_embedding):
            try:
                similarity = 1 - cosine(query_embedding, doc_embedding)
                similarities.append((similarity, doc_info))
            except ValueError as e:
                logging.warning(f"Erro ao calcular similaridade para documento '{doc_info.get('title', 'N/A')}': {e}. Verifique as dimensões dos embeddings.")
        else:
            logging.warning(f"Documento '{doc_info.get('title', 'N/A')}' com embedding inválido ou incompatível. Pulando.")
    
    similarities.sort(key=lambda x: x[0], reverse=True)
    
    return similarities[:top_k]

def analyze_coverage_with_context(query, relevant_docs_with_similarity):
    """
    Analisa a cobertura da documentação para uma query/tópico e sugere lacunas,
    usando os documentos completos como contexto para a análise.
    Retorna um dicionário com a resposta do modelo e informações dos documentos relevantes.
    """
    if not PROCESSED_DOCS:
        return {"response_text": "A documentação não foi carregada. Por favor, verifique a inicialização da aplicação.", "relevant_docs_info": []}

    relevant_docs_info = []
    if not relevant_docs_with_similarity:
        prompt_for_suggestions = f"""
        A documentação atual não contém informações diretas sobre o tópico: "{query}".
        Com base no seu conhecimento geral sobre documentação de produtos de segurança da informação,
        por favor, sugira **5 possíveis tópicos de documentos ou seções que poderiam ser criadas** para cobrir este assunto.
        Formate as sugestões como uma lista numerada simples.

        **Sugestões:**
        """
        logging.info(f"Gerando sugestões de cobertura para: '{query}' (nenhum doc relevante)")
        try:
            model = genai.GenerativeModel(GENERATIVE_MODEL)
            response = model.generate_content(
                prompt_for_suggestions,
                generation_config=genai.types.GenerationConfig(temperature=0.7)
            )
            return {"response_text": f"Não foi possível encontrar informações claras na documentação sobre '{query}'. \n\n**Possíveis tópicos para cobrir esta lacuna:**\n{response.text}", "relevant_docs_info": []}
        except Exception as e:
            logging.error(f"Erro ao gerar sugestões de cobertura: {e}", exc_info=True)
            return {"response_text": f"Não foi possível encontrar informações claras na documentação sobre '{query}'. Erro ao gerar sugestões.", "relevant_docs_info": []}
    else:
        context_str = ""
        for sim, doc in relevant_docs_with_similarity:
            similarity_percent = f"{sim * 100:.2f}%"
            context_str += f"Título: {doc['title']}\nSlug: {doc.get('slug', 'N/A')}\nCaminho do Arquivo: {doc.get('filepath', 'N/A')}\nConteúdo: {doc['content']}\n\n"
            relevant_docs_info.append({
                "title": doc['title'],
                "slug": doc.get('slug', 'N/A'),
                "relevance": similarity_percent
            })

        prompt_for_refinement = f"""
        A pergunta/tópico para análise de cobertura é: "{query}".
        Com base no contexto fornecido da documentação existente abaixo, e no seu conhecimento geral sobre documentação de produtos de segurança da informação,
        identifique **3 a 5 pontos de melhoria ou expansão** na documentação atual relacionados a este tópico.
        Formate cada sugestão como um item de lista numerada. Para cada sugestão, inclua um **título sugerido** e um **conteúdo sugerido** em sub-itens com asterisco. Se houver manuais ou documentos mencionados, sugira adicionar links diretos.

        **Contexto de Documentação Relevante (conteúdo completo dos documentos com título, slug e caminho do arquivo):**
        {context_str}

        **Sugestões de Melhoria de Cobertura para '{query}':**
        """
        logging.info(f"Gerando análise de cobertura com contexto para: '{query}'")
        try:
            model = genai.GenerativeModel(GENERATIVE_MODEL)
            response = model.generate_content(
                prompt_for_refinement,
                generation_config=genai.types.GenerationConfig(temperature=0.4)
            )
            return {"response_text": f"A documentação existente já aborda o tópico '{query}' em parte. Para uma cobertura mais abrangente, considere as seguintes melhorias:\n\n{response.text}", "relevant_docs_info": relevant_docs_info}
        except Exception as e:
            logging.error(f"Erro ao gerar análise de cobertura com contexto: {e}", exc_info=True)
            return {"response_text": f"A documentação existente já aborda o tópico '{query}' em parte. Erro ao analisar melhorias.", "relevant_docs_info": []}

# --- Rotas da Aplicação ---

@app.route('/')
def index():
    """Página inicial com o formulário de análise de cobertura."""
    # Renderiza o template index.html que agora está na pasta 'templates/'
    return render_template('index.html')

@app.route('/gartner/templates/help.html') # Rota mais limpa, sem caminhos de pasta
def help_page():
    return render_template('help.html') # Flask encontrará em templates/help.html

@app.route('/analyze_coverage', methods=['POST'])
def handle_analyze_coverage():
    """Rota para analisar a cobertura da documentação."""
    data = request.get_json()
    query = data.get('query', '').strip()
    if not query:
        return jsonify({"error": "Nenhuma informação/tópico fornecido para análise de cobertura."}), 400

    logging.info(f"Recebida solicitação de análise de cobertura para: '{query[:70]}...'")
    try:
        query_embedding = generate_embedding(query)
        if query_embedding is None:
            return jsonify({"error": "Não foi possível gerar o embedding para a consulta."}), 500

        relevant_docs_with_similarity = get_relevant_documents(query_embedding, top_k=5)

        coverage_result = analyze_coverage_with_context(query, relevant_docs_with_similarity)
        
        return jsonify(coverage_result)
    except Exception as e:
        logging.error(f"Erro na rota /analyze_coverage: {e}", exc_info=True)
        return jsonify({"error": f"Erro interno ao analisar cobertura: {e}", "response_text": "", "relevant_docs_info": []}), 500


# Bloco de inicialização da aplicação Flask
with app.app_context():
    if not load_documentation():
        logging.critical("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        logging.critical("ERRO CRÍTICO: Os dados da documentação não foram carregados com sucesso.")
        # Mensagem de erro atualizada para refletir a nova estrutura de arquivos
        logging.critical("A aplicação pode não funcionar corretamente. Verifique 'processed_docs.json' e execute 'extract_data_from_markdown.py' seguido por 'generate_embeddings.py'.")
        logging.critical("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    else:
        logging.info("Dados da documentação e embeddings carregados com sucesso.")

if __name__ == '__main__':
    app.run(debug=True)