from app import create_app, db
from flask_ckeditor import CKEditor

app = create_app()
ckeditor = CKEditor(app)

@app.shell_context_processor
def make_shell_context():
    return {'db': db}
