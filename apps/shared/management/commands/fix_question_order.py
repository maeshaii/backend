from django.core.management.base import BaseCommand
from apps.shared.models import QuestionCategory, Question

class Command(BaseCommand):
    help = 'Fix ordering for all existing questions'

    def handle(self, *args, **options):
        self.stdout.write("Fixing question ordering...")
        
        total_updated = 0
        
        # Get all categories ordered by their order field
        categories = QuestionCategory.objects.all().order_by('order')
        
        for category in categories:
            self.stdout.write(f"\nProcessing category: {category.title}")
            
            # Get all questions for this category, ordered by ID (creation order)
            questions = Question.objects.filter(category=category).order_by('id')
            
            if not questions.exists():
                self.stdout.write(f"   No questions found in category '{category.title}'")
                continue
                
            # Set order values starting from 0
            for index, question in enumerate(questions):
                old_order = question.order
                question.order = index
                question.save()
                
                self.stdout.write(f"   Question {question.id}: '{question.text[:50]}...' - Order: {old_order} -> {index}")
                total_updated += 1
        
        self.stdout.write(f"\nSuccessfully updated ordering for {total_updated} questions!")
        self.stdout.write("\nSummary:")
        
        # Show final ordering
        for category in categories:
            questions = Question.objects.filter(category=category).order_by('order')
            if questions.exists():
                self.stdout.write(f"\n{category.title}:")
                for q in questions:
                    required_text = " (Required)" if q.required else ""
                    self.stdout.write(f"   {q.order}. {q.text[:60]}...{required_text}")

