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
        self.from_email = os.environ.get('RESEND_FROM_EMAIL', 'onboarding@resend.dev')
        self.to_emails = [email.strip() for email in os.environ.get('RESEND_TO_EMAILS', 'me@lexo.cool').split(',') if email.strip()]
        self.enabled = bool(self.api_key)

        if self.enabled:
            resend.api_key = self.api_key
            print("Email notifications enabled automatically (RESEND_API_KEY detected). Recipients:", self.to_emails)
        else:
            print("Email notifications disabled: RESEND_API_KEY not set")
    
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
    
    def _format_metric(self, value: Any, decimals: int = 2, show_zero: bool = True) -> str:
        """Safely format numeric metrics, handling zeros and None values appropriately."""
        if value is None:
            return "—"

        # Accept ints/floats directly; try casting other types to float.
        if isinstance(value, (int, float)):
            if value == 0 and not show_zero:
                return "—"
            return f"{value:.{decimals}f}"

        try:
            numeric_value = float(value)  # type: ignore[arg-type]
            if numeric_value == 0 and not show_zero:
                return "—"
            return f"{numeric_value:.{decimals}f}"
        except (TypeError, ValueError):
            return "—"

    def _format_results_summary(self, results: Dict[str, Any]) -> str:
        """Format benchmark results into a modern HTML summary."""
        if not results:
            return """
            <div style="background: #f8f9fa; border-left: 4px solid #6c757d; padding: 1rem; margin: 1rem 0; border-radius: 0.375rem;">
                <p style="margin: 0; color: #6c757d;">📊 No detailed results available</p>
            </div>
            """
        
        # Extract results with proper field mapping
        table_rows = []
        for lang, lang_data in results.items():
            if isinstance(lang_data, dict):
                # Handle both nested results format and direct summary format
                tests_data = lang_data.get('summary', lang_data) if 'summary' in lang_data else lang_data
                
                for test_name, metrics in tests_data.items():
                    if isinstance(metrics, dict):
                        # Map field names correctly
                        avg_latency = metrics.get('latency_avg') or metrics.get('avg_latency')
                        p99_latency = metrics.get('latency_p99') or metrics.get('p99_latency')
                        throughput = metrics.get('throughput')
                        memory = metrics.get('avg_memory_mb') or metrics.get('memory_mb')
                        
                        # Determine if test has meaningful results
                        has_results = any(v and v > 0 for v in [avg_latency, p99_latency, throughput])
                        
                        # Format row with conditional styling
                        row_class = "" if has_results else "opacity: 0.6;"
                        status_emoji = "✅" if has_results else "⚠️"
                        
                        table_rows.append(f"""
                        <tr style="{row_class}">
                            <td style="padding: 12px 16px; border-bottom: 1px solid #e9ecef;">
                                <span style="display: inline-flex; align-items: center; gap: 8px;">
                                    {status_emoji}
                                    <strong style="color: #495057;">{lang.title()}</strong>
                                </span>
                            </td>
                            <td style="padding: 12px 16px; border-bottom: 1px solid #e9ecef; color: #6c757d;">
                                <code style="background: #f8f9fa; padding: 2px 6px; border-radius: 3px; font-size: 0.875em;">{test_name}</code>
                            </td>
                            <td style="padding: 12px 16px; border-bottom: 1px solid #e9ecef; text-align: right; font-family: monospace;">
                                {self._format_metric(avg_latency, show_zero=False) if avg_latency != 0 else '—'}
                            </td>
                            <td style="padding: 12px 16px; border-bottom: 1px solid #e9ecef; text-align: right; font-family: monospace;">
                                {self._format_metric(p99_latency, show_zero=False) if p99_latency != 0 else '—'}
                            </td>
                            <td style="padding: 12px 16px; border-bottom: 1px solid #e9ecef; text-align: right; font-family: monospace;">
                                {self._format_metric(throughput, 0, show_zero=False) if throughput != 0 else '—'}
                            </td>
                            <td style="padding: 12px 16px; border-bottom: 1px solid #e9ecef; text-align: right; font-family: monospace;">
                                {self._format_metric(memory, 1, show_zero=False) if memory and memory != 0 else '—'}
                            </td>
                        </tr>
                        """)
        
        if not table_rows:
            return """
            <div style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 1rem; margin: 1rem 0; border-radius: 0.375rem;">
                <p style="margin: 0; color: #856404;">⚠️ No valid benchmark results found</p>
            </div>
            """
        
        return f"""
        <div style="margin: 1.5rem 0;">
            <h3 style="color: #343a40; margin-bottom: 1rem; display: flex; align-items: center; gap: 8px;">
                📊 Benchmark Results Summary
            </h3>
            <div style="overflow-x: auto; border-radius: 0.5rem; border: 1px solid #dee2e6; background: white;">
                <table style="width: 100%; border-collapse: collapse; font-size: 0.875rem;">
                    <thead>
                        <tr style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white;">
                            <th style="padding: 16px; text-align: left; font-weight: 600;">Language</th>
                            <th style="padding: 16px; text-align: left; font-weight: 600;">Test Suite</th>
                            <th style="padding: 16px; text-align: right; font-weight: 600;">Avg Latency<br><small style="opacity: 0.8;">(ms)</small></th>
                            <th style="padding: 16px; text-align: right; font-weight: 600;">P99 Latency<br><small style="opacity: 0.8;">(ms)</small></th>
                            <th style="padding: 16px; text-align: right; font-weight: 600;">Throughput<br><small style="opacity: 0.8;">(req/s)</small></th>
                            <th style="padding: 16px; text-align: right; font-weight: 600;">Memory<br><small style="opacity: 0.8;">(MB)</small></th>
                        </tr>
                    </thead>
                    <tbody style="background: white;">
                        {''.join(table_rows)}
                    </tbody>
                </table>
            </div>
            <div style="margin-top: 0.75rem; padding: 0.5rem; background: #f8f9fa; border-radius: 0.25rem; font-size: 0.75rem; color: #6c757d;">
                ✅ Test completed successfully &nbsp;•&nbsp; ⚠️ Test failed or produced no results &nbsp;•&nbsp; — No data available
            </div>
        </div>
        """
    
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
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Benchmark Completed</title>
            </head>
            <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 20px; background-color: #f8f9fa;">
                
                <div style="background: white; border-radius: 12px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1); overflow: hidden; margin-bottom: 20px;">
                    <!-- Header -->
                    <div style="background: linear-gradient(135deg, #28a745 0%, #20c997 100%); padding: 2rem; text-align: center;">
                        <h1 style="color: white; margin: 0; font-size: 1.75rem; font-weight: 700;">
                            ✅ Benchmark Completed Successfully
                        </h1>
                        <p style="color: rgba(255, 255, 255, 0.9); margin: 0.5rem 0 0 0; font-size: 1rem;">
                            Workflow finished at {timestamp}
                        </p>
                    </div>
                    
                    <!-- Summary Cards -->
                    <div style="padding: 2rem;">
                        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem;">
                            
                            <div style="background: #f8f9fa; border: 1px solid #e9ecef; border-radius: 8px; padding: 1.25rem; text-align: center;">
                                <div style="font-size: 2rem; margin-bottom: 0.5rem;">⏱️</div>
                                <div style="font-size: 1.5rem; font-weight: 700; color: #495057; margin-bottom: 0.25rem;">{duration_str}</div>
                                <div style="font-size: 0.875rem; color: #6c757d;">Total Duration</div>
                            </div>
                            
                            <div style="background: #f8f9fa; border: 1px solid #e9ecef; border-radius: 8px; padding: 1.25rem; text-align: center;">
                                <div style="font-size: 2rem; margin-bottom: 0.5rem;">🔧</div>
                                <div style="font-size: 1.25rem; font-weight: 700; color: #495057; margin-bottom: 0.25rem;">{languages_str}</div>
                                <div style="font-size: 0.875rem; color: #6c757d;">Languages Tested</div>
                            </div>
                            
                            <div style="background: #f8f9fa; border: 1px solid #e9ecef; border-radius: 8px; padding: 1.25rem; text-align: center;">
                                <div style="font-size: 2rem; margin-bottom: 0.5rem;">🧪</div>
                                <div style="font-size: 1.25rem; font-weight: 700; color: #495057; margin-bottom: 0.25rem;">{tests_str}</div>
                                <div style="font-size: 0.875rem; color: #6c757d;">Test Suites</div>
                            </div>
                            
                        </div>
                        
                        {self._format_results_summary(results) if results else ''}
                        
                        <div style="background: #e7f3ff; border-left: 4px solid #007bff; padding: 1rem; margin-top: 1.5rem; border-radius: 0.375rem;">
                            <p style="margin: 0; color: #004085; font-size: 0.875rem;">
                                💾 <strong>Results saved:</strong> All benchmark data has been saved to the results directory for further analysis.
                            </p>
                        </div>
                        
                    </div>
                </div>
                
                <!-- Footer -->
                <div style="text-align: center; color: #6c757d; font-size: 0.75rem; margin-top: 1rem;">
                    <p style="margin: 0;">Generated by Benchmark Workflow System</p>
                </div>
                
            </body>
            </html>
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
                context_info.append(f"🔧 <strong>Language:</strong> {language}")
            if test:
                context_info.append(f"🧪 <strong>Test Suite:</strong> {test}")
            if duration is not None:
                context_info.append(f"⏱️ <strong>Elapsed Time:</strong> {self._format_duration(duration)}")
            
            context_html = ""
            if context_info:
                context_html = f"""
                <div style="background: #f8f9fa; border: 1px solid #e9ecef; border-radius: 8px; padding: 1.25rem; margin-bottom: 1.5rem;">
                    <h3 style="color: #495057; margin: 0 0 0.75rem 0; font-size: 1rem;">Execution Context</h3>
                    {'<br>'.join(f'<div style="margin: 0.25rem 0; color: #6c757d;">{info}</div>' for info in context_info)}
                </div>
                """
            
            error_details_html = ""
            if error_details:
                error_details_html = f"""
                <div style="background: #f8f9fa; border: 1px solid #e9ecef; border-radius: 8px; padding: 1.25rem; margin-bottom: 1.5rem;">
                    <h3 style="color: #495057; margin: 0 0 0.75rem 0; font-size: 1rem;">Stack Trace</h3>
                    <pre style="background: #ffffff; border: 1px solid #dee2e6; padding: 1rem; border-radius: 6px; overflow-x: auto; margin: 0; font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace; font-size: 0.8rem; color: #495057; white-space: pre-wrap; word-break: break-all;">{error_details}</pre>
                </div>
                """
            
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Benchmark Failed</title>
            </head>
            <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 20px; background-color: #f8f9fa;">
                
                <div style="background: white; border-radius: 12px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1); overflow: hidden; margin-bottom: 20px;">
                    <!-- Header -->
                    <div style="background: linear-gradient(135deg, #dc3545 0%, #c82333 100%); padding: 2rem; text-align: center;">
                        <h1 style="color: white; margin: 0; font-size: 1.75rem; font-weight: 700;">
                            ❌ Benchmark Workflow Failed
                        </h1>
                        <p style="color: rgba(255, 255, 255, 0.9); margin: 0.5rem 0 0 0; font-size: 1rem;">
                            Failure occurred at {timestamp}
                        </p>
                    </div>
                    
                    <!-- Error Content -->
                    <div style="padding: 2rem;">
                        
                        <!-- Error Message -->
                        <div style="background: #f8d7da; border: 1px solid #f5c6cb; border-radius: 8px; padding: 1.25rem; margin-bottom: 1.5rem;">
                            <h3 style="color: #721c24; margin: 0 0 0.5rem 0; font-size: 1.125rem;">Error Details</h3>
                            <p style="margin: 0; color: #721c24; font-weight: 500;">{error_message}</p>
                        </div>
                        
                        {context_html}
                        
                        {error_details_html}
                        
                        <div style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 1rem; margin-top: 1.5rem; border-radius: 0.375rem;">
                            <p style="margin: 0; color: #856404; font-size: 0.875rem;">
                                🔍 <strong>Next steps:</strong> Please check the benchmark logs for more detailed information about this failure.
                            </p>
                        </div>
                        
                    </div>
                </div>
                
                <!-- Footer -->
                <div style="text-align: center; color: #6c757d; font-size: 0.75rem; margin-top: 1rem;">
                    <p style="margin: 0;">Generated by Benchmark Workflow System</p>
                </div>
                
            </body>
            </html>
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
                "subject": f"🧪 Test Email - Benchmark Notifications - {timestamp}",
                "html": f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="utf-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>Test Email</title>
                </head>
                <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 20px; background-color: #f8f9fa;">
                    
                    <div style="background: white; border-radius: 12px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1); overflow: hidden; margin-bottom: 20px;">
                        <!-- Header -->
                        <div style="background: linear-gradient(135deg, #6f42c1 0%, #e83e8c 100%); padding: 2rem; text-align: center;">
                            <h1 style="color: white; margin: 0; font-size: 1.75rem; font-weight: 700;">
                                🧪 Test Email
                            </h1>
                            <p style="color: rgba(255, 255, 255, 0.9); margin: 0.5rem 0 0 0; font-size: 1rem;">
                                Email notification system test
                            </p>
                        </div>
                        
                        <!-- Content -->
                        <div style="padding: 2rem;">
                            <div style="background: #d1ecf1; border-left: 4px solid #17a2b8; padding: 1rem; margin-bottom: 1.5rem; border-radius: 0.375rem;">
                                <p style="margin: 0; color: #0c5460;">
                                    ✅ <strong>Success!</strong> This test email confirms that your benchmark notification system is working correctly.
                                </p>
                            </div>
                            
                            <h3 style="color: #343a40; margin-bottom: 1rem;">Configuration Details</h3>
                            <div style="background: #f8f9fa; border: 1px solid #e9ecef; border-radius: 8px; padding: 1.25rem;">
                                <div style="margin-bottom: 0.75rem;">
                                    <strong style="color: #495057;">📧 From:</strong> 
                                    <code style="background: #e9ecef; padding: 2px 6px; border-radius: 3px; margin-left: 8px;">{self.from_email}</code>
                                </div>
                                <div style="margin-bottom: 0.75rem;">
                                    <strong style="color: #495057;">📨 To:</strong> 
                                    <code style="background: #e9ecef; padding: 2px 6px; border-radius: 3px; margin-left: 8px;">{', '.join(self.to_emails)}</code>
                                </div>
                                <div style="margin-bottom: 0.75rem;">
                                    <strong style="color: #495057;">⚙️ Status:</strong> 
                                    <span style="background: #d4edda; color: #155724; padding: 2px 8px; border-radius: 12px; font-size: 0.875rem; margin-left: 8px;">
                                        {"✅ Enabled" if self.enabled else "❌ Disabled"}
                                    </span>
                                </div>
                                <div>
                                    <strong style="color: #495057;">📅 Timestamp:</strong> 
                                    <code style="background: #e9ecef; padding: 2px 6px; border-radius: 3px; margin-left: 8px;">{timestamp}</code>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Footer -->
                    <div style="text-align: center; color: #6c757d; font-size: 0.75rem; margin-top: 1rem;">
                        <p style="margin: 0;">Generated by Benchmark Workflow System</p>
                    </div>
                    
                </body>
                </html>
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
