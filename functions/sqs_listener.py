def main(event, cotext):
    try:
        for record in event["Records"]:
            print(record["body"])
        return
    except Exception as e:
        print(e)
        raise e
