# CostEst Pro - Construction Cost Estimation Platform

## Overview
CostEst Pro is a Django-based web application for construction cost estimation, project management, and material price forecasting. It integrates with CIDB (Construction Industry Development Board) data for accurate benchmarking and uses machine learning models (Linear Regression and Random Forest) for price predictions.

Key features:
- Project upload and management
- Cost estimation with CIDB benchmarking
- Actual cost tracking and variance analysis
- Inflation adjustment
- Material and labor price forecasting
- Role-based access (Admin, Contractor, QS, PM, Developer)
- Reporting (PDF/Excel exports)
- User profiles and authentication

The application uses MySQL as the database backend and is optimized for development in VS Code.

## Requirements
- Python 3.8+
- MySQL 8.0+
- Virtual environment (recommended: venv)
- Dependencies (listed in requirements.txt):
  - Django==5.2.7
  - mysqlclient==2.1.1
  - pandas==1.5.3
  - openpyxl==3.1.2
  - scikit-learn==1.3.2
  - reportlab==4.0.4
  - python-decouple==3.8

## Installation
1. **Clone the repository** (if applicable) or set up the project folder as provided.

2. **Create and activate virtual environment**:
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
text3. **Install dependencies**:

pip install -r requirements.txt
text4. **Set up environment variables**:
Create a `.env` file in the project root with:

SECRET_KEY=your-secret-key
DEBUG=True
DB_NAME=costest_db
DB_USER=your-mysql-user
DB_PASSWORD=your-mysql-password
DB_HOST=localhost
DB_PORT=3306
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password

5. **Database Setup**:
- Create MySQL database: `CREATE DATABASE costest_db;`
- Run migrations:
python manage.py makemigrations
python manage.py migrate

6. **Create superuser** (for admin access):
python manage.py createsuperuser

7. **Import CIDB Data**:
- Place Excel files in the `data/` folder (e.g., Table_B1_Materials_Prices_Q1_2025.xlsx)
- Run: `python manage.py import_prices --auto`
- Train models: `python manage.py train_forecast`

## Running the Application
1. Start the development server:

python manage.py runserver
text2. Access the app:
- User Login: http://127.0.0.1:8000/login
- Admin: http://127.0.0.1:8000/admin/

## Usage Guide
### User Roles
- **Admin**: Full access, data import, user management
- **Contractor/QS**: Upload projects, view estimates, run forecasts
- **PM/Developer**: View projects, upload actual costs, reports

### Key Features
1. **Project Upload**:
- Go to Dashboard > Upload Project
- Provide name, dates, Excel file (BOQ format)
- System auto-calculates estimates vs CIDB

2. **Forecasting**:
- From project detail: Run Forecast
- View predictions in Linear/Random Forest tabs
- Export to Excel

3. **Inflation Adjustment**:
- From project detail: Adjust Inflation
- Apply percentage to update rates

4. **Actual Costs**:
- Edit actual quantities/rates
- View variance and profitability

5. **Reports**:
- PDF/Excel exports from project detail
- All projects export from dashboard

### Management Commands
- Import prices: `python manage.py import_prices --auto`
- Train forecast: `python manage.py train_forecast`
- Fix profiles: `python manage.py fix_user_profiles`

## Project Structure

costest/
├── costest/              # Project settings
│   ├── init.py
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── data/                 # CIDB Excel files
│   ├── Table_B1_Materials_Prices_Q*.xlsx
│   └── Table_B2_Labour_Rates_Q*.xlsx
├── estimator/            # Main app
│   ├── migrations/       # Database migrations
│   ├── management/       # Custom commands
│   │   └── commands/
│   │       ├── import_prices.py
│   │       └── train_forecast.py
│   ├── templates/        # App templates
│   │   └── estimator/
│   ├── templatetags/     # Custom filters
│   ├── static/           # App static files
│   ├── init.py
│   ├── admin.py          # Admin interface
│   ├── apps.py
│   ├── forms.py          # Forms
│   ├── ml_forecast.py    # ML logic
│   ├── models.py         # Models
│   ├── signals.py        # Signals
│   ├── urls.py           # App URLs
│   ├── utils.py          # Utilities
│   └── views.py          # Views
├── media/                # Uploaded files
│   ├── avatars/
│   └── projects/
├── static/               # Global static
│   └── css/
├── templates/            # Global templates
├── manage.py
├── requirements.txt
└── train_models.py       # (Empty/legacy)

## Development Tips (VS Code)
- Install extensions: Python, Django, MySQL
- Use integrated terminal for commands
- Set up debugger with `launch.json` for Django
- Lint with Pylint or Ruff
- Format with Black

## Troubleshooting
- **Database errors**: Check MySQL connection and .env vars
- **Import fails**: Ensure Excel files in data/ with correct format
- **ML errors**: Verify scikit-learn installed
- **Email issues**: Configure Gmail SMTP in .env