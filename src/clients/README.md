# Signal CLI Setup

This folder contains notes for onboarding a Signal phone number to `signal-cli-rest-api`.

## Base URL

Local:

```text
http://127.0.0.1:8081
```

Remote via SSH tunnel:

```bash
ssh -L 8081:127.0.0.1:8081 T1_newuser1
```

Then use:

```text
http://127.0.0.1:8081
```

## Link as Secondary Device

Open this URL in a browser:

```text
http://127.0.0.1:8081/v1/qrcodelink?device_name=signal-api
```

On your phone:

```text
Signal -> Settings -> Linked Devices -> Link New Device
```

Scan the QR code.

## Register a New Number

Registration is a two-step process.

### Step 1 — Initiate registration

```bash
curl -X POST -H "Content-Type: application/json" -d "{\"use_voice\": false}" "http://127.0.0.1:8081/v1/register/+84367678281"
```

Set `"use_voice": true` to receive the code via phone call instead of SMS (useful for landlines).

If Signal requires a captcha, visit https://signalcaptchas.org/registration/generate.html, solve it, copy the `signalcaptcha://...` token from the browser console, then pass it in the body:

```bash
curl -X POST -H "Content-Type: application/json" -d "{\"captcha\": \"signalcaptcha://signal-hcaptcha."}" "http://127.0.0.1:8081/v1/register/+84559854979"
```

### Step 2 — Verify with the code

```bash
curl -X POST "http://127.0.0.1:8081/v1/register/+84559854979/verify/"
```

Replace `123-456` with the code received via SMS or voice call.

## Send a Test Message

```bash
curl -X POST -H "Content-Type: application/json" \
  http://127.0.0.1:8080/v2/send \
  -d '{
    "message": "hello from signal-cli-rest-api",
    "number": "+84559854979",
    "recipients": ["+84906303607"]
  }'
```

If the API is on a different host or port, replace `http://127.0.0.1:8080` with the correct URL.

## Setup Signal Profile

Update the profile with:

- display name
- about text
- avatar

Endpoint:

```text
PUT /v1/profiles/{accountNumber}
```

### Name Only

```bash
curl -X PUT \
  -H "Content-Type: application/json" \
  -d '{
    "name": "rcj_bot"
  }' \
  "http://127.0.0.1:8080/v1/profiles/+84559854979"
```

### Name and About

```bash
curl -X PUT \
  -H "Content-Type: application/json" \
  -d '{
    "name": "rcj_bot",
    "about": "I am a bot"
  }' \
  "http://127.0.0.1:8080/v1/profiles/+84559854979"
```

### Name, About, and Avatar

`base64_avatar` can be too large to inline directly in a shell command. The safer approach is to write the JSON body to a file.

```bash
AVATAR=$(base64 < profile.jpg | tr -d '\n')

cat > /tmp/signal_profile.json <<EOF
{
  "name": "rcj_bot",
  "about": "I am a bot",
  "base64_avatar": "$AVATAR"
}
EOF

curl -X PUT \
  -H "Content-Type: application/json" \
  --data @/tmp/signal_profile.json \
  "http://127.0.0.1:8080/v1/profiles/+84559854979"
```

### If zsh says `argument list too long`

Do not inline the base64 string into the `curl` command directly. Use a JSON file as shown above.

If needed, resize the avatar before encoding it:

```bash
magick profile.jpg -resize 512x512\> -quality 85 /tmp/profile_small.jpg
```

Then base64-encode `/tmp/profile_small.jpg` instead.

## Get group id
```
curl -X GET "http://127.0.0.1:8080/v1/receive/+84559854979"
```
```
curl -X GET "http://127.0.0.1:8080/v1/groups/+84559854979"
