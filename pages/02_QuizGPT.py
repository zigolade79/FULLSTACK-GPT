import json

from langchain.document_loaders import UnstructuredFileLoader
from langchain.text_splitter import CharacterTextSplitter
from langchain.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.callbacks import StreamingStdOutCallbackHandler
import streamlit as st
from langchain.retrievers import WikipediaRetriever
from langchain.schema import BaseOutputParser, output_parser
import os
from langchain.schema.runnable import RunnableLambda, RunnablePassthrough

class JsonOutputParser(BaseOutputParser):
    def parse(self, text):
        text = text.replace("```", "").replace("json", "")
        return json.loads(text)


output_parser = JsonOutputParser()

st.set_page_config(
    page_title="QuizGPT",
    page_icon="❓",
)

st.title("QuizGPT")
st.session_state["api_key"] = st.session_state.get("api_key")

def save_key(api_key):
    st.session_state["api_key"] = api_key
with st.sidebar:
    
    save_key(st.text_input("Input API Key"))
    
os.environ["OPENAI_API_KEY"] = st.session_state["api_key"]


if st.session_state["api_key"] != '':
    llm = ChatOpenAI(
    temperature=0.1,
    model="gpt-3.5-turbo-1106",
    streaming=True,
    callbacks=[StreamingStdOutCallbackHandler()],
    )
        
    def format_docs(docs):
        return "\n\n".join(document.page_content for document in docs)



    questions_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """
        You are a helpful assistant that is role playing as a teacher.
            
        Based ONLY on the following context make 10 (TEN) questions minimum to test the user's knowledge about the text.

        Make the questions {level}.
        
        Each question should have 4 answers, three of them must be incorrect and one should be correct.
            
        Use (o) to signal the correct answer.
            
        Question examples:
            
        Question: What is the color of the ocean?
        Answers: Red|Yellow|Green|Blue(o)
            
        Question: What is the capital or Georgia?
        Answers: Baku|Tbilisi(o)|Manila|Beirut
            
        Question: When was Avatar released?
        Answers: 2007|2001|2009(o)|1998
            
        Question: Who was Julius Caesar?
        Answers: A Roman Emperor(o)|Painter|Actor|Model
            
        Your turn!
            
        Context: {context}
    """,
            )
        ]
    )

    ##questions_chain = {"context": RunnableLambda(format_docs), "level":  RunnablePassthrough() } | questions_prompt | llm
    questions_chain = questions_prompt | llm

    formatting_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """
        You are a powerful formatting algorithm.
        
        You format exam questions into JSON format.
        Answers with (o) are the correct ones.
        
        Example Input:

        Question: What is the color of the ocean?
        Answers: Red|Yellow|Green|Blue(o)
            
        Question: What is the capital or Georgia?
        Answers: Baku|Tbilisi(o)|Manila|Beirut
            
        Question: When was Avatar released?
        Answers: 2007|2001|2009(o)|1998
            
        Question: Who was Julius Caesar?
        Answers: A Roman Emperor(o)|Painter|Actor|Model
        
        
        Example Output:
        
        ```json
        {{ "questions": [
                {{
                    "question": "What is the color of the ocean?",
                    "answers": [
                            {{
                                "answer": "Red",
                                "correct": false
                            }},
                            {{
                                "answer": "Yellow",
                                "correct": false
                            }},
                            {{
                                "answer": "Green",
                                "correct": false
                            }},
                            {{
                                "answer": "Blue",
                                "correct": true
                            }},
                    ]
                }},
                            {{
                    "question": "What is the capital or Georgia?",
                    "answers": [
                            {{
                                "answer": "Baku",
                                "correct": false
                            }},
                            {{
                                "answer": "Tbilisi",
                                "correct": true
                            }},
                            {{
                                "answer": "Manila",
                                "correct": false
                            }},
                            {{
                                "answer": "Beirut",
                                "correct": false
                            }},
                    ]
                }},
                            {{
                    "question": "When was Avatar released?",
                    "answers": [
                            {{
                                "answer": "2007",
                                "correct": false
                            }},
                            {{
                                "answer": "2001",
                                "correct": false
                            }},
                            {{
                                "answer": "2009",
                                "correct": true
                            }},
                            {{
                                "answer": "1998",
                                "correct": false
                            }},
                    ]
                }},
                {{
                    "question": "Who was Julius Caesar?",
                    "answers": [
                            {{
                                "answer": "A Roman Emperor",
                                "correct": true
                            }},
                            {{
                                "answer": "Painter",
                                "correct": false
                            }},
                            {{
                                "answer": "Actor",
                                "correct": false
                            }},
                            {{
                                "answer": "Model",
                                "correct": false
                            }},
                    ]
                }}
            ]
        }}
        ```
        Your turn!

        Questions: {context}

    """,
            )
        ]
    )

    formatting_chain = formatting_prompt | llm


    @st.cache_data(show_spinner="Loading file...")
    def split_file(file):
        file_content = file.read()
        os.makedirs("./.cache/quiz_files/", exist_ok=True)
        file_path = f"./.cache/quiz_files/{file.name}"
        with open(file_path, "wb") as f:
            f.write(file_content)
        splitter = CharacterTextSplitter.from_tiktoken_encoder(
            separator="\n",
            chunk_size=600,
            chunk_overlap=100,
        )
        loader = UnstructuredFileLoader(file_path)
        docs = loader.load_and_split(text_splitter=splitter)
        return docs


    @st.cache_data(show_spinner="Making quiz...")
    def run_quiz_chain(_docs, level, topic):
        chain = {"context": questions_chain} | formatting_chain | output_parser
        docs = format_docs(_docs)
        return chain.invoke({"context":docs, "level":level})


    @st.cache_data(show_spinner="Searching Wikipedia...")
    def wiki_search(term):
        retriever = WikipediaRetriever(top_k_results=1)
        docs = retriever.get_relevant_documents(term)
        return docs


    with st.sidebar:
        docs = None
        topic = None
        level = "easy"
        level = st.selectbox(
            "Choose level",
            (
                "easy",
                "hard",
            ),
        )
        choice = st.selectbox(
            "Choose what you want to use.",
            (
                "File",
                "Wikipedia Article",
            ),
        )
        if choice == "File":
            file = st.file_uploader(
                "Upload a .docx , .txt or .pdf file",
                type=["pdf", "txt", "docx"],
            )
            if file:
                docs = split_file(file)
        else:
            topic = st.text_input("Search Wikipedia...")
            if topic:
                docs = wiki_search(topic)


    if not docs :
        st.markdown(
            """
        Welcome to QuizGPT.
                    
        I will make a quiz from Wikipedia articles or files you upload to test your knowledge and help you study.
                    
        Get started by uploading a file or searching on Wikipedia in the sidebar.
        """
        )
    else:
        response = run_quiz_chain(docs, level, topic if topic else file.name)
        num_correct = 0
        with st.form("questions_form"):
            for idx, question in enumerate(response["questions"]):
                st.write(f"{idx+1}. " + question["question"])
                value = st.radio("Select an answer",
                [answer["answer"] for answer in question["answers"]],
                index=None, key=f"{idx}_radio")
                if ({"answer": value, "correct":True} in question["answers"]):
                    st.success("Correct ! 🙆‍♀️")
                    num_correct += 1
                elif value is not None:
                    st.error("Wrong... 😭")

            if num_correct == idx+1 :
                st.balloons()
            button = st.form_submit_button()
else:
    st.markdown(
        """
        Welcome!
                    
        Please Input your API KEY on the sidebar.
     """
    )


