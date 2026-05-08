FROM public.ecr.aws/lambda/python:3.12

WORKDIR ${LAMBDA_TASK_ROOT}

# Install runtime dependencies directly into Lambda task root.
RUN pip install --no-cache-dir \
    fastapi>=0.135.3 \
    groq>=1.1.2 \
    python-dotenv>=1.2.2 \
    vadersentiment>=3.3.2 \
    mangum>=0.19.0

COPY main.py ./

# Lambda container entrypoint expects "module.handler".
CMD ["main.handler"]