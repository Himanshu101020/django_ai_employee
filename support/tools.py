from orders.models import Order, RefundRequest
from django.utils import timezone
from .tracking_data import DELIVERY_DATA

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
