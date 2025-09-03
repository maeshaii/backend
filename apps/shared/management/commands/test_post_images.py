from django.core.management.base import BaseCommand
from apps.shared.models import Post

class Command(BaseCommand):
    help = 'Test post image URLs'

    def handle(self, *args, **options):
        posts = Post.objects.all()
        
        if not posts:
            self.stdout.write("No posts found")
            return
            
        for post in posts:
            self.stdout.write(f"Post ID: {post.post_id}")
            self.stdout.write(f"  Content: {post.post_content[:50]}...")
            self.stdout.write(f"  Has image: {bool(post.post_image)}")
            if post.post_image:
                self.stdout.write(f"  Image URL: {post.post_image.url}")
                self.stdout.write(f"  Image name: {post.post_image.name}")
            self.stdout.write("---")

