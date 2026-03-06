"""
Shared test configuration for SecureVote tests.
Sets environment to 'testing' to disable rate limiting.
"""
import os

os.environ['FLASK_ENV'] = 'testing'
