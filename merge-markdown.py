import os
import glob
from pathlib import Path

def consolidate_markdown_files(input_directory, output_file):
    """
    Consolida todos os arquivos .md de um diretório em um único arquivo.
    
    Args:
        input_directory (str): Caminho para o diretório com os arquivos .md
        output_file (str): Nome do arquivo de saída consolidado
    """
    
    # Caminho completo do diretório
    docs_path = Path(input_directory)
    
    if not docs_path.exists():
        print(f"Erro: O diretório '{input_directory}' não foi encontrado.")
        return
    
    # Busca todos os arquivos .md recursivamente
    md_files = list(docs_path.rglob('*.md'))
    
    if not md_files:
        print("Nenhum arquivo .md encontrado no diretório especificado.")
        return
    
    print(f"Encontrados {len(md_files)} arquivos Markdown.")
    
    # Ordena os arquivos por caminho para manter consistência
    md_files.sort(key=lambda x: str(x))
    
    with open(output_file, 'w', encoding='utf-8') as consolidated_file:
        # Cabeçalho do documento consolidado
        consolidated_file.write("# Documentação Consolidada - Segura\n\n")
        consolidated_file.write("---\n\n")
        
        for md_file in md_files:
            try:
                # Caminho relativo para melhor organização
                relative_path = md_file.relative_to(docs_path)
                
                # Adiciona separador e título da seção
                consolidated_file.write(f"\n\n## Arquivo: {relative_path}\n\n")
                consolidated_file.write("---\n\n")
                
                # Lê e adiciona o conteúdo do arquivo
                with open(md_file, 'r', encoding='utf-8') as current_file:
                    content = current_file.read()
                    consolidated_file.write(content)
                    consolidated_file.write("\n\n")
                
                print(f"Processado: {relative_path}")
                
            except Exception as e:
                print(f"Erro ao processar {md_file}: {str(e)}")
    
    print(f"\nConsolidação concluída! Arquivo salvo como: {output_file}")
    
    # Estatísticas do arquivo gerado
    with open(output_file, 'r', encoding='utf-8') as f:
        lines = len(f.readlines())
        f.seek(0)
        chars = len(f.read())
    
    print(f"Estatísticas do arquivo consolidado:")
    print(f"- Linhas: {lines:,}")
    print(f"- Caracteres: {chars:,}")

def main():
    # Configuração dos caminhos
    input_dir = r"C:\Users\PauloGuilhermePilott\Documents\Ferramentas\gartner\senhasegura_docs_repo\4.0\en"
    output_file = "senhasegura_docs_consolidated.md"
    
    print("Iniciando consolidação da documentação Senhasegura...")
    print(f"Diretório de origem: {input_dir}")
    print(f"Arquivo de destino: {output_file}")
    print("-" * 50)
    
    consolidate_markdown_files(input_dir, output_file)

if __name__ == "__main__":
    main()