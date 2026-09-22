from django.shortcuts import get_object_or_404, render
import json
from django.http import JsonResponse
import time
from orders.models import Order
from .models import Conversation, Message
from .agents import run_support_agent
from django.contrib.admin.views.decorators import staff_member_required
from django.http import StreamingHttpResponse
from .event_queue import subscribe, unsubscribe, publish

# Create your views here.
def chat(request, order_id):
    if request.method == 'POST':
        data = json.loads(request.body)
        user_message = data.get('message')

        if not user_message:
            return JsonResponse({'error': 'Empty message'}, status=400)

        order = get_object_or_404(Order, id=order_id, user=request.user)

        conversation, created = Conversation.objects.get_or_create(
            order = order,
            user = request.user
        )
        
        Message.objects.create(
            conversation = conversation,
            role = 'user',
            content = user_message
        )

        event = {"type":"user_message", "message":user_message, "name": request.user.first_name};
        publish(conversation.id, event);

        reply = run_support_agent(conversation.id, order.id, request.user.id)

        
        Message.objects.create(
            conversation = conversation,
            role = 'assistant',
            content = reply
        )

        # time.sleep(5)
        return JsonResponse({'reply': reply})

    return JsonResponse({'error': 'Invalid request method'}, status=405)

@staff_member_required
def dashboard(request):
    conversations = Conversation.objects.all().order_by('-created_at')
    context = {
        'conversations':conversations
    }

    return render(request, 'support/dashboard.html', context)

@staff_member_required
def conversation_detail(request, conversation_id):
    conversation = get_object_or_404(Conversation, id=conversation_id)
    messages = conversation.messages.order_by('created_at')
    agentlogs = conversation.agentlogs.order_by('created_at')
    
    context = {
        'conversation':conversation,
        'messages': messages,
        'agentlogs':agentlogs
    }

    return render(request, 'support/conversation_detail.html', context)

@staff_member_required
def conversation_stream(request, conversation_id):
    # The Generator Function
    def event_stream(conversation_id):
        # Register this browser tab to the event queue
        q = subscribe(conversation_id)
        
        try:
            while True:
                # The Blocking Wait: Execution pauses here until an AI agent publishes an event.
                event = q.get()

                yield f"data: {json.dumps(event)}\n\n"
        finally:
            # The Cleanup: If the admin closes the tab, the connection drops, and this block executes.
            unsubscribe(conversation_id, q)

    response = StreamingHttpResponse(event_stream(conversation_id), content_type='text/event-stream')
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no" 
    return response