"""Probe configured buckets using only newly created, temporary QA objects."""
import os
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import boto3
import requests
from botocore.config import Config
from dotenv import dotenv_values

values = {}
for path in ('.env', '.env.local'):
    values.update(dotenv_values(path, interpolate=False))
values.update({key: value for key, value in os.environ.items() if value})
required = ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'OBJECT_STORAGE_BUCKET', 'PRIVATE_UPLOADS_BUCKET']
assert all(values.get(key) for key in required), 'Storage credentials are not configured locally.'
client = boto3.client('s3', endpoint_url=values.get('OBJECT_STORAGE_ENDPOINT_URL') or None,
    region_name=values.get('OBJECT_STORAGE_REGION', 'auto'),
    aws_access_key_id=values['AWS_ACCESS_KEY_ID'], aws_secret_access_key=values['AWS_SECRET_ACCESS_KEY'],
    config=Config(signature_version='s3v4', s3={'addressing_style': 'path'}, retries={'max_attempts': 2}))
for label, setting in [('listing photos', 'OBJECT_STORAGE_BUCKET'), ('private evidence', 'PRIVATE_UPLOADS_BUCKET')]:
    key = 'qa-probes/' + uuid4().hex + '.txt'
    bucket = values[setting]
    created = False
    stage = 'upload'
    try:
        client.put_object(Bucket=bucket, Key=key, Body=b'FoodLoop temporary storage QA.', ContentType='text/plain', ACL='private')
        created = True
        stage = 'authenticated download'
        assert client.get_object(Bucket=bucket, Key=key)['Body'].read() == b'FoodLoop temporary storage QA.'
        url = client.generate_presigned_url('get_object', Params={'Bucket': bucket, 'Key': key}, ExpiresIn=60)
        stage = 'signed download'
        response = requests.get(url, timeout=20)
        assert response.status_code == 200 and response.content == b'FoodLoop temporary storage QA.'
        parsed = urlsplit(url)
        stage = 'anonymous access check'
        public = requests.get(urlunsplit((parsed.scheme, parsed.netloc, parsed.path, '', '')), timeout=20)
        assert public.status_code in (400, 401, 403, 404) and public.content != b'FoodLoop temporary storage QA.', 'Storage object unexpectedly allows anonymous access.'
        print(label + ': upload, download, signed access and anonymous denial PASS', flush=True)
    except Exception as error:
        code = getattr(error, 'response', {}).get('Error', {}).get('Code', '') if isinstance(getattr(error, 'response', {}), dict) else ''
        print('Failure stage:', stage, 'type:', type(error).__name__, 'code:', code, flush=True)
        if stage == 'signed download':
            print('Signed HTTP status:', response.status_code, flush=True)
        if stage == 'anonymous access check':
            print('Anonymous HTTP status:', public.status_code, flush=True)
        raise SystemExit(label + ': storage probe failed; provider responses withheld to protect credentials.') from None
    finally:
        if created:
            # Delete only the exact unique key created by this invocation.
            assert key.startswith('qa-probes/') and len(key.split('/')[-1]) == 36
            client.delete_object(Bucket=bucket, Key=key)
print('Temporary QA objects removed; existing uploads were untouched.')
