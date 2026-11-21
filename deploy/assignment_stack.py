"""The second local Docker Compose stack (project "food-assignment").

Its port and image overrides used to live in a second env file. Compose cannot layer one file two ways,
so they are kept here and applied through the environment, which takes priority over the env file.
"""
import os

OVERRIDES = {
    "APP_IMAGE": "cloudproject1-app:handoff",
    "LOCAL_LOG_DIR": "/var/log/food",
    "LOCAL_WEB_PORT": "3010",
    "LOCAL_MYSQL_PORT": "13307",
    "LOCAL_FIRESTORE_PORT": "18080",
    "LOCAL_KAFKA_PORT": "39092",
    "LOCAL_ORDER_PORT": "18081",
    "LOCAL_DELIVERY_PORT": "18082",
    "LOCAL_CUSTOMER_PORT": "18083",
    "LOCAL_RESTAURANT_PORT": "15051",
    "LOCAL_RESTAURANT_HTTP_PORT": "18084",
    "LOCAL_TASK_PORT": "18085",
    "LOCAL_PAYMENT_PORT": "18086",
    "LOCAL_KITCHEN_PORT": "18087",
    "LOCAL_NOTIFICATION_PORT": "18088",
    "LOCAL_ZK_1_PORT": "12181",
    "LOCAL_ZK_2_PORT": "12182",
    "LOCAL_ZK_3_PORT": "12183",
}

COMPOSE = ["docker", "compose", "-p", "food-assignment", "--env-file", ".env.example",
           "-f", "compose.yaml", "-f", "compose.assignment.yaml"]


def environment():
    env = dict(os.environ)
    env.update(OVERRIDES)
    return env
