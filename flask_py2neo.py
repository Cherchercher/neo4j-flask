from __future__ import absolute_import
from flask import current_app
from py2neo import Graph

__version__ = "0.2.0"


class Py2Neo(object):
    def __init__(self, app=None):
        self.app = app
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        """This callback can be used to initialize an application for the
        use with this database setup.
        """
        app.config.setdefault("PY2NEO_BOLT", False)
        app.config.setdefault("PY2NEO_SECURE", False)
        app.config.setdefault("PY2NEO_HOST", "localhost")
        app.config.setdefault("PY2NEO_HTTP_PORT", 7474)
        app.config.setdefault("PY2NEO_HTTPS_PORT", 7473)
        app.config.setdefault("PY2NEO_BOLT_PORT", 7687)
        app.config.setdefault("PY2NEO_USER", "neo4j")
        app.config.setdefault("PY2NEO_PASSWORD", "cherhuang")
        config_params = {
            "bolt": app.config["PY2NEO_BOLT"],
            "secure": app.config["PY2NEO_SECURE"],
            "host": app.config["PY2NEO_HOST"],
            "http_port": app.config["PY2NEO_HTTP_PORT"],
            "https_port": app.config["PY2NEO_HTTPS_PORT"],
            "bolt_port": app.config["PY2NEO_BOLT_PORT"],
            "user": app.config["PY2NEO_USER"],
            "password": app.config["PY2NEO_PASSWORD"],
        }

        config_params = {
            "bolt": app.config["PY2NEO_BOLT"],
            "secure": app.config["PY2NEO_SECURE"],
            "host": app.config["PY2NEO_HOST"],
            "http_port": app.config["PY2NEO_HTTP_PORT"],
            "https_port": app.config["PY2NEO_HTTPS_PORT"],
            "bolt_port": app.config["PY2NEO_BOLT_PORT"],
            "port": app.config["PY2NEO_BOLT_PORT"],
            "user": app.config["PY2NEO_USER"],
            "password": app.config["PY2NEO_PASSWORD"],
            "encrypted": False
        }
        # graph = Graph("http://localhost:5687/db/data/", bolt=False)
        # app.extensions["graph"] = Graph(**config_params)
        app.extensions["graph"] = Graph(
            "http://ec2-18-210-20-159.compute-1.amazonaws.com:7474", user=config_params['user'], password=config_params['password'], bolt=False)

    def get_app(self, reference_app=None):
        """Helper method that implements the logic to look up an
        application."""
        if reference_app is not None:
            return reference_app
        if current_app:
            return current_app
        if self.app is not None:
            return self.app
        raise RuntimeError(
            "application not registered on db instance and no application"
            "bound to current context"
        )

    @property
    def graph(self, app=None):
        app = self.get_app(app)
        return app.extensions["graph"]
