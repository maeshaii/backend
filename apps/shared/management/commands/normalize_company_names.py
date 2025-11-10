from django.core.management.base import BaseCommand

from apps.shared.models import EmploymentHistory, OJTCompanyProfile


class Command(BaseCommand):
    help = "Normalize stored company names to uppercase canonical form."

    def handle(self, *_args, **_options):
        employment_updates = 0
        ojt_updates = 0

        for employment in EmploymentHistory.objects.exclude(company_name_current__isnull=True).exclude(company_name_current=""):
            current = employment.company_name_current
            normalized = ' '.join(current.strip().split()).upper()
            if normalized and current != normalized:
                employment.company_name_current = normalized
                employment.save(update_fields=["company_name_current"])
                employment_updates += 1

        for profile in OJTCompanyProfile.objects.exclude(company_name__isnull=True).exclude(company_name=""):
            original = profile.company_name
            normalized = profile.company_name
            if normalized:
                normalized = ' '.join(normalized.strip().split()).upper()
            if normalized and original != normalized:
                profile.company_name = normalized
                profile.save(update_fields=["company_name"])
                ojt_updates += 1

        self.stdout.write(self.style.SUCCESS(
            f"Normalized {employment_updates} employment company name(s) and {ojt_updates} OJT company name(s)."
        ))

