# Email Notifications Setup

This document explains how to set up email notifications for benchmark workflow completion and failures using the Resend API.

## Quick Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Get a Resend API key:**
   - Sign up at [Resend](https://resend.com)
   - Go to [API Keys](https://resend.com/api-keys)
   - Create a new API key

3. **Configure environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

4. **Verify your domain** (if using custom domain):
   - Follow [Resend domain verification](https://resend.com/docs/dashboard/domains/introduction)
   - Or use the default `onboarding@resend.dev` for testing

## Configuration

Set these environment variables:

| Variable | Required | Description |
|----------|----------|-------------|
| `RESEND_API_KEY` | Yes | Your Resend API key (notifications enable automatically when set) |
| `RESEND_FROM_EMAIL` | No | From email address (default: `benchmark@example.com`) |
| `RESEND_TO_EMAILS` | Yes* | Comma-separated recipient emails |

*Required so the notifier knows where to send messages

## Example Configuration

```bash
# Your Resend API key (automatically enables notifications)
RESEND_API_KEY=re_abcd1234...

# Verified from address
RESEND_FROM_EMAIL=benchmark@yourdomain.com

# Recipients (comma-separated)
RESEND_TO_EMAILS=admin@company.com,devops@company.com
```

## Testing Email Setup

Test your configuration before running benchmarks:

```bash
cd Benchmark
python3 -c "from notifications import EmailNotifier; EmailNotifier().send_test_email()"
```

Or run the notifications module directly:
```bash
python3 notifications.py
```

## Email Types

The system sends two types of emails:

### 1. Success Notifications ✅
Sent when benchmark workflow completes successfully:
- Total execution time
- Languages tested  
- Test suites executed
- Results summary table with metrics
- Timestamp

### 2. Failure Notifications ❌
Sent when workflow fails:
- Error message and details
- Context (language/test being executed)
- Elapsed time before failure
- Full error traceback
- Timestamp

## Troubleshooting

### "RESEND_API_KEY not set" Error
- Ensure environment variable is exported: `export RESEND_API_KEY=your_key`
- Check `.env` file exists and is properly formatted
- Verify the key is valid in your Resend dashboard

### "From address not verified" Error
- Verify your domain in Resend dashboard
- Use `onboarding@resend.dev` for testing
- Ensure `RESEND_FROM_EMAIL` matches verified address

### Emails Not Being Sent
- Ensure `RESEND_API_KEY` is exported in the shell where you run benchmarks
- Verify recipient emails in `RESEND_TO_EMAILS`
- Check Resend dashboard for delivery status
- Test with `python3 notifications.py`

### Rate Limiting
- Resend free tier: 100 emails/day, 3,000/month
- Monitor usage in Resend dashboard
- Consider upgrading plan for higher limits

## Security Notes

- Keep your API key secure and never commit it to version control
- Use environment variables or secure secret management
- The `.env.example` file shows the format but contains placeholder values
- Add `.env` to your `.gitignore` file

## Integration Details

The email notifications are integrated into:

1. **Main workflow** (`run.py`):
   - Success notification after all benchmarks complete
   - Failure notification on any error
   - Keyboard interrupt handling

2. **Benchmark failures**:
   - Language-specific failures
   - Manager connection issues
   - Missing dependencies
   - Plot generation errors

3. **Email content**:
   - HTML-formatted messages
   - Results summary table
   - Error details and context
   - Execution timing information

## Customization

To customize email templates, modify the methods in `notifications.py`:
- `send_completion_email()` - Success message format
- `send_failure_email()` - Error message format  
- `_format_results_summary()` - Results table HTML

Example custom notification:
```python
from notifications import EmailNotifier

notifier = EmailNotifier()
notifier.send_completion_email(
    duration=123.45,
    results={"java": {"prime": {"avg_latency": 45.2}}},
    languages=["java"],
    tests=["prime"]
)
```
