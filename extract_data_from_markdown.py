# extract_data_from_markdown.py
import re
import json
import os

def extract_metadata_and_clean_content(full_doc_content):
    """
    Extrai metadados (title, slug) e retorna o conteúdo limpo sem o bloco de metadados.
    """
    metadata = {"title": None, "slug": None}
    
    metadata_block_match = re.search(r'(##\s*Metadata_Start.*?##\s*Metadata_End)', full_doc_content, re.DOTALL)
    
    content_without_metadata = full_doc_content

    if metadata_block_match:
        metadata_block = metadata_block_match.group(1)
        
        title_match = re.search(r'##\s*title:\s*(.*)', metadata_block)
        if title_match:
            metadata["title"] = title_match.group(1).strip()
        
        slug_match = re.search(r'##\s*slug:\s*(.*)', metadata_block)
        if slug_match:
            metadata["slug"] = slug_match.group(1).strip()
            
        content_without_metadata = full_doc_content.replace(metadata_block, '', 1).strip()
        
        # Lógica para remover anotações como ":::(Internal) (Private notes)"
        if content_without_metadata.startswith(':::'):
            # Encontra a primeira ocorrência de ":::" e pega o que vem depois
            parts = content_without_metadata.split(":::", 1)
            if len(parts) > 1:
                # Verifica se a parte após o ::: é o conteúdo real e não apenas espaços ou quebras de linha
                potential_content = parts[1].strip()
                # Uma heurística simples: se o conteúdo potencial tem mais de X caracteres ou contém alguma formatação de Markdown
                # pode ser o início do corpo do documento. Caso contrário, assume que o ":::" era uma anotação final.
                # Ajuste o 100 conforme a média de comprimento de anotações versus início de conteúdo.
                if len(potential_content) > 100 or re.search(r'^[#*`\-]', potential_content, re.MULTILINE):
                    content_without_metadata = potential_content
                else: # Se for uma string curta ou sem formatação, pode ser apenas uma anotação no final do meta
                    content_without_metadata = parts[0].strip() # Mantém a parte antes do :::
            # else: # Se não há segunda parte após o split, o ::: está no final do texto
            #     content_without_metadata = parts[0].strip()
        
    return metadata, content_without_metadata

def extract_data_from_markdown(markdown_file_path="senhasegura_docs_consolidated.md", output_json_path="raw_docs.json"):
    """
    Processa o arquivo markdown consolidado, extrai documentos individuais,
    seus metadados e conteúdo limpo, salvando-os em um JSON intermediário.
    """
    if not os.path.exists(markdown_file_path):
        print(f"Erro: O arquivo '{markdown_file_path}' não foi encontrado.")
        return False

    print(f"Extraindo dados do Markdown consolidado: '{markdown_file_path}'...")

    extracted_docs = []

    with open(markdown_file_path, 'r', encoding='utf-8') as f:
        full_content = f.read()

    # Regex para dividir por "## Arquivo: <caminho>.md" seguido por 3 ou mais hífens.
    doc_pattern = re.compile(r'## Arquivo: (.*?\.md)\s*\n*-{3,}\s*\n*(.*?)(?=\n## Arquivo:|\Z)', re.DOTALL)
    
    matches = doc_pattern.finditer(full_content)

    num_processed = 0
    
    for match in matches:
        file_path_relative = match.group(1).strip()
        raw_doc_content = match.group(2).strip()

        if not raw_doc_content:
            print(f"Atenção: Conteúdo vazio para o arquivo '{file_path_relative}'. Pulando.")
            continue

        metadata, cleaned_content = extract_metadata_and_clean_content(raw_doc_content)
        
        doc_title = metadata["title"]
        doc_slug = metadata["slug"]

        # Fallback para título e slug se não forem encontrados no frontmatter
        if not doc_title:
            doc_title = os.path.basename(file_path_relative).replace('.md', '').replace('-', ' ').replace('_', ' ').strip()
            print(f"Atenção: Título não encontrado no frontmatter para '{file_path_relative}'. Usando '{doc_title}'.")
        
        if not doc_slug:
            temp_slug_source = doc_title if doc_title else os.path.basename(file_path_relative).replace('.md', '')
            doc_slug = re.sub(r'[^a-z0-9]+', '-', temp_slug_source.lower()).strip('-')
            print(f"Atenção: Slug não encontrado no frontmatter para '{file_path_relative}'. Gerando: '{doc_slug}'.")

        if not cleaned_content:
            print(f"Atenção: Conteúdo efetivo (sem metadados) vazio para o arquivo '{file_path_relative}'. Pulando.")
            continue

        doc_data = {
            "title": doc_title,
            "slug": doc_slug,
            "content": cleaned_content, # Conteúdo LIMPO do documento
            "filepath": file_path_relative,
        }
        extracted_docs.append(doc_data)
        num_processed += 1
        if num_processed % 10 == 0:
            print(f"Extraídos {num_processed} documentos...")
    
    if not extracted_docs:
        print("Nenhum documento extraído com sucesso. Verifique o arquivo de entrada.")
        return False

    try:
        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(extracted_docs, f, ensure_ascii=False, indent=4)
        print(f"Extração concluída. Salvou {len(extracted_docs)} documentos em '{output_json_path}'.")
        return True
    except Exception as e:
        print(f"Erro ao salvar o arquivo JSON: {e}")
        return False

if __name__ == "__main__":
    success = extract_data_from_markdown()
    if not success:
        print("A extração dos dados do Markdown falhou.")
    else:
        print("Extração dos dados do Markdown concluída com sucesso.")