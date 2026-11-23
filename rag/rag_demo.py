"""Small RAG demo - LangChain + ChromaDB.

Indexes a few sample academic documents (synthetic) in a local ChromaDB
vector store and answers a question by retrieving the most relevant chunks.
This mirrors, at demo scale, the RAG assistant built at UM6P to query
academic / ABET documentation in natural language.

Run:  pip install -r requirements.txt && python rag/rag_demo.py
"""

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings

SAMPLE_DOCS = [
    "CLO1: Apply knowledge of computing and mathematics appropriate to the programme.",
    "SO1: Analyse a complex computing problem and apply principles of computing to solve it.",
    "A CLO is considered attained when at least 70% of students score at least 70%.",
    "The Gold layer of the Lakehouse exposes fact_grades, dim_course and dim_student to Power BI.",
    "Course Learning Outcomes (CLOs) are mapped to ABET Student Outcomes (SOs) per programme.",
]


def main():
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    store = Chroma.from_documents(
        [Document(page_content=text) for text in SAMPLE_DOCS],
        embedding=embeddings,
        collection_name="abet_demo",
    )
    question = "When is a CLO considered attained?"
    results = store.similarity_search(question, k=2)
    print(f"Question: {question}\n")
    for doc in results:
        print(f"- {doc.page_content}")


if __name__ == "__main__":
    main()
