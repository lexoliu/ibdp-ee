#!/usr/bin/env python3
"""Test script for email notifications functionality."""

import os
import sys
from notifications import EmailNotifier

def test_configuration():
    """Test email notification configuration."""
    print("=== Email Notification Configuration Test ===")
    
    notifier = EmailNotifier()
    
    print(f"Notifications enabled: {notifier.enabled}")
    print(f"API key configured: {'✅' if notifier.api_key else '❌'}")
    print(f"From email: {notifier.from_email}")
    print(f"To emails: {notifier.to_emails}")
    
    if not notifier.enabled:
        print("\n⚠️  Email notifications are disabled.")
        print("Set RESEND_API_KEY in your environment to enable them automatically.")
        return False
    
    if not notifier.api_key:
        print("\n❌ RESEND_API_KEY not configured.")
        print("Please set your Resend API key in environment variables.")
        return False
    
    if not notifier.to_emails or notifier.to_emails == ['']:
        print("\n❌ RESEND_TO_EMAILS not configured.")
        print("Please set recipient email addresses.")
        return False
    
    print("\n✅ Configuration looks good!")
    return True

def test_completion_email():
    """Test sending a completion email."""
    print("\n=== Testing Completion Email ===")
    
    notifier = EmailNotifier()
    
    # Sample results data
    sample_results = {
        "java": {
            "prime": {
                "latency_p50": 45.2,
                "latency_p99": 89.5,
                "throughput": 1250.3,
                "avg_memory_mb": 512.8
            },
            "light": {
                "latency_p50": 12.1,
                "latency_p99": 25.4,
                "throughput": 2100.7,
                "avg_memory_mb": 485.2
            }
        },
        "go": {
            "prime": {
                "latency_p50": 38.7,
                "latency_p99": 72.1,
                "throughput": 1480.5,
                "avg_memory_mb": 128.4
            }
        }
    }
    
    success = notifier.send_completion_email(
        duration=187.5,  # ~3 minutes
        results=sample_results,
        languages=["java", "go"],
        tests=["prime", "light"],
        mode="normal"  # Test with normal mode
    )
    
    if success:
        print("✅ Completion email sent successfully!")
    else:
        print("❌ Failed to send completion email.")
    
    return success

def test_failure_email():
    """Test sending a failure email."""
    print("\n=== Testing Failure Email ===")
    
    notifier = EmailNotifier()
    
    success = notifier.send_failure_email(
        error_message="Service failed to start",
        error_details="Could not bind to port 8080: Address already in use\n\nTraceback:\n  File 'run.py', line 327\n    RuntimeError: Port unavailable",
        language="rust",
        test="prime",
        duration=23.4
    )
    
    if success:
        print("✅ Failure email sent successfully!")
    else:
        print("❌ Failed to send failure email.")
    
    return success

def main():
    """Run all email notification tests."""
    print("🧪 Email Notification Test Suite")
    print("=" * 50)
    
    # Test configuration
    config_ok = test_configuration()
    
    if not config_ok:
        print("\n❌ Configuration issues detected. Please fix them before testing emails.")
        sys.exit(1)
    
    # Ask user if they want to send test emails
    response = input("\n📧 Send test emails? This will actually send emails to configured recipients. (y/N): ")
    
    if response.lower() != 'y':
        print("Skipping email sending tests.")
        return
    
    print("\n🚀 Sending test emails...")
    
    # Test completion email
    completion_ok = test_completion_email()
    
    # Test failure email  
    failure_ok = test_failure_email()
    
    # Summary
    print(f"\n📊 Test Results:")
    print(f"Configuration: {'✅' if config_ok else '❌'}")
    print(f"Completion email: {'✅' if completion_ok else '❌'}")
    print(f"Failure email: {'✅' if failure_ok else '❌'}")
    
    if completion_ok and failure_ok:
        print("\n🎉 All tests passed! Email notifications are working correctly.")
    else:
        print("\n⚠️  Some tests failed. Check your configuration and Resend dashboard.")

if __name__ == "__main__":
    main()
