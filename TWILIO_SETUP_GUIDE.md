# Twilio SMS Reminder Setup

## Overview

The tracker settings page now supports sending reminder text messages through Twilio. This guide explains how to configure a Twilio trial account, verify recipients, and set the required environment variables.

---

## 1. Create a Twilio Account

1. Go to [https://www.twilio.com/try-twilio](https://www.twilio.com/try-twilio) and sign up for a free trial.
2. Complete email and phone verification.
3. When prompted, choose **Programmable SMS** as your primary use case.

> **Trial limits:** Messages are free but carry the “Sent from your Twilio trial account” prefix and can be delivered only to verified numbers until you upgrade.

---

## 2. Get Your Credentials

Within the Twilio console:

1. Navigate to **Account Info**.
2. Copy the **Account SID** and **Auth Token**.
3. Click **Get a Trial Number** and assign a phone number to your project.

---

## 3. Verify Recipient Numbers (Trial Only)

Before you can message real alumni on the trial tier, you must verify each target number:

1. Go to **Phone Numbers → Manage → Verified caller IDs**.
2. Add the phone number (including country code) you want to test with.
3. Twilio will send a one-time verification code to confirm ownership.

---

## 4. Configure Environment Variables

Add the following keys to your `backend/.env` file. Replace each placeholder with your actual values:

```bash
# Twilio SMS configuration
TWILIO_SMS_ENABLED=true
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_FROM_NUMBER=+1XXXXXXXXXX
```

Restart the Django server after saving `.env` so the new settings take effect.

---

## 5. Install Dependencies

Ensure the `twilio` package is installed (already added to `backend/requirements.txt`). When deploying or updating, run:

```bash
pip install -r requirements.txt
```

---

## 6. Sending SMS Reminders

1. Open **Admin → Tracker → Settings**.
2. Select alumni who have not responded.
3. Click **“📱 Send via SMS”**.
4. Review the result dialog to confirm deliveries or identify numbers that need attention.

The backend automatically:
- Converts the HTML template to friendly plain text.
- Personalizes content using `[User's Name]`.
- Injects the tracker link for each recipient.

---

## 7. Common Issues & Tips

| Issue | Cause | Fix |
|-------|-------|-----|
| `Twilio SMS is disabled` | `TWILIO_SMS_ENABLED` not set to `true` | Update `.env` |
| `Missing or invalid phone number` | Number absent or not in international format | Update alumni profile (use `+63...` style) |
| `Error 21215` | Number not verified on trial | Add number under **Verified Caller IDs** |
| `Error 20003` | Invalid SID/Auth token | Double-check `.env` entries |
| Messages carry “Sent from your Twilio trial account” | Trial account limitation | Upgrade Twilio project when ready |

---

## 8. Ready for Production?

When you graduate from the trial:
- Upgrade your Twilio account.
- Register a branded sender ID or local phone number.
- Remove recipient verification limits.
- Optionally configure messaging services, opt-out keywords, and compliance features.

---

## Support

Questions? Reach out to the engineering team or consult Twilio’s SMS documentation: [https://www.twilio.com/docs/sms](https://www.twilio.com/docs/sms)








