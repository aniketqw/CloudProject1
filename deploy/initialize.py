"""Ordered, additive schema initialization; never drops tables or existing fixtures."""
import importlib
import os
from common.deployment import require_profile
def main():
    require_profile()
    from customer_service.customer_service import create_app as customer_app
    from customer_service.models import db as customers
    app=customer_app({"AUTO_CREATE_SCHEMA":False})
    with app.app_context():customers.create_all()
    for name in ["order_service.schema","payment_service.schema","kitchen_workflow.schema","delivery_assignment_service.schema","notification_service.schema","task_scheduler.schema"]:
        importlib.import_module(name).main()
    print("Ordered additive schemas are ready.",flush=True)
if __name__=="__main__":main()
