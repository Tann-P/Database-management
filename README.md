# Database-management

## Project Description
A Django-based web application for managing database operations with an emphasis on data upload, preview, and management. This application allows users to upload Excel files, preview data, and perform database operations through a user-friendly interface.

## Features
- File Upload: Support for Excel (.xlsx) file uploads
- Data Preview: View uploaded data before committing to the database
- Data Management: Interface for managing database entries
- Responsive Design: User-friendly interface that works across devices

## Technologies Used
- Django
- Python
- SQLite
- HTML/CSS
- Excel Data Processing

## Installation

### Prerequisites
- Python 3.x
- Django
- Required Python packages (see below)

### Setup
1. Clone this repository:
   ```
   git clone https://github.com/Tann-P/Database-management.git
   cd Database-management
   ```

2. Install required packages:
   ```
   pip install django pandas openpyxl
   ```

3. Apply migrations:
   ```
   python manage.py migrate
   ```

4. Run the development server:
   ```
   python manage.py runserver
   ```

5. Access the application at `http://localhost:8000/`

## Usage
1. Navigate to the upload form page
2. Select an Excel file to upload
3. Preview and validate the data
4. Confirm to save the data to the database
5. Manage uploaded data through the dashboard interface

## Project Structure
- `dashboard/`: Main application containing views, models, and templates
- `db_management/`: Project configuration files
- `media/uploads/`: Directory for storing uploaded files
- `static/`: Static assets (CSS, JS, images)

## License
This project is licensed under the MIT License.

## Author
- Tann-P