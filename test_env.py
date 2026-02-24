#!/usr/bin/env python3
"""Test script to verify .env loading and AWS credentials."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Test 1: Load .env
print("=" * 60)
print("TEST 1: Loading .env file")
print("=" * 60)
env_path = Path(__file__).parent / ".env"
print(f"Looking for .env at: {env_path.resolve()}")
print(f"File exists: {env_path.exists()}")

if env_path.exists():
    with open(env_path, 'r') as f:
        print(f"Content of .env:\n{f.read()}")

load_dotenv(env_path)

# Test 2: Check what was loaded
print("\n" + "=" * 60)
print("TEST 2: Environment variables after load_dotenv()")
print("=" * 60)
aws_key = os.getenv("AWS_ACCESS_KEY")
aws_secret = os.getenv("AWS_SECRET_KEY")
print(f"AWS_ACCESS_KEY: {aws_key if aws_key else '(not set)'}")
print(f"AWS_SECRET_KEY: {aws_secret if aws_secret else '(not set)'}")

# Test 3: Map to boto3 variable names
print("\n" + "=" * 60)
print("TEST 3: Mapping to AWS boto3 variable names")
print("=" * 60)
if aws_key:
    os.environ["AWS_ACCESS_KEY_ID"] = aws_key
    print(f"Set AWS_ACCESS_KEY_ID = {os.getenv('AWS_ACCESS_KEY_ID')}")
if aws_secret:
    os.environ["AWS_SECRET_ACCESS_KEY"] = aws_secret
    print(f"Set AWS_SECRET_ACCESS_KEY = {os.getenv('AWS_SECRET_ACCESS_KEY')}")

# Test 4: Verify boto3 can see them
print("\n" + "=" * 60)
print("TEST 4: Can boto3 see the credentials?")
print("=" * 60)
try:
    import boto3
    session = boto3.Session()
    creds = session.get_credentials()
    if creds:
        print(f"✓ Credentials loaded by boto3")
        print(f"  Access Key ID: {creds.access_key[:10]}..." if creds.access_key else "  (None)")
        print(f"  Secret Access Key: {creds.secret_key[:10] if creds.secret_key else '(None)'}...")
    else:
        print("✗ boto3 cannot find credentials")
except Exception as e:
    print(f"✗ Error checking boto3 credentials: {e}")
