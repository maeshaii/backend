# WhereNaYou - Alumni Management System

A comprehensive alumni management system built with Django (backend) and React (frontend) for tracking and managing alumni data, OJT (On-the-Job Training) records, and statistics.

## 🚀 Features

### Backend (Django)
- **Alumni Management**: Complete CRUD operations for alumni records
- **User Authentication**: JWT-based authentication system
- **Statistics API**: Comprehensive alumni statistics and analytics
- **Data Import/Export**: Excel and CSV file handling
- **Admin Dashboard**: Django admin interface for data management

### Frontend (React)
- **Coordinator Dashboard**: Import OJT data and view statistics
- **Admin Interface**: User management and system administration
- **Responsive Design**: Modern UI with mobile-friendly components
- **Real-time Updates**: Dynamic data loading and updates

### Mobile App (React Native/Expo)
- **Cross-platform**: iOS and Android support
- **Alumni Directory**: Browse and search alumni records
- **Profile Management**: Update personal information
- **Push Notifications**: Real-time updates and announcements

## 🛠️ Tech Stack

### Backend
- **Django 5.2.3**: Web framework
- **Django REST Framework**: API development
- **PostgreSQL**: Database (via psycopg2)
- **JWT Authentication**: Secure user authentication
- **Pandas**: Data processing and analysis
- **OpenPyXL**: Excel file handling

### Frontend
- **React 18**: UI library
- **TypeScript**: Type-safe development
- **React Router**: Navigation
- **Axios**: HTTP client

### Mobile
- **React Native**: Cross-platform mobile development
- **Expo**: Development platform
- **TypeScript**: Type-safe development

## 📁 Project Structure

```
trial/
├── backend/                 # Django backend
│   ├── apps/
│   │   ├── alumni_stats/    # Statistics app
│   │   ├── alumni_users/    # Alumni management
│   │   ├── api/            # API endpoints
│   │   ├── shared/         # Shared models
│   │   └── tracker/        # Tracking functionality
│   ├── backend/            # Django settings
│   └── manage.py
├── web-frontend/           # React frontend
│   ├── src/
│   │   ├── components/     # Reusable components
│   │   ├── pages/          # Page components
│   │   └── services/       # API services
│   └── package.json
├── wny-mobile/            # React Native mobile app
│   ├── app/               # App screens
│   ├── components/        # Mobile components
│   └── services/          # API services
└── README.md
```

## 🚀 Getting Started

### Prerequisites
- Python 3.12+
- Node.js 18+
- PostgreSQL
- Git

### Backend Setup
1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Create and activate virtual environment:
   ```bash
   python -m venv env312
   source env312/bin/activate  # On Windows: env312\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your database and secret settings
   ```

5. Run migrations:
   ```bash
   python manage.py migrate
   ```

6. Create superuser:
   ```bash
   python manage.py createsuperuser
   ```

7. Start the development server:
   ```bash
   python manage.py runserver
   ```

### Scripts Directory
- All one-off scripts for data maintenance, backfills, or admin tasks should be placed in `backend-wny/scripts/` or converted to Django management commands under `apps/shared/management/commands/`.
- Remove or archive scripts from the backend root after migration.

### Frontend Setup
1. Navigate to the web-frontend directory:
   ```bash
   cd web-frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start the development server:
   ```bash
   npm start
   ```

### Mobile App Setup
1. Navigate to the wny-mobile directory:
   ```bash
   cd wny-mobile
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start the Expo development server:
   ```bash
   npx expo start
   ```

## 📊 API Endpoints

### Authentication
- `POST /api/auth/login/` - User login
- `POST /api/auth/refresh/` - Refresh token
- `POST /api/auth/logout/` - User logout

### Alumni Management
- `GET /api/alumni/` - List alumni
- `POST /api/alumni/` - Create alumni record
- `GET /api/alumni/{id}/` - Get alumni details
- `PUT /api/alumni/{id}/` - Update alumni record
- `DELETE /api/alumni/{id}/` - Delete alumni record

### Statistics
- `GET /api/statistics/` - Get alumni statistics
- `GET /api/statistics/years/` - Get year-wise statistics

## 🔧 Configuration

### Environment Variables
Create a `.env` file in the backend directory:

```env
DEBUG=True
SECRET_KEY=your-secret-key
DATABASE_URL=postgresql://user:password@localhost:5432/wherenayou
ALLOWED_HOSTS=localhost,127.0.0.1
CORS_ALLOWED_ORIGINS=http://localhost:3000
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 👥 Team

- **Backend Development**: Django/Python
- **Frontend Development**: React/TypeScript
- **Mobile Development**: React Native/Expo
- **UI/UX Design**: Modern, responsive design

## 📞 Support

For support and questions, please contact the development team or create an issue in the repository. 