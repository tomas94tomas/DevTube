import os
import boto3
from botocore.exceptions import ClientError


BUCKET = os.getenv("AWS_S3_BUCKET", "")
REGION = os.getenv("AWS_REGION", "eu-central-1")


_session = boto3.session.Session(region_name=REGION)
s3 = _session.client("s3")


def upload_fileobj(fileobj, key, content_type):
extra = {"ContentType": content_type}
s3.upload_fileobj(fileobj, BUCKET, key, ExtraArgs=extra)
return key




def presigned_url(key, expires=3600):
try:
return s3.generate_presigned_url(
"get_object",
Params={"Bucket": BUCKET, "Key": key},
ExpiresIn=expires,
)
except ClientError:
return None
