from flask import Flask, render_template, request, abort, make_response, jsonify, redirect, url_for, send_from_directory
from werkzeug.utils import secure_filename
import os
import pandas as pd

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
        print(file)
        if 'file' not in request.files:
          return 'No file part in the request', 400
        if file.filename == '':
          return 'No selected file', 400
        if file and not allowed_file(file.filename):
          return 'File type not allowed', 400
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            
            print("filename", file)
            file.save(os.path.join(basedir, app.config['UPLOAD_FOLDER'], filename))
            
            filex = os.path.join(basedir,app.config['UPLOAD_FOLDER'], filename)
            print(filex)
            data_csv = pd.read_csv(os.path.join(basedir, app.config['UPLOAD_FOLDER'], filename))
            data_csv['Time'] = pd.to_datetime(data_csv['Time'], format='%d-%m-%Y %H:%M:%S')
            data_csv['Date'] = data_csv['Time'].dt.date
            sorted_data = data_csv.groupby(['Name', 'Date']).agg(
                earliest_time=('Time', 'min'),
                latest_time=('Time', 'max')
            ).reset_index()
            sorted_data['hours_difference'] = (sorted_data['latest_time'] - sorted_data['earliest_time'])
            sorted_data['hours_difference_str'] = sorted_data['hours_difference'].apply(lambda x: f"{x.components.hours:02}:{x.components.minutes:02}")
            
            # Identify overtime
            # Calculate overtime
            def calculate_overtime(time_diff):
                if time_diff.components.hours >= 9:
                    overtime_seconds = (time_diff - pd.Timedelta(hours=9)).total_seconds()
                    overtime_hours = int(overtime_seconds // 3600)
                    overtime_minutes = int((overtime_seconds % 3600) // 60)
                    return f"{overtime_hours:02}:{overtime_minutes:02}"
                else:
                    return "00:00"
            sorted_data['overtime'] = sorted_data['hours_difference'].apply(calculate_overtime)
            
            # Here you should save the file
            # file.save('./uploaded', filename)
            try:
                sorted_data.to_csv( os.path.join(basedir, app.config['DOWNLOAD_FOLDER'], 'sorted.csv'), index=False)
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
    app.run(host='127.0.0.1', port=5000, debug=True)