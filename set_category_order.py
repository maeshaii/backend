from apps.shared.models import QuestionCategory

def run():
    # Map of title to intended order
    order_map = {
        'INTRODUCTION': 0,
        'PART I : PERSONAL PROFILE': 1,
        'PART II : EMPLOYMENT HISTORY': 2,
        'PART III : EMPLOYMENT STATUS': 3,
        'IF UNEMPLOYED': 4,
        'PART IV : FURTHER STUDY': 5,
    }
    updated = 0
    for cat in QuestionCategory.objects.all():
        if cat.title in order_map:
            cat.order = order_map[cat.title]
            cat.save()
            updated += 1
            print(f"Set order {cat.order} for '{cat.title}'")
        else:
            print(f"Skipped category '{cat.title}' (not in order map)")
    print(f"Updated {updated} categories.") 