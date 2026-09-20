from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="cronradar-celery",
    version="0.1.1",
    author="CronRadar",
    author_email="support@cronradar.com",
    description="Detect missed and failed Celery periodic tasks with Beat schedule discovery and execution lifecycle tracking.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/cronradar/cronradar-celery",
    project_urls={
        "Documentation": "https://docs.cronradar.com/integrations/celery",
        "Product": "https://cronradar.com/celery",
        "Source": "https://github.com/cronradar/cronradar-celery",
        "Tracker": "https://github.com/cronradar/cronradar-celery/issues",
    },
    packages=find_packages(),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Monitoring",
    ],
    python_requires=">=3.8",
    install_requires=[
        "cronradar>=0.1.1",
        "celery>=5.0.0",
    ],
    keywords="celery beat periodic-tasks monitoring missed-tasks failed-tasks auto-discovery cronradar",
    license="Proprietary",
)
