"""
Django management command to run comprehensive messaging system tests.

Usage:
    python manage.py run_messaging_tests
    python manage.py run_messaging_tests --verbose
    python manage.py run_messaging_tests --report
    python manage.py run_messaging_tests --coverage
"""

import json
import os
from datetime import datetime
from django.core.management.base import BaseCommand, CommandError
from django.test.utils import get_runner
from django.conf import settings
from apps.messaging.tests.test_runner import MessagingTestRunner, generate_test_report


class Command(BaseCommand):
    help = 'Run comprehensive messaging system tests'

    def add_arguments(self, parser):
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Run tests in verbose mode',
        )
        parser.add_argument(
            '--report',
            action='store_true',
            help='Generate detailed test report',
        )
        parser.add_argument(
            '--coverage',
            action='store_true',
            help='Generate coverage report',
        )
        parser.add_argument(
            '--output',
            type=str,
            help='Output file for test report',
        )
        parser.add_argument(
            '--categories',
            nargs='+',
            choices=['websocket', 'security', 'performance', 'integration', 'all'],
            default=['all'],
            help='Test categories to run',
        )

    def handle(self, *args, **options):
        self.stdout.write('Running Messaging System Tests...')
        self.stdout.write('=' * 50)
        
        try:
            # Initialize test runner
            test_runner = MessagingTestRunner()
            
            # Run tests
            verbosity = 2 if options['verbose'] else 1
            results = test_runner.run_all_tests(verbosity=verbosity)
            
            # Check for errors
            if 'error' in results:
                raise CommandError(f'Test execution failed: {results["error"]}')
            
            # Display results
            self._display_results(results)
            
            # Generate report if requested
            if options['report']:
                self._generate_report(results, options['output'])
            
            # Generate coverage report if requested
            if options['coverage']:
                self._generate_coverage_report(results)
            
            # Exit with appropriate code
            if results['test_results']['failures'] > 0 or results['test_results']['errors'] > 0:
                raise CommandError('Some tests failed')
            
            self.stdout.write(
                self.style.SUCCESS('All tests passed successfully!')
            )
            
        except Exception as e:
            raise CommandError(f'Test execution failed: {e}')

    def _display_results(self, results):
        """Display test results."""
        test_results = results['test_results']
        performance = results['performance_metrics']
        summary = results['summary']
        
        # Display summary
        self.stdout.write('')
        self.stdout.write('Test Summary:')
        self.stdout.write('-' * 30)
        self.stdout.write(f'Overall Grade: {summary["overall_grade"]}')
        self.stdout.write(f'Total Tests: {summary["total_tests"]}')
        self.stdout.write(f'Successful: {summary["successful_tests"]}')
        self.stdout.write(f'Failed: {summary["failed_tests"]}')
        self.stdout.write(f'Errors: {summary["error_tests"]}')
        self.stdout.write(f'Success Rate: {summary["success_rate"]:.1%}')
        self.stdout.write('')
        
        # Display performance
        self.stdout.write('Performance:')
        self.stdout.write('-' * 30)
        self.stdout.write(f'Duration: {performance["total_duration"]:.2f}s')
        self.stdout.write(f'Tests/Second: {performance["tests_per_second"]:.1f}')
        self.stdout.write(f'Grade: {performance["performance_grade"]}')
        self.stdout.write('')
        
        # Display coverage
        coverage = results['coverage_analysis']
        self.stdout.write('Coverage:')
        self.stdout.write('-' * 30)
        self.stdout.write(f'Overall: {coverage["overall_coverage"]:.1%}')
        self.stdout.write(f'Line: {coverage["line_coverage"]:.1%}')
        self.stdout.write(f'Branch: {coverage["branch_coverage"]:.1%}')
        self.stdout.write(f'Function: {coverage["function_coverage"]:.1%}')
        self.stdout.write(f'Grade: {coverage["coverage_grade"]}')
        self.stdout.write('')
        
        # Display recommendations
        recommendations = summary['recommendations']
        if recommendations:
            self.stdout.write('Recommendations:')
            self.stdout.write('-' * 30)
            for rec in recommendations:
                self.stdout.write(f'• {rec}')
            self.stdout.write('')
        
        # Display failures if any
        if test_results['failures'] > 0:
            self.stdout.write(
                self.style.ERROR(f'Failures ({test_results["failures"]}):')
            )
            for failure in test_results['failure_details']:
                self.stdout.write(f'  {failure[0]}: {failure[1]}')
            self.stdout.write('')
        
        # Display errors if any
        if test_results['errors'] > 0:
            self.stdout.write(
                self.style.ERROR(f'Errors ({test_results["errors"]}):')
            )
            for error in test_results['error_details']:
                self.stdout.write(f'  {error[0]}: {error[1]}')
            self.stdout.write('')

    def _generate_report(self, results, output_file=None):
        """Generate detailed test report."""
        if not output_file:
            output_file = f'messaging_test_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        
        try:
            # Generate report
            report_content = generate_test_report(results, output_file)
            
            self.stdout.write(f'Test report generated: {output_file}')
            self.stdout.write(
                self.style.SUCCESS('Report generation completed successfully')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Failed to generate report: {e}')
            )

    def _generate_coverage_report(self, results):
        """Generate coverage report."""
        try:
            coverage = results['coverage_analysis']
            
            # Create coverage report file
            coverage_file = f'messaging_coverage_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
            
            with open(coverage_file, 'w') as f:
                f.write('Messaging System Coverage Report\n')
                f.write('=' * 50 + '\n\n')
                f.write(f'Generated: {datetime.now().isoformat()}\n\n')
                f.write(f'Overall Coverage: {coverage["overall_coverage"]:.1%}\n')
                f.write(f'Line Coverage: {coverage["line_coverage"]:.1%}\n')
                f.write(f'Branch Coverage: {coverage["branch_coverage"]:.1%}\n')
                f.write(f'Function Coverage: {coverage["function_coverage"]:.1%}\n')
                f.write(f'Grade: {coverage["coverage_grade"]}\n\n')
                
                if coverage['uncovered_lines']:
                    f.write('Uncovered Lines:\n')
                    f.write('-' * 30 + '\n')
                    for line in coverage['uncovered_lines']:
                        f.write(f'  {line}\n')
            
            self.stdout.write(f'Coverage report generated: {coverage_file}')
            self.stdout.write(
                self.style.SUCCESS('Coverage report generation completed successfully')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Failed to generate coverage report: {e}')
            )

















































