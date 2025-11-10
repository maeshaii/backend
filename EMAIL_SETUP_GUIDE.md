# Email Configuration Guide for Tracker Form Reminders

## Overview

The CTU Alumni Management System now supports sending tracker form reminders via email. This guide explains how to configure email functionality for your deployment.

---

## 📧 Features

- ✅ Send tracker form links directly to alumni email addresses
- ✅ Professional HTML email templates with CTU branding
- ✅ Personalized messages with user names
- ✅ Batch sending with detailed error reporting
- ✅ Automatic validation of email addresses
- ✅ Fallback for users without email addresses

---

## 🔧 Configuration Steps

### 1. Choose Your Email Provider

You can use any SMTP email service. Popular options:

#### **Gmail** (Recommended for development/small deployments)
- Free tier available
- Easy to set up
- Requires "App Password" (not your regular Gmail password)

#### **SendGrid** (Recommended for production)
- Professional email service
- Better deliverability
- Free tier: 100 emails/day

#### **AWS SES** (For large deployments)
- Scalable solution
- Very cost-effective for high volumes
- Requires AWS account

#### **Semaphore** (Popular in Philippines)
- Local email provider
- Good for Philippine deployments
- Competitive pricing

---

### 2. Set Up Environment Variables

Create or update your `.env` file in the `backend` directory:

#### For Gmail:

```bash
# Email Configuration (Gmail)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-16-character-app-password
```

**Important for Gmail:**
1. Enable 2-Step Verification in your Google Account
2. Generate an "App Password" at https://myaccount.google.com/apppasswords
3. Use the App Password (not your regular password) in `EMAIL_HOST_PASSWORD`

#### For SendGrid:

```bash
# Email Configuration (SendGrid)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.sendgrid.net
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=your-sendgrid-api-key
```

#### For AWS SES:

```bash
# Email Configuration (AWS SES)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=email-smtp.us-east-1.amazonaws.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-ses-smtp-username
EMAIL_HOST_PASSWORD=your-ses-smtp-password
```

#### For Other SMTP Providers:

```bash
# Email Configuration (Generic SMTP)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.your-provider.com
EMAIL_PORT=587  # or 465 for SSL
EMAIL_USE_TLS=True  # or False if using SSL
EMAIL_HOST_USER=your-username
EMAIL_HOST_PASSWORD=your-password
```

---

### 3. Test Your Configuration

#### Option 1: Using Django Shell

```bash
cd backend
python manage.py shell
```

Then run:

```python
from django.core.mail import send_mail
from django.conf import settings

send_mail(
    subject='Test Email from CTU Alumni System',
    message='This is a test email to verify configuration.',
    from_email=settings.EMAIL_HOST_USER,
    recipient_list=['your-test-email@example.com'],
    fail_silently=False,
)
```

#### Option 2: Using the Web Interface

1. Log in as an admin
2. Go to Tracker → Settings
3. Select a user (or yourself for testing)
4. Click "📧 Send via Email"
5. Check if the email arrives

---

## 🎨 Email Template

The system automatically formats emails with:

- **Professional HTML layout** with CTU colors
- **Personalized greeting** using the alumni's name
- **Clickable tracker form link** embedded in the message
- **Responsive design** that works on mobile and desktop
- **CTU branding** in the header
- **Footer disclaimer** indicating it's an automated message

### Example Email:

```
┌──────────────────────────────────────┐
│    CTU Alumni Tracker Form           │ (Blue header)
├──────────────────────────────────────┤
│                                       │
│  Hi John Doe,                        │
│                                       │
│  We hope you're doing well! This is  │
│  a gentle reminder to complete the   │
│  required Tracker Form...            │
│                                       │
│  👉 Fill Out the Tracker Form        │ (Clickable link)
│                                       │
│  Thank you!                          │
│  CCICT                               │
│                                       │
├──────────────────────────────────────┤
│  This is an automated message from   │ (Gray footer)
│  CTU CCICT Alumni Management System  │
│  Please do not reply to this email   │
└──────────────────────────────────────┘
```

---

## 📊 Usage Instructions

### For Administrators:

1. **Navigate to Tracker Settings**
   - Go to Admin Dashboard
   - Click on "Tracker" → "Settings"

2. **Select Recipients**
   - View the list of users who haven't responded
   - Use checkboxes to select specific users
   - Or click "Select All" to choose everyone

3. **Customize Message (Optional)**
   - Click "Edit" to modify the default message
   - Use `[User's Name]` placeholder for personalization
   - Use formatting buttons for styling

4. **Send Emails**
   - Click "📧 Send via Email" button
   - Confirm the action
   - View detailed results

### Understanding Results:

The system will show:
- ✅ **Successfully sent**: Emails delivered successfully
- ⚠️ **No email address**: Users without email in their profile
- ❌ **Failed**: Emails that failed to send (with error details)

---

## 🛠️ Troubleshooting

### Email Not Sending

**Problem**: No emails are being sent

**Solutions**:
1. Check that `.env` file exists in the `backend` directory
2. Verify all EMAIL_* variables are set correctly
3. Restart the Django server after changing `.env`
4. Check Django logs for error messages

### Gmail "Authentication Failed"

**Problem**: Gmail rejects the login

**Solutions**:
1. Ensure 2-Step Verification is enabled on your Google account
2. Use an App Password, not your regular Gmail password
3. App Password format: `xxxx xxxx xxxx xxxx` (remove spaces in .env file)
4. Check that "Less secure app access" is NOT being used (deprecated by Google)

### Emails Go to Spam

**Problem**: Recipients receive emails in spam folder

**Solutions**:
1. **For Development**: Acceptable, inform users to check spam
2. **For Production**:
   - Use a professional email service (SendGrid, AWS SES)
   - Set up SPF, DKIM, and DMARC records for your domain
   - Use a verified sending domain
   - Avoid spam trigger words in subject/content

### SSL/TLS Errors

**Problem**: Connection errors or certificate issues

**Solutions**:
1. For port 587: Set `EMAIL_USE_TLS=True`
2. For port 465: Set `EMAIL_USE_SSL=True` (requires code change)
3. Check if firewall is blocking the port
4. Try different port numbers supported by your provider

### Users Without Email

**Problem**: Many users don't have email addresses

**Solutions**:
1. Import email addresses from Excel during alumni import
2. Ask users to update their profiles
3. Use the tracker form to collect email addresses
4. Consider using the in-app notification system as backup

---

## 🔒 Security Best Practices

### For Production Deployments:

1. **Never commit `.env` file to Git**
   ```bash
   # Add to .gitignore
   echo ".env" >> .gitignore
   ```

2. **Use environment-specific settings**
   - Development: Gmail is acceptable
   - Production: Use professional services (SendGrid/SES)

3. **Rotate credentials regularly**
   - Change SMTP passwords every 3-6 months
   - Use separate credentials for different environments

4. **Monitor email sending**
   - Check Django logs regularly
   - Set up alerts for failed sends
   - Monitor your email provider's dashboard

5. **Rate limiting**
   - Most free tiers have daily limits
   - Batch large sends across multiple days
   - Consider upgrading for bulk sending

---

## 📝 Email Provider Limits

| Provider | Free Tier Limit | Cost After Limit |
|----------|----------------|------------------|
| Gmail | ~500/day | N/A (personal use) |
| SendGrid | 100/day | $19.95/month (40k emails) |
| AWS SES | 62,000/month (if within AWS) | $0.10 per 1000 emails |
| Semaphore | Varies | Contact provider |

**Tip**: For tracker reminders to ~1000 alumni, SendGrid or AWS SES recommended for production.

---

## 🧪 Development vs Production

### Development (.env):
```bash
# Use Gmail for testing
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=test-account@gmail.com
EMAIL_HOST_PASSWORD=test-app-password

# OR use console backend to see emails in console (no actual sending)
# EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
```

### Production (.env):
```bash
# Use professional service
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.sendgrid.net
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=SG.xxxxxxxxxxxxxxxxxxxx
```

---

## 💡 FAQ

**Q: Can I send to multiple alumni at once?**  
A: Yes! Select multiple users and click "Send via Email". The system sends individual personalized emails to each.

**Q: What happens if a user doesn't have an email?**  
A: The system will skip them and report it in the results. Use the "Send Form" button for in-app notifications instead.

**Q: Can I customize the email template?**  
A: Yes! Edit the message in the Tracker Settings page. The HTML template styling is in the backend code (`apps/api/views.py` → `send_email_reminder_view`).

**Q: How do I know if emails were sent successfully?**  
A: The system shows a detailed report after sending, including success count, failures, and users without emails.

**Q: Can I use my university's email server?**  
A: Yes! Contact your IT department for SMTP credentials and use them in the configuration.

**Q: Is there a sending limit?**  
A: Depends on your email provider. Check the "Email Provider Limits" table above.

---

## 📞 Support

For issues or questions:

1. Check the troubleshooting section above
2. Review Django server logs: `backend/logs/` or console output
3. Test with console backend first (no actual sending)
4. Ensure all environment variables are set correctly

---

## 🚀 Quick Start Checklist

- [ ] Choose an email provider (Gmail for testing recommended)
- [ ] Create/update `.env` file in `backend` directory
- [ ] Add all required EMAIL_* environment variables
- [ ] Generate App Password (if using Gmail)
- [ ] Restart Django server
- [ ] Test sending with Django shell or web interface
- [ ] Verify email arrives and looks correct
- [ ] Update alumni email addresses in database
- [ ] Ready to send tracker form reminders! 🎉

---

**Last Updated**: 2025-01-10  
**Version**: 1.0

