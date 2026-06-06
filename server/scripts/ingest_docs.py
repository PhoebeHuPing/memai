import os
import sys
from dotenv import load_dotenv

# Add project root to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from server.services.rag_service import RAGService

def main():
    # Load environment variables from .env
    load_dotenv()
    
    # Path to source PDF documents
    data_dir = os.path.join(os.getcwd(), "server", "data")
    
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
        print(f"Created data directory at: {data_dir}")
        print("Please place MOE policy PDF files in this directory and run the script again.")
        return

    # Check if there are any PDFs in the directory
    pdfs = [f for f in os.listdir(data_dir) if f.endswith('.pdf')]
    if not pdfs:
        print(f"No PDF files found in {data_dir}.")
        print("Please place MOE policy PDF files in this directory and run the script again.")
        return

    print(f"Found {len(pdfs)} PDF(s). Starting ingestion pipeline...")
    
    try:
        service = RAGService()
        service.ingest_documents(data_dir)
        print("✅ Ingestion completed successfully. ChromaDB is now populated.")
    except Exception as e:
        print(f"❌ Error during ingestion: {e}")

if __name__ == "__main__":
    main()
