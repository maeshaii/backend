# OJT Stats App

This Django app provides comprehensive statistics and tracking for On-the-Job Training (OJT) students, specifically designed for coordinators to monitor and manage OJT statuses.

## Overview

The OJT Stats app allows coordinators to:
- Track OJT student statuses (Ongoing, Completed, Incomplete)
- Generate comprehensive statistics and reports
- Monitor completion rates and academic progress
- Export detailed data for analysis and reporting

## API Endpoints

### 1. OJT Statistics Overview
**GET** `/api/ojt-statistics/overview/`

Returns an overview of OJT statistics including:
- Total OJT students count
- Status counts (Ongoing, Completed, Incomplete)
- Completion rates by percentage
- Year and course breakdowns

**Query Parameters:**
- `year`: Filter by graduation year (e.g., `2024`, `ALL`)
- `course`: Filter by course (e.g., `BSIT`, `ALL`)

### 2. Detailed Statistics
**GET** `/api/ojt-statistics/detailed/`

Provides detailed statistics based on the specified type.

**Query Parameters:**
- `year`: Filter by graduation year
- `course`: Filter by course
- `type`: Statistics type (`ALL`, `status_tracking`, `academic_progress`, `coordinator_summary`)

**Statistics Types:**
- **ALL**: Comprehensive overview with all metrics
- **status_tracking**: Focus on OJT status progression and tracking
- **academic_progress**: Academic statistics broken down by OJT status
- **coordinator_summary**: Summary view for coordinator management

### 3. Data Export
**GET** `/api/ojt-statistics/export/`

Exports detailed OJT data for reporting and analysis.

**Query Parameters:**
- `year`: Filter by graduation year
- `course`: Filter by course
- `status`: Filter by OJT status (`Ongoing`, `Completed`, `Incomplete`, `ALL`)

## OJT Status Values

The app tracks three main OJT statuses that coordinators can assign:

1. **Ongoing** - Student is currently undergoing OJT
2. **Completed** - Student has successfully completed OJT
3. **Incomplete** - Student did not complete OJT

## Usage Examples

### Get Overview for BSIT Students in 2024
```
GET /api/ojt-statistics/overview/?year=2024&course=BSIT
```

### Get Status Tracking Statistics
```
GET /api/ojt-statistics/detailed/?type=status_tracking&year=2024
```

### Export Completed OJT Data
```
GET /api/ojt-statistics/export/?status=Completed&year=2024
```

## Response Format

All endpoints return JSON responses with the following structure:
```json
{
    "success": true,
    "total_ojt": 150,
    "status_counts": {
        "Ongoing": 45,
        "Completed": 95,
        "Incomplete": 10
    },
    "completion_rate": 63.33,
    "ongoing_rate": 30.0,
    "incomplete_rate": 6.67
}
```

## For Coordinators

This app is specifically designed to help coordinators:
- Monitor OJT progress across different courses and years
- Identify students who need attention (Incomplete status)
- Track completion rates for program assessment
- Generate reports for administrative purposes
- Make data-driven decisions about OJT program improvements

## Technical Notes

- The app filters users by `account_type__ojt=True`
- OJT status is stored in the `ojtstatus` field of the User model
- All statistics are calculated in real-time from the database
- The app supports filtering by year, course, and OJT status
