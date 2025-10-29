"""
Django management command to seed tracker questions from exported data.

This command reads the exported tracker_questions_seed.py file and creates
all the questions and categories in the database exactly as they were exported.

Usage:
    python manage.py seed_tracker_questions
    python manage.py seed_tracker_questions --noinput  # Skip confirmation
"""

from django.core.management.base import BaseCommand
import os
import sys


class Command(BaseCommand):
    help = 'Seed tracker questions from exported seed file'

    def add_arguments(self, parser):
        parser.add_argument(
            '--noinput',
            action='store_true',
            help='Skip confirmation prompt',
        )
        parser.add_argument(
            '--seed-file',
            type=str,
            default='apps/shared/management/commands/tracker_questions_seed.py',
            help='Path to seed file (relative to backend directory)',
        )

    def handle(self, *args, **options):
        noinput = options['noinput']
        seed_file = options['seed_file']

        # Get the backend directory
        backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        full_seed_path = os.path.join(backend_dir, seed_file)

        if not os.path.exists(full_seed_path):
            self.stdout.write(
                self.style.ERROR(
                    f'Seed file not found: {full_seed_path}\n'
                    f'Please run: python manage.py export_tracker_questions\n'
                    f'to generate the seed file first.'
                )
            )
            return

        # Import the seed function from the seed file
        try:
            # Add the backend directory to Python path temporarily
            sys.path.insert(0, backend_dir)
            
            # Import the module (handle both absolute and relative imports)
            import importlib.util
            spec = importlib.util.spec_from_file_location("tracker_questions_seed", full_seed_path)
            seed_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(seed_module)
            
            from apps.shared.models import Question, QuestionCategory
            
            # Check if questions already exist
            existing_questions = Question.objects.count()
            existing_categories = QuestionCategory.objects.count()
            
            if existing_questions > 0 or existing_categories > 0:
                self.stdout.write(
                    self.style.WARNING(
                        f'Found {existing_questions} existing questions and '
                        f'{existing_categories} existing categories.'
                    )
                )
                
                if not noinput:
                    response = input('Existing questions will be DELETED and replaced. Continue? (yes/no): ')
                    if response.lower() != 'yes':
                        self.stdout.write(self.style.ERROR('Aborted.'))
                        return
                
                # Delete existing data
                self.stdout.write('Deleting existing questions and categories...')
                Question.objects.all().delete()
                QuestionCategory.objects.all().delete()
                self.stdout.write(self.style.SUCCESS('Deleted existing data.'))

            # Call the seed function
            self.stdout.write('Seeding tracker questions from exported data...')
            
            try:
                categories, questions = seed_module.seed_tracker_questions(apps=None, schema_editor=None)
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'\n✅ Successfully created:\n'
                        f'   - {len(categories)} categories\n'
                        f'   - {len(questions)} questions'
                    )
                )
                
                # Show summary
                self.stdout.write('\n📋 Categories created:')
                for cat in categories:
                    q_count = cat.questions.count()
                    self.stdout.write(f'   • {cat.title} ({q_count} questions)')
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error seeding questions: {str(e)}')
                )
                import traceback
                self.stdout.write(self.style.ERROR(traceback.format_exc()))
                raise

        except ImportError as e:
            self.stdout.write(
                self.style.ERROR(
                    f'Failed to import seed file: {str(e)}\n'
                    f'Make sure the seed file exists and is valid Python.'
                )
            )
            raise
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Unexpected error: {str(e)}')
            )
            import traceback
            self.stdout.write(self.style.ERROR(traceback.format_exc()))
            raise
        finally:
            # Clean up path
            if backend_dir in sys.path:
                sys.path.remove(backend_dir)

