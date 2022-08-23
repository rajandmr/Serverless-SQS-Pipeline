import simplejson as json


def custom_response(code: int, body):
    """Build a standard JSON response

    Args:
        code: int: HTTP status code
        body: AnyOf [JSON serializable string, dict]: Body to serialize
    """
    return {
        "statusCode": code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Credentials": True,
        },
        "body": json.dumps(body),
        "isBase64Encoded": False,
    }
