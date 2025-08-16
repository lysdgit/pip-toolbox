from setuptools import setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="pip-toolbox",
    version="0.4.2",
    author="lilys",
    author_email="lysder@qq.com",
    description="A toolbox for managing Python packages",
    long_description=long_description,
    long_description_content_type="text/markdown",  
    packages=["pip_toolbox"],
    install_requires=[
        "tk"
    ],
    entry_points={
        "console_scripts": [
            "pip-toolbox=pip_toolbox.main:main",
        ],
    },
)
