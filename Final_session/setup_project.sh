#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

AWS_REGION="${AWS_REGION:-us-east-1}"
ECR_REPO="${ECR_REPO:-sentiment-api}"
IMAGE_TAG="${IMAGE_TAG:-v1}"
LAMBDA_FUNCTION="${LAMBDA_FUNCTION:-sentiment-api-fn}"
IAM_ROLE_NAME="${IAM_ROLE_NAME:-sentiment-api-lambda-role}"
API_NAME="${API_NAME:-sentiment-api-http}"
LAMBDA_TIMEOUT="${LAMBDA_TIMEOUT:-30}"
LAMBDA_MEMORY_MB="${LAMBDA_MEMORY_MB:-512}"
GROQ_API_KEY="${GROQ_API_KEY:-}"
DOCKER_CMD=(docker)
log() { printf "\n[INFO] %s\n" "$*"; }
warn() { printf "\n[WARN] %s\n" "$*" >&2; }
err() { printf "\n[ERROR] %s\n" "$*" >&2; }

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    err "Required command not found: $1"
    return 1
  fi
}

install_aws_cli_if_needed() {
  if command -v aws >/dev/null 2>&1; then
    return 0
  fi

  log "AWS CLI not found. Attempting install (Linux x86_64)..."
  need_cmd curl
  need_cmd unzip

  if [[ "$(uname -s)" != "Linux" || "$(uname -m)" != "x86_64" ]]; then
    err "Automatic AWS CLI install supports Linux x86_64 in this script."
    err "Install AWS CLI manually, then rerun."
    exit 1
  fi

  tmp_dir="$(mktemp -d)"
  trap 'rm -rf "$tmp_dir"' EXIT

  curl -sS "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "$tmp_dir/awscliv2.zip"
  unzip -q "$tmp_dir/awscliv2.zip" -d "$tmp_dir"

  if command -v sudo >/dev/null 2>&1; then
    sudo "$tmp_dir/aws/install" --update
  else
    "$tmp_dir/aws/install" --update
  fi

  if ! command -v aws >/dev/null 2>&1; then
    err "AWS CLI installation did not succeed."
    exit 1
  fi
}

prompt_value() {
  local var_name="$1"
  local prompt="$2"
  local current_value="$3"
  local input

  read -r -p "$prompt [$current_value]: " input || true
  if [[ -n "${input:-}" ]]; then
    printf -v "$var_name" '%s' "$input"
  else
    printf -v "$var_name" '%s' "$current_value"
  fi
}

ensure_aws_identity() {
  if aws sts get-caller-identity --query Account --output text >/dev/null 2>&1; then
    return 0
  fi

  warn "AWS CLI credentials are not configured or invalid."
  log "Running: aws configure"
  aws configure
}

ensure_docker_access() {
  if docker info >/dev/null 2>&1; then
    DOCKER_CMD=(docker)
    return 0
  fi

  if command -v sudo >/dev/null 2>&1; then
    warn "No direct Docker socket access; attempting sudo for Docker commands."
    if sudo -v >/dev/null 2>&1 && sudo docker info >/dev/null 2>&1; then
      DOCKER_CMD=(sudo docker)
      return 0
    fi
  fi

  err "Docker is not accessible for the current user."
  err "Fix one of the following, then rerun:"
  err "1) Start Docker daemon/service"
  err "2) Add your user to docker group: sudo usermod -aG docker \$USER && newgrp docker"
  err "3) Run script with sudo if appropriate"
  exit 1
}

validate_region() {
  local regions
  regions="$(aws ec2 describe-regions --all-regions --query 'Regions[].RegionName' --output text 2>/dev/null || true)"

  if [[ -z "$regions" ]]; then
    warn "Could not fetch AWS region list (permission/network). Skipping strict region validation."
    return 0
  fi

  if ! grep -qw -- "$AWS_REGION" <<<"$regions"; then
    err "Invalid or unsupported AWS region: $AWS_REGION"
    err "Example valid regions: us-east-1, us-east-2, us-west-1, us-west-2, eu-west-1, ap-south-1"
    exit 1
  fi
}

create_ecr_repo_if_missing() {
  if aws ecr describe-repositories --repository-names "$ECR_REPO" --region "$AWS_REGION" >/dev/null 2>&1; then
    log "ECR repository exists: $ECR_REPO"
    return 0
  fi

  log "Creating ECR repository: $ECR_REPO"
  aws ecr create-repository \
    --repository-name "$ECR_REPO" \
    --image-scanning-configuration scanOnPush=true \
    --region "$AWS_REGION" >/dev/null
}

ensure_lambda_role() {
  if aws iam get-role --role-name "$IAM_ROLE_NAME" >/dev/null 2>&1; then
    log "IAM role exists: $IAM_ROLE_NAME"
    return 0
  fi

  log "Creating IAM role: $IAM_ROLE_NAME"
  trust_file="$(mktemp)"
  cat >"$trust_file" <<'JSON'
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
JSON

  aws iam create-role \
    --role-name "$IAM_ROLE_NAME" \
    --assume-role-policy-document "file://$trust_file" >/dev/null
  rm -f "$trust_file"

  aws iam attach-role-policy \
    --role-name "$IAM_ROLE_NAME" \
    --policy-arn "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole" >/dev/null

  log "Waiting for IAM role propagation..."
  sleep 10
}

build_and_push_image() {
  log "Logging in Docker to ECR"
  aws ecr get-login-password --region "$AWS_REGION" \
    | "${DOCKER_CMD[@]}" login --username AWS --password-stdin "$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com" >/dev/null

  log "Building Docker image"
  "${DOCKER_CMD[@]}" build -t "$ECR_REPO:$IMAGE_TAG" .

  log "Tagging and pushing image: $IMAGE_URI"
  "${DOCKER_CMD[@]}" tag "$ECR_REPO:$IMAGE_TAG" "$IMAGE_URI"
  "${DOCKER_CMD[@]}" push "$IMAGE_URI"
}

create_or_update_lambda() {
  if aws lambda get-function --function-name "$LAMBDA_FUNCTION" --region "$AWS_REGION" >/dev/null 2>&1; then
    log "Updating existing Lambda function image"
    aws lambda update-function-code \
      --function-name "$LAMBDA_FUNCTION" \
      --image-uri "$IMAGE_URI" \
      --region "$AWS_REGION" >/dev/null
  else
    log "Creating Lambda function: $LAMBDA_FUNCTION"
    aws lambda create-function \
      --function-name "$LAMBDA_FUNCTION" \
      --package-type Image \
      --code "ImageUri=$IMAGE_URI" \
      --role "$ROLE_ARN" \
      --timeout "$LAMBDA_TIMEOUT" \
      --memory-size "$LAMBDA_MEMORY_MB" \
      --region "$AWS_REGION" >/dev/null
  fi

  if [[ -n "$GROQ_API_KEY" ]]; then
    log "Setting Lambda environment variable: GROQ_API_KEY"
    aws lambda update-function-configuration \
      --function-name "$LAMBDA_FUNCTION" \
      --environment "Variables={GROQ_API_KEY=$GROQ_API_KEY}" \
      --region "$AWS_REGION" >/dev/null
  fi
}

create_or_get_http_api() {
  API_ID="$(aws apigatewayv2 get-apis \
    --region "$AWS_REGION" \
    --query "Items[?Name=='$API_NAME'].ApiId | [0]" \
    --output text)"

  if [[ "$API_ID" == "None" || -z "$API_ID" ]]; then
    log "Creating API Gateway HTTP API: $API_NAME"
    API_ID="$(aws apigatewayv2 create-api \
      --name "$API_NAME" \
      --protocol-type HTTP \
      --target "arn:aws:lambda:$AWS_REGION:$ACCOUNT_ID:function:$LAMBDA_FUNCTION" \
      --region "$AWS_REGION" \
      --query ApiId --output text)"
  else
    log "API Gateway HTTP API exists: $API_NAME (API_ID=$API_ID)"
  fi
}

allow_api_gateway_invoke() {
  local statement_id="apigw-invoke-$API_ID"
  if aws lambda add-permission \
    --function-name "$LAMBDA_FUNCTION" \
    --statement-id "$statement_id" \
    --action "lambda:InvokeFunction" \
    --principal "apigateway.amazonaws.com" \
    --source-arn "arn:aws:execute-api:$AWS_REGION:$ACCOUNT_ID:$API_ID/*/*/*" \
    --region "$AWS_REGION" >/dev/null 2>&1; then
    log "Added Lambda invoke permission for API Gateway"
  else
    warn "Lambda invoke permission may already exist (continuing)"
  fi
}

print_summary() {
  API_URL="$(aws apigatewayv2 get-api \
    --api-id "$API_ID" \
    --region "$AWS_REGION" \
    --query ApiEndpoint --output text)"

  cat <<EOF

========================================
Setup complete.
========================================
AWS Region:      $AWS_REGION
ECR Repository:  $ECR_REPO
Image URI:       $IMAGE_URI
Lambda Function: $LAMBDA_FUNCTION
API ID:          $API_ID
API URL:         $API_URL

Try:
  curl "$API_URL/health"
  curl -X POST "$API_URL/predict" -H "Content-Type: application/json" -d '{"text":"This workshop is awesome!"}'
EOF
}

main() {
  log "Starting project setup and deployment..."

  install_aws_cli_if_needed
  need_cmd docker
  need_cmd aws
  ensure_aws_identity
  ensure_docker_access

  prompt_value AWS_REGION "AWS region" "$AWS_REGION"
  validate_region
  prompt_value ECR_REPO "ECR repository name" "$ECR_REPO"
  prompt_value IMAGE_TAG "Docker image tag" "$IMAGE_TAG"
  prompt_value LAMBDA_FUNCTION "Lambda function name" "$LAMBDA_FUNCTION"
  prompt_value IAM_ROLE_NAME "IAM role name for Lambda" "$IAM_ROLE_NAME"
  prompt_value API_NAME "API Gateway HTTP API name" "$API_NAME"

  read -r -p "Set GROQ_API_KEY on Lambda now? (leave blank to skip): " input_groq || true
  if [[ -n "${input_groq:-}" ]]; then
    GROQ_API_KEY="$input_groq"
  fi

  ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
  IMAGE_URI="$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:$IMAGE_TAG"

  create_ecr_repo_if_missing
  ensure_lambda_role
  ROLE_ARN="$(aws iam get-role --role-name "$IAM_ROLE_NAME" --query Role.Arn --output text)"
  build_and_push_image
  create_or_update_lambda
  create_or_get_http_api
  allow_api_gateway_invoke
  print_summary
}

main "$@"
