from decouple import config
from google import genai

client = genai.Client(api_key=config('GEMINI_API_KEY'))

# response = client.models.generate_content(
#     model=config('GEMINI_MODEL'),
#     contents="Five name of animals"
# )

response = client.interactions.create(
    model=config("GEMINI_MODEL"),
    system_instruction="""
    You are a primary school Mathematics teacher who teaches kids.
    Please teach student every concept in easy and fun way.
    Don't respond in markdown.
    """,
    input="What is BODMAS?"
)
print(response.output_text)
# print(response.text)


# Tools Schema practice...
# TOOLS = [
#     {
#         "name":"get_order_details",
#         "description": "Fetch all order details including status...Use when customer ask...",
#         "parameters":{
#             "type":"object",
#             "properties":{
#                 "order_id":{
#                     "type":"string",
#                     "description": "The order ID to look up.",
#                 }
#             },
#             "required" : ["order_id"]

#         }
#     }
# ]
