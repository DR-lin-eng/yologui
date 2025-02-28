from setuptools import setup, find_packages

setup(
    name="yolov8-trainer",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "ultralytics>=8.0.0",
        "torch>=1.7.0",
        "torchvision>=0.8.1",
        "pyside6>=6.0.0",
        "pyyaml>=5.3.1",
    ],
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "yolov8-trainer=main:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["icon.png"],
    },
)
