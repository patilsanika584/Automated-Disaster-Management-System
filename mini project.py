import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
import sqlite3
import re
import time
import smtplib
from email.message import EmailMessage
from PIL import Image, ImageTk
import urllib.request
import io

EMAIL_REGEX = re.compile(r"^[^@]+@[^@]+\.[^@]+$")
ADMIN_EMAIL = "your_gmail@gmail.com"
ADMIN_PASSWORD = "your_app_password_here"

def send_email_alert(to, subject, body):
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = ADMIN_EMAIL
    msg['To'] = to
    msg.set_content(body)
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(ADMIN_EMAIL, ADMIN_PASSWORD)
            smtp.send_message(msg)
        return True
    except Exception as e:
        print("Email error:", e)
        return False

def init_db():
    conn = sqlite3.connect('disaster_app.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (name TEXT PRIMARY KEY, age INTEGER, location TEXT, phoneno TEXT, emailid TEXT, password TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS services
                 (timestamp TEXT, user TEXT, disaster TEXT, food_packets INTEGER,
                  medical_kits INTEGER, location TEXT, evac_center TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS supplies
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  year INTEGER, location TEXT,
                  total_food INTEGER, total_med INTEGER,
                  given_food INTEGER, given_med INTEGER)''')
    conn.commit()
    return conn

def reset_supplies_table(conn):
    c = conn.cursor()
    c.execute("DROP TABLE IF EXISTS supplies")
    c.execute('''
        CREATE TABLE supplies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER,
            location TEXT,
            total_food INTEGER,
            total_med INTEGER,
            given_food INTEGER,
            given_med INTEGER
        )
    ''')
    conn.commit()

def ensure_default_supplies(conn):
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM supplies")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO supplies (year, location, total_food, total_med, given_food, given_med) VALUES (?, ?, ?, ?, ?, ?)",
                  (2025, "Maharashtra", 5000, 3000, 0, 0))
        conn.commit()

def update_supply_usage(conn, location, year, food_used, med_used):
    c = conn.cursor()
    c.execute("SELECT total_food, total_med, given_food, given_med FROM supplies WHERE location=? AND year=?", (location, year))
    row = c.fetchone()
    if not row:
        messagebox.showerror("Error", f"No supply record found for {location}, {year}.")
        return False, None
    total_food, total_med, given_food, given_med = row
    available_food = total_food - given_food
    available_med = total_med - given_med
    if food_used > available_food or med_used > available_med:
        alert_msg = f"ALERT: Supply insufficient at {location} for {year}.\nAvailable: {available_food} food, {available_med} medical.\nRequested: {food_used} food, {med_used} medical."
        messagebox.showwarning("Supply Alert", alert_msg)
        send_email_alert(ADMIN_EMAIL, f"Supply Alert [{location}]", alert_msg)
        return False, (available_food, available_med)
    new_given_food = given_food + food_used
    new_given_med = given_med + med_used
    c.execute("UPDATE supplies SET given_food=?, given_med=? WHERE location=? AND year=?", (new_given_food, new_given_med, location, year))
    conn.commit()
    return True, (total_food - new_given_food, total_med - new_given_med)

def get_users_from_db(conn):
    c = conn.cursor()
    c.execute('SELECT name, age, location, phoneno, emailid, password FROM users')
    return c.fetchall()

def add_user_to_db(conn, name, age, location, phoneno, emailid, password):
    c = conn.cursor()
    try:
        c.execute('INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)', (name, age, location, phoneno, emailid, password))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False

def get_user_by_name_password(conn, name, password):
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE name=? AND password=?', (name, password))
    return c.fetchone()

def add_service_to_db(conn, timestamp, user, disaster, food_packets, medical_kits, location, evac_center):
    c = conn.cursor()
    c.execute('INSERT INTO services VALUES (?, ?, ?, ?, ?, ?, ?)', (timestamp, user, disaster, food_packets, medical_kits, location, evac_center))
    conn.commit()

def get_services_from_db(conn):
    c = conn.cursor()
    c.execute('SELECT * FROM services')
    return c.fetchall()

evacuation_centers = {
    "Mumbai": ["Mumbai Central Shelter", "Andheri Gymkhana", "Contact: 022-26123371"],
    "Pune": ["Pune Collector Office Grounds", "Shivajinagar Hall", "Contact: 020-26123371"],
    "Nashik": ["Godavari Nagar Center", "City Stadium Shelter", "Contact: 0253-2311234"],
    "Nagpur": ["Rescue Shelter Ground", "Government School 1", "Contact: 0712-2562001"],
    "Kolhapur": ["Main Stadium (Capacity: 500)", "Community Hall - North", "DDMA Office: 0231-2659232"],
    "Sangli": ["Collector Office Grounds", "School Hall A", "Toll-free: 1077, Office: 0233-2600500"],
    "Satara": ["Civic Center", "Community Shelter 1", "DDMA Office: 02162-232175"],
    "Aurangabad": ["Nagar Parishad Hall", "Town Shelter B", "Contact: 0240-2331550"],
    "Solapur": ["District Relief Camp", "Government Polytechnic Hall", "Contact: 0217-2729999"],
    "Thane": ["Thane Shelter Complex", "Kalwa Hall", "Contact: 022-25341300"],
}

class DisasterManagementApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Automated Disaster Management System")
        self.root.geometry("650x750")
        self.root.resizable(False, False)
        self.conn = init_db()
        reset_supplies_table(self.conn)
        ensure_default_supplies(self.conn)
        self.logged_in = False
        self.current_user = None
        self.evacuation_centers = evacuation_centers.copy()

        try:
            self.bg_image = tk.PhotoImage(file="C:\\Users\\Lenovo\\Downloads\\python_f.gif")
            self.bg_label = tk.Label(self.root, image=self.bg_image)
            self.bg_label.place(x=10, y=300)
        except Exception:
            self.bg_label = tk.Label(self.root, bg="white")
            self.bg_label.place(x=10, y=300)

        self.validate_int_cmd = self.root.register(self._only_numbers_callback)
        self.create_main_widgets()

    def _only_numbers_callback(self, text):
        return text == "" or text.isdigit()

    def _is_valid_phone(self, s):
        return s.isdigit() and len(s) == 10

    def _is_valid_email(self, s):
        return bool(EMAIL_REGEX.match(s))

    def create_main_widgets(self):
        self.title_lbl = tk.Label(self.root, text="** Automated Disaster Management System **", font=("Arial", 16, "bold"), bg="lightpink", fg="black")
        self.title_lbl.place(x=80, y=20)
        self.register_person_btn = tk.Button(self.root, text="Register Person", font=("Arial", 12), bg="green", fg="white", width=16, command=self.show_registration_fields)
        self.register_person_btn.place(x=300, y=320)
        self.login_btn = tk.Button(self.root, text="Login", font=("Arial", 12), bg="green", fg="white", width=16, command=self.show_login_fields)
        self.login_btn.place(x=300, y=370)

    def hide_main_buttons(self):
        self.register_person_btn.place_forget()
        self.login_btn.place_forget()
        self.title_lbl.place_forget()
        self.bg_label.place_forget()

    def show_main_buttons(self):
        self.bg_label.place(x=10, y=300)
        self.title_lbl.place(x=80, y=20)
        self.register_person_btn.place(x=300, y=320)
        self.login_btn.place(x=300, y=370)

    def show_registration_fields(self):
        self.hide_main_buttons()
        self.reg_widgets = []
        self.name_var = tk.StringVar()
        self.age_var = tk.StringVar()
        self.location_var = tk.StringVar()
        self.phone_var = tk.StringVar()
        self.email_var = tk.StringVar()
        self.password_var = tk.StringVar()
        labels = [("Name", self.name_var, None), ("Age", self.age_var, self.validate_int_cmd), ("Location", self.location_var, None),
                  ("Phone No.", self.phone_var, self.validate_int_cmd), ("Email", self.email_var, None), ("Password", self.password_var, None)]
        y = 70
        for label_text, var, validation in labels:
            lbl = tk.Label(self.root, text=label_text + " :", font=("Arial", 12), fg="orange")
            lbl.place(x=50, y=y)
            entry = tk.Entry(self.root, textvariable=var, font=("Arial", 11), bd=3)
            if label_text == "Password":
                entry.config(show="*")
            if validation:
                entry.config(validate="key", validatecommand=(validation, "%P"))
            entry.place(x=180, y=y)
            self.reg_widgets.extend([lbl, entry])
            y += 45
        submit_btn = tk.Button(self.root, text="Submit", font=("Arial", 11, "bold"), bg="skyblue", command=self.submit_registration)
        submit_btn.place(x=150, y=y + 10)
        clear_btn = tk.Button(self.root, text="Clear", font=("Arial", 11), command=self.clear_registration)
        clear_btn.place(x=260, y=y + 10)
        back_btn = tk.Button(self.root, text="Back", font=("Arial", 11), command=self.back_to_main_from_registration)
        back_btn.place(x=360, y=y + 10)
        self.reg_widgets.extend([submit_btn, clear_btn, back_btn])

    def submit_registration(self):
        name = self.name_var.get().strip()
        age = self.age_var.get().strip()
        location = self.location_var.get().strip()
        phone = self.phone_var.get().strip()
        email = self.email_var.get().strip()
        password = self.password_var.get()
        if not all([name, age, location, phone, email, password]):
            messagebox.showerror("Error", "Please fill all fields.")
            return
        if not age.isdigit():
            messagebox.showerror("Error", "Age must be a number.")
            return
        if not self._is_valid_phone(phone):
            messagebox.showerror("Error", "Phone number must be exactly 10 digits.")
            return
        if not self._is_valid_email(email):
            messagebox.showerror("Error", "Invalid email address.")
            return
        success = add_user_to_db(self.conn, name, int(age), location, phone, email, password)
        if success:
            messagebox.showinfo("Registered", f"Registration successful for {name}.")
        else:
            messagebox.showerror("Error", f"User '{name}' already exists.")
        self.clear_registration()

    def clear_registration(self):
        for var in [self.name_var, self.age_var, self.location_var, self.phone_var, self.email_var, self.password_var]:
            var.set("")

    def back_to_main_from_registration(self):
        for w in getattr(self, "reg_widgets", []):
            try:
                w.destroy()
            except Exception:
                pass
        self.show_main_buttons()

    def show_login_fields(self):
        self.hide_main_buttons()
        self.login_widgets = []
        self.username_var = tk.StringVar()
        self.login_password_var = tk.StringVar()
        lbl_u = tk.Label(self.root, text="Username :", font=("Arial", 12), fg="orange")
        lbl_u.place(x=50, y=120)
        entry_u = tk.Entry(self.root, textvariable=self.username_var, font=("Arial", 11), bd=3)
        entry_u.place(x=180, y=120)
        lbl_p = tk.Label(self.root, text="Password :", font=("Arial", 12), fg="orange")
        lbl_p.place(x=50, y=170)
        entry_p = tk.Entry(self.root, textvariable=self.login_password_var, show="*", font=("Arial", 11), bd=3)
        entry_p.place(x=180, y=170)
        login_btn = tk.Button(self.root, text="Login", font=("Arial", 11, "bold"), bg="skyblue", command=self.login)
        login_btn.place(x=180, y=220)
        clear_btn = tk.Button(self.root, text="Clear", font=("Arial", 11), command=self.clear_login)
        clear_btn.place(x=270, y=220)
        back_btn = tk.Button(self.root, text="Back", font=("Arial", 11), command=self.back_to_main_from_login)
        back_btn.place(x=360, y=220)
        self.login_widgets.extend([lbl_u, entry_u, lbl_p, entry_p, login_btn, clear_btn, back_btn])

    def clear_login(self):
        self.username_var.set("")
        self.login_password_var.set("")

    def back_to_main_from_login(self):
        for w in getattr(self, "login_widgets", []):
            try:
                w.destroy()
            except Exception:
                pass
        self.show_main_buttons()

    def login(self):
        username = self.username_var.get().strip()
        password = self.login_password_var.get()
        if not username or not password:
            messagebox.showerror("Error", "Please enter username and password.")
            return
        user = get_user_by_name_password(self.conn, username, password)
        if not user:
            messagebox.showerror("Login Failed", "Incorrect username or password.")
            return
        self.logged_in = True
        self.current_user = {
            "name": user[0],
            "age": user[1],
            "location": user[2],
            "phoneno": user[3],
            "emailid": user[4],
            "password": user[5]
        }
        for w in getattr(self, "login_widgets", []):
            try:
                w.destroy()
            except Exception:
                pass
        self.show_post_login_buttons()

    def show_post_login_buttons(self):
        self.hide_main_buttons()

        self.external_service_btn = tk.Button(self.root, text="External Service", font=("Arial", 12), bg="green", fg="white", width=18, command=self.show_external_fields)
        self.external_service_btn.place(x=60, y=120)

        # Sensor alert just below external service button
        self.sensor_alert_btn = tk.Button(self.root, text="Sensor Alert Check", font=("Arial", 12), bg="orange", fg="black", width=18, command=self.sensor_alert_check)
        self.sensor_alert_btn.place(x=60, y=180)

        self.status_report_btn = tk.Button(self.root, text="View Status Report", font=("Arial", 12), bg="green", fg="white", width=18, command=self.view_status_report)
        self.status_report_btn.place(x=320, y=120)

        self.recent_activities_btn = tk.Button(self.root, text="Recent Activities", font=("Arial", 12), bg="blue", fg="white", width=18, command=self.show_recent_activities)
        self.recent_activities_btn.place(x=320, y=180)

        self.logout_btn = tk.Button(self.root, text="Logout", font=("Arial", 12), bg="red", fg="white", width=18, command=self.logout)
        self.logout_btn.place(x=190, y=250)

    def logout(self):
        for btn in [self.external_service_btn, self.status_report_btn, self.sensor_alert_btn, self.recent_activities_btn, self.logout_btn]:
            try:
                btn.destroy()
            except Exception:
                pass
        self.logged_in = False
        self.current_user = None
        self.show_main_buttons()

    def show_external_fields(self):
        for btn in [self.external_service_btn, self.status_report_btn, self.sensor_alert_btn, self.recent_activities_btn, self.logout_btn]:
            try:
                btn.place_forget()
            except Exception:
                pass
        self.external_widgets = []
        self.disaster_var = tk.StringVar()
        self.food_var = tk.StringVar()
        self.medkits_var = tk.StringVar()
        self.curr_loc_var = tk.StringVar()
        self.selected_center_var = tk.StringVar()
        y = 70
        items = [
            ("Disaster Type", self.disaster_var, None),
            ("Food Packets", self.food_var, self.validate_int_cmd),
            ("Medical Kits", self.medkits_var, self.validate_int_cmd),
            ("Current Location", self.curr_loc_var, None)
        ]
        for label_text, var, validation in items:
            lbl = tk.Label(self.root, text=label_text + " :", font=("Arial", 12), fg="orange")
            lbl.place(x=40, y=y)
            entry = tk.Entry(self.root, textvariable=var, font=("Arial", 11), bd=3)
            if validation:
                entry.config(validate="key", validatecommand=(validation, "%P"))
            entry.place(x=200, y=y)
            self.external_widgets.extend([lbl, entry])
            y += 45
        select_center_btn = tk.Button(self.root, text="Select Nearest Center", font=("Arial", 11), command=self.update_centers_by_location)
        select_center_btn.place(x=200, y=y)
        self.external_widgets.append(select_center_btn)
        y += 35
        lbl_choice = tk.Label(self.root, text="Nearest Evacuation Center:", font=("Arial", 11))
        lbl_choice.place(x=40, y=y)
        self.center_combo = ttk.Combobox(self.root, textvariable=self.selected_center_var, width=55, state="readonly")
        self.center_combo.place(x=40, y=y + 30)
        all_centers_flat = self._flatten_centers()
        self.center_combo['values'] = all_centers_flat
        self.external_widgets.extend([lbl_choice, self.center_combo])
        evac_lbl = tk.Label(self.root, text="All Maharashtra Evacuation Centers:", font=("Arial", 12, "bold"))
        evac_lbl.place(x=40, y=y + 70)
        self.external_widgets.append(evac_lbl)
        self.evacs_table = ttk.Treeview(self.root, columns=("District", "Center 1", "Center 2", "Contact"), show='headings', height=8)
        self.evacs_table.heading("District", text="District")
        self.evacs_table.heading("Center 1", text="Center 1")
        self.evacs_table.heading("Center 2", text="Center 2")
        self.evacs_table.heading("Contact", text="Contact")
        self.evacs_table.column("District", width=140)
        self.evacs_table.column("Center 1", width=200)
        self.evacs_table.column("Center 2", width=200)
        self.evacs_table.column("Contact", width=150)
        for district, centers in self.evacuation_centers.items():
            c1 = centers[0] if len(centers) > 0 else ""
            c2 = centers[1] if len(centers) > 1 else ""
            contact = centers[2] if len(centers) > 2 else ""
            self.evacs_table.insert("", tk.END, values=(district, c1, c2, contact))
        self.evacs_table.place(x=40, y=y + 100, width=650)
        self.external_widgets.append(self.evacs_table)
        y += 230
        submit_btn = tk.Button(self.root, text="Submit Service", font=("Arial", 11, "bold"), bg="lightgreen", command=self.submit_services)
        submit_btn.place(x=140, y=580)
        clear_btn = tk.Button(self.root, text="Clear", font=("Arial", 11), command=self.clear_service_form)
        clear_btn.place(x=280, y=580)
        back_btn = tk.Button(self.root, text="Back", font=("Arial", 11), command=self.back_to_post_login_from_external)
        back_btn.place(x=350, y=580)
        self.external_widgets.extend([submit_btn, clear_btn, back_btn])

    def _flatten_centers(self):
        flat = []
        for city, centers in self.evacuation_centers.items():
            for c in centers:
                flat.append(f"{city} - {c}")
        return flat

    def update_centers_by_location(self):
        loc = self.curr_loc_var.get().strip()
        if not loc:
            self.center_combo['values'] = self._flatten_centers()
            messagebox.showinfo("Centers", "Showing all evacuation centers.")
            return
        matched = None
        for city in self.evacuation_centers.keys():
            if city.lower() == loc.lower():
                matched = city
                break
        if matched:
            centers = self.evacuation_centers[matched]
            self.center_combo['values'] = [f"{matched} - {c}" for c in centers]
            if centers:
                self.center_combo.current(0)
            messagebox.showinfo("Centers", f"Nearest centers for {matched} shown.")
        else:
            self.center_combo['values'] = self._flatten_centers()
            messagebox.showinfo("Centers", f"No evacuation centers found for '{loc}'. Showing all centers.")

    def clear_service_form(self):
        for v in [self.disaster_var, self.food_var, self.medkits_var, self.curr_loc_var, self.selected_center_var]:
            v.set("")
        self.center_combo['values'] = self._flatten_centers()

    def back_to_post_login_from_external(self):
        for w in getattr(self, "external_widgets", []):
            try:
                w.destroy()
            except Exception:
                pass
        self.show_post_login_buttons()

    def submit_services(self):
        d_type = self.disaster_var.get().strip()
        food = self.food_var.get().strip()
        medkits = self.medkits_var.get().strip()
        location = self.curr_loc_var.get().strip()
        selected_center = self.selected_center_var.get().strip()
        if not all([d_type, food, medkits, location]):
            messagebox.showerror("Error", "Please fill all fields (Disaster Type, Food Packets, Medical Kits, Current Location).")
            return
        if not food.isdigit() or not medkits.isdigit():
            messagebox.showerror("Error", "Food Packets and Medical Kits must be integer numbers.")
            return
        user = self.current_user["name"] if self.current_user else "Unknown"
        add_service_to_db(self.conn, time.strftime("%Y-%m-%d %H:%M:%S"), user, d_type, int(food), int(medkits), location, selected_center if selected_center else "Not selected")
        messagebox.showinfo("Success", f"Services recorded.\nEvacuation center: {selected_center}")
        self.clear_service_form()

    def view_status_report(self):
        win = tk.Toplevel(self.root)
        win.title("Status Report")
        win.geometry("700x600")
        users = get_users_from_db(self.conn)
        services = get_services_from_db(self.conn)
        header = tk.Label(win, text=f"People: {len(users)}    Services: {len(services)}", font=("Arial", 12, "bold"))
        header.pack(pady=8)
        frame = tk.Frame(win)
        frame.pack(expand=True, fill='both', padx=8, pady=4)
        txt = tk.Text(frame, wrap="word")
        txt.pack(side="left", expand=True, fill="both")
        scrollbar = tk.Scrollbar(frame, command=txt.yview)
        scrollbar.pack(side="right", fill="y")
        txt.config(yscrollcommand=scrollbar.set)
        txt.insert(tk.END, "---- Registered People ----\n")
        for i, p in enumerate(users, start=1):
            txt.insert(tk.END, f"\nPerson #{i}\n")
            txt.insert(tk.END, f"Name: {p[0]}\nAge: {p[1]}\nLocation: {p[2]}\nPhone: {p[3]}\nEmail: {p[4]}\n---------------------------\n")
        txt.insert(tk.END, "\n\n---- Services Provided ----\n")
        for i, s in enumerate(services, start=1):
            txt.insert(tk.END, f"\nService #{i} at {s[0]}\nBy User: {s[1]}\nDisaster: {s[2]}\nFood Packets: {s[3]}\nMedical Kits: {s[4]}\nLocation: {s[5]}\nEvac Center: {s[6]}\n---------------------------\n")

    def sensor_alert_check(self):
        users = get_users_from_db(self.conn)
        if not users:
            messagebox.showinfo("No Data", "No registered people yet.")
            return
        idx = simpledialog.askinteger("Select Person", f"Enter person index (1 to {len(users)}):")
        if idx is None or idx < 1 or idx > len(users):
            messagebox.showerror("Error", "Invalid index.")
            return
        person = users[idx - 1]
        disaster = simpledialog.askstring("Disaster Type", "Enter disaster type (Flood/Earthquake/Fire):")
        if not disaster:
            return
        disaster = disaster.lower()
        alert_msg = ""
        if disaster == "flood":
            level = simpledialog.askinteger("Flood Sensor", "Enter current water level (in meters):")
            if level is None:
                return
            if level >= 5:
                alert_msg = "ALERT: High flood water level detected. Evacuate immediately!"
                messagebox.showwarning("ALERT", alert_msg)
            elif level >= 3:
                alert_msg = "Warning: Moderate flood level. Prepare for evacuation."
                messagebox.showinfo("Warning", alert_msg)
            else:
                alert_msg = "Status: Water level normal."
                messagebox.showinfo("Status", alert_msg)
        elif disaster == "earthquake":
                
            try:
                magnitude = float(simpledialog.askstring("Earthquake Sensor", "Enter tremor magnitude:"))
                if magnitude >= 6.0:
                    alert_msg = "ALERT: Strong earthquake tremors detected."
                    messagebox.showwarning("ALERT", alert_msg)
                elif magnitude >= 4.0:
                    alert_msg = "Warning: Moderate tremors detected."
                    messagebox.showinfo("Warning", alert_msg)
                else:
                    alert_msg = "Status: Tremors normal."
                    messagebox.showinfo("Status", alert_msg)
            except Exception:
                messagebox.showerror("Error", "Invalid input.")
                return
        elif disaster == "fire":
            level = simpledialog.askinteger("Fire Sensor", "Enter smoke level (1-10):")
            if level is None:
                return
            if level >= 7:
                alert_msg = "ALERT: High smoke levels detected. Evacuate!"
                messagebox.showwarning("ALERT", alert_msg)
            elif level >= 4:
                alert_msg = "Warning: Moderate smoke detected."
                messagebox.showinfo("Warning", alert_msg)
            else:
                alert_msg = "Status: Smoke level normal."
                messagebox.showinfo("Status", alert_msg)
        else:
            alert_msg = "No sensor data for this disaster type."
            messagebox.showinfo("Sensor", alert_msg)
        email_to = person[4]
        subject = f"Disaster Sensor Alert [{disaster.title()}]"
        sent = send_email_alert(email_to, subject, f"Dear {person[0]}, {alert_msg}")
        if sent:
            messagebox.showinfo("Email Sent", f"Sensor alert sent automatically to {email_to}.")
        else:
            messagebox.showerror("Email Error", f"Failed to send alert to {email_to}.")


                
    def show_recent_activities(self):
        window = tk.Toplevel(self.root)
        window.title("Recent Activities")
        window.geometry("400x700")
        recent_activities = [
            "Flood relief operations conducted in District A.",
            "Medical camp established at Village B, Maharashtra.",
            "Earthquake aid distribution completed in District C.",
            "Clean water supply setup in flood affected zones in Kolhapur.",
            "Volunteer ambulance services started at Satara.",
            "Food packet distribution in drought affected areas of Sangli.",
            "Community health awareness programs conducted in Solapur.",
        ]
        lbl_heading = tk.Label(window, text="Recent Activities", font=("Arial", 14, "bold"), fg="darkblue")
        lbl_heading.pack(pady=10)
        txt = tk.Text(window, wrap="word", font=("Arial", 12))
        txt.pack(expand=True, fill='both', padx=10, pady=10)
        for activity in recent_activities:
            txt.insert(tk.END, f"- {activity}\n\n")

def main():
    root = tk.Tk()
    app = DisasterManagementApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
