from flask_restful import Resource
from flask import render_template
from flask import flash


class WebStatus(Resource):
    @classmethod
    def error(cls, errstr):
        flash(errstr)
        return render_template('error.html')

    @classmethod
    def status(cls):
        return render_template('status.html')
