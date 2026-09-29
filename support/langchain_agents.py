from django.conf import settings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent
from .agents import SUPPORT_SYSTEM_PROMPT, MANAGER_SYSTEM_PROMPT, RISK_SYSTEM_PROMPT
from .langchain_tools import get_order_details, get_refund_history, check_delivery_status, search_knowledge_base, get_customer_risk_profile
from langgraph.checkpoint.memory import InMemorySaver
from .models import Conversation, AgentLog
from langchain.agents.middleware import wrap_tool_call
from .event_queue import publish, SENTINEL
from langchain.tools import tool

llm = ChatGoogleGenerativeAI(model=settings.GEMINI_MODEL, api_key=settings.GEMINI_API_KEY)

support_tools = [get_order_details, get_refund_history, check_delivery_status, search_knowledge_base]

checkpointer = InMemorySaver()


def run_support_agent_langchain(user_message, conversation_id, order_id, user_id):
    conv = Conversation.objects.get(id=conversation_id)

    config = {"configurable": {"thread_id": str(conversation_id)}}

    contextual_message = f"[CURRENT STATE CONTEXT: This conversation is about order number #{order_id}.The current logged-in user ID is {user_id}.] {user_message}"

    @tool
    def escalate_to_manager(case_summary: str) -> dict:
        """
        Escalate the case to the Manager Agent for a strict refund decision. 
        Use this ONLY when a customer explicitly requests a refund or compensation. 
        You MUST prepare a detailed case summary including order details, 
        refund history, and customer complaint before escalating.
        """
        decision = run_manager_agent_langchain(case_summary, conversation_id)
        return {"decision": decision}

    @wrap_tool_call
    def log_tool_calls_middleware(request, handler):
        # Extract the tool name and arguments from the LangChain request object
        tool_name = request.tool_call['name']
        tool_input = request.tool_call['args']

        event = {"type":"tool_call", "message": f"Calling tool {tool_name} with {tool_input}"}
        publish(conversation_id, event)

        # --- BEFORE EXECUTION ---
        # Save a log to the database showing the AI is about to call a tool
        AgentLog.objects.create(
            conversation = conv,
            event_type='tool_call', 
            message=f"Calling tool {tool_name} with {tool_input}"
        )
        
        # Execute the tool
        tool_result = handler(request)

        event = {"type":"tool_result", "message": f"{tool_name} returned {str(tool_result.content)[:200]}"}
        publish(conversation_id, event)

        # --- AFTER EXECUTION ---
        # Save a log to the database showing the raw data the tool returned
        AgentLog.objects.create(
            conversation=conv, 
            event_type="tool_result", 
            message=f"{tool_name} returned {str(tool_result.content)[:200]}"
        )
    
        return tool_result

    support_agent = create_agent(
        model=llm,
        tools = support_tools + [escalate_to_manager],
        system_prompt = SUPPORT_SYSTEM_PROMPT,
        checkpointer = checkpointer,
        middleware = [log_tool_calls_middleware]
        )

    result = support_agent.invoke(
            {"messages": [{"role": "user", "content": contextual_message}]},
            config=config,
            )

    raw_content = result["messages"][-1].content

    if isinstance(raw_content, list):
        final_reply = raw_content[0].get('text', '')
    else:
        final_reply = raw_content
    
    event = {"type": "final","message":final_reply}
    publish(conversation_id, event)
    
    AgentLog.objects.create(conversation=conv, event_type="final_reply", message=final_reply)

    publish(conversation_id, SENTINEL)
    
    return final_reply

def run_manager_agent_langchain(case_summary, conversation_id):
    conv = Conversation.objects.get(id=conversation_id)
    
    @tool
    def assess_fraud_risk(user_id: int) -> dict:
        """
        Consults the Risk Agent to assess fraud risk for a customer.
        Use this when a refund request looks suspicious or the customer has multiple refund requests.
        Pass the user ID to get a risk verdict.
        """
        verdict = run_risk_agent_langchain(user_id, conversation_id)
        return {"result": verdict}

    event = {"type": "manager", "message": f"Case received for review: {case_summary[:200]}..."}
    publish(conversation_id, event)

    AgentLog.objects.create(
        conversation=conv,
        event_type="manager", 
        message=f"Case received for review: {case_summary[:200]}..."
    )

    # Middleware
    @wrap_tool_call
    def log_manager_tool_calls_middleware(request, handler):
        tool_name = request.tool_call['name']
        # Before executing the tool
        event = {"type": "manager", "message": f"Consulting Risk Agent for fraud assessment (Tool: {tool_name})."}
        publish(conversation_id, event)
        AgentLog.objects.create(
            conversation=conv,
            event_type="manager",
            message=f"Consulting Risk Agent for fraud assessment (Tool: {tool_name})."
        )
        tool_result = handler(request)

        # After executing the tool
        return tool_result
    
    manager_agent = create_agent(
        model=llm,
        system_prompt=MANAGER_SYSTEM_PROMPT,
        tools=[assess_fraud_risk],
        middleware=[log_manager_tool_calls_middleware]
    )

    result = manager_agent.invoke(
        {"messages": [{"role": "user", "content": case_summary}]}   
    )

    raw_decision = result["messages"][-1].content

    if isinstance(raw_decision, list):
        decision = raw_decision[0].get("text", "")
    else:
        decision = raw_decision
    
    event = {"type":"manager", "message":f"Decision: {decision[:200]}..."}
    publish(conversation_id, event)
    
    AgentLog.objects.create(
        conversation=conv,
        event_type="manager",
        message=f"Decision: {decision[:200]}..."
    )
    return decision

def run_risk_agent_langchain(user_id, conversation_id):
    conv = Conversation.objects.get(id=conversation_id)
    
    event = {"type":"risk", "message":f"Starting fraud assessment for user ID {user_id}"}
    publish(conversation_id, event)
    
    AgentLog.objects.create(
        conversation=conv,
        event_type="risk",
        message=f"Starting fraud assessment for user ID {user_id}"
    )
    
    @wrap_tool_call
    def log_risk_tool_calls_middleware(request, handler):
        tool_name = request.tool_call['name']
        
        event = {"type":"risk", "message":f"Calling {tool_name} to get customer risk profile."}
        publish(conversation_id, event)
        
        AgentLog.objects.create(
            conversation=conv,
            event_type="risk",
            message=f"Calling {tool_name} to get customer risk profile."
        )

        tool_result = handler(request)
        return tool_result

    risk_agent = create_agent(
        model=llm,
        system_prompt=RISK_SYSTEM_PROMPT,
        tools=[get_customer_risk_profile],
        middleware=[log_risk_tool_calls_middleware]
    )
    
    initial_command = f"Please assess the fraud risk for user ID {user_id}. Use your tool to get their profile and return a verdict."
    
    result = risk_agent.invoke(
        {"messages": [{"role": "user", "content": initial_command}]}
    )

    raw_verdict = result['messages'][-1].content

    if isinstance(raw_verdict, list):
        verdict = raw_verdict[0].get("text", "")
    else:
        verdict = raw_verdict

    event = {"type":"risk", "message": verdict}
    publish(conversation_id, event)
    AgentLog.objects.create(
        conversation=conv,
        event_type="risk",
        message=f"Verdict: {verdict[:200]}"
        )
    return verdict
    