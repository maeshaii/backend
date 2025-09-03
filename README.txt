Django Backend Setup Instructions
================================

This guide will help you set up and run the Django backend for this project.

---

1. Install Python
-----------------
- Make sure you have Python 3.8 or newer installed.
- Check your version:
  python --version

---

2. Set Up a Virtual Environment (Recommended)
---------------------------------------------
- Open a terminal in your project directory.
- Create a virtual environment:
  python -m venv env
- Activate the virtual environment:
  - On Windows:
      env\Scripts\activate
  - On macOS/Linux:
      source env/bin/activate

---

3. Create requirements.txt
--------------------------
- Create a file named requirements.txt in your project root with the following content:

Django>=5.2.3
djangorestframework>=3.16.0
djangorestframework-simplejwt>=5.5.0
django-cors-headers>=4.7.0
psycopg2-binary>=2.9.10
python-dotenv>=1.1.1
pandas>=2.3.0
openpyxl>=3.1.5
python-dateutil>=2.9.0.post0
pytz>=2025.2
numpy>=2.3.1
six>=1.17.0
PyJWT>=2.9.0
sqlparse>=0.5.3
tzdata>=2025.2

---

4. Install Dependencies
-----------------------
- With your virtual environment activated, run:
  pip install -r requirements.txt

---

5. Set Up Environment Variables
-------------------------------
- If your project uses a .env file, create it in the backend directory and add the required variables.

---

6. Apply Database Migrations
----------------------------
cd backend
python manage.py makemigrations
python manage.py migrate

---

7. Create a Superuser (Optional)
-------------------------------
python manage.py createsuperuser

---

8. Run the Development Server
-----------------------------
python manage.py runserver

- The server will start at http://127.0.0.1:8000/
- Admin panel: http://127.0.0.1:8000/admin/

---

If you need help with the frontend or encounter any issues, please ask for assistance! 