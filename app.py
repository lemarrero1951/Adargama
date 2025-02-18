import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, SelectField, IntegerField, TextAreaField
from wtforms.validators import DataRequired, NumberRange
from flask_wtf.csrf import CSRFProtect
from flask_migrate import Migrate
from flask_wtf.file import FileField, FileAllowed
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Configuración de la aplicación
app.secret_key = os.getenv("SECRET_KEY", "defaultsecretkey")

# Configuración de la base de datos SQLite
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(BASE_DIR, "barrancos.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Configuración de la carpeta de subida de imágenes
app.config["UPLOAD_FOLDER"] = os.path.join(BASE_DIR, "static", "uploads")

# Inicialización de extensiones
db = SQLAlchemy(app)
migrate = Migrate(app, db)
csrf = CSRFProtect(app)

# Modelo de datos con __tablename__ y extend_existing para evitar redefiniciones
class Barranco(db.Model):
    __tablename__ = 'barranco'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False, unique=True)
    ubicacion = db.Column(db.String(200), nullable=False)
    dificultad = db.Column(db.String(50), nullable=False)
    num_rapeles = db.Column(db.Integer, nullable=False)
    metros_rapeles = db.Column(db.JSON, nullable=False)  # Se espera una lista de números
    volado = db.Column(db.String(10), nullable=False)
    imagen = db.Column(db.String(200), nullable=True)       # Nombre del archivo de imagen
    comentarios = db.Column(db.Text, nullable=True)         # Campo para comentarios

    def __repr__(self):
        return f"<Barranco {self.nombre}>"

# Formulario para agregar/editar barrancos
class BarrancoForm(FlaskForm):
    nombre = StringField("Nombre", validators=[DataRequired()])
    ubicacion = StringField("Ubicación", validators=[DataRequired()])
    dificultad = SelectField("Dificultad", choices=[("Baja", "Baja"), ("Media", "Media"), ("Alta", "Alta")],
                              validators=[DataRequired()])
    num_rapeles = IntegerField("Número de rápeles",
                               validators=[DataRequired(), NumberRange(min=1, message="Debe ser al menos 1")])
    metros_rapeles = TextAreaField("Metros de cada rápel (separados por comas)", validators=[DataRequired()])
    volado = SelectField("¿Hay volado?", choices=[("Sí", "Sí"), ("No", "No")], validators=[DataRequired()])
    imagen = FileField("Fotografía del Barranco", validators=[
        FileAllowed(["jpg", "jpeg", "png"], "Solo se permiten imágenes!")
    ])
    comentarios = TextAreaField("Comentarios")
    submit = SubmitField("Guardar")

# Ruta principal: listado de barrancos
@app.route("/")
def index():
    barrancos = Barranco.query.all()
    return render_template("index.html", barrancos=barrancos)

# Ruta para agregar un nuevo barranco
@app.route("/agregar", methods=["GET", "POST"])
def agregar():
    form = BarrancoForm()
    if form.validate_on_submit():
        # Verificar que no exista un barranco con el mismo nombre
        if Barranco.query.filter_by(nombre=form.nombre.data).first():
            flash("Ya existe un barranco con ese nombre.", "danger")
            return render_template("form.html", form=form, accion="Agregar")
        
        # Convertir la cadena de metros a una lista de float
        try:
            metros_list = [float(x.strip()) for x in form.metros_rapeles.data.split(",") if x.strip() != ""]
        except ValueError:
            flash("Error al convertir los metros de rápel. Use números separados por comas.", "danger")
            return render_template("form.html", form=form, accion="Agregar")
        
        if len(metros_list) != form.num_rapeles.data:
            flash("La cantidad de metros no coincide con el número de rápeles.", "danger")
            return render_template("form.html", form=form, accion="Agregar")
        
        nuevo_barranco = Barranco(
            nombre=form.nombre.data,
            ubicacion=form.ubicacion.data,
            dificultad=form.dificultad.data,
            num_rapeles=form.num_rapeles.data,
            metros_rapeles=metros_list,
            volado=form.volado.data,
            comentarios=form.comentarios.data
        )
        
        # Procesar la imagen si se sube alguna
        if form.imagen.data:
            filename = secure_filename(form.imagen.data.filename)
            image_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            form.imagen.data.save(image_path)
            nuevo_barranco.imagen = filename
        
        db.session.add(nuevo_barranco)
        db.session.commit()
        flash("Barranco agregado exitosamente.", "success")
        return redirect(url_for("index"))
    
    return render_template("form.html", form=form, accion="Agregar")

# Ruta para editar un barranco existente
@app.route("/editar/<int:id>", methods=["GET", "POST"])
def editar(id):
    barranco = Barranco.query.get_or_404(id)
    form = BarrancoForm(obj=barranco)
    if request.method == "GET":
        # Prellenar el campo de metros_rapeles como cadena separada por comas
        form.metros_rapeles.data = ", ".join(str(x) for x in barranco.metros_rapeles)
    if form.validate_on_submit():
        # Verificar que si se cambia el nombre, no se duplique
        if form.nombre.data != barranco.nombre and Barranco.query.filter_by(nombre=form.nombre.data).first():
            flash("Ya existe un barranco con ese nombre.", "danger")
            return render_template("form.html", form=form, accion="Editar")
        
        try:
            metros_list = [float(x.strip()) for x in form.metros_rapeles.data.split(",") if x.strip() != ""]
        except ValueError:
            flash("Error al convertir los metros de rápel. Use números separados por comas.", "danger")
            return render_template("form.html", form=form, accion="Editar")
        
        if len(metros_list) != form.num_rapeles.data:
            flash("La cantidad de metros no coincide con el número de rápeles.", "danger")
            return render_template("form.html", form=form, accion="Editar")
        
        # Actualizar campos
        barranco.nombre = form.nombre.data
        barranco.ubicacion = form.ubicacion.data
        barranco.dificultad = form.dificultad.data
        barranco.num_rapeles = form.num_rapeles.data
        barranco.metros_rapeles = metros_list
        barranco.volado = form.volado.data
        barranco.comentarios = form.comentarios.data
        
        # Procesar una nueva imagen si se proporciona
        if form.imagen.data:
            filename = secure_filename(form.imagen.data.filename)
            image_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            form.imagen.data.save(image_path)
            barranco.imagen = filename
        
        db.session.commit()
        flash("Barranco actualizado exitosamente.", "success")
        return redirect(url_for("index"))
    
    return render_template("form.html", form=form, accion="Editar")

# Ruta para eliminar un barranco
@app.route("/eliminar/<int:id>", methods=["POST"])
def eliminar(id):
    barranco = Barranco.query.get_or_404(id)
    db.session.delete(barranco)
    db.session.commit()
    flash("Barranco eliminado.", "danger")
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)