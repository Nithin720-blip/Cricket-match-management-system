# Cricket Match Management System

An **Elite Cricket Management System** built with **FastAPI**, **SQLAlchemy**, **MySQL (PyMySQL)**, and **Jinja2 Templates**.

---

## Prerequisites

Before running the project, make sure you have the following installed on your machine:
1. **Python 3.8+**
2. **MySQL Server** (e.g., via [XAMPP](https://www.apachefriends.org/), [WampServer](https://www.wampserver.com/), or standalone MySQL installation)

---

## Step-by-Step Setup

Follow these steps to run the project locally on your machine:

### 1. Start MySQL Server
Ensure that your local MySQL server is running.
- If using **XAMPP**, open the XAMPP Control Panel and start the **MySQL** module.
- The project is configured by default to connect to local MySQL with the username `root` and **no password** (`mysql+pymysql://root:@localhost/cricket_db`). If your database username or password is different, update the `DATABASE_URL` in [database.py](file:///d:/cricket_match_management_systen/database.py).

### 2. Activate the Virtual Environment
Open your terminal (PowerShell, Command Prompt, or terminal in VS Code) and navigate to the project directory:
```powershell
.venv\Scripts\activate
```

### 3. Install Dependencies
Install all required packages from `requirements.txt`:
```powershell
pip install -r requirements.txt
```

### 4. Initialize Database
We have created a helper script [init_db.py](file:///d:/cricket_match_management_systen/init_db.py) to automatically create the MySQL database, set up the required tables, and seed a default administrator account. Run:
```powershell
python init_db.py
```
*Upon success, it will print:*
> `Default admin created successfully! Credentials -> Username: admin | Password: admin123`

### 5. Run the Application
Start the FastAPI development server using **Uvicorn**:
```powershell
uvicorn main:app --reload
```

---

## Accessing the Application

Once Uvicorn is running, open your web browser and navigate to:
- **User Dashboard / Home Page:** [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **Admin Panel Login:** [http://127.0.0.1:8000/admin/login](http://127.0.0.1:8000/admin/login)
  - **Username:** `admin`
  - **Password:** `admin123`
