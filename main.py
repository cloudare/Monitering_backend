import os
import oracledb
from flask import Flask, request, render_template, redirect, url_for, send_file, flash,session,jsonify
from io import BytesIO
from datetime import datetime
import dbconnector as db
from werkzeug.security import check_password_hash
from datetime import timedelta
from functools import wraps
import base64
from math import ceil
from collections import defaultdict
import time
import threading
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.secret_key = "f82d2cf52736a67adf5c8e5eaa83426e38b44af4de6757c08a41221f4b123abc"  # Change this to a strong secret key
app.permanent_session_lifetime = timedelta(minutes=30)  # Session timeout
pending_commands = defaultdict(list)
command_outputs = {}
notifications_store = {}  # device_id: message
# Store which devices have acknowledged
acknowledged = set()
socketio = SocketIO(app, cors_allowed_origins="*")

@app.route("/")
def index():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    try:
        if request.method == 'POST':
            username = request.form['username']
            password = request.form['password']

            conn = db.get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT password_hash FROM admin_users WHERE username = :1", [username])
            user = cursor.fetchone()
            cursor.close()
            conn.close()

            if user and check_password_hash(user[0], password):
                session['username'] = username
                flash('Login successful!', 'success')
                return redirect(url_for('index'))
            else:
                flash('Invalid username or password', 'danger')

        return render_template('login.html')
    except Exception as e:
        flash(f'Something went wrong: {str(e)}', 'danger')
        return render_template('login.html')


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('You must log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


@app.route('/logout')
@login_required
def logout():
    session.pop('username', None)
    flash('Logged out successfully', 'info')
    return redirect(url_for('login'))


# ---- APP_CONFIG Management ----
# def get_app_config_pivot():
#     try:
#         conn = db.get_db()
#         cursor = conn.cursor()

#         cursor.execute("""
#             SELECT 
#                 username,
#                 screenshot_interval,
#                 history_interval,
#                 log_usage_interval,
#                 track_app_usage_interval,
#                 upload_app_usage_memory_interval,
#                 log_wifi_info,
#                 ip_address
#             FROM app_config
#             ORDER BY username
#         """)
        
#         rows = cursor.fetchall()
#         cursor.close()
#         conn.close()

#         configs = []
#         for row in rows:
#             configs.append({
#                 "username": row[0],
#                 "screenshot_interval": row[1],
#                 "history_interval": row[2],
#                 "log_usage_interval": row[3],
#                 "track_app_usage_interval": row[4],
#                 "upload_app_usage_memory_interval": row[5],
#                 "log_wifi_info": row[6],
#                 "ip_address": row[7]
#             })

#         return configs
#     except Exception as e:
#         flash(f'Something went wrong: {str(e)}', 'danger')


@app.route("/app_config")
@login_required
def app_config_list():
    try:
        page = int(request.args.get('page', 1))
        per_page = 10
        offset = (page - 1) * per_page

        conn = db.get_db()
        cur = conn.cursor()

        # Total records
        cur.execute("SELECT COUNT(*) FROM app_config")
        total_records = cur.fetchone()[0]
        total_pages = max(ceil(total_records / per_page), 1)

        # Pagination window (e.g. show 5 pages)
        window_size = 5
        half_window = window_size // 2
        start_page = max(1, page - half_window)
        end_page = min(total_pages, start_page + window_size - 1)
        page_range = range(start_page, end_page + 1)

        # cur.execute("""
        #     SELECT 
        #         id,
        #         username,
        #         screenshot_interval,
        #         history_interval,
        #         log_usage_interval,
        #         track_app_usage_interval,
        #         upload_app_usage_memory_interval,
        #         log_wifi_info,
        #         created_at,
        #         created_by,
        #         updated_at,
        #         updated_by,
        #         ip_address,
        #         Update_check_Interval
        #     FROM app_config
        #     ORDER BY id
        # """)
        # Fetch current page rows
        cur.execute(f"""
            SELECT 
                id,
                username,
                screenshot_interval,
                history_interval,
                log_usage_interval,
                track_app_usage_interval,
                upload_app_usage_memory_interval,
                log_wifi_info,
                created_at,
                created_by,
                updated_at,
                updated_by,
                ip_address,
                Update_check_Interval,
                screenshot_flag,
                history_flag,
                app_flag,
                wifi_flag,
                update_flag
            FROM app_config
            ORDER BY id
            OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY
        """, {'offset': offset, 'limit': per_page})

        rows = cur.fetchall()
        cur.close()
        conn.close()
        # print(rows)
        # Convert to list of dicts
        columns = [
            "id",
            "username",
            "screenshot_interval",
            "history_interval",
            "log_usage_interval",
            "track_app_usage_interval",
            "upload_app_usage_memory_interval",
            "log_wifi_info",
            "created_at",
            "created_by",
            "updated_at",
            "updated_by",
            "ip_address",
            "Update_check_Interval",
            "screenshot_flag",
            "history_flag",
            "app_flag",
            "wifi_flag",
            "update_flag"
        ]
        configs = [dict(zip(columns, row)) for row in rows]
        # return render_template("app_config_list.html", configs=configs)
        return render_template("app_config_list.html",
                               configs=configs,
                               current_page=page,
                               total_pages=total_pages,
                               page_range=page_range)
    except Exception as e:
        flash(f'Something went wrong: {str(e)}', 'danger')
        print(str(e))
        # return render_template("app_config_list.html", configs=[])
        return render_template("app_config_list.html", configs=[], current_page=1, total_pages=1, page_range=range(1, 2))


@app.route('/app_config/add', methods=['GET', 'POST'])
@login_required
def app_config_add_user():
    try:
        if request.method == 'POST':
            conn = db.get_db()
            cursor = conn.cursor()

            # Collect form data
            username = request.form['username']
            screenshot_interval = request.form['screenshot_interval']
            history_interval = request.form['history_interval']
            log_usage_interval = request.form['log_usage_interval']
            track_app_usage_interval = request.form['track_app_usage_interval']
            upload_app_usage_memory_interval = request.form['upload_app_usage_memory_interval']
            log_wifi_info = request.form['log_wifi_info']
            Update_check_Interval = request.form['Update_check_Interval']
            screenshot_flag = request.form['screenshot_flag']
            history_flag = request.form['history_flag']
            app_flag = request.form['app_flag']
            wifi_flag = request.form['wifi_flag']
            update_flag = request.form['update_flag']

            # Insert a single row
            cursor.execute("""
                INSERT INTO app_config (
                    username,
                    screenshot_interval,
                    history_interval,
                    log_usage_interval,
                    track_app_usage_interval,
                    upload_app_usage_memory_interval,
                    log_wifi_info,
                    created_by,
                    Update_check_Interval,
                    screenshot_flag,
                    history_flag,
                    app_flag,
                    wifi_flag,
                    update_flag
                ) VALUES (
                    :1, :2, :3, :4, :5, :6, :7, :8, :9, :10, :11, :12, :13, :14
                )
            """, (
                username,
                screenshot_interval,
                history_interval,
                log_usage_interval,
                track_app_usage_interval,
                upload_app_usage_memory_interval,
                log_wifi_info,
                "admin_portal",  # Created by
                Update_check_Interval,
                screenshot_flag,
                history_flag,
                app_flag,
                wifi_flag,
                update_flag
            ))

            conn.commit()
            cursor.close()
            conn.close()

            flash('User config added successfully!', 'success')
            return redirect(url_for('app_config_list'))

        return render_template('app_config_add_user.html')
    except Exception as e:
        flash(f'Something went wrong: {str(e)}', 'danger')
        return render_template('app_config_add_user.html')


@app.route('/app_config/edit/<username>', methods=['GET', 'POST'])
@login_required
def app_config_edit_user(username):
    try:
        conn = db.get_db()
        cursor = conn.cursor()

        if request.method == 'POST':
            # Extract form data
            screenshot_interval = request.form['screenshot_interval']
            history_interval = request.form['history_interval']
            log_usage_interval = request.form['log_usage_interval']
            track_app_usage_interval = request.form['track_app_usage_interval']
            upload_app_usage_memory_interval = request.form['upload_app_usage_memory_interval']
            log_wifi_info = str(request.form['log_wifi_info'])
            # ip_address = request.form['ip_address']
            Update_check_Interval = request.form['Update_check_Interval']
            screenshot_flag = int(request.form.get('screenshot_flag'))
            history_flag = int(request.form.get('history_flag'))
            app_flag = int(request.form.get('app_flag'))
            wifi_flag = int(request.form.get('wifi_flag'))
            update_flag = int(request.form.get('update_flag'))

            print(f"""UPDATE app_config
                SET screenshot_interval = {screenshot_interval},
                    history_interval = {history_interval},
                    log_usage_interval = {log_usage_interval},
                    track_app_usage_interval = {track_app_usage_interval},
                    upload_app_usage_memory_interval = {upload_app_usage_memory_interval},
                    log_wifi_info = '{log_wifi_info}',
                    updated_at = CURRENT_TIMESTAMP,
                    updated_by = 'admin_portal',
                    Update_check_Interval = {Update_check_Interval},
                    screenshot_flag = {screenshot_flag},
                    history_flag = {history_flag},
                    app_flag = {app_flag},
                    wifi_flag = {wifi_flag},
                    update_flag = {update_flag}
                WHERE username = '{username}'
            """)
            # Update row directly
            cursor.execute(f"""UPDATE app_config
                SET screenshot_interval = {screenshot_interval},
                    history_interval = {history_interval},
                    log_usage_interval = {log_usage_interval},
                    track_app_usage_interval = {track_app_usage_interval},
                    upload_app_usage_memory_interval = {upload_app_usage_memory_interval},
                    log_wifi_info = '{log_wifi_info}',
                    updated_at = CURRENT_TIMESTAMP,
                    updated_by = 'admin_portal',
                    Update_check_Interval = {Update_check_Interval},
                    screenshot_flag = {screenshot_flag},
                    history_flag = {history_flag},
                    app_flag = {app_flag},
                    wifi_flag = {wifi_flag},
                    update_flag = {update_flag}
                WHERE username = '{username}'
            """)
            # cursor.execute("""
            #     UPDATE app_config
            #     SET screenshot_interval = :1,
            #         history_interval = :2,
            #         log_usage_interval = :3,
            #         track_app_usage_interval = :4,
            #         upload_app_usage_memory_interval = :5,
            #         log_wifi_info = :6,
            #         updated_at = CURRENT_TIMESTAMP,
            #         updated_by = :7,
            #         Update_check_Interval = :9,
            #         screenshot_flag = :10,
            #         history_flag = :11,
            #         app_flag = :12,
            #         wifi_flag = :13,
            #         update_flag = :14
            #     WHERE username = :8
            # """, (
            #     screenshot_interval,
            #     history_interval,
            #     log_usage_interval,
            #     track_app_usage_interval,
            #     upload_app_usage_memory_interval,
            #     log_wifi_info,
            #     "admin_portal",  # Updated by
            #     username,
            #     Update_check_Interval,
            #     screenshot_flag,
            #     history_flag,
            #     app_flag,
            #     wifi_flag,
            #     update_flag
            # ))
            
            conn.commit()
            cursor.close()
            conn.close()

            flash('User config updated successfully!', 'success')
            return redirect(url_for('app_config_list'))
        
        # Load current config
        cursor.execute("""
            SELECT username, screenshot_interval, history_interval, log_usage_interval,
                track_app_usage_interval, upload_app_usage_memory_interval, log_wifi_info, ip_address, Update_check_Interval, screenshot_flag,
                history_flag,
                app_flag,
                wifi_flag,
                update_flag
            FROM app_config WHERE username = :1
        """, [username])

        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if not row:
            flash("No config found for this user!", "danger")
            return redirect(url_for('app_config_list'))

        user_config = {
            "username": row[0],
            "screenshot_interval": row[1],
            "history_interval": row[2],
            "log_usage_interval": row[3],
            "track_app_usage_interval": row[4],
            "upload_app_usage_memory_interval": row[5],
            "log_wifi_info": row[6],
            "ip_address" : row[7],
            "Update_check_Interval": row[8],
            "screenshot_flag" : row[9],
            "history_flag" : row[10],
            "app_flag" : row[11],
            "wifi_flag" : row[12],
            "update_flag" : row[13]
        }

        return render_template('app_config_edit_user.html', user_config=user_config)
    except Exception as e:
        flash(f'Something went wrong: {str(e)}', 'danger')
        return redirect(url_for('app_config_list'))


@app.route('/app_config/delete/<username>', methods=['GET'])
@login_required
def app_config_delete_user(username):
    try:
        conn = db.get_db()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM APP_CONFIG WHERE USERNAME = :1", [username])
        conn.commit()
        cursor.close()
        conn.close()

        flash(f'Config for {username} deleted successfully!', 'success')
        return redirect(url_for('app_config_list'))
    except Exception as e:
        flash(f'Something went wrong: {str(e)}', 'danger')


# ---- FILE_UPDATES Management ----
@app.route("/file_updates")
@login_required
def file_updates_list():
    try:
        conn = db.get_db()
        cur = conn.cursor()
        cur.execute("SELECT id, file_name, version,  creation_date, update_date, created_by, updated_by FROM file_updates")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return render_template("file_updates_list.html", rows=rows)
    except Exception as e:
        flash(f'Something went wrong: {str(e)}', 'danger')
        return render_template("file_updates_list.html", rows=[])
    

@app.route("/file_updates/upload", methods=["GET", "POST"])
@login_required
def file_updates_upload():
    try:
        if request.method == "POST":
            version_name = request.form.get("version_name")  # Get version name
            file = request.files["file"]
            if not file:
                flash("No file selected!", "danger")
                return redirect(url_for("file_updates_upload"))

            file_name = file.filename
            file_data = file.read()

            conn = db.get_db()
            cur = conn.cursor()
            # cur.execute("""
            #     INSERT INTO file_updates (file_name, version, file_data, created_by)
            #     VALUES (:1, :2, :3, :4)
            # """, (file_name,version_name, file_data, "admin_portal"))
            # Check if the file_name already exists in the table
            cur.execute("SELECT COUNT(*) FROM file_updates WHERE file_name = :1", [file_name])
            exists = cur.fetchone()[0]

            if exists:
                # Update the existing row
                cur.execute("""
                    UPDATE file_updates
                    SET version = :1,
                        file_data = :2,
                        update_date = CURRENT_TIMESTAMP,
                        updated_by = :3
                    WHERE file_name = :4
                """, (version_name, file_data, "admin_portal", file_name))
                flash(f"File '{file_name}' updated successfully!", "success")
            else:
                # Insert a new row
                cur.execute("""
                    INSERT INTO file_updates (file_name, version, file_data, created_by)
                    VALUES (:1, :2, :3, :4)
                """, (file_name, version_name, file_data, "admin_portal"))
                flash(f"File '{file_name}' uploaded successfully!", "success")

            conn.commit()
            cur.close()
            conn.close()
            # flash(f"File '{file_name}' uploaded successfully!", "success")
            return redirect(url_for("file_updates_list"))
        return render_template("file_updates_upload.html")
    except Exception as e:
        flash(f'Something went wrong: {str(e)}', 'danger')
        return redirect(url_for("file_updates_upload"))


@app.route("/file_updates/download/<int:file_id>")
@login_required
def file_updates_download(file_id):
    try:
        conn = db.get_db()
        cur = conn.cursor()
        cur.execute("SELECT file_name, file_data FROM file_updates WHERE id = :1", [file_id])
        row = cur.fetchone()

        if row:
            file_name, file_data = row
            # Convert LOB to bytes if needed
            if hasattr(file_data, "read"):
                file_data = file_data.read()
            cur.close()
            conn.close()
            return send_file(BytesIO(file_data), as_attachment=True, download_name=file_name)
        else:
            cur.close()
            conn.close()
            flash("File not found!", "danger")
            return redirect(url_for("file_updates_list"))
    except Exception as e:
        flash(f'Something went wrong: {str(e)}', 'danger')
        return redirect(url_for("file_updates_list"))


@app.route("/cloud_app_config/edit/<int:config_id>", methods=["GET", "POST"])
@login_required
def cloud_app_config_edit(config_id):
    try:
        conn = db.get_db()
        cur = conn.cursor()

        if request.method == "POST":
            username = request.form["username"]
            screenshot_interval = request.form["screenshot_interval"]
            history_interval = request.form["history_interval"]
            log_usage_interval = request.form["log_usage_interval"]
            track_app_usage_interval = request.form["track_app_usage_interval"]
            upload_app_usage_memory_interval = request.form["upload_app_usage_memory_interval"]
            log_wifi_info = request.form["log_wifi_info"]

            # Update record in CLOUD_APP_CONFIG table
            cur.execute("""
                UPDATE APP_CONFIG
                SET username = :1,
                    screenshot_interval = :2,
                    history_interval = :3,
                    log_usage_interval = :4,
                    track_app_usage_interval = :5,
                    upload_app_usage_memory_interval = :6,
                    log_wifi_info = :7,
                    updated_at = CURRENT_TIMESTAMP,
                    updated_by = :8
                WHERE id = :9
            """, (
                username,
                screenshot_interval,
                history_interval,
                log_usage_interval,
                track_app_usage_interval,
                upload_app_usage_memory_interval,
                log_wifi_info,
                "admin_portal",  # Who updated the record
                config_id
            ))

            conn.commit()
            cur.close()
            conn.close()
            flash("Configuration updated successfully!", "success")
            return redirect(url_for("app_config_list"))

        # GET request – fetch existing data
        cur.execute("""
            SELECT id,
                username,
                screenshot_interval,
                history_interval,
                log_usage_interval,
                track_app_usage_interval,
                upload_app_usage_memory_interval,
                log_wifi_info
            FROM APP_CONFIG
            WHERE id = :id
        """, [config_id])

        row = cur.fetchone()
        cur.close()
        conn.close()

        if not row:
            flash("Configuration not found!", "danger")
            return redirect(url_for("app_config_list"))

        return render_template("app_config_edit.html", config=row)
    except Exception as e:
        flash(f'Something went wrong: {str(e)}', 'danger')


@app.route("/screenshots")
def screenshots_redirect():
    """Redirect to first user's screenshots."""
    try:
        conn = db.get_db()
        cur = conn.cursor()
        cur.execute("SELECT MIN(user_id) FROM user_screenshots")
        first_user = cur.fetchone()[0]
        cur.close()
        conn.close()

        if not first_user:
            flash("No users found!", "danger")
            return render_template("screenshots_list.html", screenshots=[], users=[])

        return redirect(url_for("screenshots_by_userid", user_id=first_user))
    except Exception as e:
        flash(f"Error: {str(e)}", "danger")
        return render_template("screenshots_list.html", screenshots=[], users=[])


@app.route("/screenshots/user/<string:user_id>")
def screenshots_by_userid(user_id):
    """Show all screenshots for a specific user_id."""
    try:
        conn = db.get_db()
        cur = conn.cursor()

        # Pagination settings
        per_page = 5
        page = max(int(request.args.get("page", 1)), 1)  # Ensure page is at least 1
        offset = (page - 1) * per_page

        cur.execute("SELECT COUNT(*) FROM user_screenshots WHERE user_id = :1", [user_id])

        total_records = cur.fetchone()[0]
        total_pages = ceil(total_records / per_page)
        # rows = cur.fetchall()

        # Fetch paginated screenshots
        cur.execute("""
            SELECT id, user_id, created_at, screenshot
            FROM (
                SELECT id, user_id, created_at, screenshot
                FROM user_screenshots
                WHERE user_id = :1
                ORDER BY created_at DESC
            ) 
            OFFSET :2 ROWS FETCH NEXT :3 ROWS ONLY
        """, (user_id, offset, per_page))
        rows = cur.fetchall()

        screenshots = []
        for row in rows:
            screenshots.append({
                "id": row[0],
                "user_id": row[1],
                "created_at": row[2],
                "screenshot": row[3].decode() if isinstance(row[3], bytes) else row[3]
            })

        # Fetch distinct user_ids for dropdown
        cur.execute("SELECT DISTINCT user_id FROM user_screenshots ORDER BY user_id")
        # users = cur.fetchall()
        users = [u[0] for u in cur.fetchall()]

        # Compute pagination range
        window = 2  # show current_page ±2 pages
        start_page = max(1, page - window)
        end_page = min(total_pages, page + window)
        page_range = range(start_page, end_page + 1)

        # cur.close()
        # conn.close()

        # return render_template("screenshots_list.html", 
        #                        screenshots=screenshots, 
        #                        filter_user_id=user_id,
        #                        users=users)
        return render_template(
            "screenshots_list.html",
            screenshots=screenshots,
            filter_user_id=user_id,
            users=users,
            current_page=page,
            total_pages=total_pages,
            page_range=page_range
        )
    except Exception as e:
        print(str(e))
        flash(f"Error: {str(e)}", "danger")
        return render_template("screenshots_list.html", screenshots=[], users=[])


# @app.route("/screenshots/view/<int:screenshot_id>")
# def view_screenshot(screenshot_id):
#     """Serve screenshot image by ID."""
#     try:
#         conn = db.get_db()
#         cur = conn.cursor()
#         cur.execute("SELECT screenshot FROM user_screenshots WHERE id = :1", [screenshot_id])
#         row = cur.fetchone()
#         cur.close()
#         conn.close()

#         if row and row[0]:
#             blob_data = row[0]
#             if hasattr(blob_data, "read"):  # For Oracle LOBs
#                 blob_data = blob_data.read()
#             return send_file(BytesIO(blob_data), mimetype="image/png")
#         else:
#             flash("Screenshot not found!", "danger")
#             return redirect(url_for("screenshots_redirect"))
#     except Exception as e:
#         flash(f"Error: {str(e)}", "danger")
#         return redirect(url_for("screenshots_redirect"))
    

@app.route("/active_windows")
def active_windows_list():
    try:
        # Pagination
        page = int(request.args.get("page", 1))
        per_page = 10
        offset = (page - 1) * per_page

        # Filter
        user_id = request.args.get("user_id", None)

        conn = db.get_db()
        cur = conn.cursor()

        # Total count
        if user_id:
            cur.execute("SELECT COUNT(*) FROM user_active_windows WHERE user_id = :1", (user_id,))
        else:
            cur.execute("SELECT COUNT(*) FROM user_active_windows")
        total_rows = cur.fetchone()[0]
        total_pages = (total_rows + per_page - 1) // per_page

        # Fetch filtered & paginated data
        if user_id:
            cur.execute("""
                SELECT user_id, active_window, logged_at, created_at, created_by 
                FROM user_active_windows
                WHERE user_id = :1
                ORDER BY logged_at DESC
                OFFSET :2 ROWS FETCH NEXT :3 ROWS ONLY
            """, (user_id, offset, per_page))
        else:
            cur.execute("""
                SELECT user_id, active_window, logged_at, created_at, created_by 
                FROM user_active_windows
                ORDER BY logged_at DESC
                OFFSET :1 ROWS FETCH NEXT :2 ROWS ONLY
            """, (offset, per_page))

        rows = cur.fetchall()
        cur.close()
        conn.close()

        return render_template("active_windows_list.html", rows=rows,
                               current_page=page,
                               total_pages=total_pages,
                               filter_user_id=user_id)
    except Exception as e:
        flash(f"Something went wrong: {str(e)}", "danger")
        return render_template("active_windows_list.html", rows=[],
                               current_page=1, total_pages=1, filter_user_id=None)



@app.route("/app_usage")
def app_usage_list():
    try:
        # Pagination setup
        page = int(request.args.get("page", 1))
        per_page = 10
        offset = (page - 1) * per_page

        user_id = request.args.get("user_id", None)

        conn = db.get_db()
        cur = conn.cursor()

        # Total row count for pagination
        if user_id:
            cur.execute("""
                SELECT COUNT(*) FROM user_app_usage WHERE user_id = :user_id
            """, {"user_id": user_id})
        else:
            cur.execute("SELECT COUNT(*) FROM user_app_usage")

        total_rows = cur.fetchone()[0]
        total_pages = (total_rows + per_page - 1) // per_page

        # Paginated data query
        if user_id:
            cur.execute("""
                SELECT user_id, app_name, window_title, usage_time
                FROM user_app_usage
                WHERE user_id = :user_id
                ORDER BY usage_time DESC
                OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY
            """, {"user_id": user_id, "offset": offset, "limit": per_page})
        else:
            cur.execute("""
                SELECT user_id, app_name, window_title, usage_time
                FROM user_app_usage
                ORDER BY usage_time DESC
                OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY
            """, {"offset": offset, "limit": per_page})

        rows = cur.fetchall()
        cur.close()
        conn.close()

        return render_template("app_usage_list.html", rows=rows,
                               current_page=page,
                               total_pages=total_pages,
                               filter_user_id=user_id)
    except Exception as e:
        flash(f"Something went wrong: {str(e)}", "danger")
        return render_template("app_usage_list.html", rows=[],
                               current_page=1, total_pages=1, filter_user_id=None)



@app.route("/browser_history")
def browser_history_list():
    try:
        # Pagination setup
        page = int(request.args.get("page", 1))
        per_page = 10  # Number of rows per page
        offset = (page - 1) * per_page

        user_id = request.args.get("user_id", None)

        # print(user_id)
        conn = db.get_db()
        cur = conn.cursor()

         # Total count for pagination
        if user_id:
            cur.execute("""
                SELECT COUNT(*) FROM user_browser_history
                WHERE user_id = :user_id
            """, {"user_id": user_id})
        else:
            cur.execute("SELECT COUNT(*) FROM user_browser_history")

        total_rows = cur.fetchone()[0]
        total_pages = (total_rows + per_page - 1) // per_page

        # Paginated query
        if user_id:
            cur.execute("""
                SELECT user_id, browser, url, visited_at
                FROM user_browser_history
                WHERE user_id = :user_id
                ORDER BY visited_at DESC
                OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY
            """, {"limit": per_page, "offset": offset, "user_id": user_id})
        else:
            cur.execute("""
                SELECT user_id, browser, url, visited_at
                FROM user_browser_history
                ORDER BY visited_at DESC
                OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY
            """, {"limit": per_page, "offset": offset})

        # # Paginated query
        # cur.execute("""
        #     SELECT user_id, browser, url, visited_at
        #     FROM user_browser_history
        #     ORDER BY visited_at DESC
        #     OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY
        # """, {"limit": per_page, "offset": offset})

        rows = cur.fetchall()
        cur.close()
        conn.close()

        return render_template("browser_history_list.html", rows=rows,
                               current_page=page, total_pages=total_pages,
                               filter_user_id=user_id)
    except Exception as e:
        flash(f"Something went wrong: {str(e)}", "danger")
        return render_template("browser_history_list.html", rows=[], current_page=1,
                               total_pages=1, filter_user_id=user_id)


@app.route("/wifi_logs")
def wifi_logs_list():
    try:
        # Pagination setup
        page = int(request.args.get("page", 1))
        per_page = 10
        offset = (page - 1) * per_page

        # Filter
        user_id = request.args.get("user_id", None)

        conn = db.get_db()
        cur = conn.cursor()

        # Count total rows for pagination
        if user_id:
            cur.execute("SELECT COUNT(*) FROM user_wifi_logs WHERE user_id = :1", (user_id,))
        else:
            cur.execute("SELECT COUNT(*) FROM user_wifi_logs")
        total_rows = cur.fetchone()[0]
        total_pages = (total_rows + per_page - 1) // per_page

        # Fetch filtered and paginated data
        if user_id:
            cur.execute("""
                SELECT user_id, ssid, bssid, signal, logged_at
                FROM user_wifi_logs
                WHERE user_id = :1
                ORDER BY logged_at DESC
                OFFSET :2 ROWS FETCH NEXT :3 ROWS ONLY
            """, (user_id, offset, per_page))
        else:
            cur.execute("""
                SELECT user_id, ssid, bssid, signal, logged_at
                FROM user_wifi_logs
                ORDER BY logged_at DESC
                OFFSET :1 ROWS FETCH NEXT :2 ROWS ONLY
            """, (offset, per_page))

        rows = cur.fetchall()
        cur.close()
        conn.close()

        return render_template("wifi_logs_list.html", rows=rows,
                               current_page=page,
                               total_pages=total_pages,
                               filter_user_id=user_id)
    except Exception as e:
        flash(f"Something went wrong: {str(e)}", "danger")
        return render_template("wifi_logs_list.html", rows=[],
                               current_page=1, total_pages=1, filter_user_id=None)


@app.route("/external_devices")
def external_devices_list():
    try:
        # Pagination setup
        page = int(request.args.get("page", 1))
        per_page = 10
        offset = (page - 1) * per_page

        # Filter
        username = request.args.get("username", None)

        conn = db.get_db()
        cur = conn.cursor()

        # Count total rows for pagination
        if username:
            cur.execute("SELECT COUNT(*) FROM external_device WHERE username = :1", (username,))
        else:
            cur.execute("SELECT COUNT(*) FROM external_device")
        total_rows = cur.fetchone()[0]
        total_pages = (total_rows + per_page - 1) // per_page

        # Fetch filtered and paginated data
        if username:
            cur.execute("""
                SELECT username, ip_address, device_id, pnp_id, description, created_at, created_by, updated_at, updated_by
                FROM external_device
                WHERE username = :1
                ORDER BY created_at DESC
                OFFSET :2 ROWS FETCH NEXT :3 ROWS ONLY
            """, (username, offset, per_page))
        else:
            cur.execute("""
                SELECT username, ip_address, device_id, pnp_id, description, created_at, created_by, updated_at, updated_by
                FROM external_device
                ORDER BY created_at DESC
                OFFSET :1 ROWS FETCH NEXT :2 ROWS ONLY
            """, (offset, per_page))

        rows = cur.fetchall()
        cur.close()
        conn.close()

        return render_template("external_devices_list.html", rows=rows,
                               current_page=page,
                               total_pages=total_pages,
                               filter_username=username)
    except Exception as e:
        flash(f"Something went wrong: {str(e)}", "danger")
        return render_template("external_devices_list.html", rows=[],
                               current_page=1, total_pages=1, filter_username=None)


# @app.route("/api/notify", methods=["POST"])
# def receive_notification():
#     data = request.json
#     print(f"[NOTIFICATION] {data}")
#     # Optionally save to database or log file
#     return jsonify({"status": "received"}), 200

def get_latest_outputs():
    return command_outputs

def get_all_device_ids():
    try:
        conn = db.get_db()
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT USERNAME FROM APP_CONFIG")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        device_ids = [row[0] for row in rows]
        print(device_ids)
        return device_ids
    except Exception as e:
        print(str(e))


# @app.route('/remote')
@app.route("/remote", methods=["GET", "POST"])
def remote():
    try:
        device_ids = get_all_device_ids()  # You must define this function to fetch IDs from DB or elsewhere
        output = get_latest_outputs()      # If needed
        return render_template("remote.html", device_ids=device_ids, output=output)
    except Exception as e:
        print(str(e))

@app.route('/send_command', methods=["POST"])
def send_command():
    try:
        device_id = request.form["device_id"]
        command = request.form["command"]
        pending_commands[device_id].append(command)
        return redirect(url_for('remote'))
    except Exception as e:
        print(str(e))

@app.route("/api/get_command")
def get_command():
    try:
        device_id = request.args.get("device_id")
        # cmd = pending_commands.pop(device_id, None) 
        # return jsonify({"command": cmd} if cmd else {})
        cmd = None
        if pending_commands[device_id]:
            cmd = pending_commands[device_id].pop(0)
        return jsonify({"command": cmd} if cmd else {})
    except Exception as e:
        print(str(e))

@app.route("/api/send_output", methods=["POST"])
def receive_output():
    try:
        data = request.json
        print(data)
        device_id = data["device_id"]
        output = data["output"]
        command = data["command"]
        command_outputs[device_id] = {
            "user": data.get("user", "unknown"),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "output": output,
            "command": command
        }
        return jsonify({"status": "received"})
    except Exception as e:
        print(str(e))


@app.route('/notifications')
def notifications_page():
    device_ids = get_all_device_ids()
    return render_template("notifications.html", device_ids=device_ids, acknowledged=acknowledged)


@app.route('/send_notification', methods=["POST"])
def send_notification():
    device_id = request.form["device_id"]
    message = request.form["message"]
    notifications_store[device_id] = message
    # return redirect(url_for('notifications_page'))
    # Mark as sent (optional, if you want to show "sent" before user receives)
    acknowledged.discard(device_id)  # Reset any previous acknowledgment

    # Store a flash message or log that admin sent the notification
    flash(f"📤 Notification sent to {device_id}", "info")
    
    return redirect(url_for('notifications_page'))  # Or wherever your page is


@app.route('/api/get_notification')
def get_notification():
    device_id = request.args.get("device_id")
    msg = notifications_store.pop(device_id, None)
    return jsonify({"message": msg} if msg else {})


@app.route('/api/ack_notification', methods=['POST'])
def ack_notification():
    data = request.get_json()
    device_id = data.get("device_id")
    if device_id:
        acknowledged.add(device_id)
        return jsonify({"status": "acknowledged"}), 200
    return jsonify({"error": "Missing device_id"}), 400
    # if device_id in acknowledged:
    #     return jsonify({"acknowledged": True})
    # return jsonify({"acknowledged": False})


@app.route('/api/check_acknowledgement')
def check_acknowledgement():
    device_id = request.args.get("device_id")
    if device_id in acknowledged:
        return jsonify({"acknowledged": True})
    return jsonify({"acknowledged": False})


def delete_old_data():
    cutoff_date = datetime.now() - timedelta(days=7)  # 7 days ago
    cutoff_str = cutoff_date.strftime("%Y-%m-%d %H:%M:%S")  # Oracle-friendly string

    tables = [
        "user_screenshots",
        "user_active_windows",
        "user_app_usage",
        "user_browser_history",
        "user_wifi_logs",
        "external_device"
    ]

    conn = db.get_db()
    cursor = conn.cursor()

    try:
        for table in tables:
            query = f"DELETE FROM {table} WHERE created_at < TO_DATE(:cutoff, 'YYYY-MM-DD HH24:MI:SS')"
            print(query)
            cursor.execute(query, {"cutoff": cutoff_str})
            print(f"Deleted old data from {table}")

        conn.commit()
        print("Old data deletion complete.")
    except Exception as e:
        print("Error deleting data:", e)
        conn.rollback()
    finally:
        cursor.close()
        conn.close()


def schedule_deletion():
    """Run deletion every 24 hours in background."""
    while True:
        delete_old_data()
        time.sleep(86400)  # 24 hours


# Start background deletion when Flask starts
threading.Thread(target=schedule_deletion, daemon=True).start()

# ------------------ Run -------------------
if __name__ == "__main__":
    from pyngrok import conf, ngrok
    conf.get_default().auth_token = "2h8hVm4h8eU4vrlVgyCXZyYjwXG_31bxvzDPmabEAeLGHi1WS"
    conf.get_default().check_for_updates = False
    public_url = ngrok.connect(addr="127.0.0.1:5000", bind_tls=True)
    print(f"Ngrok URL → {public_url}")
    # init_db()
    # add_user("agent2", "password2", "agent-2")

    socketio.run(app, host="0.0.0.0", port=5000)
    # app.run(debug=True, host="0.0.0.0", port=3000)