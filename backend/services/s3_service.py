import boto3
from botocore.exceptions import ClientError
from config import AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION, S3_BUCKET_NAME


def get_s3_client():
    return boto3.client(
        "s3",
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION,
    )


def ensure_bucket_exists():
    s3 = get_s3_client()
    try:
        s3.head_bucket(Bucket=S3_BUCKET_NAME)
    except ClientError:
        create_kwargs = {"Bucket": S3_BUCKET_NAME}
        if AWS_REGION != "us-east-1":
            create_kwargs["CreateBucketConfiguration"] = {
                "LocationConstraint": AWS_REGION
            }
        s3.create_bucket(**create_kwargs)


def upload_file_to_s3(file_path: str, s3_key: str) -> str:
    s3 = get_s3_client()
    ensure_bucket_exists()
    s3.upload_file(file_path, S3_BUCKET_NAME, s3_key)
    return f"s3://{S3_BUCKET_NAME}/{s3_key}"


def download_file_from_s3(s3_key: str, local_path: str) -> str:
    s3 = get_s3_client()
    s3.download_file(S3_BUCKET_NAME, s3_key, local_path)
    return local_path


def list_documents() -> list[dict]:
    s3 = get_s3_client()
    try:
        ensure_bucket_exists()
        response = s3.list_objects_v2(Bucket=S3_BUCKET_NAME, Prefix="documents/")
        if "Contents" not in response:
            return []
        return [
            {
                "key": obj["Key"],
                "name": obj["Key"].split("/")[-1],
                "size": obj["Size"],
                "last_modified": obj["LastModified"].isoformat(),
            }
            for obj in response["Contents"]
            if not obj["Key"].endswith("/")
        ]
    except ClientError:
        return []


def delete_file_from_s3(s3_key: str):
    s3 = get_s3_client()
    try:
        s3.delete_object(Bucket=S3_BUCKET_NAME, Key=s3_key)
    except ClientError:
        pass
