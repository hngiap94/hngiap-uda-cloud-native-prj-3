import logging
from os import getenv
from flask import Flask, render_template, request, jsonify

import pymongo
from flask_pymongo import PyMongo

from prometheus_flask_exporter import PrometheusMetrics

from flask_opentracing import FlaskTracing
from jaeger_client import Config
from jaeger_client.metrics.prometheus import PrometheusMetricsFactory
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor

app = Flask(__name__)
FlaskInstrumentor().instrument_app(app)
RequestsInstrumentor().instrument()

metrics = PrometheusMetrics(app)
metrics.info('backend', 'Backend App', version='1.0.0')

logging.getLogger("").handlers = []
logging.basicConfig(format="%(message)s", level=logging.DEBUG)
logger = logging.getLogger(__name__)

def init_tracer(service):

    config = Config(
        config={
            "sampler": {"type": "const", "param": 1},
            "logging": True,
            "reporter_batch_size": 1,
        },
        service_name=service,
        validate=True,
        metrics_factory=PrometheusMetricsFactory(service_name_label=service),
    )

    # this call also sets opentracing.tracer
    return config.initialize_tracer()

tracer = init_tracer("backend")
flask_tracer = FlaskTracing(tracer, True, app)

app.config["MONGO_DBNAME"] = "example-mongodb"
app.config[
    "MONGO_URI"
] = "mongodb://example-mongodb-svc.default.svc.cluster.local:27017/example-mongodb"

mongo = PyMongo(app)


@app.route("/")
def homepage():
    with tracer.start_span("home-page") as span:
        return "Hello World"


@app.route("/api")
def my_api():
    with tracer.start_span("api") as span:
        answer = "something"
        span.set_tag("answer", answer)
        return jsonify(repsonse=answer)


@app.route("/star", methods=["POST"])
def add_star():
    with tracer.start_span("star") as span:
        try:
            star = mongo.db.stars
            name = request.json["name"]
            distance = request.json["distance"]
            star_id = star.insert({"name": name, "distance": distance})
            new_star = star.find_one({"_id": star_id})
            output = {"name": new_star["name"], "distance": new_star["distance"]}
            return jsonify({"result": output})
        except Exception:
            logger.error(f"Failed to get stars from database")
            span.set_tag("Exception", "Error when getting stars from database")

if __name__ == "__main__":
    app.run()
