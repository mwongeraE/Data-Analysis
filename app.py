from flask import Flask, render_template, request, abort, make_response, jsonify, redirect, url_for, send_from_directory
from werkzeug.utils import secure_filename
import os
import pandas as pd
from datetime import datetime, timedelta

app = Flask(__name__)

app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB
app.config['UPLOAD_FOLDER'] = './uploaded'
app.config['DOWNLOAD_FOLDER'] = './csv'
basedir = os.path.abspath(os.path.dirname(__file__))

@app.route('/')
def home():
    return render_template('upload_form.html')

@app.route('/uploads/<name>')
def download_file(name):
    return send_from_directory(app.config["DOWNLOAD_FOLDER"], name)
  
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' in request.files:
        file = request.files['file']
        if file.filename == '':
            return 'No selected file', 400
        if file and not allowed_file(file.filename):
            return 'File type not allowed', 400
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(basedir, app.config['UPLOAD_FOLDER'], filename))
            
            # Read the additional form data
            start_date_str = request.form.get('start_date')
            end_date_str = request.form.get('end_date')
            hours = request.form.get('hours')
            
            # Convert the dates to datetime objects
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
            
            # Read the uploaded CSV file
            filex = os.path.join(basedir, app.config['UPLOAD_FOLDER'], filename)
            data_csv = pd.read_csv(filex)
            data_csv['Time'] = pd.to_datetime(data_csv['Time'], dayfirst=True)
            data_csv['Date'] = data_csv['Time'].dt.date
            
            # Generate a complete DataFrame of all weekdays between the start and end dates
            all_dates = pd.DataFrame({'Date': pd.date_range(start=start_date, end=end_date)})
            all_dates = all_dates[all_dates['Date'].dt.weekday != 6]
            all_dates['Date'] = all_dates['Date'].dt.date
            
            # Group the data by employee and date, and calculate the earliest and latest times
            data_csv = data_csv.groupby(['Emp ID', 'Name', 'Date'], as_index=False).agg(
                earliest_time=('Time', 'min'),
                latest_time=('Time', 'max')
            ).reset_index(drop=True)
            data_csv['hours_difference'] = (data_csv['latest_time'] - data_csv['earliest_time'])
            data_csv['hours_difference_str'] = data_csv['hours_difference'].apply(lambda x: f"{x.components.hours:02}:{x.components.minutes:02}")
            
            # Extract unique employee details for generating absence entries
            employees = data_csv[['Emp ID', 'Name']].drop_duplicates()
            
            # Merge all dates with employee data to generate all possible combinations
            all_combinations = pd.merge(employees, all_dates, how='cross')
            
            # Merge all combinations with grouped data to identify absences
            full_data = pd.merge(all_combinations, data_csv, on=['Emp ID', 'Name', 'Date'], how='left')
            
            # Fill NaN values for absence entries
            full_data['earliest_time'].fillna(pd.NaT, inplace=True)
            full_data['latest_time'].fillna(pd.NaT, inplace=True)
            full_data['hours_difference'].fillna(pd.Timedelta(seconds=0), inplace=True)
            full_data['hours_difference_str'].fillna("00:00", inplace=True)
            full_data['Attendance State'] = full_data['earliest_time'].apply(lambda x: 'Present' if pd.notna(x) else 'Absent')
            
            # Calculate overtime with Saturday rule
            def calculate_overtime(row):
                if row['Attendance State'] == 'Absent':
                    return "00:00"
                
                time_diff = row['hours_difference']
                if pd.notnull(time_diff):
                    # Check for Saturdays
                    if row['Date'].weekday() == 5:  # Saturday
                        threshold = pd.Timedelta(hours=6)
                    else:  # Other weekdays
                        threshold = pd.Timedelta(hours=int(hours))
                    if time_diff > threshold:
                        overtime_seconds = (time_diff - threshold).total_seconds()
                        overtime_hours = int(overtime_seconds // 3600)
                        overtime_minutes = int((overtime_seconds % 3600) // 60)
                        return f"{overtime_hours:02}:{overtime_minutes:02}"
                return "00:00"

            full_data['overtime'] = full_data.apply(calculate_overtime, axis=1)

            # Sort and save the data
            full_data.sort_values(by=['Emp ID', 'Date'], inplace=True)
            try:
                output_path = os.path.join(basedir, app.config['DOWNLOAD_FOLDER'], 'sorted.csv')
                full_data.to_csv(output_path, index=False)
            except Exception as e:
                return f'Error saving file: {str(e)}', 500
            
            return redirect(url_for('download_file', name='sorted.csv'))

    return 'No file uploaded'
  
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'csv'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
           
@app.errorhandler(413)
def too_large(e):
    return make_response(jsonify(message="File is too large"), 413)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)