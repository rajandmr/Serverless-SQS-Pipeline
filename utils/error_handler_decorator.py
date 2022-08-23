# Custom decorator for handling different type of exceptions occurred
import json

from botocore.exceptions import ClientError
from pydantic import ValidationError

from utils.custom_response import custom_response
from utils.generic_error import GenericError


def error_handler(func):
    """Decorator used to catch certain types of Exceptions"""

    def validate(*args, **kwargs):
        try:
            to_return = func(*args, **kwargs)
        except ValidationError as e:
            errors = []
            errors_list = json.loads(e.json())
            for error in errors_list:
                errors.append({"attribute": error["loc"][0], "msg": error["msg"]})
            return custom_response(400, errors)
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                print("NOT_FOUND", e)
                return custom_response(403, {"message": f"CLIENT ERROR: {e}"})
            else:
                print("BAD REQUEST", e)
                return custom_response(400, {"message": f"BAD REQUEST {e}"})
        except GenericError as e:
            print(e)
            return e.serialize_response()
        except Exception as e:
            print(e)
            raise e
        return to_return

    return validate
