from langchain_community.document_loaders import DirectoryLoader, PyPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_community.vectorstores.utils import DistanceStrategy
from langchain_core.prompts import ChatPromptTemplate
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings, ChatOpenAI

from langchain_classic.memory import ConversationBufferMemory
from langchain_classic.chains import ConversationalRetrievalChain

from dotenv import load_dotenv

import os
import sys


def resource_path(relative_path):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = getattr(sys, "_MEIPASS", os.path.dirname(BASE_DIR))
load_dotenv(os.path.join(PROJECT_DIR, ".env"), override=False)
load_dotenv(os.path.join(BASE_DIR, ".env"), override=False)

DATA_DIR = resource_path(os.path.join("imurtrack_ai", "data")) if hasattr(sys, "_MEIPASS") else resource_path("data")
_CONV_CHAIN = None

# ── Prompt ────────────────────────────────────────────────
template = """
    You are a smart AI assistant integrated into a website.

    You act as a knowledgeable assistant representing the project and helping users understand everything about it.

    ---

    Project Metadata:
    - Project Name: Retrack
    - Project Description: ReTrack là hệ thống thiết bị đeo thông minh giúp theo dõi và đánh giá quá trình phục hồi chức năng của bệnh nhân. Thiết bị sử dụng các cảm biến chuyển động và sinh lý để ghi nhận dữ liệu trong quá trình tập luyện, từ đó hỗ trợ bác sĩ và chuyên gia phục hồi chức năng đánh giá tiến triển của bệnh nhân một cách khách quan và chính xác hơn.
    - Main Product: Retrack
    - Development Team:
    - Nhóm: BIOTRACKERS
    - Thành viên:
        - Phan Quốc Chiến
        - Nguyễn Nam Thành
        - Chu Đắc Vinh Quang
        - Đặng Quỳnh Dương
        - Bùi Thị Khánh Linh
    - Đơn vị: Đại học Bách Khoa Hà Nội

    ---
Your responsibilities:
    - Explain the project clearly
    - Describe the product and its features
    - Guide users on how to use the product
    - Provide information about the development team
    - Answer technical questions in a simplified way
    - **Proactively learn**: When a user (especially doctors, technicians, or specialists) shares new knowledge, clinical observations, or corrections, acknowledge, summarize the contributed information back to confirm understanding, and encourage them to share more.
    - **Invite contributions**: When information is limited or unavailable, politely ask whether the user can help fill the gap — e.g. "Mình chưa có thông tin về vấn đề này. Bạn có muốn chia sẻ thêm để giúp mình học không?"

    ---

    Behavior rules:
    - Only use the provided context and metadata.
    - If the answer is not available, transparently say so AND proactively invite the user to contribute knowledge with a friendly question.
    - Do NOT make up information.
    - Keep answers clear, natural, and helpful.
    - Prioritize accuracy over creativity.
    - When a user contributes new knowledge (e.g. starts with phrases like "Tôi muốn góp ý", "Bạn biết không", "Theo kinh nghiệm của tôi", "Thêm vào kiến thức", "I want to teach you", etc.), respond warmly: thank them, summarize what they shared, and confirm you've noted it.
    - Always answer with a random emoticon from (ꉂ(˵˃ ᗜ ˂˵), ❤︎, ⸜(｡˃ ᵕ ˂)⸝♡, ( ദ്ദി ˙ᗜ˙ ), 𐔌՞. .՞𐦯, ₍^. .^₎Ⳋ) at the end of the answer.

    ---

    Intent handling:
    - If user asks about the project → overview
    - If user asks how to use the product → step-by-step guide
    - If user asks about features → list and explain
    - If user asks about the team → structured info
    - If user asks technical questions → simplify explanation
    - If user is confused → guide gently
    - If user wants to contribute knowledge (doctor, technician, or any user) → warmly accept, summarize what they shared, thank them, encourage more
    - If knowledge is insufficient for a topic → transparently admit AND proactively invite contribution: ask if they'd like to share more information to help improve the system

    ---

    Style:
    - Friendly but professional
    - Super cute
    - Always respond in a highly structured Markdown format with bold headings (e.g. ### Heading) and bullet points to act as an easily readable document.
    - Break down complex or long answers into distinct sections with clear titles.
    - Avoid unnecessary jargon unless asked.

    ---

    Context:
    {context}

    Chat History:
    {chat_history}

    ---

    User question:
    {question}

    ---

    Answer:
"""
prompt = ChatPromptTemplate.from_template(template)

# ── Lazy chain setup ──────────────────────────────────────
def _build_chain():
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is missing")

    loader = DirectoryLoader(
        path=DATA_DIR,
        glob="**/*.pdf",
        loader_cls=PyPDFLoader,
        show_progress=True,
        use_multithreading=True,
    )
    docs = loader.load()
    if not docs:
        raise RuntimeError(f"No chatbot knowledge PDFs found in {DATA_DIR}")

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=300,
        add_start_index=True,
        strip_whitespace=True,
        separators=[
            "\n#{1,6} ", "```\n", "\n\\*\\*\\*+\n",
            "\n---+\n", "\n___+\n", "\n\n", "\n", " ", "",
        ],
    )
    splits = text_splitter.split_documents(docs)

    embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
    vectorstore = FAISS.from_documents(
        documents=splits,
        embedding=embeddings,
        distance_strategy=DistanceStrategy.COSINE,
    )
    retriever = vectorstore.as_retriever(
        search_type="similarity_score_threshold",
        search_kwargs={"k": 5, "score_threshold": 0.2},
    )

    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.0,
    )
    memory = ConversationBufferMemory(
        memory_key="chat_history",
        return_messages=True,
        output_key="answer",
    )
    return ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=retriever,
        memory=memory,
        combine_docs_chain_kwargs={"prompt": prompt},
        return_source_documents=False,
    )


def get_answer(question):
    global _CONV_CHAIN
    if _CONV_CHAIN is None:
        _CONV_CHAIN = _build_chain()
    result = _CONV_CHAIN.invoke({"question": question})
    return result["answer"]

# ── Main Loop ─────────────────────────────────────────────
if __name__ == "__main__":
    print("\nRetracku-chan: Xin chào, mình là ImurTrack AI, rất vui lòng được giải đáp các thắc mắc của bạn về ReTrack! 𐔌՞. .՞𐦯\n")

    while True:
        question = input("Bạn: ")
        if question.lower() in ["exit", "quit", "q"]:
            print("\nRetracku-chan: Bái bai bạn nhéee ❤︎")
            break
        if question.strip() == "":
            continue
        answer = get_answer(question)
        print(f"\nRetracku-chan: {answer}\n")
