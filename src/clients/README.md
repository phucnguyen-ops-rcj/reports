# Signal CLI Setup

This folder contains notes for onboarding a Signal phone number to `signal-cli-rest-api`.

## Base URL

Local:

```text
http://127.0.0.1:8080
```

Remote via SSH tunnel:

```bash
ssh -L 8080:127.0.0.1:8080 T1_newuser1
```

Then use:

```text
http://127.0.0.1:8080
```

## Link as Secondary Device

Open this URL in a browser:

```text
http://127.0.0.1:8080/v1/qrcodelink?device_name=signal-api
```

On your phone:

```text
Signal -> Settings -> Linked Devices -> Link New Device
```

Scan the QR code.

## Register a Number with Captcha

Request the captcha challenge:

```bash
curl -X POST http://127.0.0.1:8080/v1/register/+84901234567/captcha
```

This returns a JSON object with a captcha image (base64 encoded PNG). Decode and solve the captcha manually to get the text token.

Then register the number with the captcha token:

```bash
curl -X POST http://127.0.0.1:8080/v1/register/+84901234567/captcha/{captcha_text}
```

Replace `{captcha_text}` with the actual solved captcha text.

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
curl -X GET "http://127.0.0.1:8080/v1/receive/+1234567890"
```
```
curl -X GET "http://127.0.0.1:8080/v1/groups/+1234567890"
