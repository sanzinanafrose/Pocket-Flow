# PocketFlow – Module 1: Expense Entry & Categorization

## Features Included
1. **[Sanzinan]** View and update profile (name, email, password, avatar)
2. **[Jannatunnesa]** Add new expenses (title, amount, date, category)
3. **[Sadia]** Predefined categories: Food, Transport, Entertainment, Bills, Shopping, Health, Education, Other
4. **[Sanzinan]** Custom notes and tags per expense

---

## Setup & Run in VS Code

### 1. Open the project
Open this folder in VS Code.

### 2. Create a virtual environment (recommended)
Open the **Terminal** in VS Code (`Ctrl + `` ` ``) and run:

```bash
python -m venv venv
```

Activate it:
- **Windows:** `venv\Scripts\activate`
- **Mac/Linux:** `source venv/bin/activate`

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the app
```bash
python app.py
```

### 5. Open in browser
Visit: [http://127.0.0.1:5000](http://127.0.0.1:5000)

---

## Default Credentials
Register a new account at `/register`.

## Project Structure
```
module1/
├── app.py                          # Main Flask application
├── requirements.txt                # Dependencies (Flask only)
├── module1.db                      # SQLite database (auto-created on first run)
├── static/
│   ├── css/style.css
│   ├── js/main.js
│   └── uploads/avatars/            # Profile picture uploads
└── templates/
    ├── base.html
    ├── profile.html                 # Feature 1 & 4
    ├── auth/
    │   ├── login.html
    │   └── register.html
    └── expenses/
        ├── dashboard.html           # Expense list
        ├── add_expense.html         # Feature 2 & 3 & 4
        └── edit_expense.html        # Edit expense
```
