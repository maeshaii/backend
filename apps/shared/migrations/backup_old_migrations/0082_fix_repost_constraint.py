# Generated manually to fix repost constraint issue

from django.db import migrations, models
from django.db.models import Q, CheckConstraint


class Migration(migrations.Migration):

    dependencies = [
        ('shared', '0081_fix_like_constraint'),
    ]

    operations = [
        # Remove old constraints if they exist
        migrations.RemoveConstraint(
            model_name='repost',
            name='repost_post_or_forum_not_both',
        ),
        migrations.RemoveConstraint(
            model_name='repost',
            name='repost_one_content_type_only',
        ),
        # Add new constraint for Repost - exactly one content type
        migrations.AddConstraint(
            model_name='repost',
            constraint=CheckConstraint(
                check=(
                    Q(post__isnull=False, forum__isnull=True, donation_request__isnull=True) |
                    Q(post__isnull=True, forum__isnull=False, donation_request__isnull=True) |
                    Q(post__isnull=True, forum__isnull=True, donation_request__isnull=False)
                ),
                name='repost_one_content_type_only',
            ),
        ),
    ]

