import boto3
import json
import urllib.request
import urllib.parse
import urllib.error
import os
import logging
from requests_aws4auth import AWS4Auth
from opensearchpy import OpenSearch, RequestsHttpConnection
from dateutil.tz import tzutc

# logger = logging.getLogger()
# logger.setLevel(logging.DEBUG)

# --------------- Helper Functions -----------------------------

def detect_labels(bucket, key):
    rekognition = boto3.client('rekognition')
    try:
        response = rekognition.detect_labels(Image={
            "S3Object": {
                "Bucket": bucket,
                "Name": key}})
    except Exception as e:
        print(e)
        print("Error processing object {} from bucket {}. ".format(key, bucket) +
              "Make sure your object and bucket exist and your bucket is in the same region as this function.")
        raise e
    labels = [label_prediction['Name'].lower() for label_prediction in response['Labels']]

    return labels



def is_valid_image_file(key):
    return key.lower().endswith(('.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.gif'))


def get_labels_and_created_time(bucket, key):
    s3 = boto3.client('s3', region_name='us-east-1',
                      aws_access_key_id=os.getenv('KEY_ID'),
                      aws_secret_access_key=os.getenv('SECRET_KEY'))
    detected_lables = detect_labels(bucket, key)
    image_metadata = s3.head_object(Bucket=bucket, Key=key)
    # logger.debug(image_metadata)
    print(image_metadata)
    if ('x-amz-meta-customlabels' in image_metadata['ResponseMetadata']['HTTPHeaders'] and
            image_metadata['ResponseMetadata']['HTTPHeaders']['x-amz-meta-customlabels']):
        custom_lables = image_metadata['ResponseMetadata']['HTTPHeaders']['x-amz-meta-customlabels'].split(',')
        custom_lables = [lable.strip() for lable in custom_lables]
    else:
        custom_lables = []
    created_time = image_metadata['LastModified']
    labels = list(set(detected_lables + custom_lables))
    print(labels)
    return labels, created_time


def build_a1(bucket, created_time, key, labels):
    a1 = {
        'objectKey': key,
        'bucket': bucket,
        'createdTimestamp': created_time.strftime("%Y-%m-%dT%H:%M:%S"),
        'labels': labels
    }
    a1 = json.dumps(a1)
    return a1

def open_search_create_index(a1):
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
    response = open_search.index(index='photos-cf', body=a1)
    return response

# --------------- Main handler ------------------


def lambda_handler(event, context):
    for record in event['Records']:
        bucket = record['s3']['bucket']['name']
        key = urllib.parse.unquote_plus(record['s3']['object']['key'])
        labels, created_time = get_labels_and_created_time(bucket, key)
        print(labels)
        a1 = build_a1(bucket, created_time, key, labels)
        response = open_search_create_index(a1)
        print(response)

