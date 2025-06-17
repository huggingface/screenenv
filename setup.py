from setuptools import find_packages, setup

setup(
    name="screenenv",
    version="0.1.0",
    packages=find_packages(),
    package_data={"client": ["py.typed"]},
    install_requires=[
        "requests",
        "playwright",
        "fastapi",
        "uvicorn",
        "pydantic",
    ],
    python_requires=">=3.8",
)
