from google import genai
from django.conf import settings
from google.genai import types
from .tools import get_order_details, get_refund_history, check_delivery_status, get_customer_risk_profile
from .models import Conversation, Message, AgentLog

client = genai.Client(api_key=settings.GEMINI_API_KEY)
gemini_model = settings.GEMINI_MODEL

# 1. Support System Prompt (Maya's Job Description)
SUPPORT_SYSTEM_PROMPT = """
You are Maya, a customer support agent at Cool Breeze AC.
You help customers with issues related to their AC orders.

Your Responsibilities:
- Always use your tools to gather facts before responding.
- Check order details when a customer mentions their order.
- Check delivery status if an order is delayed or tracking info is requested.
- Check refund history before making any refund-related evaluations.

Your Personality:
- Be empathetic, friendly, and professional.
- Remain patient even when the customer is angry or frustrated.
- Keep your replies clear, concise, and confident.

Important Rules:
1. Always check order details first using your tools before responding with assumptions.
2. NEVER approve or deny a refund yourself. You do not have the authority to process refunds.
3. If a refund decision is requested, tell the customer you are checking with your team/manager while you evaluate the request.
4. Don't respond in markdown format.

ESCALATION PROTOCOL:
If a customer explicitly requests a refund or compensation, you MUST immediately execute the escalate_to_manager tool. Do not ask the customer for permission. Do not tell the customer you are preparing a summary. Gather the facts using your database tools, and then immediately call the escalate_to_manager tool in the exact same thought process.
"""
MANAGER_SYSTEM_PROMPT = """
You are a senior support manager at CoolBreeze AC.
A support agent has escalated a customer case to you for a refund decision.

Your responsibilities:
- Review the case summary carefully
- Consider the customer's refund history
- Make a fair and final refund decision
- Give a clear reason for your decision

Your decision options:
- Approve refund — if the case is genuine and within policy
- Deny refund — if the case is suspicious or outside policy
- Escalate to risk team — if you suspect fraud

Important rules:
- Be fair but firm
- Base decision on facts — not emotions
- Always give a specific reason for your decision
- Keep your response concise and professional
"""

RISK_SYSTEM_PROMPT = """
You are a Fraud Risk Analyst at Cool Breeze AC.
A support manager has sent you a customer profile for risk assessment.

Your Job:
1. Analyze the customer's order and refund patterns.
2. Identify suspicious behavior.
3. Return a clear risk verdict.

Risk Levels:
- LOW: Genuine customer, normal behavior.
- MEDIUM: Some suspicious signals, proceed with caution.
- HIGH: Clear fraud pattern, refund denial recommended.

Response Format:
- Risk Level: [Low/Medium/High]
- Key Signals: [What you found suspicious or genuine]
- Recommendation: [What the manager should do]

Important Rules:
- Be objective. Base your verdict on data only.
- One bad refund does not make someone fraudulent. Customers face genuine issues.
- Look for holistic patterns across their history, not just isolated incidents.

"""

# 2. Tool Schemas
SUPPORT_TOOLS = [
    types.Tool(
        function_declarations=[
            # Tool 1: Order Details
            types.FunctionDeclaration(
                name="get_order_details",
                description="Fetch complete order details including status, carrier, tracking number, and days since order was placed. Use this when customer mentions their order or complains about delivery.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "order_id":types.Schema(
                            type=types.Type.INTEGER,
                            description="The order ID to look up."
                        )
                    },
                    required=["order_id"]
                )  
            ),
            # Tool 2: Refund History
            types.FunctionDeclaration(
                name="get_refund_history",
                description="Get complete refund history for a user. Use this before making any refund related decisions.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "user_id":types.Schema(
                            type=types.Type.INTEGER,
                            description="The user ID to check refund history for."
                        )
                    },
                    required = ["user_id"]
                )
            ),
            # Tool 3: Delivery Status
            types.FunctionDeclaration(
                name="check_delivery_status",
                description="Check current delivery status using tracking number and carrier. Use this when customer complains about delayed or missing delivery.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "tracking_number":types.Schema(
                            type=types.Type.STRING,
                            description="Get shipment tracking number"
                        ),
                        "carrier":types.Schema(
                            type=types.Type.STRING,
                            description="The carrier name, for example BlueDart or E-kart."
                        )
                    },
                    required = ["tracking_number", "carrier"]
                )
            ),
            types.FunctionDeclaration(
                name="escalate_to_manager",
                description="Escalate the case to the Manager Agent for a strict refund decision. Use this ONLY when a customer explicitly requests a refund or compensation. You MUST prepare a detailed case summary including order details, refund history, and customer complaint before escalating.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "case_summary":types.Schema(
                            type=types.Type.STRING,
                            description="The complete case summary to pass to the manager."
                        )
                    },
                    required = ["case_summary"]
                )
            )
        ]
    )
]

MANAGER_TOOLS = [
     types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="assess_fraud_risk",
                description="Consults the Risk Agent to assess fraud risk for a customer. Use this when a refund request looks suspicious or the customer has multiple refund requests. Pass the user ID to get a risk verdict.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "user_id":types.Schema(
                           type=types.Type.INTEGER,
                           description="The user ID to assess fraud risk for." 
                        )
                    },
                    required = ["user_id"]
                )
            )
        ]
     )
]

RISK_TOOLS = [
    types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="get_customer_risk_profile",
                description="Get complete risk profile for a customer including order history, refund patterns, and ratio. Use this to assess the fraud risk.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "user_id":types.Schema(
                           type=types.Type.INTEGER,
                           description="The user ID to assess the risk for." 
                        )
                    },
                    required = ["user_id"]
                )
            )
        ]
    )
]

# 3. Execute Tool Function
def execute_tool(tool_name, tool_input):
    if tool_name == 'get_order_details':
        return get_order_details(order_id=tool_input['order_id'])

    elif tool_name == 'get_refund_history':
        return get_refund_history(user_id=tool_input['user_id'])

    elif tool_name == 'check_delivery_status':
        return check_delivery_status(
            tracking_number=tool_input['tracking_number'],
            carrier=tool_input['carrier']
            )
    
    elif tool_name == 'escalate_to_manager':
        case_summary = tool_input.get("case_summary")
        print("case_summary===>", case_summary)
        decision = run_manager_agent(case_summary)
        print("Decision====>", decision)
        return decision

    elif tool_name == 'assess_fraud_risk':
        user_id = tool_input['user_id']
        print(f"-> Manager consulting Risk Agent for User ID: {user_id}")
        verdict = run_risk_agent(user_id)
        print(f"-> Risk Verdict Received: {verdict}")
        return verdict

    elif tool_name == 'get_customer_risk_profile':
        user_id = tool_input['user_id']
        return get_customer_risk_profile(user_id)

    else:
        return f"Error: Tool '{tool_name}' is not recognized."

# 4. The Agent Loop
def run_support_agent(conversation_id, order_id, user_id):
    conv = Conversation.objects.get(id=conversation_id)

    dynamic_system_prompt = f"""
    {SUPPORT_SYSTEM_PROMPT}
    
    CURRENT STATE CONTEXT:
    This conversation is about order number {order_id}.
    The current logged-in user ID is {user_id}.
    """


    conversation_messages=[]
    messages = conv.messages.order_by('created_at')
    for msg in messages:
        gemini_role = 'model' if msg.role == 'assistant' else 'user'
        conversation_messages.append({
            'role':gemini_role,
            'parts':[{'text': msg.content}]
        })

    # The Agent while loop
    # MAX_LOOPS = 5  # Safety mechanism to prevent infinite loops
    loop_count = 0

    # while loop_count < MAX_LOOPS:
    while True:
        loop_count += 1
        
        # Trigger the API Call
        response = client.models.generate_content(
            model=gemini_model,
            contents=conversation_messages,
            config=types.GenerateContentConfig(
                system_instruction=dynamic_system_prompt,
                max_output_tokens=1024,
                tools=SUPPORT_TOOLS
            )
        )

        # Check if the AI wants to use a tool
        if response.function_calls:
            print(f"Loop {loop_count}: AI is calling tools...")
            conversation_messages.append(response.candidates[0].content)

            # Execute all requested tools
            tool_responses = [] 
            for call in response.function_calls:
                print(f"-> Executing: {call.name} with {call.args}")
                raw_result = execute_tool(call.name, call.args)

                # Format the result specifically for Gemini
                tool_responses.append(
                    types.Part.from_function_response(
                        name=call.name,
                        response={"result": raw_result}
                    )
                )
            
            # Append the database facts back to the history and loop again
            conversation_messages.append(
                types.Content(role="user", parts=tool_responses)
            )
            
        else:
            # E. The AI generated standard text. Break the loop and return it.
            return response.text
            
    # return "Error: I required too many steps to process this request."

def run_manager_agent(case_summary):
    manager_messages = [{'role': 'user', 'parts': [{'text': case_summary}]}]

    while True:
        response = client.models.generate_content(
            model=gemini_model,
            contents=manager_messages,
            config=types.GenerateContentConfig(
                system_instruction=MANAGER_SYSTEM_PROMPT,
                max_output_tokens=1024,
                tools=MANAGER_TOOLS
            )
        )

        if response.function_calls:
            manager_messages.append(response.candidates[0].content)

            tool_responses = []
            for call in response.function_calls:
                raw_result = execute_tool(call.name, call.args)
                tool_responses.append(
                    types.Part.from_function_response(
                        name=call.name,
                        response={"result": raw_result}
                    )
                )
            manager_messages.append(
                types.Content(role="user", parts=tool_responses)
            )
        else:
            return response.text

def run_risk_agent(user_id):
    initial_command = f"Please assess the fraud risk for user ID {user_id}. Use your tool to get their profile and return a verdict."

    risk_messages = [
        {
            'role': 'user',
            'parts':[{'text': initial_command}]
        }
    ]

    while True:
        response = client.models.generate_content(
            model=gemini_model,
            contents=risk_messages,
            config=types.GenerateContentConfig(
                system_instruction=RISK_SYSTEM_PROMPT,
                max_output_tokens=1024,
                tools=RISK_TOOLS
            )
        )

        if response.function_calls:
            risk_messages.append(response.candidates[0].content)

            tool_responses=[]
            for call in response.function_calls:
                print(f"Call===> {call.name} {call.args}" )
                raw_result = execute_tool(call.name, call.args)
                tool_responses.append(
                    types.Part.from_function_response(
                        name=call.name,
                        response={'result': raw_result}
                    )
                )
            
            risk_messages.append(
                types.Content(role="user", parts=tool_responses)
            )
        else:
            return response.text