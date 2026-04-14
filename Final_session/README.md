# Sentiment API (FastAPI + VADER + Groq) on AWS Lambda

This project is a **Python FastAPI sentiment API** that:
- Classifies input text as **POSITIVE** or **NEGATIVE** using **VADER**.
- Returns a confidence-like score from the VADER compound value.
- Optionally generates a playful roast using **Groq** (if `GROQ_API_KEY` is set).
- Is packaged for **AWS Lambda (container image)** using the provided `Dockerfile`.

---

## What this project does

### API routes
- `GET /`  
  Serves a simple HTML UI for entering text and viewing prediction results.
- `POST /predict`  
  Accepts JSON:
  ```json
  { "text": "your message here" }
  ```
  Returns:
  ```json
  {
    "label": "POSITIVE",
    "score": 0.8123,
    "roast": "..."
  }
  ```
- `GET /health`  
  Health endpoint:
  ```json
  { "status": "ok" }
  ```

### Main components
- `main.py`
  - Builds `FastAPI()` app.
  - Uses `SentimentIntensityAnalyzer` from `vaderSentiment`.
  - Uses `Groq` client for roast generation.
  - Exposes `handler = Mangum(app)` for Lambda compatibility.
- `pyproject.toml`
  - Python `>=3.12`
  - Dependencies: `fastapi`, `mangum`, `vadersentiment`, `groq`, `python-dotenv`, `uvicorn`.

---

## What is happening in the Dockerfile

```dockerfile
FROM public.ecr.aws/lambda/python:3.12
WORKDIR ${LAMBDA_TASK_ROOT}
RUN pip install --no-cache-dir ...dependencies...
COPY main.py ./
CMD ["main.handler"]
```

Explanation:
1. `FROM public.ecr.aws/lambda/python:3.12`  
   Uses AWS Lambda’s official Python 3.12 base image.
2. `WORKDIR ${LAMBDA_TASK_ROOT}`  
   Uses Lambda task root as the working directory.
3. `RUN pip install ...`  
   Installs runtime packages into the container image.
4. `COPY main.py ./`  
   Copies app code.
5. `CMD ["main.handler"]`  
   Tells Lambda to call `handler` from `main.py` (`main.handler`).

---

## Run locally (optional)

```bash
cd /home/raqeeb/AWS_CLub/ML_sesssion/sentiment-api
python -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Open: `http://localhost:8000`

Set Groq key (optional, enables roast mode):
```bash
export GROQ_API_KEY="your_groq_api_key"
```

---

## AWS setup: CLI, ECR, image push, Lambda, API Gateway

### One-command setup script

```bash
cd /home/raqeeb/AWS_CLub/ML_sesssion/sentiment-api
./setup_project.sh
```

The script prompts for values, then sets up ECR, builds/pushes the image, creates/updates Lambda, and configures API Gateway.

If Docker permission fails (`/var/run/docker.sock`), run:
```bash
sudo usermod -aG docker $USER
newgrp docker
```

Replace placeholders:
- `AWS_REGION` (example: `us-east-1`)
- `ACCOUNT_ID` (your AWS account)
- `ECR_REPO` (example: `sentiment-api`)
- `IMAGE_TAG` (example: `v1`)
- `LAMBDA_FUNCTION` (example: `sentiment-api-fn`)

### 1. Install and configure AWS CLI

Install (Linux x86_64):
```bash
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install
aws --version
```

Configure credentials:
```bash
aws configure
```

You will enter:
- AWS Access Key ID
- AWS Secret Access Key
- Default region name
- Default output format (e.g. `json`)

### 2. Create ECR repository

```bash
AWS_REGION=us-east-1
ECR_REPO=sentiment-api

aws ecr create-repository \
  --repository-name "$ECR_REPO" \
  --image-scanning-configuration scanOnPush=true \
  --region "$AWS_REGION"
```

### 3. Build, tag, and push Docker image to ECR

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=us-east-1
ECR_REPO=sentiment-api
IMAGE_TAG=v1
IMAGE_URI="$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:$IMAGE_TAG"

# Login Docker to ECR
aws ecr get-login-password --region "$AWS_REGION" | \
docker login --username AWS --password-stdin "$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"

# Build image
docker build -t "$ECR_REPO:$IMAGE_TAG" .

# Tag image for ECR
docker tag "$ECR_REPO:$IMAGE_TAG" "$IMAGE_URI"

# Push to ECR
docker push "$IMAGE_URI"
```

### 4. Create Lambda execution role (one-time)

```bash
cat > trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Service": "lambda.amazonaws.com" },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

aws iam create-role \
  --role-name sentiment-api-lambda-role \
  --assume-role-policy-document file://trust-policy.json

aws iam attach-role-policy \
  --role-name sentiment-api-lambda-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
```

Get role ARN:
```bash
ROLE_ARN=$(aws iam get-role --role-name sentiment-api-lambda-role --query Role.Arn --output text)
echo "$ROLE_ARN"
```

### 5. Create Lambda function from container image

```bash
LAMBDA_FUNCTION=sentiment-api-fn
AWS_REGION=us-east-1

aws lambda create-function \
  --function-name "$LAMBDA_FUNCTION" \
  --package-type Image \
  --code ImageUri="$IMAGE_URI" \
  --role "$ROLE_ARN" \
  --timeout 30 \
  --memory-size 512 \
  --region "$AWS_REGION"
```

Set Groq key in Lambda env variables (optional):
```bash
aws lambda update-function-configuration \
  --function-name "$LAMBDA_FUNCTION" \
  --environment "Variables={GROQ_API_KEY=your_groq_api_key}" \
  --region "$AWS_REGION"
```

If you push a new image tag later:
```bash
aws lambda update-function-code \
  --function-name "$LAMBDA_FUNCTION" \
  --image-uri "$IMAGE_URI" \
  --region "$AWS_REGION"
```

### 6. Create and configure API Gateway (HTTP API)

Create API:
```bash
API_ID=$(aws apigatewayv2 create-api \
  --name sentiment-api-http \
  --protocol-type HTTP \
  --target "arn:aws:lambda:$AWS_REGION:$ACCOUNT_ID:function:$LAMBDA_FUNCTION" \
  --region "$AWS_REGION" \
  --query ApiId --output text)

echo "$API_ID"
```

Allow API Gateway to invoke Lambda:
```bash
aws lambda add-permission \
  --function-name "$LAMBDA_FUNCTION" \
  --statement-id apigw-invoke-permission \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:$AWS_REGION:$ACCOUNT_ID:$API_ID/*/*/*" \
  --region "$AWS_REGION"
```

Get invoke URL:
```bash
API_URL=$(aws apigatewayv2 get-api --api-id "$API_ID" --region "$AWS_REGION" --query ApiEndpoint --output text)
echo "$API_URL"
```

Test health endpoint:
```bash
curl "$API_URL/health"
```

Test prediction endpoint:
```bash
curl -X POST "$API_URL/predict" \
  -H "Content-Type: application/json" \
  -d '{"text":"This session was really helpful and fun!"}'
```

---

## Notes

- If `GROQ_API_KEY` is missing, sentiment still works, but roast mode returns a guidance message.
- Lambda + API Gateway may take a short time after initial creation before responding consistently.
- Keep AWS credentials secure; do not hardcode secrets in source files.
