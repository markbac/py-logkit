from setuptools import setup, find_packages

setup(
    name='pylogkit',
    version='0.1.0',
    description='A structured and colourised logging toolkit for Python apps',
    author='Mark Bacon',
    packages=find_packages(),
    install_requires=[
        'colorlog>=6.0.0',
        'python-json-logger>=2.0.7'
    ],
    classifiers=[
        'Programming Language :: Python :: 3',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.7',
)
