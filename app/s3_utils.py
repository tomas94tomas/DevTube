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


def delete_object(key: str) -> bool:
    """
    Delete an object from S3. Returns True if we attempted the delete.
    Swallows 'NoSuchKey' so it’s safe to call even if the file is already gone.
    """
    if not key or not BUCKET:
        return False
    try:
        s3.delete_object(Bucket=BUCKET, Key=key)
        return True
    except ClientError as e:
        # Ignore missing objects; re-raise other errors
        err = getattr(e, "response", {}).get("Error", {}).get("Code", "")
        if err in ("NoSuchKey", "404"):
            return False
        raise
