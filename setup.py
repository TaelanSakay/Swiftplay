from setuptools import setup, Extension, find_packages
from setuptools.command.build_ext import build_ext
import sys

class get_pybind_include(object):
    def __str__(self):
        import pybind11
        return pybind11.get_include()

class BuildExt(build_ext):
    c_opts = {
        "msvc": ["/EHsc", "/std:c++17"],
        "unix": ["-std=c++17"],
    }

    def build_extensions(self):
        ct = self.compiler.compiler_type
        opts = self.c_opts.get(ct, [])
        if ct == "unix":
            opts.append("-DVERSION_INFO=\"{}\"".format(self.distribution.get_version()))
        for ext in self.extensions:
            ext.extra_compile_args = opts
        build_ext.build_extensions(self)

ext_modules = [
    Extension(
        "swiftplay.lob._compactbook",
        ["src/swiftplay/lob/compact_book.cpp"],
        include_dirs=[get_pybind_include()],
        language="c++",
    )
]

setup(
    name="swiftplay",
    version="0.1.0",
    description="A cryptocurrency market-making system focused on decision-quality quoting",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    ext_modules=ext_modules,
    cmdclass={"build_ext": BuildExt},
    zip_safe=False,
)
