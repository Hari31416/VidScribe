from app.utils import create_simple_logger

import os
import logging
from typing import Iterable, Optional, Dict, Any, List, Union, BinaryIO
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from boto3.s3.transfer import TransferConfig

logger = logging.getLogger(__name__)


logger = create_simple_logger(__name__)


class S3Storage:
    """
    Provider-agnostic S3 storage helper.
    Works with AWS S3 and any S3-compatible service (e.g., MinIO) by configuring endpoint_url.
    """

    def __init__(
        self,
        bucket: str,
        endpoint_url: Optional[str] = None,
        region_name: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        use_ssl: Optional[bool] = None,
        extra_config: Optional[Dict[str, Any]] = None,
        transfer_cfg: Optional[TransferConfig] = None,
    ):
        self.bucket = bucket
        self.endpoint_url = endpoint_url or os.getenv("S3_ENDPOINT_URL")
        self.region_name = (
            region_name or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
        )
        self.access_key = access_key or os.getenv("AWS_ACCESS_KEY_ID")
        self.secret_key = secret_key or os.getenv("AWS_SECRET_ACCESS_KEY")
        self.use_ssl = use_ssl  # if None, derived from endpoint_url (http->False, https->True) by botocore

        logger.debug(
            f"Initializing S3Storage for bucket '{bucket}' with endpoint '{self.endpoint_url}' "
            f"and region '{self.region_name}'"
        )

        # Signature v4 is broadly compatible and recommended
        cfg = Config(signature_version="s3v4", **(extra_config or {}))

        self.client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region_name,
            use_ssl=self.use_ssl,
            config=cfg,
        )

        # Automatically handles multipart uploads for large files
        self.transfer_cfg = transfer_cfg or TransferConfig()
        self.ensure_bucket()

    def ensure_bucket(self) -> None:
        """Create the bucket if it doesn't exist."""
        try:
            logger.debug(f"Checking if bucket '{self.bucket}' exists")
            self.client.head_bucket(Bucket=self.bucket)
            logger.debug(f"Bucket '{self.bucket}' already exists")
        except ClientError as e:
            code = int(e.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0))
            logger.warning(f"Bucket check failed with status code {code}: {e}")
            if code == 404:
                # Bucket doesn't exist, create it
                logger.info(f"Creating bucket '{self.bucket}'")
                try:
                    params = {"Bucket": self.bucket}
                    # For MinIO or non-AWS S3, skip region constraint
                    if (
                        self.region_name
                        and self.region_name != "us-east-1"
                        and not self.endpoint_url
                    ):
                        params["CreateBucketConfiguration"] = {
                            "LocationConstraint": self.region_name
                        }
                    self.client.create_bucket(**params)
                    logger.info(f"Successfully created bucket '{self.bucket}'")
                except ClientError as create_err:
                    # If bucket already exists (race condition), ignore
                    create_code = create_err.response.get("Error", {}).get("Code")
                    if create_code not in [
                        "BucketAlreadyExists",
                        "BucketAlreadyOwnedByYou",
                    ]:
                        logger.error(f"Failed to create bucket: {create_err}")
                        raise
                    logger.info(
                        f"Bucket '{self.bucket}' already exists (race condition)"
                    )
            elif code == 400:
                # Bad Request - try to create bucket anyway (might be MinIO quirk)
                logger.info(
                    f"Got 400 error, attempting to create bucket '{self.bucket}' anyway"
                )
                try:
                    self.client.create_bucket(Bucket=self.bucket)
                    logger.info(f"Successfully created bucket '{self.bucket}'")
                except ClientError as create_err:
                    create_code = create_err.response.get("Error", {}).get("Code")
                    if create_code not in [
                        "BucketAlreadyExists",
                        "BucketAlreadyOwnedByYou",
                    ]:
                        logger.error(
                            f"Failed to create bucket after 400 error: {create_err}"
                        )
                        raise
                    logger.info(f"Bucket '{self.bucket}' already exists")
            elif code == 301:
                # Wrong region; caller should pass correct region_name
                logger.error(f"Bucket '{self.bucket}' is in a different region")
                raise
            else:
                logger.error(f"Unexpected error checking bucket: {e}")
                raise

    def write_file(
        self, key: str, local_path: str, extra_args: Optional[Dict[str, Any]] = None
    ) -> None:
        """Upload a local file to the given key."""
        logger.info(f"Uploading file from '{local_path}' to '{self.bucket}/{key}'")
        self.client.upload_file(
            Filename=local_path,
            Bucket=self.bucket,
            Key=key,
            ExtraArgs=extra_args or {},
            Config=self.transfer_cfg,
        )
        logger.info(f"Successfully uploaded '{key}'")

    def write_bytes(
        self,
        key: str,
        data: Union[bytes, BinaryIO],
        content_type: Optional[str] = None,
        extra_args: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Upload in-memory bytes or a file-like stream."""
        logger.debug(f"Uploading bytes to '{self.bucket}/{key}'")
        args = dict(extra_args or {})
        if content_type:
            args["ContentType"] = content_type
        body = data  # bytes or file-like object
        self.client.put_object(Bucket=self.bucket, Key=key, Body=body, **args)
        logger.debug(f"Successfully uploaded bytes to '{key}'")

    def copy(
        self, src_key: str, dst_key: str, extra_args: Optional[Dict[str, Any]] = None
    ) -> None:
        """Copy an object within the same bucket."""
        logger.info(f"Copying '{src_key}' to '{dst_key}' in bucket '{self.bucket}'")
        copy_source = {"Bucket": self.bucket, "Key": src_key}
        self.client.copy(
            CopySource=copy_source,
            Bucket=self.bucket,
            Key=dst_key,
            ExtraArgs=extra_args or {},
        )
        logger.info(f"Successfully copied '{src_key}' to '{dst_key}'")

    def move(self, src_key: str, dst_key: str) -> None:
        """Move (copy then delete) an object."""
        logger.info(f"Moving '{src_key}' to '{dst_key}' in bucket '{self.bucket}'")
        self.copy(src_key, dst_key)
        self.delete_file(src_key)
        logger.info(f"Successfully moved '{src_key}' to '{dst_key}'")

    def read_file(self, key: str, local_path: str) -> None:
        """Download an object to a local path."""
        logger.info(f"Downloading '{self.bucket}/{key}' to '{local_path}'")
        self.client.download_file(
            Bucket=self.bucket, Key=key, Filename=local_path, Config=self.transfer_cfg
        )
        logger.info(f"Successfully downloaded '{key}'")

    def read_bytes(self, key: str) -> bytes:
        """Read an object into memory."""
        logger.debug(f"Reading bytes from '{self.bucket}/{key}'")
        resp = self.client.get_object(Bucket=self.bucket, Key=key)
        data = resp["Body"].read()
        logger.debug(f"Successfully read {len(data)} bytes from '{key}'")
        return data

    def delete_file(self, key: str) -> None:
        """Delete a single object."""
        logger.info(f"Deleting object '{self.bucket}/{key}'")
        self.client.delete_object(Bucket=self.bucket, Key=key)
        logger.info(f"Successfully deleted '{key}'")

    def delete_prefix(self, prefix: str) -> int:
        """
        Delete all objects under a prefix ("folder"). Returns number of deleted objects.
        """
        logger.info(f"Deleting all objects under prefix '{self.bucket}/{prefix}'")
        paginator = self.client.get_paginator("list_objects_v2")
        count = 0

        # Collect all keys to delete
        keys_to_delete = []
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                keys_to_delete.append(obj["Key"])

        if not keys_to_delete:
            logger.info(f"No objects found under prefix '{prefix}'")
            return 0

        logger.debug(f"Found {len(keys_to_delete)} objects to delete")

        # Try batch delete first, fall back to individual deletes if it fails
        try:
            # Delete in batches of 1000 (AWS S3 limit)
            for i in range(0, len(keys_to_delete), 1000):
                batch = keys_to_delete[i : i + 1000]
                delete_dict = {"Objects": [{"Key": key} for key in batch]}

                try:
                    response = self.client.delete_objects(
                        Bucket=self.bucket, Delete=delete_dict
                    )
                    deleted = len(response.get("Deleted", []))
                    count += deleted
                    logger.debug(
                        f"Batch deleted {deleted} objects ({count} total so far)"
                    )

                except ClientError as batch_error:
                    error_code = batch_error.response.get("Error", {}).get("Code")
                    # MinIO sometimes requires Content-MD5, fall back to individual deletes
                    if error_code in ["MissingContentMD5", "InvalidRequest"]:
                        logger.warning(
                            f"Batch delete failed with {error_code}, falling back to individual deletes"
                        )
                        for key in batch:
                            try:
                                self.client.delete_object(Bucket=self.bucket, Key=key)
                                count += 1
                            except Exception as del_err:
                                logger.warning(f"Failed to delete {key}: {del_err}")
                    else:
                        raise

        except Exception as e:
            logger.error(f"Error during batch delete: {e}")
            # Fall back to individual deletes for remaining keys
            logger.info("Falling back to individual delete operations")
            for key in keys_to_delete[count:]:
                try:
                    self.client.delete_object(Bucket=self.bucket, Key=key)
                    count += 1
                    if count % 100 == 0:
                        logger.debug(f"Deleted {count} objects so far")
                except Exception as del_err:
                    logger.warning(f"Failed to delete {key}: {del_err}")

        logger.info(f"Successfully deleted {count} objects under prefix '{prefix}'")
        return count

    def exists(self, key: str) -> bool:
        """Return True if the object exists, False otherwise."""
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError as e:
            status = e.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if status == 404:
                return False
            raise

    def list_files(self, prefix: str = "", recursive: bool = True):
        """
        Yield keys under prefix.
        If recursive=False, emulate folder listing with Delimiter="/".
        """
        paginator = self.client.get_paginator("list_objects_v2")
        if recursive:
            for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
                for obj in page.get("Contents", []):
                    yield obj["Key"]
        else:
            for page in paginator.paginate(
                Bucket=self.bucket, Prefix=prefix, Delimiter="/"
            ):
                for obj in page.get("Contents", []):
                    yield obj["Key"]

    def list_folders(self, prefix: str = ""):
        """
        Yield immediate child 'folders' (common prefixes) under prefix.
        """
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(
            Bucket=self.bucket, Prefix=prefix, Delimiter="/"
        ):
            for cp in page.get("CommonPrefixes", []):
                yield cp["Prefix"]

    def create_folder(self, prefix: str) -> None:
        """
        Create a 'folder' by placing a zero-byte object at prefix ending with '/'.
        """
        if not prefix.endswith("/"):
            prefix += "/"
        logger.info(f"Creating folder '{self.bucket}/{prefix}'")
        self.client.put_object(Bucket=self.bucket, Key=prefix, Body=b"")
        logger.info(f"Successfully created folder '{prefix}'")

    def generate_presigned_url(
        self,
        key: str,
        expiration: int = 3600,
        method: str = "get_object",
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Generate a presigned URL for the given object key.
        method: "get_object" or "put_object"
        expiration: time in seconds for the presigned URL to remain valid
        extra_params: additional parameters to include in the request
        """
        logger.debug(
            f"Generating presigned URL for '{self.bucket}/{key}' with expiration {expiration}s"
        )
        params = {"Bucket": self.bucket, "Key": key}
        if extra_params:
            params.update(extra_params)
        url = self.client.generate_presigned_url(
            ClientMethod=method,
            Params=params,
            ExpiresIn=expiration,
        )
        logger.debug(f"Generated presigned URL for '{key}'")
        return url
