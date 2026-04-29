from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="cronradar-celery",
    version="0.0.6",
    author="Administrator",
    author_email="contact@cronradar.com",
    description="Automatic monitoring for Celery periodic tasks. Monitor selective tasks or all tasks with auto-discovery.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/cronradar/cronradar-celery",
    project_urls={
        "Documentation": "https://cronradar.com/docs",
        "Source": "https://github.com/cronradar/cronradar-celery",
        "Tracker": "https://github.com/cronradar/cronradar-celery/issues",
    },
    packages=find_packages(),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: Other/Proprietary License",
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
        "cronradar>=0.0.6",
        "celery>=5.0.0",
    ],
    keywords="celery monitoring cron task beat periodic auto-discovery cronradar",
    license="Proprietary",
)
