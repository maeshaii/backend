from django.db import migrations

def seed_tracker_questions(apps, schema_editor):
    QuestionCategory = apps.get_model('shared', 'QuestionCategory')
    Question = apps.get_model('shared', 'Question')

    # Define categories and questions (as per screenshots and /api/tracker/questions/)
    categories = [
        {
            'title': 'INTRODUCTION',
            'description': 'To our Dear Graduates,\nKindly complete this questionnaire accurately and truthfully. Your responses will be used for research purposes to assess employability and, ultimately, improve the curriculum programs offered at Cebu Technological University (CTU). Rest assured that your answers to this survey will be treated with the utmost confidentiality. Thank you very much!\nIf you have any questions, you may contact the office of the Alumni Director through email address gts@ctu.edu.ph or Contact no: (032) 402 4060.',
            'questions': [
                {'text': 'Year Graduated', 'type': 'text', 'options': []},
                {'text': 'Course Graduated', 'type': 'text', 'options': []},
                {'text': 'Email', 'type': 'text', 'options': []},
            ]
        },
        {
            'title': 'PART I : PERSONAL PROFILE',
            'description': 'N/A if not applicable',
            'questions': [
                {'text': 'Last Name', 'type': 'text', 'options': []},
                {'text': 'First Name', 'type': 'text', 'options': []},
                {'text': 'Middle Name (If none write N/A)', 'type': 'text', 'options': []},
                {'text': 'Age', 'type': 'text', 'options': []},
                {'text': 'Birthdate', 'type': 'text', 'options': []},
                {'text': 'Landline or Mobile Number', 'type': 'text', 'options': []},
                {'text': 'Social Media Account Link (e.g https://www.facebook.com/aboloc)', 'type': 'text', 'options': []},
                {'text': 'Complete Current Address', 'type': 'text', 'options': []},
                {'text': 'Complete Home Address', 'type': 'text', 'options': []},
                {'text': 'Civil Status', 'type': 'multiple', 'options': ['Single', 'Married', 'Widow']},
            ]
        },
        {
            'title': 'PART II : EMPLOYMENT HISTORY',
            'description': 'N/A if not applicable',
            'questions': [
                {'text': 'Name of your organization/employer (1st employer right after graduation)', 'type': 'text', 'options': []},
                {'text': 'Date Hired (1st employer right after graduation)', 'type': 'text', 'options': []},
                {'text': 'Position (1st employer right after graduation) N/A if not applicable', 'type': 'text', 'options': []},
                {'text': 'Status of your employment (1st employer right after graduation)', 'type': 'multiple', 'options': ['Permanent', 'Temporary']},
                {'text': 'Company Address (1st employer right after graduation)', 'type': 'text', 'options': []},
                {'text': 'Sector (1st employer right after graduation)', 'type': 'radio', 'options': ['Private', 'Government']},
                {'text': 'First Employment Supporting Document', 'type': 'file', 'options': []},
                {'text': 'Are you PRESENTLY employed ?', 'type': 'radio', 'options': ['Yes', 'No']},
                {'text': 'Did you pursue futher study?', 'type': 'radio', 'options': ['Yes', 'No']},
            ]
        },
        {
            'title': 'PART III : EMPLOYMENT STATUS',
            'description': 'N/A if not applicable',
            'questions': [
                {'text': 'Are you employed by a company/organization or are you self employed ?', 'type': 'multiple', 'options': ['Employed by a company/organization', 'Self-employed', 'Freelance/Contract-based']},
                {'text': 'Status of your current employment', 'type': 'multiple', 'options': ['Permanent', 'Temporary']},
                {'text': 'Current Company Name', 'type': 'text', 'options': []},
                {'text': 'Current Position', 'type': 'text', 'options': []},
                {'text': 'Current Sector of your Job', 'type': 'radio', 'options': ['Private', 'Government']},
                {'text': 'How long have you been employed?', 'type': 'text', 'options': []},
                {'text': 'Current Salary range', 'type': 'text', 'options': []},
                {'text': 'Have you received any awards or recognition during your employment?', 'type': 'radio', 'options': ['Yes', 'No']},
                {'text': 'Supporting Documents for awards/recognition', 'type': 'file', 'options': []},
                {'text': 'Employment Supporting Document(Current)', 'type': 'file', 'options': []},
            ]
        },
        {
            'title': 'IF UNEMPLOYED',
            'description': '',
            'questions': [
                {'text': 'Reason for unemployment', 'type': 'checkbox', 'options': ['Family concerns and the decision not to find a job', 'Health-related reasons', 'Lack of work experience', 'No job opportunity', 'Did not look for a job', 'Seeking employment', 'For further study']},
            ]
        },
        {
            'title': 'PART IV : FURTHER STUDY',
            'description': 'N/A if not applicable',
            'questions': [
                {'text': 'Date Started', 'type': 'text', 'options': []},
                {'text': 'Please specify post graduate/degree', 'type': 'text', 'options': []},
                {'text': 'Name of Institution/University', 'type': 'text', 'options': []},
                {'text': 'Total number of units obtain', 'type': 'text', 'options': []},
            ]
        },
    ]

    for cat in categories:
        category = QuestionCategory.objects.create(title=cat['title'], description=cat['description'])
        for q in cat['questions']:
            Question.objects.create(
                category=category,
                text=q['text'],
                type=q['type'],
                options=q['options'] if q['options'] else None
            )

def unseed_tracker_questions(apps, schema_editor):
    QuestionCategory = apps.get_model('shared', 'QuestionCategory')
    QuestionCategory.objects.all().delete()

class Migration(migrations.Migration):
    dependencies = [
        ('shared', '0004_questioncategory_question_trackerresponse'),
    ]

    operations = [
        migrations.RunPython(seed_tracker_questions, unseed_tracker_questions),
    ] 