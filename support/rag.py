import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
import os
from pypdf import PdfReader

# Initialize Chromadb client
client = chromadb.PersistentClient(path="./chroma_db")

embedding_fn = DefaultEmbeddingFunction()

# get or create collection
collection = client.get_or_create_collection(
    name="coolbreeze_docs",
    embedding_function=embedding_fn
)

def chunk_text(text, chunk_size=500):
    chunks = []
    current_chunks = []
    current_size = 0

    words = text.split()
    for word in words:
        current_chunks.append(word)
        current_size += len(word) + 1

        if current_size >= chunk_size:
            chunks.append(' '.join(current_chunks))
            current_chunks = []
            current_size = 0
    
    if current_chunks:
        chunks.append(' '.join(current_chunks))

    return chunks

def load_documents():
    docs_path = "support/documents/"
    documents = []
    ids = []

    for filename in os.listdir(docs_path):
        if filename.endswith('.pdf'):
            file_path = os.path.join(docs_path, filename)

            reader = PdfReader(file_path)
            raw_text = ""

            for page in reader.pages:
                raw_text += page.extract_text()
            
            chunks = chunk_text(raw_text, chunk_size=500)

            for i, chunk in enumerate(chunks):
                documents.append(chunk)
                unique_id = f"{filename}_{i}"
                ids.append(unique_id)

    # Load the data into the ChromaDB collection
    if documents:
        collection.add(
            documents=documents,
            ids=ids
        )
    print(f"Loaded {len(documents)} chunks into ChromaDB.")


def search_knowledge_base(query):
    results = collection.query(query_texts=[query], n_results=3)
    if not results['documents'][0]:
        return 'No relevant information found in company documents.'

    matched_chunks = results['documents'][0]

    return '\n\n'.join(matched_chunks)