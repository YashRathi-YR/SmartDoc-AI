import streamlit as st
from PyPDF2 import PdfReader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
import google.generativeai as genai
from langchain.vectorstores import FAISS
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.chains.question_answering import load_qa_chain
from langchain.prompts import PromptTemplate
import os

st.set_page_config(page_title="Doctor Document ", layout="wide")

st.markdown("""
## Doctor Document: Get instant insights from your Documents and Information related to them.

This chatbot is built using the Retrieval-Augmented Generation (RAG) framework, leveraging Google's Generative AI model Gemini-PRO. It processes uploaded PDF documents by breaking them down into manageable chunks, creates a searchable vector store, and generates accurate answers to user queries. This advanced approach ensures high-quality, contextually relevant responses for an efficient and effective user experience.

### How It Works

Follow these simple steps to interact with the chatbot:

1. **Enter Your API Key**: You'll need a Google API key for the chatbot to access Google's Generative AI models. Obtain your API key [here](https://makersuite.google.com/app/apikey).

2. **Upload Your Documents**: The system accepts multiple PDF files at once, analyzing the content to provide comprehensive insights.

3. **Ask a Question**: After processing the documents, ask any question related to the content of your uploaded documents for a precise answer.
""")

api_key = st.text_input("Enter your Google API Key:", type="password", key="api_key_input")

def get_pdf_text(pdf_docs):
    text = ""
    for pdf in pdf_docs:
        pdf_reader = PdfReader(pdf)
        for page in pdf_reader.pages:
            text += page.extract_text()
    return text

def get_text_chunks(text):
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = text_splitter.split_text(text)
    return chunks

def get_vector_store(text_chunks, api_key):
    embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001", google_api_key=api_key)
    vector_store = FAISS.from_texts(text_chunks, embedding=embeddings)
    vector_store.save_local("faiss_index")

def get_conversational_chain(api_key):
    prompt_template = """
    Answer the question as detailed as possible from the provided context. If the answer is not in the provided context, use your knowledge to answer the question based on related information, but clearly indicate that the answer is based on external knowledge.\n\n
    Context:\n {context}\n
    Question: \n{question}\n

    Answer:
    """
    model = ChatGoogleGenerativeAI(model="gemini-pro", temperature=0.3, google_api_key=api_key)
    prompt = PromptTemplate(template=prompt_template, input_variables=["context", "question"])
    chain = load_qa_chain(model, chain_type="stuff", prompt=prompt)
    return chain

def user_input(user_question, api_key):
    try:
        # Load the FAISS index
        embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001", google_api_key=api_key)
        new_db = FAISS.load_local("faiss_index", embeddings, allow_dangerous_deserialization=True)
        docs = new_db.similarity_search(user_question, k=4)

        # Generate response from PDF context
        chain = get_conversational_chain(api_key)
        response = chain({"input_documents": docs, "question": user_question}, return_only_outputs=True)

        # Check if the response contains context from the PDF
        if "the provided context does not mention" not in response["output_text"].lower():
            return f"**Answer from PDF context:** {response['output_text']}"
        else:
            # Generate fallback response using external knowledge
            model = ChatGoogleGenerativeAI(model="gemini-pro", temperature=0.3, google_api_key=api_key)
            fallback_response = model({"question": user_question})

            # Ensure the fallback response is correctly formatted
            if isinstance(fallback_response, dict) and 'output_text' in fallback_response:
                external_answer = fallback_response['output_text']
            elif isinstance(fallback_response, str):
                external_answer = fallback_response
            else:
                external_answer = "No response from external model."

            return f"**The provided context does not mention what {user_question} is, but here is what {user_question} means:** {external_answer}"
    except Exception as e:
        st.error(f"An error occurred: {e}")
        st.write(f"Debug: Exception details: {str(e)}")
        return ""

def main():
    st.header("Doctor Document: An AI Document Chatbot💁")

    if 'conversation' not in st.session_state:
        st.session_state.conversation = []

    def submit_question():
        user_question = st.session_state.user_question
        answer = user_input(user_question, api_key)
        st.session_state.conversation.append({"question": user_question, "answer": answer})

    # Display conversation history
    chat_container = st.container()
    with chat_container:
        for chat in st.session_state.conversation:
            st.write(f"**Question:** {chat['question']}")
            st.write(f"**Answer:** {chat['answer']}")

    # Question input form at the bottom
    question_container = st.container()
    with question_container:
        with st.form(key='question_form', clear_on_submit=True):
            st.text_input("Ask a Question from the PDF Files", key="user_question")
            st.form_submit_button(label='Submit Question', on_click=submit_question)

    with st.sidebar:
        st.title("Menu:")
        pdf_docs = st.file_uploader("Upload your PDF Files and Click on the Submit & Process Button", accept_multiple_files=True, key="pdf_uploader")
        if st.button("Submit & Process", key="process_button") and api_key:  # Check if API key is provided before processing
            with st.spinner("Processing..."):
                raw_text = get_pdf_text(pdf_docs)
                text_chunks = get_text_chunks(raw_text)
                get_vector_store(text_chunks, api_key)
                st.success("Done")

if __name__ == "__main__":
    main()
