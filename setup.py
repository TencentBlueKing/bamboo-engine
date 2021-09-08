"""A setuptools based setup module.

See:
https://packaging.python.org/en/latest/distributing.html
https://github.com/pypa/sampleproject
"""

# To use a consistent encoding
from codecs import open
from os import path

# Always prefer setuptools over distutils
from setuptools import find_packages, setup

here = path.abspath(path.dirname(__file__))
about = {}
with open(path.join(here, "bamboo_engine", "__version__.py"), "r", encoding="utf-8") as f:
    exec(f.read(), about)

long_description = """
Bamboo-engine is a general-purpose process engine which can parse, 
execute and schedule process tasks created by users, and provides flexible control capabilities such as pause, revoke, skip, force failure, retry and re-execute,
and advanced features such as parallelism and sub-processes. 
It can further improve the concurrent processing ability of tasks through horizontal expansion.
"""
version = about["__version__"]

setup(
    name="bamboo-engine",
    version=version,
    description="bamboo-engine",
    long_description=long_description,
    # The project's main homepage.
    url="https://github.com/TencentBlueKing/bamboo-engine",
    # Author details
    author="Blueking",
    author_email="contactus_bk@tencent.com",
    include_package_data=True,
    packages=find_packages(exclude=["tests", "tests.*"]),
    install_requires=[
        "Werkzeug>=1.0.1,<2.0",
        "pyparsing>=2.2.0,<3.0",
        "mako>=1.1.4,<2.0",
        "prometheus-client>=0.9.0,<1.0.0",
    ],
    zip_safe=False,
)
