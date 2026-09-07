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
or
```
CAPTCHA=''
curl -i -X POST \
  -H 'Content-Type: application/json' \
  -d "{\"captcha\":\"signalcaptcha://signal-hcaptcha.5fad97ac-7d06-4e44-b18a-b950b20148ff.registration.P1_eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.haJwZACjZXhwzmqc6MincGFzc2tlecUHH3q5MNMSeQub5Z5ATSGUpYGOfOtPoo8u1LIlA_FxBS61zE_yvd6pxVMGEpK0V-enSCHHpd-2b0cP_vHBHIjV0syrUfr6_uYLCSRC9sarB1t4P47A0PFGe8AreL21eKAlCezM-5BHW4xkEQY7B64Wz-LofxAGj-O8fh6Q-95qIE4DKS4LMK9Hs9Fqdd3Lv0CZOlHsURU1Hu7OEnnVrYTHI_CLTu_q5IF0_Wsaaje3lgmLZRBOH7Ig0_lTwOCPaPvD2O0GqVAJSxRz_yHn4ZZfB9HEUYXiU9-GHudln-1XGF5Xg-PbVcXDroI8C3xtRjPB2AUzy7Beyh7RDnuilALH_QojfNdgxpdIzaNMcptXQ7WXRIDLNz4JfcW83Jm3F2urb3kR2QKow_dSh9Lt9tlgWXzToGh9JsNOfeHS8TW-M-h0O2njhNRPXDGIibDjQP-IKUnAD1ktY_stsZ6vjWe9PrPD9fbuJ4SM1N3xkWrlReEYw2svM0b9plm3i3HaxDhrM1r3zNWZ2KcpMya97b0W5lORxKsewtv6nhobYN30BvMDaENCqY6qXs583CJgD5foWd4ylmJNdaNs6weFe67u_O14mhp04CX4I4cBY65dI9g9RjZcPH0RFI_9SS_DC9NvY1owQBY7mwowR4Ti8lOz1K-UzxCK48uTb1Sropdd42Qgw_Vcm-dFy4rBZaNqlH6-1rVEZsFlexc5KJYXG8LW071jzBt7uVgGIdH8JLDQNurykClTK8maVO-BBiIb5e_ehl1HlNcquMD9j8aeybGKIKAnw7r-kZzKne92qshrsq57UqHcZeI0RsyYeA-WiU_jsJeV9axIfcpa-04afcepRSUgEHqnS9U4YgzluILWcCoxrty9Wl5KH6irchASRjau8xMqjncz5tAqfvwJG12omMAcfVFpIKcTwFGWgsGY-VzWXijgcYxdoI6arMKGoDRb2fTmyLNVBfhOgJppTVvWmOH-O6XCu7u-auX9gGQAU9NQ2yGHqN99qI_eUEuHkx9esvdKTnxibcsXEBVe56DXytzbJq23S82h3nIqZ5Vs6sKoTdxQB3F6pCQNSgWTZhsm4-FzwLrTuXURdappTth-V-BS5MNYPmKOyDSKBKco4KWKURIgCa-yp16mhd5phyRClQ1qy3PqstK4OGZkBfUELDVNjSD29UMQBIuVcqOCo9qQvAifREmQEhbp2S_pSsWdoYzphd5_46ucprhqWHi0oglr1VwdBO7aQ_0h-6wqd0tT9wQ0dChp9pyy0etGPJRwIgq9KYOSgxOJ2iNqLWKRiQ5PqSqGMnjAvJ6-A3-iMoYvRZDOLJvq7mZOOyXb3UHWTPm05qh3Z3mJBzOLdIukYPOGOpSSLCLVfcJePY8UoXDUdUFZNk51kFxwd6IcB7DiIcNQiaws8AP34rro4ylZKCdtvBenPx6g-5ihBVtwocML2WOsLe1B3diqdmS733z4rHK6hJrUn20ZtosqO5qTJjq9bi_Qgm3I6EtT_k_TnZ237SO-Ea8vW2aL5co_HeKo5q0pO-jV3c9v6tTPPQIT8as3FeGR31W7FosW-04RlCvex_IYxvk5F0OG1ixblQr5N3RYJCHFWwynnt-a8CD0wuC5tI7a9Kd4eMcDnxK1AVmUX7DHoZdqdQ6dyWD_fXaQh8kcyqUyZr1oXgTtMMusrUlRnztsc2NMxhVjyIdYAq1EA9IrKY3BvnF0mSmjS0OJ4k5moP6ws7xJRDgS3A9561VA2OLw4jeSoY0DM1yp8Dk_NY7nmfcCiQlOBt4QjRGrhWr35XNEaSlbqI9HXW2qS-DPZIrirIF4HtUBOlx7r426Y8untYYyZTszvyvMyYW0pRHVavzNAtGU7_jLemD5MkOwWW_r0kqyy88SuXn-x4WRZcpIlw1bMchQy0-awmSdwEJlqW4d4jQh2zbSKGgn7HX8EteSpa2t_EsDnm-u5csUYCU6gIeU9HrAWV97PXe6xyeeAEX9IA-3fwE1HEfkBt0BCjC7_Oo8o66SKQBBUfq_4uMlT4tDlXhVBksNCGtthif1e8Uczbo8wLDdzaa6eXWLy_oPPIvqEUgcSTc3Xtlqvs6hOpHMFFd1cl4Xf6iY9Z_WhjINx8bC8DFzUHrv02qz07XVOyoXDA-0wpzU31UkWQtd6T2kYdtn6Nr3BcNGwrbHJonDtcGc-JttyP0eREN4fHNcT_yxc9pUodTh2rJaq-Dbgz4DVLXvgeksi-0iOtV2-IlKnCb9yJFPBQeQxSBrdtJYnOywtyLiLrwiHLH191mEJ1LlNA-MzNPRTd03tCcEujkciirLF3eerrx1kNAV1GG5Ugrm_0pMDaGJ5lI4yfVB6zR-V84g3KZ2N7BHg5b29pRFkKkaSSlpL3Z3SeBDiNVfFZgqU6TeVwBouwfAPlExngQ_IQ_XjGuNMWYDomtyqDFmOWE3YjJkqHNoYXJkX2lkzhWZ5FQ.YFV7DwINWyrwGwp9cGIz86nxpI0frDv393Tqc4ds_tY\"}" \
  'https://rcj-signal-bot.zeabur.app/v1/register/+84775553477'
  ```
### Step 2 — Verify with the code

```bash
curl -X POST "http://127.0.0.1:8081/v1/register/+84559854979/verify/"
```

Replace `123-456` with the code received via SMS or voice call.

## Send a Test Message

```bash
curl -X POST -H "Content-Type: application/json" \
  https://rcj-signal-bot.zeabur.app/v2/send \
  -d '{
    "message": "hello from signal-cli-rest-api",
    "number": "+84775553477",
    "recipients": ["+84906303607"]
  }'
```

If the API is on a different host or port, replace `http://127.0.0.1:8081` with the correct URL.

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
  "http://127.0.0.1:8081/v1/profiles/+84559854979"
```

### Name and About

```bash
curl -X PUT \
  -H "Content-Type: application/json" \
  -d '{
    "name": "rcj_bot",
    "about": "I am a bot"
  }' \
  "http://127.0.0.1:8081/v1/profiles/+84559854979"
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
  "http://127.0.0.1:8081/v1/profiles/+84559854979"
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
curl -X GET "http://127.0.0.1:8081/v1/receive/+84559854979"
```
```
curl -X GET "http://127.0.0.1:8081/v1/groups/+84559854979"
