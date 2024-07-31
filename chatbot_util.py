from utils.graph import Neo4jHandler
from utils.utils import OpenAIChatResponse

def get_response(query:str, history):
    db = Neo4jHandler()
    aiReponse = OpenAIChatResponse()

    records = db.handle_query(query, distance=0.5)

    if len(records) > 0:
        try:
            response = aiReponse.generate_response(query=query, history=history, record=records)
        except:
            response = "Error Occured while generating response."
    
    else:
        response = "Evidence not available."

    return response, records


if __name__ == "__main__":
    response, records = get_response(query="Can you get a report on Adam's company", history="")

    print("\n==============={response}==============\n")
    print(response)
    print("\n==============={record}==============\n")
    print(records)