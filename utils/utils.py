import os
from langchain_openai import OpenAIEmbeddings
from openai import OpenAI
from langchain_community.chat_models import ChatOpenAI
from langchain_core.runnables import Runnable, RunnableMap, RunnableLambda, RunnablePassthrough
from langchain.memory import ConversationBufferMemory
from operator import itemgetter
from dotenv import load_dotenv
from pandas import DataFrame
load_dotenv()

def generate_chatbot_tempalte(query, records, general_question:bool = False):
    record = ""
    for index,r in enumerate(records):
        record += f"""
                    - **Record : {index + 1}**
                    - **Company:** {r['CompanyName']}
                    - **Auditor Company:** {r['AuditorName']}
                    - **Report Name:** {r['ReportName']}
                    - **Report Text:** {r['ReportText']}
                """
    prompt_template_related_to_company = f"""
    # NumInformatics 10-K Analyzer Chatbot

    ## Motive
    The motive of the NumInformatics 10-K Analyzer Chatbot is to assist users in generating accurate and relevant answers based on the audit reports of companies. By leveraging similarity search through documents, the chatbot aims to provide reliable information and insights, ensuring users have access to the data they need.

    ## Chatbot Name
    AuditInsight Bot

    ## Version
    1.2.0

    ## Instructions
    You are the NumInformatics 10-K Analyzer Chatbot, an assistant designed to generate answers based on the top two similarity searches through the documents provided. Your task is to carefully and accurately analyze the given information and respond to the user's query.

    ### Steps to Follow:
    1. **Understand the Context:**
    - **Chat History:** You will be given a history of the conversation which consists of queries from the `user` and responses generated by `ai` (you). If history consist of response like "I cannot answer due to lack of evidence.", analyse the current query and records thoroughly. 

    - **Current Query:** Here is the current query from the `user`: {query}.

    2. **Analyze the Records:**
    - You will be provided with two similar records that match the query. Each record consists of:
        - **Company:** The company being audited.
        - **Auditor Company:** The company conducting the audit.
        - **Report Name:** The name of the audit report.
        - **Report Text:** The audit report generated by the `Auditor` on the `Company`.

    3. **Generate an Answer:**
    - Use the information in the records to generate an answer to the user's query.
    - Go through records thoughly and query. Try to understand the query using the company name/auditor name/report name. 
    - If the records are not provided or do not contain the relevant information ot remotely related to the query, respond with: "I cannot answer due to lack of evidence." Do not hallucinate or provide irrelevant information.

    ### Records:
    {record}

    Follow these instructions carefully to provide the most accurate and relevant response to the user's query. Please do not generate/hallucinate any records.

    """

    prompt_template_related_to_general_question = f"""
        # NumInformatics General Inquiry Chatbot

        ## Motive
        The motive of the NumInformatics General Inquiry Chatbot is to provide users with accurate and concise responses to general questions about the chatbot, including its identity, version, and operational status.

        ## Chatbot Name
        AuditInsight Bot

        ## Version
        1.2.0

        ## Instructions
        You are the NumInformatics General Inquiry Chatbot, an assistant designed to respond to user queries that are general in nature, such as inquiries about your identity, version, and status. Your task is to provide polite, accurate, and straightforward answers to these questions.

        ### Steps to Follow:
        1. **Understand the Context:**
        - **Chat History:** You will be given a history of the conversation which consists of queries from the `user` and responses generated by `ai` (you).
        - **Current Query:** Here is the current query from the `user`: {query}.

        2. **Generate an Answer:**
        - Based on the nature of the query, provide an appropriate response from the following possibilities:
            - **Identity Questions:** If the user asks who you are, respond with: "I am the AuditInsight Bot, designed to assist with analyzing 10-K audit reports."
            - **Version Questions:** If the user asks about your version, respond with: "I am currently running version 1.2.0."
            - **Status Questions:** If the user asks how you are or similar, respond with a polite and neutral statement like: "I am functioning as expected, ready to assist you."
            - **Other General Inquiries:** For other general questions, respond with a short and relevant answer based on the query.

        3. **Maintain Professionalism:**
        - Ensure your responses are polite, concise, and relevant to the user's inquiry.
        - Avoid providing any information that is not directly related to the question asked.

        Follow these instructions carefully to provide clear and helpful responses to the user's general inquiries.
    """

    return prompt_template_related_to_general_question if general_question else prompt_template_related_to_company

class OpenAIChatResponse:
    def __init__(self, **kwargs):
        self.openai_api_key = os.environ.get("OPENAI_API_KEY")
        self.client = OpenAI()
    
    def generate_response(self, history, query:str, records:DataFrame, general_question:bool = False, model:str = "gpt-3.5-turbo", max_token:int = 4000):
        
        memory = self.make_memory_from_testing_chat_history(history)

        loaded_memory = RunnablePassthrough.assign(
            chat_history=RunnableLambda(memory.load_memory_variables) | itemgetter("history"),
        )

        model = ChatOpenAI(temperature=0.3, model=model, max_tokens=max_token)

        # Handle the prompt
        handle_prompt = RunnableLambda(
            lambda inputs: inputs["prompt"]
        )

        intent_clf_chain = loaded_memory | handle_prompt| model

        prompt = generate_chatbot_tempalte(query, records, general_question)

        try: 
            result = intent_clf_chain.invoke({"prompt" : prompt})
            return result.content
        except:
            return "No Response"

    
    def make_memory_from_testing_chat_history(self,chat_history):
        """
        This function is used to convert the chatHistory generated by testing UI (tabot_chatbot_UI) 
        Generates a ConversationBufferMemory object from a chat history for chatbot_test_UI.
        
        Args:
        - chat_history (list): A list of dictionaries, each containing a message from 'user' and a response from 'ai'.
        Example: [{'user': 'Hello, how are you?', 'ai': 'I am fine, thank you.'}, ...]
        
        Returns:
        - ConversationBufferMemory: The memory object containing the conversation history.
        """
        memory = ConversationBufferMemory(
            return_messages=True,
            output_key="answer", 
            input_key="question"
        )
        
        if len(chat_history) == 0:
            return memory

        for i in range(len(chat_history)):
            user_message = chat_history[i]['user']
            ai_response = chat_history[i]['ai']

            if user_message is not None:
                memory.chat_memory.add_user_message(user_message)
            if ai_response is not None:
                memory.chat_memory.add_ai_message(ai_response)

        return memory

    def generate_summary(self, text:str, model:str = "gpt-3.5-turbo", max_token:int = 4000):
        query = f"""
                    Please generate a detailed summary of the following text: {text}
                """
        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": query,
                    }
                ],
                model=model,
                max_tokens=max_token,
            )
            return chat_completion.choices[0].message.content
        except:
            print('Error generating response')
            return None

class OpenAIEmbedder:
    def __init__(self, model:str='text-embedding-ada-002', **kwargs):
        self.model = model  # can also be text-embedding-3-large        
        self.openai_api_key = os.environ.get("OPENAI_API_KEY")

        self.embedder = OpenAIEmbeddings(
            model=self.model,  #'text-embedding-ada-002'
            openai_api_key=self.openai_api_key,
            **kwargs
        )
        
    def get_embedder(self):
        return self.embedder
    
    def embed_text(self, text:str):
        return self.embedder.embed_query(text)
    
    def embed_query(self, query_text:str):
        return self.embedder.embed_query(query_text)

    def embed_documents(self, docs:list[str]):
        return self.embedder.embed_documents(docs)
    


if __name__ == "__main__":
    # Step 1: Create the memory object
    history = [
        {'user': 'Hello, how are you?', 'ai': 'I am fine, thank you.'}
    ]

    ai = OpenAIChatResponse()
    ai.generate_response(history=history, query="Can you give me details about compay: Apple Inc.", record=[])