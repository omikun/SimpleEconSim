#!/usr/bin/env python3
"""Build the Cython extension."""
from Cython.Build import cythonize
from setuptools import setup, Extension

ext_modules = [
    Extension(
        "region_core",
        ["region_core.pyx"],
    ),
]

setup(
    name="region_core",
    ext_modules=cythonize(ext_modules, language_level="3"),
    zip_safe=False,
)