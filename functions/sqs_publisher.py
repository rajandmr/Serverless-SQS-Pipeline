import json
import os
from uuid import uuid4

import boto3


def main(event, context):
    try:
        sqs = boto3.client("sqs")
        queue = os.environ["QUEUE_URL"]

        message_body = {"message": "Hello World!", "uuid": str(uuid4())}

        sqs.send_message(QueueUrl=queue, MessageBody=json.dumps(message_body))

        print("message sent")
        resp_body = {"message": "message published successfully", "success": True}
        return {"statusCode": 200, "body": json.dumps(resp_body)}

    except Exception as e:
        print(e)
        raise e
