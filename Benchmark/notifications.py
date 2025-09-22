"""Email notification module using Resend API for benchmark workflow notifications."""

import os
import json
import traceback
from datetime import datetime
from typing import Dict, List, Optional, Any
import resend


class EmailNotifier:
    """Handles email notifications for benchmark workflows using Resend API."""
    
    def __init__(self):
        """Initialize the email notifier with Resend API configuration."""
        self.api_key = os.environ.get('RESEND_API_KEY')
        self.from_email = os.environ.get('RESEND_FROM_EMAIL', 'benchmark@example.com')
        self.to_emails = os.environ.get('RESEND_TO_EMAILS', '').split(',')
        self.enabled = os.environ.get('EMAIL_NOTIFICATIONS', 'false').lower() == 'true'
        
        if self.enabled and self.api_key:
            resend.api_key = self.api_key
        elif self.enabled:
            print("Warning: Email notifications enabled but RESEND_API_KEY not set")
            self.enabled = False
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration in seconds to human-readable string."""
        if seconds < 60:
            return f"{seconds:.1f} seconds"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f} minutes"
        else:
            hours = seconds / 3600
            return f"{hours:.1f} hours"
    
    def _format_results_summary(self, results: Dict[str, Any]) -> str:
        """Format benchmark results into an HTML summary."""
        if not results:
            return "<p>No results available</p>"
        
        html = """
        <h3>Benchmark Results Summary</h3>
        <table style="border-collapse: collapse; width: 100%;">
            <thead>
                <tr style="background-color: #f2f2f2;">
                    <th style="border: 1px solid #ddd; padding: 8px;">Language</th>
                    <th style="border: 1px solid #ddd; padding: 8px;">Test</th>
                    <th style="border: 1px solid #ddd; padding: 8px;">Avg Latency (ms)</th>
                    <th style="border: 1px solid #ddd; padding: 8px;">P99 Latency (ms)</th>
                    <th style="border: 1px solid #ddd; padding: 8px;">Throughput (req/s)</th>
                    <th style="border: 1px solid #ddd; padding: 8px;">Avg Memory (MB)</th>
                </tr>
            </thead>
            <tbody>
        """
        
        for lang, tests in results.items():
            if isinstance(tests, dict):
                for test_name, metrics in tests.items():
                    if isinstance(metrics, dict):
                        html += f"""
                        <tr>
                            <td style="border: 1px solid #ddd; padding: 8px;">{lang}</td>
                            <td style="border: 1px solid #ddd; padding: 8px;">{test_name}</td>
                            <td style="border: 1px solid #ddd; padding: 8px;">{metrics.get('avg_latency', 'N/A'):.2f}</td>
                            <td style="border: 1px solid #ddd; padding: 8px;">{metrics.get('p99_latency', 'N/A'):.2f}</td>
                            <td style="border: 1px solid #ddd; padding: 8px;">{metrics.get('throughput', 'N/A'):.2f}</td>
                            <td style="border: 1px solid #ddd; padding: 8px;">{metrics.get('avg_memory_mb', 'N/A'):.2f}</td>
                        </tr>
                        """
        
        html += """
            </tbody>
        </table>
        """
        return html
    
    def send_completion_email(self, 
                            duration: float,
                            results: Optional[Dict[str, Any]] = None,
                            languages: Optional[List[str]] = None,
                            tests: Optional[List[str]] = None) -> bool:
        """Send email notification for successful workflow completion.
        
        Args:
            duration: Total execution time in seconds
            results: Dictionary containing benchmark results
            languages: List of languages tested
            tests: List of test suites executed
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        if not self.enabled or not self.to_emails:
            return False
        
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            duration_str = self._format_duration(duration)
            
            languages_str = ', '.join(languages) if languages else 'N/A'
            tests_str = ', '.join(tests) if tests else 'N/A'
            
            html_content = f"""
            <h2>✅ Benchmark Workflow Completed Successfully</h2>
            
            <p><strong>Timestamp:</strong> {timestamp}</p>
            <p><strong>Total Duration:</strong> {duration_str}</p>
            <p><strong>Languages Tested:</strong> {languages_str}</p>
            <p><strong>Test Suites:</strong> {tests_str}</p>
            
            {self._format_results_summary(results) if results else ''}
            
            <p style="margin-top: 20px; color: #666;">
            Results have been saved to the benchmark results directory.
            </p>
            """
            
            params = {
                "from": self.from_email,
                "to": self.to_emails,
                "subject": f"✅ Benchmark Completed - {timestamp}",
                "html": html_content
            }
            
            response = resend.Emails.send(params)
            print(f"Completion email sent successfully: {response}")
            return True
            
        except Exception as e:
            print(f"Failed to send completion email: {e}")
            return False
    
    def send_failure_email(self,
                          error_message: str,
                          error_details: Optional[str] = None,
                          language: Optional[str] = None,
                          test: Optional[str] = None,
                          duration: Optional[float] = None) -> bool:
        """Send email notification for workflow failure.
        
        Args:
            error_message: Main error message
            error_details: Detailed error information (e.g., traceback)
            language: Language being tested when failure occurred
            test: Test suite being executed when failure occurred
            duration: Elapsed time before failure (seconds)
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        if not self.enabled or not self.to_emails:
            return False
        
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            context_info = []
            if language:
                context_info.append(f"<strong>Language:</strong> {language}")
            if test:
                context_info.append(f"<strong>Test Suite:</strong> {test}")
            if duration is not None:
                context_info.append(f"<strong>Elapsed Time:</strong> {self._format_duration(duration)}")
            
            context_html = "<p>" + "<br>".join(context_info) + "</p>" if context_info else ""
            
            error_details_html = ""
            if error_details:
                error_details_html = f"""
                <h3>Error Details</h3>
                <pre style="background-color: #f5f5f5; padding: 10px; border-radius: 5px; overflow-x: auto;">
{error_details}
                </pre>
                """
            
            html_content = f"""
            <h2>❌ Benchmark Workflow Failed</h2>
            
            <p><strong>Timestamp:</strong> {timestamp}</p>
            <p><strong>Error:</strong> {error_message}</p>
            
            {context_html}
            
            {error_details_html}
            
            <p style="margin-top: 20px; color: #666;">
            Please check the benchmark logs for more information.
            </p>
            """
            
            params = {
                "from": self.from_email,
                "to": self.to_emails,
                "subject": f"❌ Benchmark Failed - {timestamp}",
                "html": html_content
            }
            
            response = resend.Emails.send(params)
            print(f"Failure email sent successfully: {response}")
            return True
            
        except Exception as e:
            print(f"Failed to send failure email: {e}")
            return False
    
    def send_test_email(self) -> bool:
        """Send a test email to verify configuration.
        
        Returns:
            bool: True if test email sent successfully, False otherwise
        """
        if not self.api_key:
            print("Error: RESEND_API_KEY not set")
            return False
        
        if not self.to_emails:
            print("Error: RESEND_TO_EMAILS not set")
            return False
        
        try:
            resend.api_key = self.api_key
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            params = {
                "from": self.from_email,
                "to": self.to_emails,
                "subject": f"Test Email - Benchmark Notifications - {timestamp}",
                "html": f"""
                <h2>Test Email</h2>
                <p>This is a test email from the benchmark notification system.</p>
                <p><strong>Timestamp:</strong> {timestamp}</p>
                <p><strong>Configuration:</strong></p>
                <ul>
                    <li>From: {self.from_email}</li>
                    <li>To: {', '.join(self.to_emails)}</li>
                    <li>Notifications Enabled: {self.enabled}</li>
                </ul>
                """
            }
            
            response = resend.Emails.send(params)
            print(f"Test email sent successfully: {response}")
            return True
            
        except Exception as e:
            print(f"Failed to send test email: {e}")
            traceback.print_exc()
            return False


if __name__ == "__main__":
    notifier = EmailNotifier()
    
    print("Testing email configuration...")
    print(f"Enabled: {notifier.enabled}")
    print(f"From: {notifier.from_email}")
    print(f"To: {notifier.to_emails}")
    
    if input("\nSend test email? (y/n): ").lower() == 'y':
        notifier.send_test_email()