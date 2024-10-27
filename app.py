from flask import Flask, request, jsonify, send_from_directory, render_template, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine, Column, Integer, String, Float, Text
from sqlalchemy.orm import scoped_session, sessionmaker
from geoalchemy2 import Geometry
from geoalchemy2.functions import ST_AsGeoJSON
from geoalchemy2.shape import from_shape
from shapely.geometry import shape, Polygon
import json
import os
from werkzeug.utils import secure_filename
import geopandas as gpd
import logging
from logging.handlers import RotatingFileHandler
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Length, EqualTo
from flask_bcrypt import Bcrypt
import time
from sqlalchemy.exc import IntegrityError
import random
import string
from flask_migrate import Migrate

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = 'your_secret_key'  # Change this to a random secret key

# Set up logging
if not os.path.exists('logs'):
    os.mkdir('logs')
file_handler = RotatingFileHandler('logs/app.log', maxBytes=10240, backupCount=10)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
))
file_handler.setLevel(logging.INFO)
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)
app.logger.info('Application startup')

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:1234@localhost/bibiani_spatial_planning'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
ALLOWED_EXTENSIONS = {'geojson', 'png', 'jpg', 'jpeg', 'gif', 'tif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max-limit

# Initialize database and session
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'  # Redirect to login page if not logged in
migrate = Migrate(app, db)

# User model
class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)

# Plot model
class Plot(db.Model):
    __tablename__ = 'plots'
    id = db.Column(db.Integer, primary_key=True)
    plot_number = db.Column(db.String(100), nullable=False, unique=True)
    owner_name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    area_sqm = db.Column(db.Float, nullable=False)
    compliance_status = db.Column(db.String(50), nullable=False)
    image_path = db.Column(db.String(200), nullable=True)
    land_use = db.Column(db.String(100), nullable=True)
    development_status = db.Column(db.String(100), nullable=True)
    additional_info = db.Column(db.Text, nullable=True)
    geom = db.Column(Geometry(geometry_type='POLYGON', srid=4326))

    def to_dict(self):
        return {
            'id': self.id,
            'plot_number': self.plot_number,
            'owner_name': self.owner_name,
            'address': self.address,
            'area_sqm': self.area_sqm,
            'compliance_status': self.compliance_status,
            'image_path': self.image_path,
            'land_use': self.land_use,
            'development_status': self.development_status,
            'additional_info': self.additional_info,
            'geom': json.loads(db.session.scalar(ST_AsGeoJSON(self.geom)))
        }

# Cadastra model
class Cadastra(db.Model):
    __tablename__ = 'cadastra'
    id = db.Column(db.Integer, primary_key=True)
    plot_number = db.Column(db.String(100), nullable=False)
    owner_name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    area_sqm = db.Column(db.Float, nullable=False)
    compliance_status = db.Column(db.String(50), nullable=False)
    land_use = db.Column(db.String(100), nullable=True)
    development_status = db.Column(db.String(100), nullable=True)
    additional_info = db.Column(db.Text, nullable=True)
    geom = db.Column(Geometry(geometry_type='POLYGON', srid=4326))
    custom_coordinates = db.Column(db.Text, nullable=True)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Registration form
class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=2, max=150)])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Sign Up')

# Login form
class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

# Routes for user authentication
@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        new_user = User(username=form.username.data, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        flash('Your account has been created! You can now log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Login Unsuccessful. Please check username and password', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/uploads/<path:filename>')
def serve_static(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/bibiani_layout', methods=['GET'])
def get_bibiani_layout():
    try:
        shapefile_path = 'data/shapefiles/bibiani_layout.shp'
        if not os.path.exists(shapefile_path):
            return jsonify({"error": "Shapefile not found"}), 404

        gdf = gpd.read_file(shapefile_path)
        if gdf.empty:
            return jsonify({"error": "Shapefile is empty"}), 404

        gdf = gdf.to_crs(epsg=4326)
        geojson_data = json.loads(gdf.to_json())
        return jsonify(geojson_data)
    except Exception as e:
        app.logger.error(f"Error in get_bibiani_layout: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/plots', methods=['GET'])
@login_required
def get_plots():
    try:
        plots = Plot.query.all()
        return jsonify([plot.to_dict() for plot in plots])
    except Exception as e:
        app.logger.error(f"Error in get_plots: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/plots', methods=['POST'])
@login_required
def create_plot():
    try:
        data = request.form
        file = request.files.get('image')
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            image_url = url_for('serve_static', filename=filename, _external=True)
        else:
            image_url = None
        
        geom = shape(json.loads(data['geom']))
        
        # Generate a unique plot number if not provided or if it already exists
        plot_number = data.get('plot_number')
        if not plot_number:
            plot_number = generate_unique_plot_number()
        
        new_plot = Plot(
            plot_number=plot_number,
            owner_name=data['owner_name'],
            address=data['address'],
            area_sqm=float(data['area_sqm']),
            compliance_status=data['compliance_status'],
            image_path=image_url,
            geom=from_shape(geom, srid=4326),
            land_use=data.get('land_use'),
            development_status=data.get('development_status'),
            additional_info=data.get('additional_info')
        )
        
        db.session.add(new_plot)
        db.session.commit()

        app.logger.info(f'Plot created successfully: {new_plot.plot_number}')
        return jsonify({"message": "Plot created successfully", "plot_id": new_plot.id, "plot_number": new_plot.plot_number})
    except IntegrityError as e:
        db.session.rollback()
        if "uq_plots_plot_number" in str(e):
            new_plot_number = generate_unique_plot_number()
            return jsonify({"error": "Plot number already exists", "suggested_plot_number": new_plot_number}), 409
        else:
            app.logger.error(f"Error in create_plot: {str(e)}", exc_info=True)
            return jsonify({"error": str(e)}), 500
    except Exception as e:
        app.logger.error(f"Error in create_plot: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/plots/<int:id>', methods=['GET'])
@login_required
def get_plot(id):
    try:
        plot = Plot.query.get_or_404(id)
        return jsonify(plot.to_dict())
    except Exception as e:
        app.logger.error(f"Error in get_plot: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/plots/<int:id>', methods=['PUT'])
@login_required
def update_plot(id):
    try:
        plot = Plot.query.get_or_404(id)
        data = request.form
        file = request.files.get('image')
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            plot.image_path = url_for('serve_static', filename=filename, _external=True)

        geom = shape(json.loads(data['geom']))
        plot.plot_number = data['plot_number']
        plot.owner_name = data['owner_name']
        plot.address = data['address']
        plot.area_sqm = float(data['area_sqm'])
        plot.compliance_status = data['compliance_status']
        plot.geom = from_shape(geom, srid=4326)
        plot.land_use = data.get('land_use')
        plot.development_status = data.get('development_status')
        plot.additional_info = data.get('additional_info')

        db.session.commit()

        app.logger.info(f'Plot updated successfully: {plot.plot_number}')
        return jsonify({"message": "Plot updated successfully", "plot": plot.to_dict()})
    except Exception as e:
        app.logger.error(f"Error in update_plot: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/plots/<int:id>', methods=['DELETE'])
@login_required
def delete_plot(id):
    try:
        plot = Plot.query.get_or_404(id)
        db.session.delete(plot)
        db.session.commit()

        app.logger.info(f'Plot deleted successfully: {plot.plot_number}')
        return jsonify({"message": "Plot deleted successfully"})
    except Exception as e:
        app.logger.error(f"Error in delete_plot: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/save_polygon', methods=['POST'])
@login_required
def save_polygon():
    try:
        data = request.get_json()
        coords = data.get('geom')

        # Validate coordinates
        if not coords or len(coords) < 3:
            return jsonify({"error": "At least three coordinates are required."}), 400

        # Convert coordinates to a string representation
        coords_str = json.dumps(coords)

        # For now, we'll just return the coordinates as a success message
        # In a real application, you might want to save this to a temporary storage or session
        return jsonify({"message": "Polygon coordinates received", "coordinates": coords_str}), 200

    except Exception as e:
        app.logger.error(f"Error in save_polygon: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/save_cadastra', methods=['POST'])
@login_required
def save_cadastra():
    try:
        data = request.get_json()
        app.logger.info(f"Received data: {data}")  # Log the received data
        coords = data.get('geom')

        # Ensure coordinates are valid
        if not coords or len(coords) < 3:
            return jsonify({"error": "At least three coordinates are required."}), 400

        # Create a polygon from the coordinates
        polygon = Polygon([(coord[1], coord[0]) for coord in coords])  # [Lng, Lat] format

        new_cadastra = Cadastra(
            plot_number=data.get('plot_number'),
            owner_name=data.get('owner_name'),
            address=data.get('address'),
            area_sqm=float(data.get('area_sqm')),
            compliance_status=data.get('compliance_status'),
            land_use=data.get('land_use'),
            development_status=data.get('development_status'),
            additional_info=data.get('additional_info'),
            geom=from_shape(polygon, srid=4326),
            custom_coordinates=json.dumps(coords)
        )
        db.session.add(new_cadastra)
        db.session.commit()

        app.logger.info(f'Cadastra entry saved successfully: {new_cadastra.plot_number}')
        return jsonify({"message": "Cadastra entry saved successfully", "cadastra_id": new_cadastra.id}), 201
    except Exception as e:
        app.logger.error(f"Error in save_cadastra: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.errorhandler(404)
def not_found_error(error):
    return jsonify({"error": "Not Found"}), 404

@app.errorhandler(500)
def internal_error(error):
    app.logger.error('Server Error: %s', (error), exc_info=True)
    db.session.rollback()
    return jsonify({"error": "Internal Server Error"}), 500

@app.teardown_appcontext
def shutdown_session(exception=None):
    db.session.remove()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_unique_plot_number():
    while True:
        plot_number = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        if not Plot.query.filter_by(plot_number=plot_number).first():
            return plot_number

def save_as_shapefile(cadastra):
    try:
        # Create a GeoDataFrame
        gdf = gpd.GeoDataFrame({
            'plot_number': [cadastra.plot_number],
            'owner_name': [cadastra.owner_name],
            'address': [cadastra.address],
            'area_sqm': [cadastra.area_sqm],
            'compliance_status': [cadastra.compliance_status],
            'land_use': [cadastra.land_use],
            'development_status': [cadastra.development_status],
            'additional_info': [cadastra.additional_info]
        }, geometry=[cadastra.geom])

        # Define the shapefile path
        shapefile_path = os.path.join('shapefiles', f'cadastra_{cadastra.id}.shp')

        # Save the GeoDataFrame as a shapefile
        gdf.to_file(shapefile_path, driver='ESRI Shapefile')
        app.logger.info(f'Shapefile created successfully: {shapefile_path}')
    except Exception as e:
        app.logger.error(f"Error saving shapefile: {str(e)}", exc_info=True)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # This will create the new column
    app.run(debug=True, host='127.0.0.1', port=5001)