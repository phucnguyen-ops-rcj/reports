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

## Register a New Number

Registration is a two-step process.

### Step 1 — Initiate registration

```bash
curl -X POST -H "Content-Type: application/json" -d "{\"use_voice\": false}" "http://127.0.0.1:8080/v1/register/+84559854979"
```

Set `"use_voice": true` to receive the code via phone call instead of SMS (useful for landlines).

If Signal requires a captcha, visit https://signalcaptchas.org/registration/generate.html, solve it, copy the `signalcaptcha://...` token from the browser console, then pass it in the body:

```bash
curl -X POST -H "Content-Type: application/json" -d "{\"captcha\": \"signalcaptcha://signal-hcaptcha.5fad97ac-7d06-4e44-b18a-b950b20148ff.registration.P1_eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.haJwZACjZXhwzmnfdwuncGFzc2tlecUFPBOu3QeLySV5n-RW7Df_P7e7TcWgYS2Skeq5LVWxCyojSZ5MLR6dVi5GdjEO8iB9drm9WGAWUt1myYwO-GOKBiZkL1sMaUMC-uaVGiL7Bmzhu_wHuDr7h2jnvVVJ7ARXXMwz3ECAEVm1DEbo3YvzHtbJUSGJDLKs1WYI0cI8Vbi65wzZB1HBx3Qo5hMNW6aO7Q6l-hSU2MpH4tXQwSIWGiEIxjBfvd6Y5qB1LrBLOgVDuYgsgZlYAPopanBr-YD1HM8LgatfR7hjCwwo_bSFmLqA6ydH_0QTVk9KxT4L3g2nfL52ME9vze-zUuHIP3Ms-8ckR6aSBA8rzGmwFqtX8GOP4mpm1U6dfRJrxvgMwh_c2eX-o6vPd3WZQc5N2YDcfpwcJBJQ9fyzrfcuSImY_x8LHhHN0sxYxg6t3XA1qtFyFqZRWgvj-o7tfS2zcaqG4AJhqvsA6kSduxcOrHCWHKaigem_0ZVdYA20w9P3pNPqZ8mjNAyVE20UHJt8S6098eCIwrsD1ollKX09_vB3_yeEL8u1AFm98N-_NaxprACm-I2lLzbfRxu5wZaUJD9NWIDYmTf7IwTH4iDS5eKVxtqLHx0zHH7Utn1nOkl1262EnoH0ON03Q7Su8NRGg6Y2mPSINJs_cLTBElbj0G5ZTVs1wdtF8qd_9xQrj95wTW6nyinGNCt9hNNcNCWWuFJiwAyt0P-f7QoyTw1jqdKXBcWZyBzQkhKI4cvg9gr1q82_XtjrWcPYYlydAWVuhDTuOnTaJej7nWCSD8y926DcR05p7zR627PDb_tR15LJYedt35LlP2fEBNDpPMuN7Uu_31U1WBLYJ3cDrpVH7svjUX08UF_I2RtXahE7wdtc8U8j2lQVeECV7wlnJTllovoeS3KGWBpJYzZ8QAvvlEw_zFm0hO45RhrGAadCeDWKiSD97s-6LT4kDGtW7n5JoJKQz3g-hc2EotcNP5ss2Y-hyMreFAORDHI9_Vx03A8_1kdBT1y_DPVi-fjdiGV_YxIXdRRm88mzLKC8yh5PirApGS8u50gCIzdf8TIQopIXG4WUeUVg35ATgClXWUhqy7wtf9Ak5P_99SfkhARohUibEviEVbaJ0r7mXIGZQcrstowpLp63F7N6npvI70dZjVLH6PqIN_1Eu2uUgIs57NUchgzdmv9o5Kt6n8gLUMsMMn6Jz6nWLzH5gmn1cbAoXwpVx8ocdZ1ihrkj2KdRCz27LBWiYMAJ4xSuUweXx4T90cWyuIKko16klYPh8Z53mUlSjuNQS2YbWqSmgcfSCwmZN8V2Wv72u4MKJ0oVzW0YAydSEZ30xmBAG4WqFibeLdPrFeVkT_oXWAml8eRd81EnIb3ClwHHJBje1E9F6t-xOyQwz1_gcKpqqqNHDj3NDeIKMsYPsKu_SbW_DHP_27uHycRIE9nTJ2omFIeA447Y0-yiBeivTbHYuqi9pYMTWZbN0MmWI6Yl-yLOK2IZFSU0X_mecSVzz-lITQrbQg4ET0p_-RJvLsJz1iYeOP9eZA3s3KZNYuREEalm90OiJ8HZKgPh4xCPHwXkYOaSAv2sx18BzzCBKTyUeRmVxUc9eyTYXBVQhc1UQp-0faY2Gwlci6Yjz1n8uRTWSb0zYzVGbzBVBKOfQgVaYRREwDXj7O72cNpSxfQ5F2U6WJ5pYsX4XGJz-hZK44FA-CjtSs1C29_99ANjE_pCvOlXLBuMHRlqFkjIOa5cISRjwbENTO_dVzBXuIVhLhQUqcTmkTdrfQ4BMp7mU2IWyCEVkPn-omtyqDFkNTMwNTI2qHNoYXJkX2lkzhWZ5FQ.m3n-7WnYBE1sb8AnhMv7OP9ROzvTRE2Kiw09fO6wN-8\"}" "http://127.0.0.1:8080/v1/register/+84559854979"
```

### Step 2 — Verify with the code

```bash
curl -X POST "http://127.0.0.1:8080/v1/register/+84559854979/verify/123-456"
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
curl -X GET "http://127.0.0.1:8080/v1/receive/+1234567890"
```
```
curl -X GET "http://127.0.0.1:8080/v1/groups/+1234567890"
