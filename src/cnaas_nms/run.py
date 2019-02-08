from cnaas_nms.api import app

# Workaround for bug with reloader https://github.com/pallets/flask/issues/1246
import os
os.environ['PYTHONPATH'] = os.getcwd()

if __name__ == '__main__':
    app.run(debug=True)
