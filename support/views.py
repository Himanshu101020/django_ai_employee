from django.shortcuts import get_object_or_404, render
import json
from django.http import JsonResponse
import time
from orders.models import Order
from .models import Conversation, Message
from .agents import run_support_agent

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

        reply = run_support_agent(conversation.id, order.id, request.user.id)

        Message.objects.create(
            conversation = conversation,
            role = 'assistant',
            content = reply
        )

        # time.sleep(5)
        return JsonResponse({'reply': reply})

    return JsonResponse({'error': 'Invalid request method'}, status=405)

