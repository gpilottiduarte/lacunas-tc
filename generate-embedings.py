# generate_embeddings.py
import json
import os
import google.generativeai as genai
from dotenv import load_dotenv
import time

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# --- Configuração da API do Google Gemini ---
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("A variável de ambiente GOOGLE_API_KEY não está configurada.")
genai.configure(api_key=GOOGLE_API_KEY)
EMBEDDING_MODEL = "models/embedding-001"

def clean_text_for_embedding(text):
    """
    Remove caracteres especiais e formatação markdown para texto que será EMBEDDADO.
    Pode ser mais agressivo aqui, pois é apenas para o embedding de busca.
    """
    import re # Importa re dentro da função para ser autocontido, ou globalmente no topo
    # Remove links markdown, bold/italic, cabeçalhos, code blocks, blockquotes, listas, tabelas
    text = re.sub(r'\[.*?\]\(.*?\)|\*\*|__|\*|_|#+|`+|^\s*[-+*]\s*|^>\s*|\|.*?-+\s*\|', '', text, flags=re.MULTILINE)
    text = re.sub(r'\s+', ' ', text).strip() # Remove múltiplos espaços e quebras de linha
    text = re.sub(r'\n+', ' ', text).strip() # Substitui múltiplas quebras de linha por um espaço
    return text

def generate_embedding_with_retry(text_content):
    """
    Gera um embedding para o conteúdo de texto, com mecanismo de retry.
    """
    retries = 3
    for attempt in range(retries):
        try:
            response = genai.embed_content(model=EMBEDDING_MODEL, content=text_content)
            return response['embedding']
        except Exception as e:
            print(f"Erro ao gerar embedding (tentativa {attempt+1}/{retries}): {e}")
            if attempt < retries - 1:
                time.sleep(2 ** attempt) # Espera exponencial
            else:
                return None # Retorna None se todas as retries falharem
    return None

def generate_embeddings_for_docs(input_json_path="raw_docs.json", output_json_path="processed_docs.json"):
    """
    Lê o JSON com dados de documentos, gera embeddings para cada um,
    e salva o resultado final com embeddings em um novo JSON.
    """
    if not os.path.exists(input_json_path):
        print(f"Erro: O arquivo '{input_json_path}' não foi encontrado. Por favor, execute 'extract_data_from_markdown.py' primeiro.")
        return False

    print(f"Gerando embeddings para documentos de '{input_json_path}'...")

    try:
        with open(input_json_path, 'r', encoding='utf-8') as f:
            raw_docs = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Erro ao decodificar JSON de '{input_json_path}': {e}")
        return False
    except Exception as e:
        print(f"Erro inesperado ao carregar '{input_json_path}': {e}")
        return False

    processed_docs = []
    total_docs = len(raw_docs)
    
    for i, doc_data in enumerate(raw_docs):
        doc_title = doc_data.get("title", "Título Desconhecido")
        doc_content = doc_data.get("content", "")
        file_path_relative = doc_data.get("filepath", "N/A")

        # Para o embedding, usamos o título + uma parte do conteúdo limpo
        embedding_text_raw = f"{doc_title}. {doc_content[:1024]}" # Limite para evitar exceder tokens
        
        embedding_text = clean_text_for_embedding(embedding_text_raw)
        
        if not embedding_text.strip():
            print(f"Atenção: Texto limpo para embedding vazio para o arquivo '{file_path_relative}'. Pulando embedding.")
            doc_data["embedding"] = None # Marcar como None ou omitir se não houver embedding
            processed_docs.append(doc_data)
            continue

        doc_embedding = generate_embedding_with_retry(embedding_text)

        if doc_embedding is not None:
            doc_data["embedding"] = doc_embedding
            processed_docs.append(doc_data)
            if (i + 1) % 10 == 0:
                print(f"Gerados embeddings para {i + 1}/{total_docs} documentos...")
        else:
            print(f"Atenção: Falha ao gerar embedding para o arquivo '{file_path_relative}'. Documento será incluído sem embedding.")
            doc_data["embedding"] = None # Explicitamente define como None
            processed_docs.append(doc_data) # Inclui o documento mesmo sem embedding, mas com None

    if not processed_docs:
        print("Nenhum documento processado com sucesso (sem embeddings ou dados de entrada).")
        return False

    try:
        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(processed_docs, f, ensure_ascii=False, indent=4)
        print(f"Geração de embeddings concluída. Salvou {len(processed_docs)} documentos com embeddings em '{output_json_path}'.")
        return True
    except Exception as e:
        print(f"Erro ao salvar o arquivo JSON: {e}")
        return False

if __name__ == "__main__":
    success = generate_embeddings_for_docs()
    if not success:
        print("A geração de embeddings falhou.")
    else:
        print("Geração de embeddings concluída com sucesso.")