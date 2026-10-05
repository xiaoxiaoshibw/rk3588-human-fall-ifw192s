#!/usr/bin/env python3
"""Install the pure ``core`` package for the ROS1 node (`catkin_python_setup`)."""

from distutils.core import setup

from catkin_pkg.python_setup import generate_distutils_setup

setup(**generate_distutils_setup(
    packages=["core"],
    package_dir={"": "."},
))
