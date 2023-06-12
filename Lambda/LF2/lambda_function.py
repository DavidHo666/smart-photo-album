import boto3
import json
from requests_aws4auth import AWS4Auth
from opensearchpy import OpenSearch, RequestsHttpConnection
import os



def lambda_handler(event, context):
    print(event)
    print(context)
    query = event["queryStringParameters"]["q"]
    # query = "show me trees"
    keywords = get_keywords_from_lex(query)
    results = []
    for keyword in keywords:
        query = build_query(keyword)
        os_response = open_search_search_keyword(query)
        for res in os_response['hits']['hits']:
            print(os_response['hits']['hits'])
            photo_url = "https://{}.s3.amazonaws.com/{}".format(res["_source"]["bucket"], res["_source"]["objectKey"])
            result = {
                'url': photo_url,
                'labels': res['_source']['labels']
            }
            results.append(result)
    output = {
        'results': results
    }
    print(output)
    return {
        "isBase64Encoded": False,
        "statusCode": 200,
        "body": json.dumps(output),
        "headers": {
            "content-type": "application/json",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "OPTIONS,POST,GET"
        }
    }

def build_query(keyword):
    query = {
        # "size": 1000,
        "query": {
            "query_string": {
                "default_field": "labels",
                "query": keyword
            }
        }
    }
    return query


def get_keywords_from_lex(query):
    lex = boto3.client('lexv2-runtime')
    lex_response = lex.recognize_text(
        botId='J3SHDSPF6A',  # MODIFY HERE
        botAliasId='RZW4CB7XO5',
        localeId='en_US',
        sessionId='test_session',
        text=query
    )
    keywords = []
    try:
        values = lex_response["interpretations"][0]["intent"]["slots"]["keywords"]["values"]
        for value in values:
            if value['value']["resolvedValues"]:
                keywords.append(value['value']["resolvedValues"][0].lower())
            else:
                keywords.append(value['value']["interpretedValue"].lower())
    except Exception as e:
        return {
            'statusCode': 500,
            'body': "Lex failed to parse keywords"
        }
    return keywords

def open_search_search_keyword(query):
    region = 'us-east-1'
    service = 'es'
    credentials = boto3.Session().get_credentials()
    awsauth = AWS4Auth(credentials.access_key, credentials.secret_key, region, service, session_token=credentials.token)
    open_search = OpenSearch(
        hosts=[{'host': os.getenv('OS_HOST'), 'port': 443}],
        http_auth=awsauth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection
    )
    response = open_search.search(index='photos-cf', body=query)
    return response
