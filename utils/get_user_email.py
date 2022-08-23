def get_email(event):
    email = event['requestContext']['authorizer']['claims']['email']
    return email
