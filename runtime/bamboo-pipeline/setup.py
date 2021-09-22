"""A setuptools based setup module.

See:
https://packaging.python.org/en/latest/distributing.html
https://github.com/pypa/sampleproject
"""

# To use a consistent encoding
from os import path

# Always prefer setuptools over distutils
from setuptools import find_packages, setup

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
version = __import__("pipeline").__version__

setup(
    name="bamboo-pipeline",
    version=version,
    description="bamboo-pipeline",
    long_description="runtime for bamboo-engine base on Django and Celery",
    # The project's main homepage.
    url="https://github.com/TencentBlueKing/bamboo-engine/runtime/bamboo-pipeline",
    # Author details
    author="Blueking",
    author_email="contactus_bk@tencent.com",
    include_package_data=True,
    packages=find_packages(
        exclude=[
            "pipeline.tests",
            "pipeline.tests.*",
            "test",
            "test.*",
        ],
    ),
    install_requires=[
        # Base
        "Django>=2.2.6,<4.0",
        "requests>=2.22.0,<=2.23.0",
        "celery>=4.4.0,<5.0",
        "django-celery-beat>=2.1.0,<2.3",
        "django-celery-results>=1.2.1,<2.2",
        "Mako>=1.0.6,<2.0",
        "pytz==2019.3",
        "bamboo-engine==1.3.2",
        # pipeline
        "jsonschema==2.5.1",
        "ujson>=1.35",
        "pyparsing>=2.2.0,<3.0",
        "redis==3.2.0",
        "redis-py-cluster==2.1.0",
        "django-timezone-field>=4.0,<4.2",
        "boto3==1.9.130",
        "Werkzeug==1.0.1",
        "prometheus-client>=0.9.0,<1.0",
    ],
    zip_safe=False,
)
