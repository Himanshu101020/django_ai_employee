from datetime import timedelta
from orders.models import Order, RefundRequest
from django.utils import timezone
from .tracking_data import DELIVERY_DATA
from .rag import search_knowledge_base as rag_search

def get_order_details(order_id):
    try:
        order = Order.objects.get(id=order_id)
        days_since = (timezone.now() - order.created_at).days 
        result = {
            "order_id": order.id,
            "product_name": order.product_name,
            "amount": str(order.amount),
            "delivery_address": order.delivery,
            "status": order.status,
            "carrier": order.carrier,
            "tracking_number": order.tracking_number,
            "orderd_on": order.created_at.strftime("%d %b %Y"),
            "days_since_order": days_since,
        }
        return result

    except Order.DoesNotExists():
        return f"Order #{order_id} not found."

def get_refund_history(user_id):
    refunds =  RefundRequest.objects.filter(user=user_id).order_by('-created_at')
    history = []
    for refund in refunds:
        history.append({
            "order_id": refund.order.id,
            "product_name": refund.order.product_name,
            "reason": refund.reason,
            "status": refund.status,
            "requested_on": refund.created_at.strftime("%d %b %Y")
        })
    return {
        "total_refund_requested": len(history),
        "history": history
    }

def check_delivery_status(tracking_number, carrier):
    result = DELIVERY_DATA.get(tracking_number)

    if not result:
        default_response = {
            'status': 'Unknown',
            'last_location': 'Tracking info unavailable',
            "last_update": 'N/A',
            "estimated_delivery": 'Contact carrier directly',
            "delay_reason": 'No updates from carrier',
        }
        result = default_response
    
    result['tracking_number'] = tracking_number
    result['carrier'] = carrier
    return result

def get_customer_risk_profile(user_id):
    refunds = RefundRequest.objects.filter(user_id=user_id)
    orders = Order.objects.filter(user_id=user_id)

    ninety_days_ago = timezone.now() - timedelta(days=90)
    print("Ninety Days ago===>", ninety_days_ago)
    recent_refunds = refunds.filter(created_at__gte=ninety_days_ago).count()
    
    denied = refunds.filter(status='denied').count()
    pending = refunds.filter(status='pending').count()
    approved = refunds.filter(status='approved').count()

    total_orders = orders.count()
    total_refunds = orders.count()

    if total_orders > 0:
        refund_to_order_ratio = round(total_refunds/total_orders, 2)
    else:
        refund_to_order_ratio = 0

    return {
        'user_id': user_id,
        'total_orders': total_orders,
        'total_refunds': total_refunds,
        "refunds_last_90_days": recent_refunds,
        "denied_refunds": denied,
        "approved_refunds": approved,
        "pending_refunds": pending,
        "refund_to_order_ratio": refund_to_order_ratio
    }

def search_knowledge_base(query):
    result = rag_search(query)
    return {"result": result}