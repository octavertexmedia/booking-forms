"""AWS Lambda entrypoint for serverless Wagtail (API Gateway HTTP API / Function URL)."""

from mangum import Mangum

from portal.asgi import application

handler = Mangum(application, lifespan="off")
