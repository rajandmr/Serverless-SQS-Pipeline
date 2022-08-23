import simplejson as json
import boto3
from loguru import logger
# import pyjq
from os import getenv
from sys import stdout
from marshmallow import Schema
import requests
from datetime import datetime, timedelta
import chargebee

if getenv('TEST_MODE') == "true":
    logger.add("app.log", serialize=True)
else:
    logger.add(stdout, serialize=True)
security_log = logger.level("SECURITY", no=38)
context = logger.bind()


# if logging.getLogger().hasHandlers():
#     logging.getLogger().setLevel(logging.INFO)
# else:
#     logging.basicConfig(level=logging.INFO)

# context = logging.getLogger()


db = boto3.resource("dynamodb")
table = db.Table("appsecengineer")

ssm = boto3.client("ssm")
cognito = boto3.client('cognito-idp')

ADMIN_POOL_ID = (
    ssm.get_parameter(Name="ADMIN_USER_POOL_ID", WithDecryption=True)
    .get("Parameter")
    .get("Value")
)

CHARGEBEE_API_KEY = (
    ssm.get_parameter(Name="CHARGEBEE_API_KEY", WithDecryption=True)
    .get("Parameter")
    .get("Value")
)

CHARGEBEE_URL = (
    ssm.get_parameter(Name="CHARGEBEE_URL")
    .get("Parameter")
    .get("Value")
)


def get_log():
    return logger


class MySchema(Schema):
    error_messages = {'unknown': "Invalid Atrribute"}


def make_response(status, message, log=True):
    if log:
        context.info(f"Response: status-{status}, body-{message}")
    return {
        "statusCode": status,
        "body": json.dumps(message),
        "headers": {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Credentials": True,
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Allow-Methods": "OPTIONS,GET,POST",
        },
    }


def check_role(email):
    try:
        user_info = cognito.admin_get_user(
            UserPoolId=ADMIN_POOL_ID,
            Username=email
        )
    except cognito.exceptions.UserNotFoundException:
        context.warning(f"User with email {email} not found")
        return {}
    user_attrs = {i['Name']: i['Value']
                  for i in user_info.get('UserAttributes', {})}
    return user_attrs.get('custom:role', 'Admin')


def build_update_expression(data):
    expr = []
    values = {}
    for k, v in data.items():
        expr.append(f"{k} = :{k}")
        values[f":{k}"] = v
    return "SET " + ", ".join(expr), values


def get_do_password():
    do_obj = ssm.get_parameter(Name="bti-do-password", WithDecryption=True)
    print("do obj", do_obj)
    # if pyjq.first(".Parameter.Value", do_obj) is not None:
    #     print("do obj", do_obj)
    #     return pyjq.first(".Parameter.Value", do_obj)

    # return None


def upload_file(data, name, obj_type, bucket, file_name):
    s3 = boto3.client('s3')
    response = s3.get_bucket_location(Bucket=bucket)
    prefix = f"https://{bucket}.s3.{response['LocationConstraint']}.amazonaws.com/"
    default_photo = f"{prefix}{obj_type}/default_icon.png"
    ext = file_name.rsplit(".", maxsplit=1)[1] if file_name else "png"
    key = f"{obj_type}/{name.strip().replace(' ', '_')}.{ext}"
    error = None
    try:
        resp = s3.put_object(
            Bucket=bucket,
            Key=key,
            Body=data
        )
        # if pyjq.first(".ResponseMetadata.HTTPStatusCode", resp) == 200:
        return prefix + key, error
    except s3.exceptions.ClientError as e:
        error = str(e)
    return default_photo, error


def cb_weekly_subscriber_customers():
    chargebee.configure(CHARGEBEE_API_KEY, CHARGEBEE_URL)
    today = datetime.now()
    next_week = today - timedelta(days=7)
    date_from = int(next_week.timestamp())

    data = {
        'created_at[after]': str(date_from)
    }
    cb_data = chargebee.Subscription.list(params=data)
    list_users = []
    for subs in cb_data:
        created_at = subs._response.get('subscription').get('created_at')
        created_at = datetime.fromtimestamp(created_at).strftime("%d-%b-%Y")

        data_dict = {
            'created': created_at,
            'email': subs._response.get('customer').get('email'),
            'first_name': subs._response.get('customer').get('first_name'),
            'last_name': subs._response.get('customer').get('last_name'),
            'plan': subs._response.get('subscription').get('subscription_items')[0].get('item_price_id'),
            'current_term_start': datetime.fromtimestamp(subs._response.get('subscription').get('current_term_start', 0)).strftime("%d-%b-%Y"),
            'current_term_end': datetime.fromtimestamp(subs._response.get('subscription').get('current_term_end', 0)).strftime("%d-%b-%Y")
        }
        list_users.append(data_dict)
    while cb_data.next_offset:
        data['offset'] = cb_data.next_offset
        cb_data = chargebee.Subscription.list(params=data)
        for subs in cb_data:
            created_at = subs._response.get('subscription').get('created_at')
            created_at = datetime.fromtimestamp(
                created_at).strftime("%d-%b-%Y")

            data_dict = {
                'created': created_at,
                'email': subs._response.get('customer').get('email'),
                'first_name': subs._response.get('customer').get('first_name'),
                'last_name': subs._response.get('customer').get('last_name'),
                'plan': subs._response.get('subscription').get('subscription_items')[0].get('item_price_id'),
                'current_term_start': datetime.fromtimestamp(subs._response.get('subscription').get('current_term_start', 0)).strftime("%d-%b-%Y"),
                'current_term_end': datetime.fromtimestamp(subs._response.get('subscription').get('current_term_end', 0)).strftime("%d-%b-%Y")
            }
            list_users.append(data_dict)
    list_users.sort(key=lambda item: item.get("created"), reverse=True)
    return list_users


def cb_subscriber_customers(subscription_type='None'):
    chargebee.configure(CHARGEBEE_API_KEY, CHARGEBEE_URL)
    list_users = []
    payload = {
        "limit": 50
    }
    if subscription_type != 'None':
        payload['item_price_id[is]'] = subscription_type

    cb_response = chargebee.Subscription.list(params=payload)

    for subs in cb_response:
        created_at = subs._response.get('subscription').get('created_at')
        created_at = datetime.fromtimestamp(created_at).strftime("%d-%b-%Y")
        data_dict = {
            'created': created_at,
            'email': subs._response.get('customer').get('email'),
            'first_name': subs._response.get('customer').get('first_name'),
            'last_name': subs._response.get('customer').get('last_name'),
            'plan': subs._response.get('subscription').get('subscription_items')[0].get('item_price_id'),
            'current_term_start': datetime.fromtimestamp(subs._response.get('subscription').get('current_term_start', 0)).strftime("%d-%b-%Y"),
            'current_term_end': datetime.fromtimestamp(subs._response.get('subscription').get('current_term_end', 0)).strftime("%d-%b-%Y")
        }
        list_users.append(data_dict)
    while cb_response.next_offset:
        payload["offset"] = cb_response.next_offset
        cb_response = chargebee.Subscription.list(params=payload)
        for subs in cb_response:
            created_at = subs._response.get('subscription').get('created_at')
            created_at = datetime.fromtimestamp(
                created_at).strftime("%d-%b-%Y")
            data_dict = {
                'created': created_at,
                'email': subs._response.get('customer').get('email'),
                'first_name': subs._response.get('customer').get('first_name'),
                'last_name': subs._response.get('customer').get('last_name'),
                'plan': subs._response.get('subscription').get('subscription_items')[0].get('item_price_id'),
                'current_term_start': datetime.fromtimestamp(subs._response.get('subscription').get('current_term_start', 0)).strftime("%d-%b-%Y"),
                'current_term_end': datetime.fromtimestamp(subs._response.get('subscription').get('current_term_end', 0)).strftime("%d-%b-%Y")
            }
            list_users.append(data_dict)
    return list_users


def covert_to_dollar(cents):
    centsStr = str(cents)
    d, c = centsStr[:-2], centsStr[-2:]
    if cents > 99:
        return f"{d}.{c}"
    else:
        return c + ' cents'


def cb_get_plan_info(plan_id):
    chargebee.configure(CHARGEBEE_API_KEY, CHARGEBEE_URL)
    plan_dict = {}
    plan_info = chargebee.ItemPrice.retrieve(plan_id)
    if plan_info.item_price.status == 'active':
        cent = int(plan_info.item_price.price)
        plan_dict['plan_name'] = plan_info.item_price.external_name
        plan_dict['price'] = covert_to_dollar(cent)
    return plan_dict
