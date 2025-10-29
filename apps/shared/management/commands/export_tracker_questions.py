"""
Django management command to export tracker questions from the database.

This command reads all QuestionCategory and Question objects from the database
and generates a Python seed file that can be used to recreate the exact same
questions on another database.

Usage:
    python manage.py export_tracker_questions

The generated file will be saved as:
    backend/apps/shared/management/commands/tracker_questions_seed.py
"""

from django.core.management.base import BaseCommand
from apps.shared.models import QuestionCategory, Question
import json
from datetime import datetime
import os


class Command(BaseCommand):
    help = 'Export tracker questions from database to a seed file'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            type=str,
            default='apps/shared/management/commands/tracker_questions_seed.py',
            help='Output file path (relative to backend directory)',
        )
        parser.add_argument(
            '--overwrite',
            action='store_true',
            help='Overwrite existing seed file without confirmation',
        )

    def _format_categories_data(self, categories_data):
        """Format categories data as a Python literal string"""
        lines = ['[']
        for cat_idx, cat in enumerate(categories_data):
            lines.append('        {')
            lines.append(f"            'title': {repr(cat['title'])},",)
            
            # Format description with proper escaping
            lines.append(f"            'description': {repr(cat['description'])},",)
            
            lines.append(f"            'order': {cat['order']},")
            lines.append("            'questions': [")
            
            for q_idx, q in enumerate(cat['questions']):
                lines.append('                {')
                lines.append(f"                    'text': {repr(q['text'])},",)
                lines.append(f"                    'type': {repr(q['type'])},",)
                
                # Format options properly using JSON for lists
                if q['options']:
                    options_str = json.dumps(q['options'], ensure_ascii=False)
                    lines.append(f"                    'options': {options_str},")
                else:
                    lines.append("                    'options': [],",)
                
                lines.append(f"                    'required': {q['required']},",)
                lines.append(f"                    'order': {q['order']},")
                lines.append('                }' + (',' if q_idx < len(cat['questions']) - 1 else ''))
            
            lines.append("            ]")
            lines.append('        }' + (',' if cat_idx < len(categories_data) - 1 else ''))
        
        lines.append('    ]')
        return '\n'.join(lines)

    def handle(self, *args, **options):
        output_path = options['output']
        overwrite = options['overwrite']

        # Get all categories with their questions, ordered properly
        categories = QuestionCategory.objects.prefetch_related('questions').order_by('order', 'id')
        
        if not categories.exists():
            self.stdout.write(
                self.style.WARNING('No categories found in the database.')
            )
            return

        # Build the data structure
        categories_data = []
        total_questions = 0

        for category in categories:
            questions = category.questions.all().order_by('order', 'id')
            
            questions_data = []
            for question in questions:
                # Handle options - convert to list if it's a string or None
                options = question.options
                if options is None:
                    options = []
                elif isinstance(options, str):
                    try:
                        options = json.loads(options)
                    except (ValueError, TypeError):
                        options = [options]
                elif not isinstance(options, list):
                    options = list(options) if options else []

                questions_data.append({
                    'text': question.text,
                    'type': question.type,
                    'options': options,
                    'required': question.required,
                    'order': question.order,
                })
                total_questions += 1

            categories_data.append({
                'title': category.title,
                'description': category.description or '',
                'order': category.order,
                'questions': questions_data,
            })

        # Generate the Python file content
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        formatted_data = self._format_categories_data(categories_data)
        
        file_content = f'''"""
Auto-generated tracker questions seed file.
Generated on: {timestamp}

This file contains the exact questions from the database.
DO NOT EDIT THIS FILE MANUALLY - it will be overwritten when you run:
    python manage.py export_tracker_questions

To use this file to seed questions in a new database, run:
    python manage.py seed_tracker_questions
"""

from apps.shared.models import QuestionCategory, Question


# Categories and questions exported from database
CATEGORIES_DATA = {formatted_data}


def seed_tracker_questions(apps=None, schema_editor=None):
    """
    Seed tracker questions from exported data.
    Can be used as a migration function or standalone.
    
    Returns:
        tuple: (list of created categories, list of created questions)
    """
    if apps:
        # Running as a migration
        QuestionCategory = apps.get_model('shared', 'QuestionCategory')
        Question = apps.get_model('shared', 'Question')
        use_migration_mode = True
    else:
        # Running standalone
        from apps.shared.models import QuestionCategory, Question
        use_migration_mode = False

    # Delete existing questions and categories to ensure clean state
    if not use_migration_mode:
        Question.objects.all().delete()
        QuestionCategory.objects.all().delete()

    created_categories = []
    created_questions = []

    for cat_data in CATEGORIES_DATA:
        # Create category
        category = QuestionCategory.objects.create(
            title=cat_data['title'],
            description=cat_data['description'],
            order=cat_data.get('order', 0)
        )
        created_categories.append(category)

        # Create questions for this category
        for q_data in cat_data['questions']:
            question = Question.objects.create(
                category=category,
                text=q_data['text'],
                type=q_data['type'],
                options=q_data['options'] if q_data['options'] else None,
                required=q_data.get('required', False),
                order=q_data.get('order', 0)
            )
            created_questions.append(question)

    return created_categories, created_questions


def unseed_tracker_questions(apps, schema_editor):
    """Remove all tracker questions (for migration rollback)"""
    QuestionCategory = apps.get_model('shared', 'QuestionCategory')
    QuestionCategory.objects.all().delete()

'''

        # Construct absolute path
        backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        full_output_path = os.path.join(backend_dir, output_path)
        
        # Check if file exists
        if os.path.exists(full_output_path) and not overwrite:
            response = input(f'File {full_output_path} already exists. Overwrite? (yes/no): ')
            if response.lower() != 'yes':
                self.stdout.write(self.style.ERROR('Aborted.'))
                return

        # Ensure directory exists
        os.makedirs(os.path.dirname(full_output_path), exist_ok=True)

        # Write file
        with open(full_output_path, 'w', encoding='utf-8') as f:
            f.write(file_content)

        self.stdout.write(
            self.style.SUCCESS(
                f'\n✅ Successfully exported:\n'
                f'   - {len(categories_data)} categories\n'
                f'   - {total_questions} questions\n'
                f'   To: {full_output_path}'
            )
        )
        self.stdout.write(
            f'\n📝 To seed these questions in another database, run:\n'
            f'   python manage.py seed_tracker_questions'
        )
