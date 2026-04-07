# Signal CLI REST API Notes

This repo contains local notes for running `signal-cli-rest-api` and setting up a Signal phone number for API usage.

Detailed Signal setup notes also live in `src/signal-cli/README.md`.

## Start the API

```bash
cd ~/signal-cli-rest-api/src
nohup env MODE=native SIGNAL_CLI_CONFIG_DIR=$HOME/.local/share/signal-api go run main.go > ~/signal-api.log 2>&1 &
```

Check that the API is reachable:

```bash
curl http://127.0.0.1:8080/swagger/index.html
```

If the API runs on a remote EC2 host, tunnel it first:

```bash
ssh -L 8080:127.0.0.1:8080 T1_newuser1
```

Then open:

```bash
curl http://127.0.0.1:8080/swagger/index.html
```

## Stop the API

To stop the running API service:

```bash
pkill -f "go run main.go"
```

This will kill the background process started with `nohup`.

## Signal Number Setup

You have two common setup paths:

1. Link the API as a secondary device to an existing Signal account.
2. Register the phone number directly through the REST API.

### Option: Register the Phone Number via REST API

Use this if the number is not already linked and you want the API instance to register it directly. Signal requires captcha for registration.

1. Get the captcha token:
   - Go to https://signalcaptchas.org/registration/generate.html
   - Solve the captcha
   - Right-click on the "Open Signal" link and copy the link to get the captcha token (e.g., `signal-hcaptcha-short.xxxxx.registration.yyyyyy`)

2. Register the number with the captcha token:

```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"captcha":"signal-hcaptcha-short.xxxxx.registration.yyyyyy"}' \
  http://127.0.0.1:8080/v1/register/+84559854979
```

Replace `+84559854979` with your real Signal number in international format and `signal-hcaptcha-short.xxxxx.registration.yyyyyy` with the actual captcha token.

3. Verify the number with the SMS code you received:

```bash
curl -X POST http://127.0.0.1:8080/v1/register/+84559854979/verify/123456
```

Replace `123456` with the verification code you received.

## Send a Test Message

```bash
curl -X POST -H "Content-Type: application/json" \
  http://127.0.0.1:8080/v2/send \
  -d '{
    "message": "Test via Signal API",
    "number": "+84559854979",
    "recipients": ["+84906303607"]
  }'
```
### Setting up profile
    AVATAR=$(base64 < /Users/admin/rcj/reports/avatar.png | tr -d '\n')

    curl -X PUT \
    -H "Content-Type: application/json" \
    -d "{
      \"name\": \"rcj_bot\",
      \"about\": \"I am a bot\",
      \"base64_avatar\": \"${AVATAR}\"
    }" \
    "http://127.0.0.1:8080/v1/profiles/+84559854979"
    

